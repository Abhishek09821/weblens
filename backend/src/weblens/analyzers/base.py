"""Analyzer contract and shared builders.

Analyzers are pure, synchronous functions over collected evidence. They cannot perform I/O -
not by policy but by construction: they receive a frozen ``RawEvidence`` and have no client,
no socket, and no browser handle to reach for.

The builders below exist so 25+ modules do not each reinvent finding construction, and so the
mapping from "what did we see" to :class:`FindingStatus` happens in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from weblens.domain.enums import (
    Confidence,
    EvidenceKind,
    EvidenceSlot,
    FindingStatus,
    SectionKey,
)
from weblens.domain.evidence import EvidenceRef, RawEvidence
from weblens.domain.findings import Finding, FindingValue, Interpretation

# Confidence is internal reasoning metadata; this table is the only place it influences
# anything user-facing (docs/blueprint/decisions.md D5).
_ASSERTED_BY_CONFIDENCE = {
    Confidence.DEFINITIVE: FindingStatus.VERIFIED,
    Confidence.STRONG: FindingStatus.VERIFIED,
    Confidence.MODERATE: FindingStatus.INFERRED,
    Confidence.WEAK: FindingStatus.INFERRED,
}


def status_for(confidence: Confidence) -> FindingStatus:
    """Map internal confidence onto the user-facing status of an asserted finding."""
    return _ASSERTED_BY_CONFIDENCE[confidence]


@dataclass(frozen=True)
class AnalyzerContext:
    """Everything an analyzer is allowed to see."""

    evidence: RawEvidence
    findings: dict[str, Finding] = field(default_factory=dict)
    """Findings already produced in this scan, keyed by id. Read-only by convention;
    aggregators such as ``security.scoring`` consume it via ``depends_on``."""


@dataclass
class AnalyzerOutput:
    findings: list[Finding] = field(default_factory=list)
    interpretations: list[Interpretation] = field(default_factory=list)
    data: object | None = None
    limitations: list[str] = field(default_factory=list)


class Analyzer(Protocol):
    """The contract every analyzer implements."""

    id: str
    section: SectionKey
    version: str
    requires: frozenset[EvidenceSlot]
    depends_on: frozenset[str]

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput: ...


class FindingBuilder:
    """Helper bound to one analyzer, so ids and ``source`` are consistent by construction."""

    def __init__(self, analyzer_id: str) -> None:
        self._analyzer_id = analyzer_id

    def _id(self, slug: str) -> str:
        return f"{self._analyzer_id}:{slug}"

    def detected(
        self,
        slug: str,
        *,
        category: str,
        name: str,
        value: FindingValue = None,
        confidence: Confidence = Confidence.DEFINITIVE,
        evidence: list[EvidenceRef],
        values: list[str] | None = None,
        unit: str | None = None,
        details: dict[str, FindingValue | list[str]] | None = None,
        limitations: list[str] | None = None,
    ) -> Finding:
        """An asserted finding. ``evidence`` is required - the model enforces it too."""
        return Finding(
            id=self._id(slug),
            category=category,
            name=name,
            status=status_for(confidence),
            detected=True,
            value=value,
            values=values or [],
            unit=unit,
            confidence=confidence,
            evidence=evidence,
            source=self._analyzer_id,
            details=details or {},
            limitations=limitations or [],
        )

    def not_detected(
        self,
        slug: str,
        *,
        category: str,
        name: str,
        reason: str,
        evidence: list[EvidenceRef] | None = None,
        limitations: list[str] | None = None,
    ) -> Finding:
        """Evidence was available and the signal was absent.

        Not the same as "not used" - that distinction is L-TECH-01 and it is why this method
        demands a reason rather than defaulting one.
        """
        return self._negative(
            slug,
            status=FindingStatus.NOT_DETECTED,
            category=category,
            name=name,
            reason=reason,
            evidence=evidence,
            limitations=limitations,
            detected=False,
        )

    def not_determinable(
        self,
        slug: str,
        *,
        category: str,
        name: str,
        reason: str,
        evidence: list[EvidenceRef] | None = None,
        limitations: list[str] | None = None,
    ) -> Finding:
        """The property is not observable from outside the target, by nature."""
        return self._negative(
            slug,
            status=FindingStatus.NOT_DETERMINABLE,
            category=category,
            name=name,
            reason=reason,
            evidence=evidence,
            limitations=limitations,
            detected=None,
        )

    def unable_to_verify(
        self,
        slug: str,
        *,
        category: str,
        name: str,
        reason: str,
        limitations: list[str] | None = None,
    ) -> Finding:
        """Required evidence was not collected, so no claim can be made either way."""
        return self._negative(
            slug,
            status=FindingStatus.UNABLE_TO_VERIFY,
            category=category,
            name=name,
            reason=reason,
            evidence=None,
            limitations=limitations,
            detected=None,
        )

    def _negative(
        self,
        slug: str,
        *,
        status: FindingStatus,
        category: str,
        name: str,
        reason: str,
        evidence: list[EvidenceRef] | None,
        limitations: list[str] | None,
        detected: bool | None,
    ) -> Finding:
        return Finding(
            id=self._id(slug),
            category=category,
            name=name,
            status=status,
            detected=detected,
            evidence=evidence or [],
            source=self._analyzer_id,
            limitations=limitations or [],
            reason=reason,
        )

    def interpretation(self, slug: str, *, statement: str, basis: list[str]) -> Interpretation:
        return Interpretation(
            id=self._id(slug), statement=statement, basis=basis, source=self._analyzer_id
        )


# --- EvidenceRef factories -------------------------------------------------------------
# Consistent ``source`` paths matter: they are shown to users, printed in reports, and used
# by the AI grounding check to resolve citations.


def header_evidence(name: str, value: str, *, hop_url: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.HTTP_HEADER,
        source=f"http.headers.{name.lower()}",
        excerpt=value,
        location=hop_url,
    )


def meta_evidence(descriptor: str, content: str | None, *, url: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.META_TAG,
        source=f"dom.meta_tags[{descriptor}]",
        excerpt=content,
        location=url,
    )


def element_evidence(
    selector: str, excerpt: str | None = None, *, url: str | None = None
) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.HTML_ELEMENT,
        source=f"dom.{selector}",
        excerpt=excerpt,
        location=url,
    )


def attribute_evidence(path: str, value: str | None) -> EvidenceRef:
    return EvidenceRef(kind=EvidenceKind.HTML_ATTRIBUTE, source=f"dom.{path}", excerpt=value)


def status_evidence(status: int, url: str) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.HTTP_STATUS, source="http.status", excerpt=str(status), location=url
    )


def robots_evidence(directive: str, url: str) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.ROBOTS_DIRECTIVE,
        source="robots.matched_directive",
        excerpt=directive,
        location=url,
    )


def missing_evidence_reason(slots: list[EvidenceSlot]) -> str:
    names = ", ".join(slot.value for slot in slots)
    return f"Required evidence was not collected in this scan: {names}."
