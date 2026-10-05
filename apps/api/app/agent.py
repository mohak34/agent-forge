"""Agent strategies with no database dependency, shared by the chat app and the eval.

direct: one tool-using agent answers the goal.
orchestrated: an LLM plans steps, a specialist agent runs each step with the previous
outputs as context, and the final writing step's output is the answer.
"""

from collections.abc import Awaitable, Callable

from app.executor import run_agent_with_tools
from app.planner import Step, plan_steps
from app.providers.base import Usage
from app.specialists import select_specialist, specialist_system
from app.tools import get_tool_schemas

ToolCallback = Callable[[str, str], Awaitable[None]]

TOOL_KINDS = {"research", "analysis"}
PRIOR_OUTPUT_CHARS = 2000


async def run_direct(
    goal: str,
    model: str,
    usage: Usage,
    on_tool_call: ToolCallback | None = None,
    provider: str = "groq",
) -> str:
    result = await run_agent_with_tools(
        goal,
        provider_override=provider,
        model_override=model,
        tools=get_tool_schemas(),
        on_tool_call=on_tool_call,
        usage=usage,
    )
    return result["text"]


async def run_step(
    goal: str,
    step: Step,
    prior: list[tuple[str, str]],
    model: str,
    usage: Usage,
    on_tool_call: ToolCallback | None = None,
    provider: str = "groq",
) -> str:
    prompt = f"Overall goal: {goal}\n\nYour task: {step.title}"
    if prior:
        context = "\n\n".join(f"## {title}\n{out[:PRIOR_OUTPUT_CHARS]}" for title, out in prior)
        prompt += f"\n\nWork done so far:\n{context}"

    result = await run_agent_with_tools(
        prompt,
        provider_override=provider,
        model_override=model,
        tools=get_tool_schemas() if step.kind in TOOL_KINDS else None,
        on_tool_call=on_tool_call,
        system=specialist_system(select_specialist(step.kind)),
        usage=usage,
    )
    return result["text"]


async def run_orchestrated(
    goal: str,
    model: str,
    usage: Usage,
    on_tool_call: ToolCallback | None = None,
    provider: str = "groq",
) -> str:
    steps = await plan_steps(goal, model, usage, provider)
    prior: list[tuple[str, str]] = []
    for step in steps:
        output = await run_step(goal, step, prior, model, usage, on_tool_call, provider)
        prior.append((step.title, output))
    return prior[-1][1]
