from app import jev
from app.config import settings

ADEQUATE = jev.noul(
    "Does the output complete the assigned task with concrete, specific content?",
    true="Directly does the task with specific facts or reasoning.",
    false="Vague, refuses, says it lacks information, or does a different task.",
)


# Jev judges the step output when a TypeSafe key is set; otherwise a length heuristic.
async def critic_review(task: str, output_text: str) -> tuple[str, str]:
    if settings.typesafe_api_key and not settings.mock_mode:
        answers = await jev.ask({"task": task, "output": output_text[-3000:]}, {"ok": ADEQUATE})
        p_ok = float(answers["ok"]["noul"])
        if p_ok < 0.5:
            return ("revise", f"Jev rated the output inadequate (p={p_ok:.2f}). Be more specific.")
        return ("approve", f"Jev rated the output adequate (p={p_ok:.2f}).")

    lowered = output_text.lower()
    if any(flag in lowered for flag in ["i cannot", "not enough information"]):
        return (
            "revise",
            "Response indicates unresolved gaps. Add actionable assumptions and next steps.",
        )
    if len(output_text.strip()) < 120:
        return ("revise", "Response lacks sufficient detail. Provide a fuller synthesis.")
    return ("approve", "Output passes baseline quality checks.")
