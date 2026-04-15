from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ToolSpec:
    name: str
    description: str
    risk_level: str


TOOL_CATALOG = [
    ToolSpec(
        name="search_web", description="Search snippets from web-like mock source", risk_level="low"
    ),
    ToolSpec(name="fetch_url", description="Fetch URL content metadata safely", risk_level="low"),
    ToolSpec(
        name="calculator", description="Evaluate basic arithmetic expression", risk_level="low"
    ),
]


def list_tools() -> list[ToolSpec]:
    return TOOL_CATALOG


def invoke_tool(tool_name: str, payload: str) -> str:
    if tool_name == "calculator":
        allowed_chars = set("0123456789+-*/(). ")
        if any(ch not in allowed_chars for ch in payload):
            raise ValueError("Calculator input contains unsupported characters")
        try:
            return str(eval(payload, {"__builtins__": {}}, {}))
        except Exception as exc:
            raise ValueError(f"Calculator failed: {exc}") from exc

    if tool_name == "fetch_url":
        parsed = urlparse(payload)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http/https URLs are allowed")
        host = parsed.netloc or "unknown-host"
        return f"Fetched metadata for {host}{parsed.path or '/'}"

    if tool_name == "search_web":
        query = payload.strip() or "empty query"
        return f"Search results for '{query}': [Result A], [Result B], [Result C]"

    raise ValueError(f"Unknown tool: {tool_name}")
