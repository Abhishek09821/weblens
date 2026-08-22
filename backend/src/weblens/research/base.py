"""Search provider protocol and null implementation.

Design goals:
- No commercial provider is hard-coded into analyzers or the pipeline.
- Configuration selects the active provider via environment/settings.
- The scan succeeds whether or not a provider is configured.
- Results carry full source provenance (URL, title, domain, excerpt).
- Low-quality results should be filtered by the provider implementation.

Provider implementations live in separate modules (e.g. ``brave.py``)
and are selected at startup by :func:`get_provider`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.observations.research import ResearchObservation, ResearchRef
from weblens.logging import get_logger

logger = get_logger(__name__)


class SourceType(StrEnum):
    """Classification of research source quality."""

    OFFICIAL = "official"
    """Official company or engineering source."""

    DOCUMENTATION = "documentation"
    """Official documentation."""

    GITHUB = "github"
    """Public GitHub repository."""

    TECH_PUBLICATION = "tech_publication"
    """Reputable technical publication."""

    TECH_INTELLIGENCE = "tech_intelligence"
    """Technology intelligence/detection service."""

    OTHER = "other"
    """Other public source."""


class SearchResult(BaseModel):
    """One result from a search provider, before relevance filtering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    title: str
    domain: str
    snippet: str = ""
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)


@runtime_checkable
class SearchProvider(Protocol):
    """Adapter interface for public web search.

    Implementations must:
    - Return only publicly accessible, credible sources
    - Prefer primary sources (official docs, engineering blogs, GitHub)
    - Never send private user data or scan evidence to the search API
    - Respect rate limits and timeouts
    - Return an empty list on failure rather than raising
    """

    @property
    def name(self) -> str:
        """Human-readable provider name for provenance tracking."""
        ...

    @property
    def is_available(self) -> bool:
        """Whether this provider is configured and functional."""
        ...

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Execute one search query and return results.

        Returns an empty list if the provider is unavailable or the query fails.
        Must not raise exceptions — failures are logged and result in empty results.
        """
        ...


class NullSearchProvider:
    """Default provider when no search API is configured.

    Returns empty results and clearly marks research as unavailable.
    """

    @property
    def name(self) -> str:
        return "none"

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return []

    @property
    def is_available(self) -> bool:
        return False


def classify_source(domain: str) -> SourceType:
    """Classify a domain into a source type for priority ranking."""
    lower = domain.lower()

    if "github.com" in lower or "github.io" in lower:
        return SourceType.GITHUB
    if "docs." in lower or "developer." in lower or "documentation" in lower:
        return SourceType.DOCUMENTATION
    if any(
        kw in lower
        for kw in ("engineering", "techblog", "blog.google", "netflixtechblog")
    ):
        return SourceType.OFFICIAL
    if any(
        kw in lower
        for kw in ("stackshare", "builtwith", "wappalyzer", "similartech", "w3techs")
    ):
        return SourceType.TECH_INTELLIGENCE
    if any(
        kw in lower
        for kw in ("infoq", "smashingmagazine", "css-tricks", "web.dev", "dev.to")
    ):
        return SourceType.TECH_PUBLICATION

    return SourceType.OTHER


# Source priority for sorting (lower number = higher priority)
_SOURCE_PRIORITY: dict[SourceType, int] = {
    SourceType.OFFICIAL: 1,
    SourceType.DOCUMENTATION: 2,
    SourceType.GITHUB: 3,
    SourceType.TECH_PUBLICATION: 4,
    SourceType.TECH_INTELLIGENCE: 5,
    SourceType.OTHER: 6,
}


async def execute_research(
    provider: SearchProvider,
    host: str,
    domain_hints: list[str] | None = None,
) -> ResearchObservation:
    """Run research queries for a target and return structured observation.

    Called by the pipeline. If the provider is a NullSearchProvider, returns
    an observation that explicitly states research was unavailable.
    """
    if isinstance(provider, NullSearchProvider):
        return ResearchObservation(
            unavailable_reason="No search provider is configured. "
            "Research findings are not available for this scan."
        )

    # Build queries targeting credible technical sources about the domain.
    queries = _build_queries(host, domain_hints)
    all_results: list[ResearchRef] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            results = await provider.search(query, limit=5)
            for result in results:
                # Deduplicate by URL
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)

                source_type = classify_source(result.domain)
                all_results.append(
                    ResearchRef(
                        url=result.url,
                        title=result.title,
                        domain=result.domain,
                        excerpt=result.snippet[:300] if result.snippet else "",
                        provider=provider.name,
                        relevance=result.relevance,
                        source_type=source_type.value,
                    )
                )
        except Exception as exc:
            logger.warning(
                "research query failed",
                extra={"query": query, "error": str(exc)[:200]},
            )

    # Sort by source priority then relevance
    all_results.sort(
        key=lambda r: (
            _SOURCE_PRIORITY.get(SourceType(r.source_type), 99),
            -r.relevance,
        )
    )

    return ResearchObservation(
        queries=queries,
        results=all_results,
        provider_name=provider.name,
    )


def _build_queries(host: str, hints: list[str] | None = None) -> list[str]:
    """Generate research queries for a domain.

    Builds dynamic queries from:
    - The target domain itself
    - Technology hints from deterministic analysis
    - Standard engineering/architecture patterns

    Targets:
    - Official engineering/tech blog posts
    - Public documentation
    - GitHub repositories
    - Technical conference talks
    - Infrastructure disclosures
    """
    base_domain = host.removeprefix("www.")
    queries: list[str] = []

    # Core domain queries
    queries.append(f"{base_domain} technology stack engineering blog")
    queries.append(f"{base_domain} site:github.com")
    queries.append(f"{base_domain} frontend framework infrastructure")

    # Company-specific engineering queries
    company_name = base_domain.split(".")[0]
    if len(company_name) > 2:
        queries.append(f"{company_name} engineering architecture")

    # Dynamic queries from detected technology hints
    if hints:
        for hint in hints[:3]:
            # Search for the specific technology in context of this domain
            queries.append(f"{base_domain} {hint}")

        # Look for unusual identifiers that might be specific to this site
        specific_hints = [h for h in hints if len(h) > 6 and not h.startswith("HTTP")]
        if specific_hints:
            queries.append(f"{specific_hints[0]} technology framework")

    # Traffic/popularity queries
    queries.append(f"{base_domain} traffic popularity ranking")

    return queries[:8]  # Cap at 8 queries to control API costs


def get_provider(provider_name: str | None = None) -> SearchProvider:
    """Resolve a search provider by name.

    Returns NullSearchProvider when no provider is configured or the name is unknown.
    Provider implementations can be added without modifying this function by extending
    the match block.
    """
    if not provider_name or provider_name == "none":
        return NullSearchProvider()

    if provider_name == "brave":
        from weblens.config import get_settings

        settings = get_settings()
        api_key = settings.brave_api_key
        if api_key:
            from weblens.research.brave import BraveSearchProvider

            return BraveSearchProvider(api_key)
        logger.warning("brave provider requested but WEBLENS_BRAVE_API_KEY is not set")
        return NullSearchProvider()

    logger.warning(
        "unknown search provider requested, falling back to none",
        extra={"provider": provider_name},
    )
    return NullSearchProvider()
