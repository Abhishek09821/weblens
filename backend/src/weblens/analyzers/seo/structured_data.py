"""Structured data analysis.

Reports: JSON-LD, microdata, and RDFa inventory with schema types and validity.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import SeoPayload

ANALYZER_ID = "seo.structured_data"


class SeoStructuredDataAnalyzer:
    """Analyzes structured data from the DOM."""

    id = ANALYZER_ID
    section = SectionKey.SEO
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
        structured_data = dom.structured_data

        if not structured_data:
            findings.append(
                self._build.not_detected(
                    "structured-data",
                    category="structured_data",
                    name="Structured data",
                    reason="No JSON-LD, microdata, or RDFa was found in the document.",
                )
            )
            return AnalyzerOutput(findings=findings)

        # Count by format
        format_counts: dict[str, int] = {}
        all_types: list[str] = []
        valid_count = 0
        invalid_count = 0

        for block in structured_data:
            format_counts[block.format] = format_counts.get(block.format, 0) + 1
            all_types.extend(block.types)
            if block.valid:
                valid_count += 1
            else:
                invalid_count += 1

        findings.append(
            self._build.detected(
                "structured-data",
                category="structured_data",
                name="Structured data blocks",
                value=len(structured_data),
                unit="count",
                values=[f"{fmt}: {count}" for fmt, count in format_counts.items()],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTML_ELEMENT,
                        source="dom.structured_data",
                        excerpt=f"{len(structured_data)} blocks: "
                        + ", ".join(f"{fmt}={count}" for fmt, count in format_counts.items()),
                    )
                ],
                details={
                    "valid": valid_count,
                    "invalid": invalid_count,
                    "formats": list(format_counts.keys()),
                },
            )
        )

        # Schema types
        unique_types = list(dict.fromkeys(all_types))
        if unique_types:
            findings.append(
                self._build.detected(
                    "schema-types",
                    category="structured_data",
                    name="Schema.org types",
                    value=len(unique_types),
                    unit="count",
                    values=unique_types[:20],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.HTML_ELEMENT,
                            source="dom.structured_data.types",
                            excerpt=", ".join(unique_types[:5]),
                        )
                    ],
                )
            )

        return AnalyzerOutput(
            findings=findings,
            data=SeoPayload(structured_data=list(structured_data)),
        )
