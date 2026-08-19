"""CSS framework and methodology detection from DOM classes and stylesheets.

Detects: Tailwind CSS, Bootstrap, Bulma, Material UI, Styled Components,
CSS Modules, and other styling approaches with observable class-name patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import DetectedProduct, TechnologyPayload

ANALYZER_ID = "technology.styling"


@dataclass(frozen=True)
class _StylingSignature:
    name: str
    categories: list[str]
    class_patterns: list[re.Pattern[str]] = field(default_factory=list)
    stylesheet_patterns: list[re.Pattern[str]] = field(default_factory=list)
    custom_property_patterns: list[re.Pattern[str]] = field(default_factory=list)


STYLING_SIGNATURES: list[_StylingSignature] = [
    _StylingSignature(
        "Tailwind CSS",
        ["css-framework", "utility-first"],
        class_patterns=[
            re.compile(r"\bflex\b.*\bitems-center\b|\bgrid\b.*\bgap-"),
            re.compile(r"\b(bg|text|border|p|m|w|h)-([\w-]+)\b"),
            re.compile(r"\b(sm|md|lg|xl|2xl):"),
        ],
        stylesheet_patterns=[re.compile(r"tailwind")],
    ),
    _StylingSignature(
        "Bootstrap",
        ["css-framework", "component-library"],
        class_patterns=[
            re.compile(r"\bcol-(sm|md|lg|xl)-\d+\b"),
            re.compile(r"\b(btn|btn-primary|btn-secondary|container-fluid)\b"),
            re.compile(r"\brow\b.*\bcol-"),
        ],
        stylesheet_patterns=[re.compile(r"bootstrap")],
    ),
    _StylingSignature(
        "Bulma",
        ["css-framework"],
        class_patterns=[
            re.compile(r"\b(is-primary|is-danger|is-size-\d)\b"),
            re.compile(r"\bcolumns?\b.*\bcolumn\b"),
        ],
        stylesheet_patterns=[re.compile(r"bulma")],
    ),
    _StylingSignature(
        "Material UI",
        ["css-framework", "component-library"],
        class_patterns=[
            re.compile(r"\bMui[A-Z]"),
            re.compile(r"\bcss-[a-z0-9]+\b"),
        ],
        custom_property_patterns=[re.compile(r"--mui-")],
    ),
    _StylingSignature(
        "Chakra UI",
        ["css-framework", "component-library"],
        class_patterns=[re.compile(r"\bchakra-")],
        custom_property_patterns=[re.compile(r"--chakra-")],
    ),
    _StylingSignature(
        "Styled Components",
        ["css-in-js"],
        class_patterns=[re.compile(r"\bsc-[a-zA-Z]{5,}")],
    ),
    _StylingSignature(
        "CSS Modules",
        ["css-methodology"],
        class_patterns=[re.compile(r"_[a-zA-Z0-9]{5,}_[a-zA-Z0-9]+")],
    ),
    _StylingSignature(
        "Emotion",
        ["css-in-js"],
        class_patterns=[re.compile(r"\bcss-[a-z0-9]{6,}")],
    ),
    _StylingSignature(
        "Foundation",
        ["css-framework"],
        class_patterns=[
            re.compile(r"\b(small|medium|large)-\d+\b.*\bcolumns?\b"),
            re.compile(r"\bcallout\b|\boff-canvas\b"),
        ],
        stylesheet_patterns=[re.compile(r"foundation")],
    ),
    _StylingSignature(
        "Ant Design",
        ["css-framework", "component-library"],
        class_patterns=[re.compile(r"\bant-[a-z]")],
        custom_property_patterns=[re.compile(r"--ant-")],
    ),
]


class TechStylingAnalyzer:
    """Detects CSS frameworks from class names, stylesheets, and CSS custom properties."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM, EvidenceSlot.STYLES})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        styles = ctx.evidence.styles
        if dom is None and styles is None:
            return AnalyzerOutput(findings=[])

        findings = []
        products: list[DetectedProduct] = []

        # Get HTML text for class pattern matching
        html_text = ctx.evidence.http.body_text if ctx.evidence.http else None

        for sig in STYLING_SIGNATURES:
            signals: list[str] = []
            evidence_refs: list[EvidenceRef] = []

            # Check class patterns in HTML
            if html_text and sig.class_patterns:
                for pattern in sig.class_patterns:
                    match = pattern.search(html_text)
                    if match:
                        signals.append(f"Class pattern: {match.group()[:60]}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ATTRIBUTE,
                                source=f"dom.class_pattern[{pattern.pattern[:40]}]",
                                excerpt=match.group()[:100],
                            )
                        )
                        break

            # Check stylesheet URLs
            if dom and sig.stylesheet_patterns:
                for stylesheet in dom.stylesheets:
                    if stylesheet.href:
                        for pattern in sig.stylesheet_patterns:
                            if pattern.search(stylesheet.href):
                                signals.append(f"Stylesheet: {stylesheet.href[:100]}")
                                evidence_refs.append(
                                    EvidenceRef(
                                        kind=EvidenceKind.STYLESHEET_URL,
                                        source=f"dom.stylesheets[href~={pattern.pattern[:30]}]",
                                        excerpt=stylesheet.href[:200],
                                    )
                                )
                                break

            # Check CSS custom properties
            if styles and sig.custom_property_patterns:
                for prop in styles.css_custom_properties:
                    for pattern in sig.custom_property_patterns:
                        if pattern.search(prop):
                            signals.append(f"CSS variable: {prop}")
                            evidence_refs.append(
                                EvidenceRef(
                                    kind=EvidenceKind.COMPUTED_STYLE,
                                    source=f"styles.css_custom_properties[{prop}]",
                                    excerpt=prop,
                                )
                            )
                            break
                    if signals:
                        break

            if signals:
                confidence = Confidence.DEFINITIVE if len(signals) >= 2 else Confidence.MODERATE
                slug = sig.name.lower().replace(" ", "-").replace(".", "-")
                finding = self._build.detected(
                    slug,
                    category="styling",
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
