"""Stage definitions.

The full pipeline is declared here, including stages whose implementation lands in later
phases, because the frontend renders the stage list from ``/capabilities`` and users deserve
to see what a scan does and does not currently do.

``weight`` drives progress reporting. Only stages that will actually run contribute to the
total, so progress reaches 100% in every build rather than stalling at a third.
"""

from __future__ import annotations

from dataclasses import dataclass

from weblens.domain.enums import StageKey


@dataclass(frozen=True)
class StageDefinition:
    key: StageKey
    label: str
    weight: int
    implemented: bool
    optional: bool = True
    """Optional stages degrade the sections that depend on them; required ones abort the scan."""


STAGES: tuple[StageDefinition, ...] = (
    StageDefinition(StageKey.VALIDATE, "Validating target", 2, True, optional=False),
    StageDefinition(StageKey.DNS, "Resolving host", 3, True),
    StageDefinition(StageKey.ROBOTS, "Checking robots.txt", 3, True),
    StageDefinition(StageKey.HTTP_PROBE, "Fetching document", 10, True, optional=False),
    StageDefinition(StageKey.TLS, "Inspecting TLS connection", 5, False),
    StageDefinition(StageKey.BROWSER_LAUNCH, "Starting browser", 5, False),
    StageDefinition(StageKey.NAVIGATE, "Loading page", 12, False),
    StageDefinition(StageKey.DOM_CAPTURE, "Capturing rendered DOM", 6, False),
    StageDefinition(StageKey.RUNTIME_CAPTURE, "Reading runtime signals", 5, False),
    StageDefinition(StageKey.STYLE_CAPTURE, "Sampling computed styles", 8, False),
    StageDefinition(StageKey.PERF_CAPTURE, "Collecting performance entries", 6, False),
    StageDefinition(StageKey.NETWORK_CAPTURE, "Finalising network ledger", 4, False),
    StageDefinition(StageKey.A11Y_CAPTURE, "Running accessibility rules", 8, False),
    StageDefinition(StageKey.RESPONSIVE_PROBE, "Measuring responsive layout", 5, False),
    StageDefinition(StageKey.SCREENSHOT, "Capturing screenshots", 4, False),
    StageDefinition(StageKey.ANALYZE, "Running analyzers", 12, True, optional=False),
    StageDefinition(StageKey.ASSEMBLE, "Assembling report", 2, True, optional=False),
)

STAGES_BY_KEY: dict[StageKey, StageDefinition] = {stage.key: stage for stage in STAGES}

IMPLEMENTED_STAGES: tuple[StageDefinition, ...] = tuple(
    stage for stage in STAGES if stage.implemented
)


def total_weight() -> int:
    """Sum of weights for stages that actually run in this build."""
    return sum(stage.weight for stage in IMPLEMENTED_STAGES)


def label_for(key: StageKey) -> str:
    return STAGES_BY_KEY[key].label
