"""Minimal client for TypeSafe's Jev decision model (POST /v1/systemone).

Jev takes a piece of state plus typed questions and returns only typed answers with
probabilities. Docs: https://docs.typesafe.ai/api
"""

import asyncio
import logging

import httpx

from app import cache
from app.config import settings

logger = logging.getLogger(__name__)

JEV_URL = "https://api.typesafe.ai/v1/systemone"
MAX_RETRIES = 6


def noul(instructions: str, true: str, false: str) -> dict:
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true, "false": false},
    }


# Returns the "answers" map keyed by question id. Cached like LLM calls when the cache is on.
async def ask(state: str | dict, questions: dict[str, dict]) -> dict[str, dict]:
    if not settings.typesafe_api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")

    payload = {"state": state, "model": "jev-latest", "questions": questions}
    key = cache.make_key("jev", payload)
    cached = cache.get(key)
    if isinstance(cached, dict):
        return cached

    headers = {"Authorization": f"Bearer {settings.typesafe_api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(MAX_RETRIES + 1):
            response = await client.post(JEV_URL, json=payload, headers=headers)
            if response.status_code not in {429, 529} or attempt == MAX_RETRIES:
                response.raise_for_status()
                break
            logger.warning(f"jev {response.status_code}, retrying in {2**attempt}s")
            await asyncio.sleep(2**attempt)

    answers = response.json()["answers"]
    cache.put(key, answers)
    return answers
