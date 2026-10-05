from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "agent-forge-api"
    api_prefix: str = "/api/v0"
    database_url: str = "postgresql+psycopg://agentforge:agentforge@postgres:5432/agentforge"
    default_model_provider: str = "groq"

    groq_api_key: str = ""
    openrouter_api_key: str = ""
    lmstudio_base_url: str = "http://host.docker.internal:1234/v1"

    groq_default_model: str = "openai/gpt-oss-20b"
    openrouter_default_model: str = "openai/gpt-4o-mini"
    lmstudio_default_model: str = "local-model"
    mock_mode: bool = False

    web_tools_enabled: bool = True
    web_fetch_timeout_seconds: int = 8
    web_fetch_max_bytes: int = 120000
    web_search_timeout_seconds: int = 8
    web_user_agent: str = "agent-forge-api/0.1"
    web_search_max_results: int = 5
    web_search_provider_priority: str = "tavily,duckduckgo"

    tavily_api_key: str = ""
    typesafe_api_key: str = ""

    # Paths are relative to apps/api: the repo-root .env, then apps/api/.env overrides it.
    # Missing files are skipped, so this also works inside the container.
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
