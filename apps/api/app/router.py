from dataclasses import dataclass

from app.config import settings
from app.providers.base import Usage


@dataclass
class RouteDecision:
    provider: str
    model: str
    reason: str


# USD per 1M tokens (input, output) at each model's paid list price. Free-tier variants
# are charged at their paid equivalent so cost comparisons reflect a real deployment.
# Unknown models fall back to the 120B rate so budgets err on the expensive side.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "muse-spark-1.3-contributor-free": (1.25, 4.25),  # OpenCode Zen, muse-spark-1.3 rate
    "local-model": (0.0, 0.0),
}
DEFAULT_PRICE = MODEL_PRICES["openai/gpt-oss-120b"]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def cost_usd(model: str, usage: Usage) -> float:
    price_in, price_out = MODEL_PRICES.get(model, DEFAULT_PRICE)
    return (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000


def estimate_cost_usd(model: str, token_estimate: int) -> float:
    return cost_usd(model, Usage(input_tokens=token_estimate))


def route_for_task(task_kind: str, budget_remaining_usd: float) -> RouteDecision:
    if budget_remaining_usd <= 0.0:
        return RouteDecision(
            provider="lmstudio",
            model="local-model",
            reason="Budget exhausted, routing to local model fallback",
        )
    return RouteDecision(
        provider="groq",
        model=settings.groq_default_model,
        reason=f"{task_kind} routed to default Groq model",
    )
