from app.config import settings
from app.providers.base import ChatMessage
from app.providers.registry import build_provider_registry


async def run_single_agent(goal: str) -> dict:
    if settings.mock_mode:
        return {
            "provider": "mock",
            "model": "mock-baseline",
            "text": f"Mock execution complete for goal: {goal}",
        }

    providers = build_provider_registry()
    provider_name = settings.default_model_provider
    provider = providers.get(provider_name)

    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    prompt = (
        f"You are the baseline agent in agent-forge. Answer clearly and concisely. Goal:\n{goal}"
    )

    result = await provider.chat([ChatMessage(role="user", content=prompt)])

    return {
        "provider": result.provider,
        "model": result.model,
        "text": result.output_text,
    }
