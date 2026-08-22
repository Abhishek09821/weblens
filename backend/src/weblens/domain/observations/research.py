"""Research observation models.

Results from the optional public-research phase. These represent publicly available
information about the target's technology, architecture, or domain — sourced from
engineering blogs, documentation, GitHub, and similar credible public sources.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchRef(BaseModel):
    """One public research result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(description="Public URL where the information was found.")
    title: str = Field(description="Page or document title.")
    domain: str = Field(description="Domain the result came from.")
    excerpt: str = Field(description="Relevant excerpt, max ~300 chars.")
    provider: str = Field(description="Which search provider returned this result.")
    relevance: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Provider-reported relevance score."
    )
    source_type: str = Field(
        default="other",
        description=(
            "Source classification: official, documentation, github, "
            "tech_publication, tech_intelligence, other."
        ),
    )


class ResearchObservation(BaseModel):
    """Aggregated research results for one target."""

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(default_factory=list, description="Queries that were executed.")
    results: list[ResearchRef] = Field(
        default_factory=list, description="All research results returned."
    )
    provider_name: str | None = Field(
        default=None, description="Name of the configured search provider."
    )
    unavailable_reason: str | None = Field(
        default=None,
        description="Set when no research provider is configured or the provider failed.",
    )
