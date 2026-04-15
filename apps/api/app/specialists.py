def select_specialist(task_kind: str) -> str:
    mapping = {
        "planning": "planner",
        "research": "researcher",
        "analysis": "analyst",
        "writing": "writer",
        "execution": "operator",
    }
    return mapping.get(task_kind, "generalist")


def specialist_instruction(specialist: str, goal: str, task_title: str) -> str:
    return (
        f"You are acting as the {specialist} specialist in agent-forge. "
        "Do the assigned task with concise, useful output.\n"
        f"Global goal: {goal}\n"
        f"Assigned task: {task_title}"
    )
