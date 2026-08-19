"""Analyzer registry.

One declarative table is the single source of truth for what WebLens can detect. The
capabilities endpoint reads it, the pipeline schedules from it, and the frontend renders
section states from it - so an unbuilt analyzer surfaces as an honest "not implemented in this
build" everywhere at once, with no place left to accidentally show an empty panel instead.

Entries without a ``factory`` are declared but not implemented. They are listed on purpose:
the phased plan is public, and a user reading a report should be able to see what was not
examined.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from weblens.analyzers.accessibility import AccessibilityAxeAnalyzer, AccessibilityStructureAnalyzer
from weblens.analyzers.architecture import (
    ArchitecturePlatformAnalyzer,
    ArchitectureRenderingAnalyzer,
    ArchitectureRuntimeAnalyzer,
)
from weblens.analyzers.base import Analyzer
from weblens.analyzers.design import (
    DesignColorAnalyzer,
    DesignLayoutAnalyzer,
    DesignMediaAnalyzer,
    DesignMotionAnalyzer,
    DesignTypographyAnalyzer,
)
from weblens.analyzers.network import NetworkResourcesAnalyzer, NetworkThirdPartiesAnalyzer
from weblens.analyzers.performance import PerformanceResourcesAnalyzer, PerformanceTimingsAnalyzer
from weblens.analyzers.security import (
    SecurityCookiesAnalyzer,
    SecurityExposureAnalyzer,
    SecurityHeadersAnalyzer,
    SecurityMixedContentAnalyzer,
    SecurityScoringAnalyzer,
    SecurityThirdPartyAnalyzer,
    SecurityTlsAnalyzer,
)
from weblens.analyzers.seo import (
    SeoIndexabilityAnalyzer,
    SeoMetadataAnalyzer,
    SeoStructuredDataAnalyzer,
)
from weblens.analyzers.technology import (
    TechFrameworkAnalyzer,
    TechLanguageAnalyzer,
    TechStackAnalyzer,
    TechStylingAnalyzer,
)
from weblens.domain.enums import EvidenceSlot, SectionKey

Slots = frozenset[EvidenceSlot]


@dataclass(frozen=True)
class AnalyzerEntry:
    id: str
    section: SectionKey
    version: str
    description: str
    requires: Slots
    phase: int
    factory: Callable[[], Analyzer] | None = None
    depends_on: frozenset[str] = frozenset()

    @property
    def implemented(self) -> bool:
        return self.factory is not None


def _slots(*slots: EvidenceSlot) -> Slots:
    return frozenset(slots)


# fmt: off
REGISTRY: tuple[AnalyzerEntry, ...] = (
    # --- technology ---------------------------------------------------------------------
    AnalyzerEntry(
        "technology.stack", SectionKey.TECHNOLOGY, "1.0.0",
        "Products detected from headers, script URLs, runtime globals and network requests.",
        _slots(EvidenceSlot.HTTP, EvidenceSlot.DOM, EvidenceSlot.RUNTIME, EvidenceSlot.NETWORK), 3,
        factory=TechStackAnalyzer,
    ),
    AnalyzerEntry(
        "technology.framework", SectionKey.TECHNOLOGY, "1.0.0",
        "JavaScript framework signals, with a version only when a signature captures one.",
        _slots(EvidenceSlot.DOM, EvidenceSlot.RUNTIME), 3,
        factory=TechFrameworkAnalyzer,
    ),
    AnalyzerEntry(
        "technology.language", SectionKey.TECHNOLOGY, "1.0.0",
        "Server-side language or runtime, where a response header discloses it.",
        _slots(EvidenceSlot.HTTP), 3,
        factory=TechLanguageAnalyzer,
    ),
    AnalyzerEntry(
        "technology.styling", SectionKey.TECHNOLOGY, "1.0.0",
        "CSS framework and methodology indicators from stylesheets and class-name shape.",
        _slots(EvidenceSlot.DOM, EvidenceSlot.STYLES), 3,
        factory=TechStylingAnalyzer,
    ),
    # --- design -------------------------------------------------------------------------
    AnalyzerEntry(
        "design.color", SectionKey.DESIGN, "1.0.0",
        "Background, text and accent colours observed in computed styles.",
        _slots(EvidenceSlot.STYLES), 4,
        factory=DesignColorAnalyzer,
    ),
    AnalyzerEntry(
        "design.typography", SectionKey.DESIGN, "1.0.0",
        "Fonts actually loaded, observed weights, and the measured type scale.",
        _slots(EvidenceSlot.STYLES), 4,
        factory=DesignTypographyAnalyzer,
    ),
    AnalyzerEntry(
        "design.layout", SectionKey.DESIGN, "1.0.0",
        "Layout system, spacing scale, radius and shadow inventory, responsive behaviour.",
        _slots(EvidenceSlot.STYLES, EvidenceSlot.VIEWPORTS), 4,
        factory=DesignLayoutAnalyzer,
    ),
    AnalyzerEntry(
        "design.media", SectionKey.DESIGN, "1.0.0",
        "SVG, image, video and picture usage, formats and lazy-loading.",
        _slots(EvidenceSlot.DOM, EvidenceSlot.NETWORK), 4,
        factory=DesignMediaAnalyzer,
    ),
    AnalyzerEntry(
        "design.motion", SectionKey.DESIGN, "1.0.0",
        "Transition and animation usage, and animation library signals.",
        _slots(EvidenceSlot.STYLES), 4,
        factory=DesignMotionAnalyzer,
    ),
    AnalyzerEntry(
        "design.interpretation", SectionKey.DESIGN, "0.0.0",
        "Reads the design findings and states a visual-language interpretation, labelled as such.",
        _slots(), 4,
        depends_on=frozenset(
            {"design.color", "design.typography", "design.layout", "design.media", "design.motion"}
        ),
    ),
    # --- security -----------------------------------------------------------------------
    AnalyzerEntry(
        "security.headers", SectionKey.SECURITY, "1.0.0",
        "Security response headers, including parsed Content-Security-Policy directives.",
        _slots(EvidenceSlot.HTTP), 2,
        factory=SecurityHeadersAnalyzer,
    ),
    AnalyzerEntry(
        "security.cookies", SectionKey.SECURITY, "1.0.0",
        "Cookie attribute observations. Cookie values are never captured.",
        _slots(EvidenceSlot.HTTP), 2,
        factory=SecurityCookiesAnalyzer,
    ),
    AnalyzerEntry(
        "security.tls", SectionKey.SECURITY, "1.0.0",
        "Negotiated protocol, cipher and certificate validity window for one connection.",
        _slots(EvidenceSlot.TLS), 2,
        factory=SecurityTlsAnalyzer,
    ),
    AnalyzerEntry(
        "security.mixed_content", SectionKey.SECURITY, "1.0.0",
        "Active and passive mixed content, and insecure form actions.",
        _slots(EvidenceSlot.DOM, EvidenceSlot.NETWORK), 2,
        factory=SecurityMixedContentAnalyzer,
    ),
    AnalyzerEntry(
        "security.third_party", SectionKey.SECURITY, "1.0.0",
        "Cross-origin script surface and Subresource Integrity coverage.",
        _slots(EvidenceSlot.DOM, EvidenceSlot.NETWORK), 2,
        factory=SecurityThirdPartyAnalyzer,
    ),
    AnalyzerEntry(
        "security.exposure", SectionKey.SECURITY, "1.0.0",
        "Version disclosure in headers, source-map references, and debug headers.",
        _slots(EvidenceSlot.HTTP), 2,
        factory=SecurityExposureAnalyzer,
    ),
    AnalyzerEntry(
        "security.scoring", SectionKey.SECURITY, "1.0.0",
        "Applies the documented rule table to the other security findings.",
        _slots(), 2,
        factory=SecurityScoringAnalyzer,
        depends_on=frozenset(
            {
                "security.headers",
                "security.cookies",
                "security.tls",
                "security.mixed_content",
                "security.third_party",
                "security.exposure",
            }
        ),
    ),
    # --- performance --------------------------------------------------------------------
    AnalyzerEntry(
        "performance.timings", SectionKey.PERFORMANCE, "1.0.0",
        "Navigation and paint timing, LCP, CLS and long tasks from one lab run.",
        _slots(EvidenceSlot.PERFORMANCE), 5,
        factory=PerformanceTimingsAnalyzer,
    ),
    AnalyzerEntry(
        "performance.resources", SectionKey.PERFORMANCE, "1.0.0",
        "Bytes and request counts by type and domain, compression and cache coverage.",
        _slots(EvidenceSlot.NETWORK), 5,
        factory=PerformanceResourcesAnalyzer,
    ),
    # --- accessibility ------------------------------------------------------------------
    AnalyzerEntry(
        "accessibility.axe", SectionKey.ACCESSIBILITY, "1.0.0",
        "axe-core rule violations grouped by impact.",
        _slots(EvidenceSlot.ACCESSIBILITY), 5,
        factory=AccessibilityAxeAnalyzer,
    ),
    AnalyzerEntry(
        "accessibility.structure", SectionKey.ACCESSIBILITY, "1.0.0",
        "Language, landmarks, heading order, alt coverage and form labelling.",
        _slots(EvidenceSlot.DOM), 5,
        factory=AccessibilityStructureAnalyzer,
    ),
    # --- seo ----------------------------------------------------------------------------
    AnalyzerEntry(
        "seo.metadata", SectionKey.SEO, "1.0.0",
        "Document metadata observed in the served HTML.",
        _slots(EvidenceSlot.DOM), 0,
        factory=SeoMetadataAnalyzer,
    ),
    AnalyzerEntry(
        "seo.indexability", SectionKey.SEO, "1.0.0",
        "robots.txt directives, X-Robots-Tag, canonical self-reference and redirect shape.",
        _slots(EvidenceSlot.HTTP, EvidenceSlot.ROBOTS), 3,
        factory=SeoIndexabilityAnalyzer,
    ),
    AnalyzerEntry(
        "seo.structured_data", SectionKey.SEO, "1.0.0",
        "JSON-LD, microdata and RDFa inventory with syntax validity.",
        _slots(EvidenceSlot.DOM), 3,
        factory=SeoStructuredDataAnalyzer,
    ),
    # --- network ------------------------------------------------------------------------
    AnalyzerEntry(
        "network.resources", SectionKey.NETWORK, "1.0.0",
        "Request ledger summary: per-domain counts and bytes, protocol and MIME mix.",
        _slots(EvidenceSlot.NETWORK), 3,
        factory=NetworkResourcesAnalyzer,
    ),
    AnalyzerEntry(
        "network.third_parties", SectionKey.NETWORK, "1.0.0",
        "Third-party domains by category and the first-party/third-party byte split.",
        _slots(EvidenceSlot.NETWORK), 3,
        factory=NetworkThirdPartiesAnalyzer,
    ),
    # --- architecture -------------------------------------------------------------------
    AnalyzerEntry(
        "architecture.rendering", SectionKey.ARCHITECTURE, "1.0.0",
        "Rendering strategy signals from the served-versus-rendered delta and hydration payloads.",
        _slots(EvidenceSlot.HTTP, EvidenceSlot.DOM, EvidenceSlot.RUNTIME), 3,
        factory=ArchitectureRenderingAnalyzer,
    ),
    AnalyzerEntry(
        "architecture.platform", SectionKey.ARCHITECTURE, "1.0.0",
        "Hosting, CDN and edge indicators from response headers and DNS observations.",
        _slots(EvidenceSlot.HTTP, EvidenceSlot.DNS), 3,
        factory=ArchitecturePlatformAnalyzer,
    ),
    AnalyzerEntry(
        "architecture.runtime", SectionKey.ARCHITECTURE, "1.0.0",
        "HTTP protocol, service worker, module usage, storage APIs and console output.",
        _slots(EvidenceSlot.RUNTIME, EvidenceSlot.NETWORK), 3,
        factory=ArchitectureRuntimeAnalyzer,
    ),
)
# fmt: on

_BY_ID: dict[str, AnalyzerEntry] = {entry.id: entry for entry in REGISTRY}


def all_entries() -> tuple[AnalyzerEntry, ...]:
    return REGISTRY


def get(analyzer_id: str) -> AnalyzerEntry:
    return _BY_ID[analyzer_id]


def entries_for_section(section: SectionKey) -> list[AnalyzerEntry]:
    return [entry for entry in REGISTRY if entry.section is section]


def implemented_entries() -> list[AnalyzerEntry]:
    """Implemented analyzers in dependency order."""
    return _topological_order([entry for entry in REGISTRY if entry.implemented])


def section_has_implementation(section: SectionKey) -> bool:
    return any(entry.implemented for entry in entries_for_section(section))


def _topological_order(entries: list[AnalyzerEntry]) -> list[AnalyzerEntry]:
    """Order entries so dependencies run first.

    Dependencies on unimplemented analyzers are ignored rather than fatal: an aggregator can
    legitimately run against whichever of its inputs exist, and it reports what was missing.
    A cycle is a programming error and fails loudly at startup.
    """
    available = {entry.id for entry in entries}
    pending: dict[str, set[str]] = {
        entry.id: set(entry.depends_on & available) for entry in entries
    }
    by_id = {entry.id: entry for entry in entries}
    ordered: list[AnalyzerEntry] = []

    while pending:
        ready = sorted(analyzer_id for analyzer_id, deps in pending.items() if not deps)
        if not ready:
            cycle = ", ".join(sorted(pending))
            raise RuntimeError(f"analyzer dependency cycle detected: {cycle}")
        for analyzer_id in ready:
            ordered.append(by_id[analyzer_id])
            del pending[analyzer_id]
        satisfied = set(ready)
        for analyzer_id in pending:
            pending[analyzer_id] -= satisfied
    return ordered


def validate_registry() -> None:
    """Fail fast on a malformed registry. Called during application startup."""
    seen: set[str] = set()
    for entry in REGISTRY:
        if entry.id in seen:
            raise RuntimeError(f"duplicate analyzer id in registry: {entry.id}")
        seen.add(entry.id)
        unknown = entry.depends_on - set(_BY_ID)
        if unknown:
            raise RuntimeError(f"{entry.id} depends on unknown analyzer(s): {sorted(unknown)}")
    _topological_order(list(REGISTRY))
