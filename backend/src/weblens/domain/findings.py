"""Findings and interpretations.

The model validator on :class:`Finding` is the load-bearing part of this module. "Every
asserted fact carries provenance" is a product promise, and enforcing it at construction
time means a claim without evidence cannot be built - so it can never reach the UI, a
report, or a stored result. Convention would not survive; an invariant does.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from weblens.domain.enums import Confidence, FindingStatus
from weblens.domain.evidence import EvidenceRef

FindingValue = str | int | float | bool | None

ASSERTED_STATUSES = frozenset({FindingStatus.VERIFIED, FindingStatus.INFERRED})
NEGATIVE_STATUSES = frozenset(
    {
        FindingStatus.NOT_DETECTED,
        FindingStatus.NOT_DETERMINABLE,
        FindingStatus.UNABLE_TO_VERIFY,
    }
)


class Finding(BaseModel):
    """One structured conclusion about one property of the target."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="'<analyzer_id>:<slug>', unique within a result.")
    category: str = Field(description="Grouping within the section, e.g. 'response_headers'.")
    name: str = Field(description="Human-readable label.")
    status: FindingStatus
    detected: bool | None = Field(
        default=None, description="None when the notion of detection does not apply."
    )
    value: FindingValue = None
    values: list[str] = Field(default_factory=list)
    unit: str | None = Field(default=None, description="'ms', 'bytes', 'px', '%', 'days'.")
    confidence: Confidence | None = Field(
        default=None,
        description=(
            "Internal reasoning metadata used to derive status. Not a user-facing "
            "qualifier - see docs/blueprint/decisions.md D5."
        ),
    )
    evidence: list[EvidenceRef] = Field(default_factory=list)
    source: str = Field(description="Id of the analyzer that produced this finding.")
    details: dict[str, FindingValue | list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    reason: str | None = Field(
        default=None, description="Required for every negative status: why not."
    )

    @model_validator(mode="after")
    def _enforce_provenance(self) -> Finding:
        if self.status in ASSERTED_STATUSES and not self.evidence:
            raise ValueError(
                f"{self.id}: a '{self.status.value}' finding must carry at least one EvidenceRef"
            )
        if self.status in NEGATIVE_STATUSES and not self.reason:
            raise ValueError(f"{self.id}: a '{self.status.value}' finding must state a reason")
        return self

    @property
    def is_asserted(self) -> bool:
        return self.status in ASSERTED_STATUSES


class Interpretation(BaseModel):
    """A subjective statement derived from findings, kept structurally separate from them.

    Interpretations cannot be built without citing findings, and only analyzers whose job
    is interpretation emit them. That is how "observed fact" and "our reading of it" stay
    apart in the API, the UI, and every generated report.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    statement: str
    basis: Annotated[list[str], Field(min_length=1)] = Field(
        description="Finding ids this reading is derived from."
    )
    source: str
    caveat: str = "Interpretation derived from observed values, not a directly observed fact."
