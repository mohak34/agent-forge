from dataclasses import dataclass
from html import unescape
import ipaddress
import json
import re
from urllib.parse import urlparse

import httpx

from app.config import settings


@dataclass
class ToolSpec:
    name: str
    description: str
    risk_level: str


TOOL_CATALOG = [
    ToolSpec(
        name="search_web",
        description="Search live web snippets (read-only) with safety limits",
        risk_level="low",
    ),
    ToolSpec(
        name="fetch_url",
        description="Fetch and summarize URL content (read-only) with safety limits",
        risk_level="low",
    ),
    ToolSpec(
        name="calculator", description="Evaluate basic arithmetic expression", risk_level="low"
    ),
]


def list_tools() -> list[ToolSpec]:
    return TOOL_CATALOG


def get_tool_schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the live web for current information, news, facts, or data. Use when the user asks about recent events, current data, or anything requiring up-to-date information beyond your training cutoff.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to submit to the web search engine",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and read the content of a specific URL. Use when the user provides a URL or when you need to read a specific web page in detail.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The full HTTP or HTTPS URL to fetch",
                        }
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Evaluate a basic arithmetic expression. Use for any math calculation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The arithmetic expression to evaluate, e.g. '2+2' or '(10 * 5) / 2'",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
    ]


def _ensure_http_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed")
    if not parsed.netloc:
        raise ValueError("URL must include a host")
    return raw_url.strip()


def _is_private_or_local_host(hostname: str) -> bool:
    lowered = hostname.lower()
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        )
    except ValueError:
        return False


def _validate_fetch_target(url: str) -> tuple[str, str]:
    safe_url = _ensure_http_url(url)
    parsed = urlparse(safe_url)
    host = parsed.hostname or ""
    if _is_private_or_local_host(host):
        raise ValueError("Local/private network hosts are blocked")
    return safe_url, host


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_html_to_text(html: str) -> str:
    stripped = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return _normalize_whitespace(unescape(stripped))


def _safe_fetch_text(url: str, timeout_seconds: int) -> str:
    safe_url, host = _validate_fetch_target(url)
    headers = {
        "User-Agent": settings.web_user_agent,
        "Accept": "text/html,application/json,text/plain,application/xml;q=0.8,*/*;q=0.5",
    }
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True, limits=limits) as client:
        response = client.get(safe_url, headers=headers)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    allowed_types = ("text/html", "text/plain", "application/json", "application/xml", "text/xml")
    if content_type and not any(kind in content_type.lower() for kind in allowed_types):
        raise ValueError(f"Unsupported content type: {content_type}")

    body_bytes = response.content[: settings.web_fetch_max_bytes]
    text = body_bytes.decode(response.encoding or "utf-8", errors="ignore")
    if "text/html" in content_type.lower():
        text = _strip_html_to_text(text)
    else:
        text = _normalize_whitespace(text)

    if not text:
        return f"Fetched {safe_url} (host={host}) but content was empty after normalization"

    preview = text[:1200]
    return f"Fetched {safe_url} (host={host}): {preview}"


from app.search_providers import build_search_engine

_search_engine = build_search_engine()


def _search_web(query: str) -> str:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Search query cannot be empty")

    results = _search_engine.search(normalized_query, settings.web_search_max_results)
    if not results:
        return f"Search results for '{normalized_query}': no high-confidence results"

    lines: list[str] = []
    for idx, result in enumerate(results, start=1):
        line = f"{idx}) {result.snippet} ({result.url})" if result.snippet else f"{idx}) {result.title} ({result.url})"
        lines.append(line)

    return f"Search results for '{normalized_query}': " + " | ".join(lines)


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
        return _safe_fetch_text(payload, timeout_seconds=settings.web_fetch_timeout_seconds)

    if tool_name == "search_web":
        return _search_web(payload)

    raise ValueError(f"Unknown tool: {tool_name}")
