from sqlalchemy.orm import Session

from app.critic import critic_review
from app.executor import run_single_agent
from app.models import Run, TaskNode, TaskNodeStatus
from app.policy import evaluate_tool_use
from app.router import estimate_cost_usd, estimate_tokens, route_for_task
from app.specialists import select_specialist, specialist_instruction
from app.search_providers import research_and_fetch
from app.tools import invoke_tool


def _dependencies_met(node: TaskNode, completed_sequences: set[int]) -> bool:
    if not node.depends_on:
        return True
    required = [part.strip() for part in node.depends_on.split(",") if part.strip()]
    for dep in required:
        if not dep.isdigit() or int(dep) not in completed_sequences:
            return False
    return True


async def execute_task_graph(
    db: Session,
    run: Run,
    task_nodes: list[TaskNode],
    create_event,
) -> tuple[dict, list[TaskNode]]:
    completed_sequences: set[int] = set()
    last_result: dict = {"provider": "", "model": "", "text": ""}

    for node in task_nodes:
        if not _dependencies_met(node, completed_sequences):
            node.status = TaskNodeStatus.BLOCKED
            create_event(
                db,
                run.id,
                "task.blocked",
                f"Node {node.sequence} blocked: missing dependencies {node.depends_on}",
                actor="orchestrator",
            )
            continue

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

        prompt = specialist_instruction(specialist=specialist, goal=run.goal, task_title=node.title)

        budget_remaining = max(run.budget_limit_usd - run.budget_used_usd, 0.0)
        route = route_for_task(node.kind, budget_remaining)
        node.routed_provider = route.provider
        node.routed_model = route.model
        create_event(
            db,
            run.id,
            "model.routed",
            f"node={node.sequence} provider={route.provider} model={route.model} reason={route.reason}",
            actor="router",
        )

        selected_tool = ""
        tool_input = ""
        tool_result = ""
        if node.kind == "research":
            selected_tool = "research_and_fetch"
            tool_input = run.goal
        elif node.kind == "analysis":
            selected_tool = "calculator"
            tool_input = "2+2"

        if selected_tool:
            decision = evaluate_tool_use("search_web" if selected_tool == "research_and_fetch" else selected_tool)
            create_event(
                db,
                run.id,
                "policy.checked",
                f"tool={selected_tool} decision={decision.decision} reason={decision.reason}",
                actor="policy",
            )
            if decision.decision != "allow":
                node.status = TaskNodeStatus.BLOCKED
                create_event(
                    db,
                    run.id,
                    "task.blocked",
                    f"Node {node.sequence} blocked by policy for tool={selected_tool}",
                    actor="policy",
                )
                continue

            if selected_tool == "research_and_fetch":
                create_event(
                    db,
                    run.id,
                    "tool.invoked",
                    f"tool=search_web input={tool_input[:80]} (research agent: searching + fetching sources)",
                    actor=specialist,
                )
                tool_result = research_and_fetch(tool_input)
                create_event(
                    db,
                    run.id,
                    "tool.completed",
                    f"tool=research_and_fetch fetched {len([l for l in tool_result.split(chr(10)) if l.startswith('Source ')])} sources",
                    actor=specialist,
                )
            else:
                tool_result = invoke_tool(selected_tool, tool_input)
                create_event(
                    db,
                    run.id,
                    "tool.invoked",
                    f"tool={selected_tool} input={tool_input} output={tool_result[:140]}",
                    actor=specialist,
                )
            prompt = f"{prompt}\nTool context ({selected_tool}): {tool_result}"

        token_estimate = estimate_tokens(prompt)
        estimated_cost = estimate_cost_usd(route.provider, token_estimate)
        node.token_estimate = token_estimate
        node.cost_estimate_usd = estimated_cost

        create_event(
            db,
            run.id,
            "budget.checked",
            f"node={node.sequence} remaining={budget_remaining:.6f} estimated={estimated_cost:.6f}",
            actor="router",
        )

        if (
            run.budget_used_usd + estimated_cost > run.budget_limit_usd
            and route.provider != "lmstudio"
        ):
            fallback = route_for_task(node.kind, 0.0)
            node.routed_provider = fallback.provider
            node.routed_model = fallback.model
            create_event(
                db,
                run.id,
                "model.fallback",
                f"node={node.sequence} fallback to provider={fallback.provider} model={fallback.model}",
                actor="router",
            )
            route = fallback
            estimated_cost = estimate_cost_usd(route.provider, token_estimate)
            node.cost_estimate_usd = estimated_cost

        if run.budget_used_usd + estimated_cost > run.budget_limit_usd:
            run.budget_exceeded = True
            create_event(
                db,
                run.id,
                "budget.exceeded",
                f"node={node.sequence} budget limit reached, stopping execution",
                actor="router",
            )
            node.status = TaskNodeStatus.BLOCKED
            break

        result = await run_single_agent(
            prompt,
            provider_override=route.provider,
            model_override=route.model,
        )
        run.budget_used_usd = round(run.budget_used_usd + estimated_cost, 6)
        node_output = result["text"][:600].strip()

        verdict, critic_note = critic_review(node_output)
        create_event(
            db,
            run.id,
            "critic.reviewed",
            f"Node {node.sequence} verdict={verdict} note={critic_note}",
            actor="critic",
        )

        if verdict == "revise":
            revise_prompt = (
                f"Revise this task output based on critic feedback.\n"
                f"Task: {node.title}\n"
                f"Feedback: {critic_note}\n"
                f"Current output: {node_output}"
            )
            revised = await run_single_agent(revise_prompt)
            node_output = revised["text"][:600].strip()
            result = revised
            create_event(
                db,
                run.id,
                "task.revised",
                f"Node {node.sequence} revised after critic feedback",
                actor=specialist,
            )

        node.output_text = node_output
        node.status = TaskNodeStatus.COMPLETED
        completed_sequences.add(node.sequence)
        create_event(
            db,
            run.id,
            "task.completed",
            f"Node {node.sequence} completed: {node.title}",
            actor=specialist,
        )
        last_result = result

    return last_result, task_nodes
