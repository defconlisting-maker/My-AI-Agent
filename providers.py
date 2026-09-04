"""
Talks to Gemini, Groq, and DeepSeek through their OpenAI-compatible chat
endpoints, so we can use one client library (openai) and one code path for
all three. Handles automatic fallback and DeepSeek key rotation/exhaustion.
"""

from openai import OpenAI, APIStatusError, RateLimitError

import key_store

PROVIDER_CONFIG = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash-lite",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
}

# Order matters: strongest/most-available free option first.
FALLBACK_ORDER = ["gemini", "groq", "deepseek"]

# Only Gemini (of these three) can actually see images. Groq's and DeepSeek's
# models here reject a request outright if any message has array-style
# (multimodal) content -- so before falling back to them, that content has
# to be flattened to plain text or the *entire* request fails, not just the
# image part.
VISION_CAPABLE_PROVIDERS = {"gemini"}


class NoProviderAvailable(Exception):
    pass


def _is_quota_error(err: Exception) -> bool:
    """Best-effort detection of 'you're out of credit/quota' vs other errors."""
    msg = str(err).lower()
    return any(term in msg for term in [
        "quota", "insufficient", "balance", "429", "rate limit", "exceeded",
    ])


def _flatten_for_text_only(messages: list) -> list:
    """Convert any multimodal (list-content) message into a plain string,
    so text-only providers don't reject the whole request over one old
    image. The image's presence is noted in words instead of silently
    dropped, so the model knows context is missing."""
    flattened = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            text_parts = []
            had_image = False
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    had_image = True
            text = "\n".join(text_parts)
            if had_image:
                text += ("\n[An image was attached here. This model can't see "
                         "images -- if it matters, ask again once Gemini is "
                         "available, or describe the image in words.]")
            new_m = dict(m)
            new_m["content"] = text
            flattened.append(new_m)
        else:
            flattened.append(m)
    return flattened


def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio or video file's spoken content via Groq's free
    Whisper endpoint. Video files work too -- only the audio track is used,
    there's no visual understanding of what's shown. Requires a Groq key
    specifically (the only one of the three offering free transcription)."""
    key = key_store.get_active_key("groq")
    if not key:
        raise NoProviderAvailable(
            "Audio/video transcription needs a Groq API key specifically "
            "(free, no card) -- add one in Settings."
        )
    client = OpenAI(api_key=key, base_url=PROVIDER_CONFIG["groq"]["base_url"])
    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
        )
    text = result.text
    # Same reasoning as documents.py: this gets resent with every future turn,
    # so an hour-long transcript shouldn't be allowed to blow the token budget.
    if len(text) > 6000:
        text = text[:6000] + "\n...[transcript truncated -- it was longer]..."
    return text


def call_with_fallback(messages, tools=None, notify=None):
    """
    Try each provider in FALLBACK_ORDER until one succeeds.
    `notify(event: dict)` is called for non-blocking status events (e.g. a
    DeepSeek key going dead) -- the caller decides how/whether to surface it.
    Returns (provider_name, response_message_dict).
    """
    errors = {}

    for provider in FALLBACK_ORDER:
        key = key_store.get_active_key(provider)
        if not key:
            errors[provider] = "no key configured"
            continue

        cfg = PROVIDER_CONFIG[provider]
        client = OpenAI(api_key=key, base_url=cfg["base_url"])

        msgs_to_send = messages if provider in VISION_CAPABLE_PROVIDERS else _flatten_for_text_only(messages)

        try:
            kwargs = {"model": cfg["model"], "messages": msgs_to_send}
            if tools:
                kwargs["tools"] = tools
            response = client.chat.completions.create(**kwargs)
            return provider, response.choices[0].message
        except (APIStatusError, RateLimitError, Exception) as e:
            errors[provider] = str(e)
            if provider == "deepseek" and _is_quota_error(e):
                key_store.mark_exhausted("deepseek", key)
                if notify:
                    notify({
                        "type": "deepseek_exhausted",
                        "message": "A DeepSeek API key just ran out of its free "
                                    "tokens. Work continues on Gemini/Groq. Add a "
                                    "new DeepSeek key anytime in Settings to bring "
                                    "it back into rotation.",
                    })
            # Try the next provider in the chain rather than failing outright.
            continue

    detail = "; ".join(f"{p}: {e}" for p, e in errors.items())
    raise NoProviderAvailable(
        f"No configured provider could handle the request. Details -- {detail}"
    )
