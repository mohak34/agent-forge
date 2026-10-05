def select_specialist(task_kind: str) -> str:
    mapping = {
        "planning": "planner",
        "research": "researcher",
        "analysis": "analyst",
        "writing": "writer",
    }
    return mapping.get(task_kind, "generalist")


def specialist_system(specialist: str) -> str:
    if specialist == "writer":
        return (
            "You are the writer on a team of agents. Using the team's work, answer the "
            "overall goal directly and concisely. Put the answer first."
        )
    return (
        f"You are the {specialist} on a team of agents. Do only your assigned task, using "
        "tools when you need facts. Report what you found concisely, with sources."
    )
