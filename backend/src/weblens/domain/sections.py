"""Report sections and their typed payloads.

A section always carries findings. Payloads hold structured extras that would be awkward as
flat findings (a colour palette, a request ledger, a rule table) - they are additive, never
a replacement for findings.

V2 model: four user-facing sections (design, technology, security, traffic). The payloads
for technology now include architecture, network, performance, and SEO structured data
that previously lived in standalone sections.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from weblens.domain.enums import (
    AnalyzerRunStatus,
    ErrorCode,
    FindingStatus,
    SectionKey,
    SectionStatus,
)
from weblens.domain.findings import Finding, Interpretation
from weblens.domain.observations import (
    AxeObservation,
    NetworkRequestRecord,
    PerformanceObservation,
    SampleCoverage,
    StructuredDataBlock,
)
from weblens.domain.security import SecurityScore


class AnalyzerRun(BaseModel):
    """Outcome of one analyzer within one scan. Present even when it did not run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: str
    status: AnalyzerRunStatus
    duration_ms: float | None = None
    error_code: ErrorCode | None = None
    error_detail: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)


class SectionMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: SectionKey
    status: SectionStatus
    analyzers: list[AnalyzerRun] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def _require_reason(self) -> SectionMeta:
        needs_reason = self.status in (
            SectionStatus.UNAVAILABLE,
            SectionStatus.NOT_IMPLEMENTED,
            SectionStatus.SKIPPED,
        )
        if needs_reason and not self.unavailable_reason:
            raise ValueError(
                f"section '{self.key.value}': status '{self.status.value}' needs a reason"
            )
        return self


class Section[TPayload](BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: SectionMeta
    findings: list[Finding] = Field(default_factory=list)
    interpretations: list[Interpretation] = Field(default_factory=list)
    data: TPayload | None = None

    def asserted_findings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.is_asserted]

    def counts_by_status(self) -> dict[str, int]:
        counts = {status.value: 0 for status in FindingStatus}
        for finding in self.findings:
            counts[finding.status.value] += 1
        return counts


# --- Section payloads ------------------------------------------------------------------


class KeyValueObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    value: str | None = None


class HreflangEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hreflang: str
    href: str | None = None


class MetadataObservation(BaseModel):
    """Document metadata as served. Lengths are reported because they are actionable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str | None = None
    title_length: int | None = None
    description: str | None = None
    description_length: int | None = None
    canonical: str | None = None
    robots_meta: str | None = None
    viewport_meta: str | None = None
    charset: str | None = None
    lang: str | None = None
    h1_texts: list[str] = Field(default_factory=list)
    open_graph: list[KeyValueObservation] = Field(default_factory=list)
    twitter: list[KeyValueObservation] = Field(default_factory=list)
    hreflang: list[HreflangEntry] = Field(default_factory=list)
    favicons: list[str] = Field(default_factory=list)


class IndexabilityObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    robots_txt_allowed: bool | None = None
    x_robots_tag: str | None = None
    canonical_is_self_referential: bool | None = None
    redirect_hop_count: int | None = None
    sitemaps: list[str] = Field(default_factory=list)


class DetectedProduct(BaseModel):
    """A technology detected from observable signals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    categories: list[str] = Field(default_factory=list)
    version: str | None = Field(
        default=None, description="Only set when a signature captured a version explicitly."
    )
    status: FindingStatus
    signal_summary: list[str] = Field(
        default_factory=list, description="Human-readable list of the signals that matched."
    )
    finding_id: str


class DomainSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str
    request_count: int
    transfer_bytes: int | None = None
    is_third_party: bool


# --- DESIGN payload -------------------------------------------------------------------


class DesignPayload(BaseModel):
    """Recreation-oriented design data. coverage reports sample quality."""

    model_config = ConfigDict(extra="forbid")

    coverage: SampleCoverage | None = None
    axe: AxeObservation | None = None


# --- TECHNOLOGY payload ---------------------------------------------------------------


class TechnologyPayload(BaseModel):
    """Consolidated technology + architecture + network + performance + SEO data."""

    model_config = ConfigDict(extra="forbid")

    products: list[DetectedProduct] = Field(default_factory=list)
    # Architecture data
    static_vs_rendered_element_delta: int | None = None
    # Network data
    requests: list[NetworkRequestRecord] = Field(default_factory=list)
    by_domain: list[DomainSummary] = Field(default_factory=list)
    network_cap_hit: bool = False
    # Performance data
    timings: PerformanceObservation | None = None
    # SEO structured data
    metadata: MetadataObservation | None = None
    indexability: IndexabilityObservation | None = None
    structured_data: list[StructuredDataBlock] = Field(default_factory=list)


# --- SECURITY payload -----------------------------------------------------------------


class HeaderObservationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    present: bool
    value: str | None = None


class SecurityPayload(BaseModel):
    """``score`` is the only score in the whole domain model (axiom A4)."""

    model_config = ConfigDict(extra="forbid")

    score: SecurityScore | None = None
    headers: list[HeaderObservationSummary] = Field(default_factory=list)


# --- TRAFFIC payload ------------------------------------------------------------------


class TrafficPayload(BaseModel):
    """Traffic and popularity intelligence from external public data sources."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str | None = Field(
        default=None, description="Which traffic provider was used, or None if unavailable."
    )
    provider_available: bool = False


# --- Section set (the four user-facing reports) ---------------------------------------


class SectionSet(BaseModel):
    """The four V2 report sections."""

    model_config = ConfigDict(extra="forbid")

    design: Section[DesignPayload]
    technology: Section[TechnologyPayload]
    security: Section[SecurityPayload]
    traffic: Section[TrafficPayload]
