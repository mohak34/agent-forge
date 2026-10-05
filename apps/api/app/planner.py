import json
import re
from dataclasses import dataclass

from app.executor import run_agent_with_tools
from app.models import Run, TaskNode, TaskNodeStatus
from app.providers.base import Usage

STEP_KINDS = {"planning", "research", "analysis", "writing"}

PLANNER_SYSTEM = (
    "You plan work for a team of specialist agents. Break the user's goal into 2 to 5 "
    "sequential steps. Each step has a short imperative title and a kind: research "
    "(find facts on the web), analysis (reason over gathered facts, compute), planning "
    "(scope or decompose), or writing (produce the final answer). The last step must be "
    'writing. Reply with only JSON: {"steps": [{"title": "...", "kind": "..."}]}'
)

FALLBACK_STEPS = [
    ("Find the facts needed to answer", "research"),
    ("Reason over the facts", "analysis"),
    ("Write the final answer", "writing"),
]


# One planned step. Steps run in order; each sees the outputs of the steps before it.
@dataclass
class Step:
    title: str
    kind: str


def parse_plan(text: str) -> list[Step]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        raw_steps = json.loads(match.group(0))["steps"] if match else []
    except (json.JSONDecodeError, KeyError, TypeError):
        raw_steps = []

    steps = [
        Step(title=str(s["title"]).strip()[:180], kind=s["kind"])
        for s in raw_steps
        if isinstance(s, dict) and s.get("title") and s.get("kind") in STEP_KINDS
    ][:5]
    if len(steps) < 2:
        return [Step(title, kind) for title, kind in FALLBACK_STEPS]
    if steps[-1].kind != "writing":
        steps.append(Step("Write the final answer", "writing"))
    return steps


async def plan_steps(goal: str, model: str, usage: Usage | None = None) -> list[Step]:
    result = await run_agent_with_tools(
        goal, provider_override="groq", model_override=model, system=PLANNER_SYSTEM, usage=usage
    )
    return parse_plan(result["text"])


def to_task_nodes(run: Run, steps: list[Step]) -> list[TaskNode]:
    return [
        TaskNode(
            run_id=run.id,
            title=step.title,
            kind=step.kind,
            sequence=index,
            depends_on=str(index - 1) if index > 1 else "",
            status=TaskNodeStatus.PENDING,
        )
        for index, step in enumerate(steps, start=1)
    ]
