"""Rendering strategy analysis.

Detects: SPA signals, SSR signals, static site signals, hydration indicators.
Based on DOM content differences, hydration payloads, and navigation patterns.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "architecture.rendering"


class ArchitectureRenderingAnalyzer:
    """Infers rendering strategy from observable signals."""

    id = ANALYZER_ID
    section = SectionKey.ARCHITECTURE
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.HTTP, EvidenceSlot.DOM, EvidenceSlot.RUNTIME})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        runtime = ctx.evidence.runtime

        if dom is None:
            return AnalyzerOutput(findings=[])

        findings = []
        signals_spa: list[str] = []
        signals_ssr: list[str] = []
        signals_static: list[str] = []

        # Check DOM content richness from static HTML
        # If the DOM has substantial text content, it's likely SSR or static
        text_len = dom.text_length or 0
        element_count = dom.element_count or 0

        # Hydration payloads indicate SSR with client-side hydration
        if runtime and runtime.hydration_payload_keys:
            signals_ssr.extend(f"Hydration: {key}" for key in runtime.hydration_payload_keys)

        # __NEXT_DATA__ is a strong SSR signal
        if runtime and "__NEXT_DATA__" in runtime.globals_present:
            signals_ssr.append("Next.js data payload present")

        # __NUXT__ is SSR
        if runtime and "__NUXT__" in runtime.globals_present:
            signals_ssr.append("Nuxt data payload present")

        # Minimal static HTML with app mount point suggests SPA
        if dom.noscript_count > 0 and dom.noscript_text_length > 50:
            signals_spa.append("Substantial <noscript> content (JS-dependent rendering)")

        # Module scripts with no pre-rendered content
        if (
            runtime
            and runtime.module_script_count
            and runtime.module_script_count > 0
            and text_len < 200
            and element_count < 50
        ):
            signals_spa.append("Minimal HTML with module scripts")

        # Rich HTML content without client-side rendering signals
        if (
            text_len > 2000
            and element_count > 100
            and runtime
            and not runtime.hydration_payload_keys
            and not (
                runtime.globals_present
                and any(
                    g in runtime.globals_present
                    for g in ["React", "Vue", "__VUE__", "angular", "ng"]
                )
            )
        ):
            signals_static.append("Rich HTML without framework hydration")

        # Service worker might indicate PWA/SPA
        if runtime and runtime.service_worker_registered:
            signals_spa.append("Service worker registered")

        # Determine primary rendering approach
        strategy = "not_determinable"
        confidence = Confidence.MODERATE
        evidence_refs: list[EvidenceRef] = []

        if signals_ssr:
            strategy = "server_rendered_with_hydration"
            confidence = Confidence.STRONG
            evidence_refs = [
                EvidenceRef(
                    kind=EvidenceKind.RUNTIME_GLOBAL,
                    source="runtime.hydration_payload_keys",
                    excerpt=signals_ssr[0],
                )
            ]
        elif signals_spa and not signals_static:
            strategy = "client_rendered_spa"
            confidence = Confidence.MODERATE
            evidence_refs = [
                EvidenceRef(
                    kind=EvidenceKind.HTML_ELEMENT,
                    source="dom.structure",
                    excerpt=signals_spa[0],
                )
            ]
        elif signals_static:
            strategy = "static_or_server_rendered"
            confidence = Confidence.MODERATE
            evidence_refs = [
                EvidenceRef(
                    kind=EvidenceKind.HTML_ELEMENT,
                    source="dom.text_length",
                    excerpt=signals_static[0],
                )
            ]

        if strategy != "not_determinable" and evidence_refs:
            findings.append(
                self._build.detected(
                    "rendering-strategy",
                    category="architecture",
                    name="Rendering strategy",
                    value=strategy,
                    confidence=confidence,
                    evidence=evidence_refs,
                    details={
                        "ssr_signals": signals_ssr[:5],
                        "spa_signals": signals_spa[:5],
                        "static_signals": signals_static[:5],
                    },
                )
            )
        else:
            findings.append(
                self._build.not_determinable(
                    "rendering-strategy",
                    category="architecture",
                    name="Rendering strategy",
                    reason="Insufficient signals to determine rendering approach reliably.",
                )
            )

        return AnalyzerOutput(findings=findings)
