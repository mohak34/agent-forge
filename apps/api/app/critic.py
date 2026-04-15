from app.config import settings


def critic_review(output_text: str) -> tuple[str, str]:
    if settings.mock_mode:
        if len(output_text.strip()) < 80:
            return (
                "revise",
                "Output is too short for a final deliverable. Expand with clearer findings and conclusion.",
            )
        return ("approve", "Output passes baseline quality checks.")

    lowered = output_text.lower()
    if any(flag in lowered for flag in ["i cannot", "not enough information"]):
        return (
            "revise",
            "Response indicates unresolved gaps. Add actionable assumptions and next steps.",
        )
    if len(output_text.strip()) < 120:
        return ("revise", "Response lacks sufficient detail. Provide a fuller synthesis.")
    return ("approve", "Output passes baseline quality checks.")
