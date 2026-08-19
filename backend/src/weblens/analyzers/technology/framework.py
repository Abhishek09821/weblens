"""JavaScript framework detection from DOM structure and runtime signals.

Detects: React, Next.js, Vue, Nuxt, Angular, Svelte, Gatsby, Remix, Ember,
and other frameworks with observable DOM or runtime signatures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import DetectedProduct, TechnologyPayload

ANALYZER_ID = "technology.framework"


@dataclass(frozen=True)
class _FrameworkSignature:
    name: str
    categories: list[str]
    # Signals: each returns (found, description)
    dom_indicators: list[str] = field(default_factory=list)
    """Attribute names or patterns to look for in DOM markup."""
    runtime_globals: list[str] = field(default_factory=list)
    hydration_keys: list[str] = field(default_factory=list)
    script_patterns: list[str] = field(default_factory=list)
    id_patterns: list[str] = field(default_factory=list)
    """Script element IDs like __NEXT_DATA__"""


FRAMEWORKS: list[_FrameworkSignature] = [
    _FrameworkSignature(
        "React",
        ["javascript-framework", "ui-library"],
        runtime_globals=["React", "__REACT_DEVTOOLS_GLOBAL_HOOK__"],
        dom_indicators=["data-reactroot", "data-reactid"],
    ),
    _FrameworkSignature(
        "Next.js",
        ["javascript-framework", "meta-framework"],
        runtime_globals=["__NEXT_DATA__", "next"],
        hydration_keys=["__NEXT_DATA__"],
        id_patterns=["__NEXT_DATA__"],
        script_patterns=["/_next/static", "_next/data"],
    ),
    _FrameworkSignature(
        "Vue.js",
        ["javascript-framework", "ui-library"],
        runtime_globals=["Vue", "__VUE__", "__vue_app__"],
        dom_indicators=["data-v-", "data-vue-"],
    ),
    _FrameworkSignature(
        "Nuxt",
        ["javascript-framework", "meta-framework"],
        runtime_globals=["__nuxt", "__NUXT__"],
        hydration_keys=["__NUXT__"],
        script_patterns=["_nuxt/"],
    ),
    _FrameworkSignature(
        "Angular",
        ["javascript-framework"],
        runtime_globals=["angular", "ng"],
        dom_indicators=["ng-version", "_nghost", "_ngcontent", "ng-app"],
    ),
    _FrameworkSignature(
        "Svelte",
        ["javascript-framework"],
        runtime_globals=["__SVELTE_HMR_ADAPTER__"],
        dom_indicators=["svelte-"],
    ),
    _FrameworkSignature(
        "Gatsby",
        ["javascript-framework", "static-site-generator"],
        runtime_globals=["__GATSBY"],
        id_patterns=["gatsby-focus-wrapper"],
        script_patterns=["/page-data/", "gatsby-"],
    ),
    _FrameworkSignature(
        "Remix",
        ["javascript-framework", "meta-framework"],
        runtime_globals=["__remixContext"],
        hydration_keys=["__remixContext"],
    ),
    _FrameworkSignature(
        "Ember.js",
        ["javascript-framework"],
        runtime_globals=["Ember"],
        dom_indicators=["ember-view", "data-ember"],
    ),
    _FrameworkSignature(
        "Backbone.js",
        ["javascript-framework"],
        runtime_globals=["Backbone"],
    ),
    _FrameworkSignature(
        "Turbo/Hotwire",
        ["javascript-framework"],
        runtime_globals=["Turbo"],
        dom_indicators=["data-turbo", "data-turbo-frame"],
    ),
    _FrameworkSignature(
        "Stimulus",
        ["javascript-framework"],
        runtime_globals=["Stimulus"],
        dom_indicators=["data-controller", "data-action"],
    ),
    _FrameworkSignature(
        "Alpine.js",
        ["javascript-framework"],
        dom_indicators=["x-data", "x-init", "x-show", "x-bind"],
    ),
    _FrameworkSignature(
        "HTMX",
        ["javascript-library"],
        dom_indicators=["hx-get", "hx-post", "hx-trigger", "hx-swap"],
        script_patterns=["htmx"],
    ),
]


class TechFrameworkAnalyzer:
    """Detects JavaScript frameworks from DOM and runtime signals."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM, EvidenceSlot.RUNTIME})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        findings = []
        products: list[DetectedProduct] = []
        dom = ctx.evidence.dom
        runtime = ctx.evidence.runtime

        if dom is None and runtime is None:
            return AnalyzerOutput(findings=[])

        # Get the full HTML for attribute scanning (from body_text if available)
        html_text = ctx.evidence.http.body_text if ctx.evidence.http else None

        for sig in FRAMEWORKS:
            signals: list[str] = []
            evidence_refs: list[EvidenceRef] = []

            # Runtime globals
            if runtime and sig.runtime_globals:
                for gname in sig.runtime_globals:
                    if gname in runtime.globals_present:
                        signals.append(f"Global: window.{gname}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.RUNTIME_GLOBAL,
                                source=f"runtime.globals_present[{gname}]",
                                excerpt=gname,
                            )
                        )

            # Hydration payloads
            if runtime and sig.hydration_keys:
                for key in sig.hydration_keys:
                    if key in runtime.hydration_payload_keys:
                        signals.append(f"Hydration payload: {key}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.RUNTIME_GLOBAL,
                                source=f"runtime.hydration_payload_keys[{key}]",
                                excerpt=key,
                            )
                        )

            # DOM indicators (check HTML text for data attributes)
            if html_text and sig.dom_indicators:
                for indicator in sig.dom_indicators:
                    if indicator in html_text:
                        signals.append(f"DOM attribute: {indicator}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ATTRIBUTE,
                                source=f"dom.attribute[{indicator}]",
                                excerpt=indicator,
                            )
                        )
                        break  # One DOM indicator is enough

            # Script URL patterns
            if dom and sig.script_patterns:
                for script in dom.scripts:
                    if script.src:
                        for pattern in sig.script_patterns:
                            if pattern in script.src:
                                signals.append(f"Script: {script.src[:100]}")
                                evidence_refs.append(
                                    EvidenceRef(
                                        kind=EvidenceKind.SCRIPT_URL,
                                        source=f"dom.scripts[src*={pattern}]",
                                        excerpt=script.src[:200],
                                    )
                                )
                                break

            # ID patterns (script tags with specific IDs)
            if html_text and sig.id_patterns:
                for id_pat in sig.id_patterns:
                    if f'id="{id_pat}"' in html_text or f"id='{id_pat}'" in html_text:
                        signals.append(f"Element ID: #{id_pat}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source=f"dom.element[id={id_pat}]",
                                excerpt=id_pat,
                            )
                        )

            if signals:
                confidence = Confidence.DEFINITIVE if len(signals) >= 2 else Confidence.STRONG
                slug = sig.name.lower().replace(" ", "-").replace(".", "-")
                finding = self._build.detected(
                    slug,
                    category="framework",
                    name=sig.name,
                    value=sig.name,
                    confidence=confidence,
                    evidence=evidence_refs[:5],
                )
                findings.append(finding)
                products.append(
                    DetectedProduct(
                        name=sig.name,
                        categories=sig.categories,
                        version=None,
                        status=finding.status,
                        signal_summary=signals[:5],
                        finding_id=finding.id,
                    )
                )

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(products=products) if products else None,
        )
