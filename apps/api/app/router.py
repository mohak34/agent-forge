from dataclasses import dataclass

from app.config import settings


@dataclass
class RouteDecision:
    provider: str
    model: str
    reason: str


MODEL_COST_PER_1K = {
    "groq": 0.0002,
    "openrouter": 0.0015,
    "lmstudio": 0.0,
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost_usd(provider: str, token_estimate: int) -> float:
    rate = MODEL_COST_PER_1K.get(provider, 0.001)
    return round((token_estimate / 1000.0) * rate, 6)


def route_for_task(task_kind: str, budget_remaining_usd: float) -> RouteDecision:
    kind = task_kind.lower().strip()

    if budget_remaining_usd <= 0.0:
        return RouteDecision(
            provider="lmstudio",
            model="local-model",
            reason="Budget exhausted, routing to local model fallback",
        )

    if kind == "planning":
        return RouteDecision(
            provider="groq",
            model=settings.groq_default_model,
            reason="Planning routed to Groq for simpler single-provider setup",
        )

    if kind in {"research", "analysis"}:
        return RouteDecision(
            provider="groq",
            model=settings.groq_default_model,
            reason="Research/analysis optimized for fast low-cost processing",
        )

    return RouteDecision(
        provider="groq",
        model=settings.groq_default_model,
        reason="Default low-cost route",
    )
