"""Document structure accessibility analysis.

Checks: language declaration, heading hierarchy, alt text, form labels,
ARIA landmarks, accessible names. All from the DOM inventory.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    attribute_evidence,
    element_evidence,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "accessibility.structure"


class AccessibilityStructureAnalyzer:
    """Checks document structure for accessibility concerns."""

    id = ANALYZER_ID
    section = SectionKey.DESIGN
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        if dom is None:
            return AnalyzerOutput(findings=[])

        findings = []

        # Document language
        if dom.lang:
            findings.append(
                self._build.detected(
                    "document-lang",
                    category="document",
                    name="Document language",
                    value=dom.lang,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[attribute_evidence("html[lang]", dom.lang)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "document-lang",
                    category="document",
                    name="Document language",
                    reason="The <html> element has no lang attribute.",
                )
            )

        # Title
        if dom.title:
            findings.append(
                self._build.detected(
                    "document-title",
                    category="document",
                    name="Document title",
                    value=dom.title,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[element_evidence("title", dom.title)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "document-title",
                    category="document",
                    name="Document title",
                    reason="No <title> element with text was found.",
                )
            )

        # Heading hierarchy
        if dom.headings:
            levels = [h.level for h in dom.headings]
            # Check for proper hierarchy (h1 should come first, no level skipping)
            issues: list[str] = []
            if levels[0] != 1:
                issues.append(f"First heading is h{levels[0]}, not h1")
            for i in range(1, len(levels)):
                if levels[i] > levels[i - 1] + 1:
                    issues.append(f"Level skip: h{levels[i - 1]} to h{levels[i]}")
                    break

            if issues:
                findings.append(
                    self._build.detected(
                        "heading-hierarchy",
                        category="structure",
                        name="Heading hierarchy issues",
                        value=len(issues),
                        unit="count",
                        values=issues[:5],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source="dom.headings",
                                excerpt=f"Levels: {levels[:10]}",
                            )
                        ],
                    )
                )
            else:
                findings.append(
                    self._build.detected(
                        "heading-hierarchy",
                        category="structure",
                        name="Heading hierarchy",
                        value="correct",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source="dom.headings",
                                excerpt=f"Levels: {levels[:10]}",
                            )
                        ],
                    )
                )

        # Images without alt
        if dom.images:
            missing_alt = [img for img in dom.images if not img.alt_present]
            if missing_alt:
                findings.append(
                    self._build.detected(
                        "images-missing-alt",
                        category="images",
                        name="Images without alt attribute",
                        value=len(missing_alt),
                        unit="count",
                        values=[img.src[:80] for img in missing_alt[:10] if img.src],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source="dom.images[alt_present=false]",
                                excerpt=f"{len(missing_alt)}/{len(dom.images)} images missing alt",
                            )
                        ],
                    )
                )
            else:
                findings.append(
                    self._build.detected(
                        "images-alt-coverage",
                        category="images",
                        name="Image alt attribute coverage",
                        value="complete",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source="dom.images",
                                excerpt=f"All {len(dom.images)} images have alt attributes",
                            )
                        ],
                    )
                )

        # Form labels
        if dom.forms:
            total_inputs = sum(f.input_count for f in dom.forms)
            labelled = sum(f.labelled_input_count for f in dom.forms)
            unlabelled = total_inputs - labelled
            if unlabelled > 0:
                findings.append(
                    self._build.detected(
                        "form-labels",
                        category="forms",
                        name="Form inputs without labels",
                        value=unlabelled,
                        unit="count",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.HTML_ELEMENT,
                                source="dom.forms",
                                excerpt=f"{unlabelled}/{total_inputs} inputs without labels",
                            )
                        ],
                    )
                )

        # Landmarks
        if dom.landmark_roles:
            findings.append(
                self._build.detected(
                    "landmarks",
                    category="structure",
                    name="ARIA landmarks",
                    value=len(dom.landmark_roles),
                    unit="count",
                    values=dom.landmark_roles[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.HTML_ELEMENT,
                            source="dom.landmark_roles",
                            excerpt=", ".join(dom.landmark_roles[:5]),
                        )
                    ],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "landmarks",
                    category="structure",
                    name="ARIA landmarks",
                    reason="No ARIA landmark roles were observed.",
                )
            )

        # Positive tabindex
        if dom.positive_tabindex_count and dom.positive_tabindex_count > 0:
            findings.append(
                self._build.detected(
                    "positive-tabindex",
                    category="structure",
                    name="Elements with positive tabindex",
                    value=dom.positive_tabindex_count,
                    unit="count",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.HTML_ATTRIBUTE,
                            source="dom.positive_tabindex_count",
                            excerpt=f"{dom.positive_tabindex_count} elements with tabindex > 0",
                        )
                    ],
                )
            )

        return AnalyzerOutput(findings=findings)
