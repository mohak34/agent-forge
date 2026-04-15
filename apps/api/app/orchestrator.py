from sqlalchemy.orm import Session

from app.critic import critic_review
from app.executor import run_single_agent
from app.models import Run, TaskNode, TaskNodeStatus
from app.policy import evaluate_tool_use
from app.specialists import select_specialist, specialist_instruction
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

        selected_tool = ""
        tool_input = ""
        if node.kind == "research":
            selected_tool = "search_web"
            tool_input = run.goal
        elif node.kind == "analysis":
            selected_tool = "calculator"
            tool_input = "2+2"

        if selected_tool:
            decision = evaluate_tool_use(selected_tool)
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

            tool_result = invoke_tool(selected_tool, tool_input)
            create_event(
                db,
                run.id,
                "tool.invoked",
                f"tool={selected_tool} input={tool_input} output={tool_result[:140]}",
                actor=specialist,
            )
            prompt = f"{prompt}\nTool context ({selected_tool}): {tool_result}"

        result = await run_single_agent(prompt)
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
