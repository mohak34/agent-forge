import json

from app.executor import run_single_agent


ALLOWED_ROUTES = {"direct", "orchestrated"}


async def classify_route(user_message: str) -> dict[str, str]:
    prompt = (
        "You classify chat execution mode for an AI system. "
        "Choose route=direct for simple requests that do not require decomposition. "
        "Choose route=orchestrated for complex tasks that need planning/subagents. "
        "Return strict JSON with keys route, reason. "
        "No markdown.\n\n"
        f"User message: {user_message}"
    )
    result = await run_single_agent(prompt, provider_override="groq")
    raw = (result.get("text") or "").strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        return {
            "route": "direct",
            "reason": "Classifier fallback due to parse failure",
        }

    route = str(parsed.get("route", "direct")).strip().lower()
    reason = str(parsed.get("reason", "Classifier decision")).strip()

    if route not in ALLOWED_ROUTES:
        route = "direct"

    return {
        "route": route,
        "reason": reason or "Classifier decision",
    }
