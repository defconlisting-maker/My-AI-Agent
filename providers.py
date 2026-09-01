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
        "model": "gemini-3.7-flash",
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


class NoProviderAvailable(Exception):
    pass


def _is_quota_error(err: Exception) -> bool:
    """Best-effort detection of 'you're out of credit/quota' vs other errors."""
    msg = str(err).lower()
    return any(term in msg for term in [
        "quota", "insufficient", "balance", "429", "rate limit", "exceeded",
    ])


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

        try:
            kwargs = {"model": cfg["model"], "messages": messages}
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
