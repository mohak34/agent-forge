from app.models import Run, TaskNode, TaskNodeStatus


def build_task_plan(run: Run) -> list[TaskNode]:
    goal = run.goal.lower()

    if "research" in goal or "competitor" in goal:
        steps = [
            ("Define scope and entities", "planning", 1, ""),
            ("Collect source material", "research", 2, "1"),
            ("Synthesize findings", "analysis", 3, "2"),
            ("Draft comparison table", "analysis", 4, "3"),
            ("Draft final summary", "writing", 5, "4"),
        ]
    else:
        steps = [
            ("Parse user objective", "planning", 1, ""),
            ("Execute baseline work", "execution", 2, "1"),
            ("Produce final output", "writing", 3, "2"),
        ]

    nodes: list[TaskNode] = []
    for index, (title, kind, sequence, depends_on) in enumerate(steps, start=1):
        nodes.append(
            TaskNode(
                run_id=run.id,
                title=title,
                kind=kind,
                sequence=sequence,
                depends_on=depends_on,
                status=TaskNodeStatus.PENDING,
                output_text=f"Planned node {index}: {title}",
            )
        )
    return nodes
