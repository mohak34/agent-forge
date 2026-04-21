import json

from app.executor import run_single_agent


ALLOWED_ROUTES = {"direct", "orchestrated"}
ALLOWED_TOOLING = {"none", "search", "search+fetch"}


async def classify_route(user_message: str) -> dict[str, str]:
    prompt = (
        "You classify chat execution mode for an AI system. "
        "Choose route=direct for simple requests that do not require decomposition. "
        "Choose route=orchestrated for complex tasks that need planning/subagents. "
        "Choose tooling=search when web search is needed, tooling=search+fetch when explicit URLs "
        "or deep source extraction is needed, tooling=none otherwise. "
        "Return strict JSON with keys route, tooling, reason. "
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
            "tooling": "search",
            "reason": "Classifier fallback due to parse failure",
        }

    route = str(parsed.get("route", "direct")).strip().lower()
    tooling = str(parsed.get("tooling", "none")).strip().lower()
    reason = str(parsed.get("reason", "Classifier decision")).strip()

    if route not in ALLOWED_ROUTES:
        route = "direct"
    if tooling not in ALLOWED_TOOLING:
        tooling = "none"

    return {
        "route": route,
        "tooling": tooling,
        "reason": reason or "Classifier decision",
    }
