"""Domain invariants.

These tests protect the product promises that would otherwise erode through ordinary
refactoring: a claim cannot exist without evidence, an absence cannot exist without a reason,
and an interpretation cannot exist without citing findings.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from weblens.domain.enums import (
    Confidence,
    EvidenceKind,
    FindingStatus,
    SectionKey,
    SectionStatus,
)
from weblens.domain.evidence import EvidenceRef
from weblens.domain.findings import Finding, Interpretation
from weblens.domain.sections import SectionMeta
from weblens.utils.text import MAX_EXCERPT_CHARS

REF = EvidenceRef(kind=EvidenceKind.HTTP_HEADER, source="http.headers.server", excerpt="nginx")


@pytest.mark.parametrize("status", [FindingStatus.VERIFIED, FindingStatus.INFERRED])
def test_asserted_finding_requires_evidence(status: FindingStatus) -> None:
    with pytest.raises(ValidationError, match="must carry at least one EvidenceRef"):
        Finding(
            id="x:y", category="c", name="n", status=status, detected=True, source="x", evidence=[]
        )


@pytest.mark.parametrize("status", [FindingStatus.VERIFIED, FindingStatus.INFERRED])
def test_asserted_finding_accepts_evidence(status: FindingStatus) -> None:
    finding = Finding(
        id="x:y",
        category="c",
        name="n",
        status=status,
        detected=True,
        source="x",
        evidence=[REF],
    )
    assert finding.is_asserted


@pytest.mark.parametrize(
    "status",
    [
        FindingStatus.NOT_DETECTED,
        FindingStatus.NOT_DETERMINABLE,
        FindingStatus.UNABLE_TO_VERIFY,
    ],
)
def test_negative_finding_requires_a_reason(status: FindingStatus) -> None:
    with pytest.raises(ValidationError, match="must state a reason"):
        Finding(id="x:y", category="c", name="n", status=status, source="x")


def test_finding_is_immutable() -> None:
    finding = Finding(
        id="x:y",
        category="c",
        name="n",
        status=FindingStatus.VERIFIED,
        detected=True,
        source="x",
        evidence=[REF],
    )
    with pytest.raises(ValidationError):
        finding.value = "mutated"  # type: ignore[misc]


def test_confidence_maps_to_status_not_to_a_percentage() -> None:
    """Confidence is internal metadata; it must never surface as a numeric qualifier."""
    from weblens.analyzers.base import status_for

    assert status_for(Confidence.DEFINITIVE) is FindingStatus.VERIFIED
    assert status_for(Confidence.STRONG) is FindingStatus.VERIFIED
    assert status_for(Confidence.MODERATE) is FindingStatus.INFERRED
    assert status_for(Confidence.WEAK) is FindingStatus.INFERRED


def test_interpretation_requires_a_basis() -> None:
    with pytest.raises(ValidationError):
        Interpretation(id="d:i", statement="feels modern", basis=[], source="design.interpretation")


def test_interpretation_carries_a_caveat_by_default() -> None:
    interpretation = Interpretation(
        id="d:i", statement="dark, rounded visual language", basis=["design.color:bg"], source="d"
    )
    assert "not a directly observed fact" in interpretation.caveat


def test_evidence_excerpt_is_truncated_and_sanitized() -> None:
    ref = EvidenceRef(
        kind=EvidenceKind.INLINE_SCRIPT,
        source="dom.scripts[0]",
        excerpt="a" * 5000 + "\x00\n\tb",
    )
    assert ref.excerpt is not None
    assert len(ref.excerpt) <= MAX_EXCERPT_CHARS
    assert "\x00" not in ref.excerpt
    assert "\n" not in ref.excerpt


@pytest.mark.parametrize(
    "status",
    [SectionStatus.UNAVAILABLE, SectionStatus.NOT_IMPLEMENTED, SectionStatus.SKIPPED],
)
def test_non_complete_section_requires_a_reason(status: SectionStatus) -> None:
    with pytest.raises(ValidationError, match="needs a reason"):
        SectionMeta(key=SectionKey.DESIGN, status=status)


def test_complete_section_needs_no_reason() -> None:
    meta = SectionMeta(key=SectionKey.DESIGN, status=SectionStatus.COMPLETE)
    assert meta.unavailable_reason is None


def test_unknown_fields_are_rejected() -> None:
    """``extra='forbid'`` turns a typo into an error instead of a silently ignored field."""
    with pytest.raises(ValidationError):
        SectionMeta(key=SectionKey.DESIGN, status=SectionStatus.COMPLETE, typo=True)  # type: ignore[call-arg]
