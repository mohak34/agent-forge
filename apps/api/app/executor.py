from app.config import settings
from app.providers.base import ChatMessage
from app.providers.registry import build_provider_registry


async def run_single_agent(
    goal: str, provider_override: str | None = None, model_override: str | None = None
) -> dict:
    if settings.mock_mode:
        return {
            "provider": provider_override or "mock",
            "model": model_override or "mock-baseline",
            "text": f"Mock execution complete for goal: {goal}",
        }

    providers = build_provider_registry()
    provider_name = provider_override or settings.default_model_provider
    provider = providers.get(provider_name)

    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    prompt = (
        f"You are the baseline agent in agent-forge. Answer clearly and concisely. Goal:\n{goal}"
    )

    if model_override is not None:
        provider.model = model_override

    result = await provider.chat([ChatMessage(role="user", content=prompt)])

    return {
        "provider": result.provider,
        "model": result.model,
        "text": result.output_text,
    }
