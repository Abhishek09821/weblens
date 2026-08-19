"""Collector protocol and the stage-reporting seam.

``StageSink`` is declared here rather than imported from ``orchestration`` so the dependency
arrow keeps pointing one way: ``orchestration -> collection``, never back. The pipeline's
progress reporter satisfies this protocol structurally.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from weblens.collection.target import NormalizedTarget
from weblens.domain.enums import ErrorCode, StageKey
from weblens.domain.evidence import RawEvidence
from weblens.domain.scan import RedirectHop, RunContext, ScanOptions


@runtime_checkable
class StageSink(Protocol):
    """Receives stage transitions as collection proceeds."""

    async def stage_started(self, key: StageKey) -> None: ...

    async def stage_completed(self, key: StageKey) -> None: ...

    async def stage_failed(self, key: StageKey, code: ErrorCode, detail: str) -> None: ...

    async def stage_skipped(self, key: StageKey, reason: str) -> None: ...


class CollectionOutcome:
    """Evidence plus the derived facts the result envelope needs.

    Redirect chain and run context are collection concerns but belong on ``TargetInfo`` and
    ``ScanMetadata``, so they travel alongside the evidence rather than inside it.
    """

    __slots__ = ("evidence", "redirect_chain", "run_context")

    def __init__(
        self,
        evidence: RawEvidence,
        redirect_chain: list[RedirectHop],
        run_context: RunContext,
    ) -> None:
        self.evidence = evidence
        self.redirect_chain = redirect_chain
        self.run_context = run_context


class Collector(Protocol):
    """Collects evidence from a target. The only layer permitted to touch the network."""

    collection_mode: str

    async def collect(
        self,
        target: NormalizedTarget,
        options: ScanOptions,
        sink: StageSink,
    ) -> CollectionOutcome: ...
