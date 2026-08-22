"""Brave Search provider implementation.

Uses the Brave Search API (https://api.search.brave.com/) to find publicly available
information about a target domain. Requires a WEBLENS_BRAVE_API_KEY environment variable.

Source priority for results:
1. Official company / engineering source
2. Official documentation
3. Public GitHub repository
4. Reputable technical publication
5. Reputable technology intelligence source
6. Other sources
"""

from __future__ import annotations

import httpx

from weblens.logging import get_logger
from weblens.research.base import SearchResult

logger = get_logger(__name__)

# Domains that indicate high-quality primary sources
_OFFICIAL_DOMAINS = frozenset({
    "engineering.atspotify.com",
    "engineering.fb.com",
    "netflixtechblog.com",
    "blog.google",
    "aws.amazon.com",
    "cloud.google.com",
    "azure.microsoft.com",
    "developer.mozilla.org",
    "web.dev",
})

_GITHUB_DOMAINS = frozenset({"github.com", "github.io"})

_TECH_PUBLICATIONS = frozenset({
    "stackshare.io",
    "builtwith.com",
    "wappalyzer.com",
    "similartech.com",
    "w3techs.com",
    "techradar.com",
    "infoq.com",
    "smashingmagazine.com",
    "css-tricks.com",
    "dev.to",
    "medium.com",
    "hackernoon.com",
})


def _relevance_for_domain(domain: str) -> float:
    """Score relevance based on domain category."""
    lower = domain.lower()
    # Official engineering blogs get highest priority
    if lower in _OFFICIAL_DOMAINS or "engineering" in lower or "techblog" in lower:
        return 0.95
    # GitHub repos are primary sources
    if any(lower.endswith(gh) or lower == gh for gh in _GITHUB_DOMAINS):
        return 0.85
    # Tech publications are reliable secondary sources
    if lower in _TECH_PUBLICATIONS:
        return 0.75
    # Official company domains (likely docs or blogs)
    if "docs." in lower or "developer." in lower or "blog." in lower:
        return 0.80
    return 0.5


class BraveSearchProvider:
    """Brave Search API provider.

    Requires WEBLENS_BRAVE_API_KEY. Returns empty results on failure rather than raising.
    """

    _BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
        )

    @property
    def name(self) -> str:
        return "brave"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Execute a search query against Brave Search API.

        Returns empty list on failure. Never raises.
        """
        try:
            response = await self._client.get(
                self._BASE_URL,
                params={
                    "q": query,
                    "count": min(limit, 20),
                    "text_decorations": "false",
                    "search_lang": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

            results: list[SearchResult] = []
            web_results = data.get("web", {}).get("results", [])

            for item in web_results[:limit]:
                url = item.get("url", "")
                domain = _extract_domain(url)
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        domain=domain,
                        snippet=item.get("description", "")[:300],
                        relevance=_relevance_for_domain(domain),
                    )
                )

            return results

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "brave search HTTP error",
                extra={"status": exc.response.status_code, "query": query[:100]},
            )
            return []
        except Exception as exc:
            logger.warning(
                "brave search failed",
                extra={"error": str(exc)[:200], "query": query[:100]},
            )
            return []


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url
