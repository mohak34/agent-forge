import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 6
RETRY_STATUSES = {429, 500, 502, 503, 529}


# POSTs JSON, retrying rate limits and transient server errors (honors Retry-After).
async def post_json(url: str, payload: dict, headers: dict[str, str], label: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(MAX_RETRIES + 1):
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                response.raise_for_status()
                return response.json()
            retry_after = response.headers.get("retry-after", "")
            is_number = retry_after.replace(".", "", 1).isdigit()
            delay = float(retry_after) if is_number else 2**attempt
            logger.warning(f"{label} {response.status_code}, retrying in {delay:.1f}s")
            await asyncio.sleep(min(delay, 120))
    raise RuntimeError("unreachable")
