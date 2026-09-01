"""
Stores API keys per provider and tracks which ones are exhausted.

Gemini and Groq keys are just used as-is (their free tier is rate-limited,
not a token bank that empties). DeepSeek keys are different: each one has a
one-time free grant that eventually runs out, so we track "this key is dead"
per key and rotate to the next one automatically.

Keys live in keys.json in the working directory. Never commit this file --
it's listed in .gitignore.
"""

import json
import os
import threading

KEYS_FILE = os.environ.get("AGENT_KEYS_FILE", "keys.json")
_lock = threading.Lock()

_DEFAULT = {
    "gemini": [],   # list of {"key": str}
    "groq": [],     # list of {"key": str}
    "deepseek": [], # list of {"key": str, "exhausted": bool}
    "tavily": [],   # list of {"key": str} -- web search, 1000 free searches/month
}


def _load() -> dict:
    if not os.path.exists(KEYS_FILE):
        return json.loads(json.dumps(_DEFAULT))
    with open(KEYS_FILE, "r") as f:
        data = json.load(f)
    for k, v in _DEFAULT.items():
        data.setdefault(k, v)
    return data


def _save(data: dict):
    with open(KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_key(provider: str, key: str):
    with _lock:
        data = _load()
        entry = {"key": key}
        if provider == "deepseek":
            entry["exhausted"] = False
        data[provider].append(entry)
        _save(data)


def get_active_key(provider: str):
    """Return the first usable key for a provider, or None if none available."""
    with _lock:
        data = _load()
        for entry in data.get(provider, []):
            if provider == "deepseek" and entry.get("exhausted"):
                continue
            if entry.get("key"):
                return entry["key"]
        return None


def mark_exhausted(provider: str, key: str):
    """Flag a DeepSeek key as dead so we stop trying it and move on silently."""
    with _lock:
        data = _load()
        for entry in data.get(provider, []):
            if entry.get("key") == key:
                entry["exhausted"] = True
        _save(data)


def has_any_key(provider: str) -> bool:
    return get_active_key(provider) is not None


def status() -> dict:
    """Summary used to render the notification banner in the UI."""
    with _lock:
        data = _load()
    out = {}
    for provider, entries in data.items():
        total = len(entries)
        if provider == "deepseek":
            exhausted = sum(1 for e in entries if e.get("exhausted"))
            out[provider] = {"total": total, "exhausted": exhausted}
        else:
            out[provider] = {"total": total}
    return out
