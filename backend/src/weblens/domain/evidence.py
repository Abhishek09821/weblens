"""Evidence: the raw observations, and the references findings point at.

``RawEvidence`` is collected once per scan and then treated as immutable input by every
analyzer. It is a Pydantic model so it can be serialized and committed as a fixture, which
is what lets analyzer tests run offline and deterministically.

The distinction that matters most in this module: a slot set to ``None`` means *not
collected*; an empty list means *collected, nothing found*. Analyzers must map the first to
``unable_to_verify`` and the second to ``not_detected``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from weblens.domain.enums import EvidenceKind, EvidenceSlot
from weblens.domain.observations import (
    AxeObservation,
    ConsoleMessage,
    DnsObservation,
    DomObservation,
    HttpObservation,
    NetworkObservation,
    PerformanceObservation,
    ResearchObservation,
    RobotsObservation,
    RuntimeObservation,
    ScreenshotArtifact,
    StyleObservation,
    TargetObservation,
    TlsObservation,
    ViewportMetrics,
)
from weblens.utils.text import MAX_EXCERPT_CHARS, sanitize_excerpt
from weblens.utils.timing import utc_now


class EvidenceRef(BaseModel):
    """A pointer to the observation that supports a finding, with a quotable excerpt.

    Deliberately self-contained rather than an index into a separate evidence store:
    findings travel alone into report files and IndexedDB, so each carries the bounded,
    sanitized excerpt it needs. ``RawEvidence`` itself is never returned by the API.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EvidenceKind
    source: str = Field(
        description="Machine path into the evidence, e.g. 'http.headers.content-security-policy'."
    )
    excerpt: str | None = Field(
        default=None, description="Sanitized, truncated raw value as observed."
    )
    location: str | None = Field(
        default=None, description="Absolute URL, CSS selector, or header name."
    )
    detail: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("excerpt")
    @classmethod
    def _sanitize(cls, value: str | None) -> str | None:
        return sanitize_excerpt(value, limit=MAX_EXCERPT_CHARS)


class RawEvidence(BaseModel):
    """Everything observed about one target in one collection run."""

    model_config = ConfigDict(extra="forbid")

    collected_at: datetime = Field(default_factory=utc_now)
    target: TargetObservation
    http: HttpObservation | None = None
    tls: TlsObservation | None = None
    dns: DnsObservation | None = None
    robots: RobotsObservation | None = None
    dom: DomObservation | None = None
    runtime: RuntimeObservation | None = None
    styles: StyleObservation | None = None
    network: NetworkObservation | None = None
    performance: PerformanceObservation | None = None
    accessibility: AxeObservation | None = None
    viewports: list[ViewportMetrics] | None = None
    console: list[ConsoleMessage] | None = None
    screenshots: list[ScreenshotArtifact] | None = None
    research: ResearchObservation | None = None

    def has(self, slot: EvidenceSlot) -> bool:
        """True when the slot was collected. Empty collections count as collected."""
        return getattr(self, slot.value, None) is not None

    def missing(self, slots: Iterable[EvidenceSlot]) -> list[EvidenceSlot]:
        return [slot for slot in slots if not self.has(slot)]

    def collected_slots(self) -> list[EvidenceSlot]:
        return [slot for slot in EvidenceSlot if self.has(slot)]
