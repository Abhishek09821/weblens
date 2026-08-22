"""Traffic data provider protocol.

Pluggable adapter for external public popularity/traffic data sources.
The application must work cleanly without any provider configured.

Implementations could wrap APIs like:
- Tranco ranking list (free, public)
- CrUX dataset (free, public)
- SimilarWeb (commercial)
- Cloudflare Radar (commercial)

No single provider is hard-coded into analyzers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from weblens.logging import get_logger

logger = get_logger(__name__)


class TrafficEstimate(BaseModel):
    """One traffic/popularity data point from a public source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(description="Name of the data source.")
    domain: str = Field(description="Domain this estimate applies to.")
    rank: int | None = Field(default=None, description="Global or category rank, if available.")
    band: str | None = Field(
        default=None,
        description="Descriptive band: 'very_high', 'high', 'medium', 'low', 'very_low'.",
    )
    monthly_visits_low: int | None = Field(
        default=None, description="Lower bound of monthly visit estimate."
    )
    monthly_visits_high: int | None = Field(
        default=None, description="Upper bound of monthly visit estimate."
    )
    category: str | None = Field(default=None, description="Site category if classified.")
    country: str | None = Field(default=None, description="Primary country if available.")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Provider-reported confidence."
    )
    source_url: str | None = Field(
        default=None, description="Public URL where this data can be verified."
    )
    limitations: list[str] = Field(default_factory=list)


@runtime_checkable
class TrafficProvider(Protocol):
    """Adapter interface for traffic/popularity data."""

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    def is_available(self) -> bool:
        """Whether the provider is configured and functional."""
        ...

    async def lookup(self, domain: str) -> TrafficEstimate | None:
        """Look up traffic data for a domain.

        Returns None if no data is available. Must not raise.
        """
        ...


class NullTrafficProvider:
    """Default when no traffic data source is configured."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def is_available(self) -> bool:
        return False

    async def lookup(self, domain: str) -> TrafficEstimate | None:
        return None


def get_traffic_provider(provider_name: str | None = None) -> TrafficProvider:
    """Resolve a traffic provider by name. Returns NullTrafficProvider when unconfigured."""
    if not provider_name or provider_name == "none":
        return NullTrafficProvider()

    logger.warning(
        "unknown traffic provider requested, falling back to none",
        extra={"provider": provider_name},
    )
    return NullTrafficProvider()
