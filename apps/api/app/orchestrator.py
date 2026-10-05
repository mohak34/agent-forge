from sqlalchemy.orm import Session

from app.agent import run_step
from app.critic import critic_review
from app.executor import run_agent_with_tools
from app.models import Run, TaskNode, TaskNodeStatus
from app.planner import Step
from app.providers.base import Usage
from app.router import cost_usd, estimate_cost_usd, estimate_tokens, route_for_task
from app.specialists import select_specialist


# Runs planned task nodes in sequence for the chat app, logging every decision as a
# trace event and charging real token cost against the run's budget.
async def execute_task_graph(
    db: Session,
    run: Run,
    task_nodes: list[TaskNode],
    create_event,
) -> tuple[dict, list[TaskNode]]:
    prior: list[tuple[str, str]] = []
    last_result: dict = {"provider": "", "model": "", "text": ""}

    for node in task_nodes:
        specialist = select_specialist(node.kind)
        create_event(
            db,
            run.id,
            "task.assigned",
            f"Node {node.sequence} assigned to specialist={specialist}",
            actor="orchestrator",
        )

        node.status = TaskNodeStatus.RUNNING
        create_event(
            db,
            run.id,
            "task.started",
            f"Node {node.sequence} started: {node.title}",
            actor=specialist,
        )

        budget_remaining = max(run.budget_limit_usd - run.budget_used_usd, 0.0)
        route = route_for_task(node.kind, budget_remaining)
        token_estimate = estimate_tokens(run.goal + "".join(out for _, out in prior))
        estimated_cost = estimate_cost_usd(route.model, token_estimate)
        if route.provider != "lmstudio" and estimated_cost > budget_remaining:
            route = route_for_task(node.kind, 0.0)
            run.budget_exceeded = True
            create_event(
                db,
                run.id,
                "model.fallback",
                f"node={node.sequence} estimated={estimated_cost:.6f} exceeds remaining="
                f"{budget_remaining:.6f}, fallback to {route.provider}/{route.model}",
                actor="router",
            )
        node.routed_provider = route.provider
        node.routed_model = route.model
        create_event(
            db,
            run.id,
            "model.routed",
            f"node={node.sequence} provider={route.provider} model={route.model} reason={route.reason}",
            actor="router",
        )

        async def on_tool_call(tool_name: str, payload: str, actor: str = specialist) -> None:
            create_event(
                db,
                run.id,
                "tool.invoked",
                f"tool={tool_name} input={payload[:140]}",
                actor=actor,
            )
            db.commit()

        usage = Usage()
        output = await run_step(
            run.goal,
            Step(node.title, node.kind),
            prior,
            route.model,
            usage,
            on_tool_call,
            provider=route.provider,
        )

        verdict, critic_note = await critic_review(node.title, output)
        create_event(
            db,
            run.id,
            "critic.reviewed",
            f"Node {node.sequence} verdict={verdict} note={critic_note}",
            actor="critic",
        )
        if verdict == "revise":
            revised = await run_agent_with_tools(
                f"Revise this task output based on critic feedback.\n"
                f"Task: {node.title}\nFeedback: {critic_note}\nCurrent output: {output}",
                provider_override=route.provider,
                model_override=route.model,
                usage=usage,
            )
            output = revised["text"]
            create_event(
                db,
                run.id,
                "task.revised",
                f"Node {node.sequence} revised after critic feedback",
                actor=specialist,
            )

        node_cost = cost_usd(route.model, usage)
        run.budget_used_usd = round(run.budget_used_usd + node_cost, 6)
        node.token_estimate = usage.input_tokens + usage.output_tokens
        node.cost_estimate_usd = round(node_cost, 6)
        create_event(
            db,
            run.id,
            "budget.charged",
            f"node={node.sequence} tokens={node.token_estimate} cost={node_cost:.6f} "
            f"used={run.budget_used_usd:.6f}/{run.budget_limit_usd:.6f}",
            actor="router",
        )

        node.output_text = output
        node.status = TaskNodeStatus.COMPLETED
        prior.append((node.title, output))
        create_event(
            db,
            run.id,
            "task.completed",
            f"Node {node.sequence} completed: {node.title}",
            actor=specialist,
        )
        last_result = {"provider": route.provider, "model": route.model, "text": output}

    return last_result, task_nodes
