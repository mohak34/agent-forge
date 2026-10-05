"""Minimal client for TypeSafe's Jev decision model (POST /systemone).

Jev takes a piece of state plus typed questions and returns only typed answers with
probabilities. Docs: https://docs.typesafe.ai/api
"""

from app import cache
from app.config import settings
from app.providers.http import post_json


def available() -> bool:
    return bool(settings.opencode_api_key or settings.typesafe_api_key)


# Prefers the free Jev on OpenCode Zen when an OpenCode key is set, else TypeSafe's API.
def _endpoint() -> tuple[str, str, str]:
    """(url, model, api_key)"""
    if settings.opencode_api_key:
        return "https://opencode.ai/zen/v1/systemone", "jev-1.13-free", settings.opencode_api_key
    if settings.typesafe_api_key:
        return "https://api.typesafe.ai/v1/systemone", "jev-latest", settings.typesafe_api_key
    raise RuntimeError("Set OPENCODE_API_KEY or TYPESAFE_API_KEY to use Jev")


def noul(instructions: str, true: str, false: str) -> dict:
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true, "false": false},
    }


# Returns the "answers" map keyed by question id. Cached like LLM calls when the cache is on.
async def ask(state: str | dict, questions: dict[str, dict]) -> dict[str, dict]:
    url, model, api_key = _endpoint()
    payload = {"state": state, "model": model, "questions": questions}
    key = cache.make_key("jev", payload)
    cached = cache.get(key)
    if isinstance(cached, dict):
        return cached

    data = await post_json(url, payload, {"Authorization": f"Bearer {api_key}"}, "jev")
    answers = data["answers"]
    cache.put(key, answers)
    return answers
