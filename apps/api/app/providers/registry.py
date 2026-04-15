from app.config import settings
from app.providers.base import ChatProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def build_provider_registry() -> dict[str, ChatProvider]:
    return {
        "groq": OpenAICompatibleProvider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            model=settings.groq_default_model,
            api_key=settings.groq_api_key,
        ),
        "openrouter": OpenAICompatibleProvider(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model=settings.openrouter_default_model,
            api_key=settings.openrouter_api_key,
            extra_headers={"HTTP-Referer": "https://agent-forge.local", "X-Title": "agent-forge"},
        ),
        "lmstudio": OpenAICompatibleProvider(
            name="lmstudio",
            base_url=settings.lmstudio_base_url,
            model=settings.lmstudio_default_model,
        ),
    }
