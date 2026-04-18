from __future__ import annotations

from app.models import ChatMessage


COMPLEX_KEYWORDS = {
    "research",
    "compare",
    "analyze",
    "analysis",
    "plan",
    "steps",
    "roadmap",
    "implement",
    "architecture",
    "evaluate",
}


def should_use_direct_mode(text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) > 220:
        return False
    return not any(keyword in lowered for keyword in COMPLEX_KEYWORDS)


def assemble_thread_goal(
    latest_user_message: str,
    summary_text: str,
    recent_messages: list[ChatMessage],
) -> str:
    parts: list[str] = []
    if summary_text.strip():
        parts.append(f"Thread summary:\n{summary_text.strip()}")

    if recent_messages:
        transcript_lines = [
            f"{message.role}: {message.content.strip()}"
            for message in recent_messages
            if message.content.strip()
        ]
        if transcript_lines:
            parts.append("Recent messages:\n" + "\n".join(transcript_lines))

    parts.append(f"Current user message:\n{latest_user_message.strip()}")
    return "\n\n".join(parts)


def build_summary_snapshot(messages: list[ChatMessage], max_chars: int = 1200) -> str:
    pairs: list[str] = []
    for message in messages:
        content = message.content.strip().replace("\n", " ")
        if not content:
            continue
        label = "U" if message.role == "user" else "A"
        pairs.append(f"{label}{message.turn_index}: {content[:160]}")

    merged = " | ".join(pairs)
    return merged[:max_chars]
