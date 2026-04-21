from dataclasses import dataclass
from html import unescape
import ipaddress
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


def _search_duckduckgo(query: str) -> str:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Search query cannot be empty")

    headers = {
        "User-Agent": settings.web_user_agent,
        "Accept": "application/json",
    }
    with httpx.Client(timeout=settings.web_search_timeout_seconds, follow_redirects=True) as client:
        response = client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": normalized_query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    lines: list[str] = []
    abstract = _normalize_whitespace(payload.get("AbstractText", ""))
    if abstract:
        source_url = payload.get("AbstractURL", "")
        if source_url:
            lines.append(f"1) {abstract} ({source_url})")
        else:
            lines.append(f"1) {abstract}")

    related = payload.get("RelatedTopics", [])
    count = len(lines)
    for topic in related:
        if count >= 5:
            break
        if isinstance(topic, dict) and "Text" in topic:
            text = _normalize_whitespace(str(topic.get("Text", "")))
            url = str(topic.get("FirstURL", "")).strip()
            if text:
                count += 1
                lines.append(f"{count}) {text}{f' ({url})' if url else ''}")
        elif isinstance(topic, dict) and "Topics" in topic:
            nested = topic.get("Topics", [])
            for item in nested:
                if count >= 5:
                    break
                if isinstance(item, dict):
                    text = _normalize_whitespace(str(item.get("Text", "")))
                    url = str(item.get("FirstURL", "")).strip()
                    if text:
                        count += 1
                        lines.append(f"{count}) {text}{f' ({url})' if url else ''}")

    if not lines:
        return f"Search results for '{normalized_query}': no high-confidence results"
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
        return _search_duckduckgo(payload)

    raise ValueError(f"Unknown tool: {tool_name}")
