from dataclasses import dataclass
import logging
import re
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        ...


class TavilyProvider:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        with httpx.Client(timeout=settings.web_search_timeout_seconds, follow_redirects=True) as client:
            response = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                },
            )
            response.raise_for_status()
            payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("results", []):
            title = _normalize_whitespace(str(item.get("title", "")))
            url = str(item.get("url", "")).strip()
            snippet = _normalize_whitespace(str(item.get("content", "")))
            if title and url:
                results.append(SearchResult(title=title, url=url, snippet=snippet))
            if len(results) >= max_results:
                break
        return results


class DuckDuckGoProvider:
    name = "duckduckgo"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        headers = {
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html",
        }
        with httpx.Client(timeout=settings.web_search_timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
            )
            response.raise_for_status()
            html = response.text

        results: list[SearchResult] = []
        result_blocks = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        snippet_blocks = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL,
        )

        for idx, (href, title_html) in enumerate(result_blocks):
            if idx >= max_results:
                break
            title = _strip_tags(title_html)
            url = _extract_ddg_url(href.strip())
            snippet = _strip_tags(snippet_blocks[idx]) if idx < len(snippet_blocks) else ""
            if title and url:
                results.append(SearchResult(title=title, url=url, snippet=snippet))

        return results


class FallbackSearchEngine:
    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = providers

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query cannot be empty")

        for provider in self.providers:
            try:
                results = provider.search(normalized_query, max_results)
                if results:
                    logger.info(f"search succeeded provider={provider.name} query={normalized_query[:80]} results={len(results)}")
                    return results
                logger.warning(f"search empty provider={provider.name} query={normalized_query[:80]}")
            except Exception as exc:
                logger.warning(f"search failed provider={provider.name} query={normalized_query[:80]} error={exc}")
                continue

        logger.error(f"search failed all providers query={normalized_query[:80]}")
        return []


def build_search_engine() -> FallbackSearchEngine:
    providers: list[SearchProvider] = []
    priority = [p.strip().lower() for p in settings.web_search_provider_priority.split(",") if p.strip()]

    for name in priority:
        if name == "tavily" and settings.tavily_api_key:
            providers.append(TavilyProvider(settings.tavily_api_key))
        elif name == "duckduckgo":
            providers.append(DuckDuckGoProvider())

    if not providers:
        providers.append(DuckDuckGoProvider())

    return FallbackSearchEngine(providers)


def _extract_ddg_url(href: str) -> str:
    match = re.search(r"uddg=([^&]+)", href)
    if match:
        from urllib.parse import unquote
        return unquote(match.group(1))
    return href


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    from html import unescape
    return _normalize_whitespace(unescape(text))
