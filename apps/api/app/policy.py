from dataclasses import dataclass

from app.config import settings


@dataclass
class PolicyDecision:
    decision: str
    reason: str


READ_ONLY_TOOLS = {"search_web", "fetch_url", "calculator"}


def evaluate_tool_use(tool_name: str) -> PolicyDecision:
    if not settings.web_tools_enabled and tool_name in {"search_web", "fetch_url"}:
        return PolicyDecision(
            decision="deny",
            reason="Web tools are disabled by runtime configuration",
        )

    if tool_name in READ_ONLY_TOOLS:
        return PolicyDecision(decision="allow", reason="Read-only tool allowed by default policy")
    return PolicyDecision(decision="deny", reason="Tool is not in allowlist for current policy")
