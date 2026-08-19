"""Progress channel.

One object owns the job state and the fan-out to SSE subscribers, which is what guarantees
``GET /scans/{id}`` and the event stream can never disagree: both read the same state, and
every event is emitted as a side effect of mutating it.

Progress is the sum of the weights of stages that actually completed. There is no timer and no
interpolation - the "no fake progress" requirement is met by having no mechanism able to fake
it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Collection
from dataclasses import dataclass, field
from datetime import datetime

from weblens.domain.enums import ErrorCode, ScanStatus, StageKey, StageStatus
from weblens.domain.errors import ProblemDetail
from weblens.domain.scan import ScanJobState, StageProgress, StageRun
from weblens.logging import get_logger
from weblens.orchestration.stages import IMPLEMENTED_STAGES, STAGES, label_for, total_weight
from weblens.utils.timing import Stopwatch, utc_now

logger = get_logger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 15.0
_SUBSCRIBER_QUEUE_SIZE = 64


@dataclass(frozen=True)
class ProgressEvent:
    """One SSE frame."""

    event: str
    data: dict[str, object]


@dataclass
class ProgressChannel:
    """Mutable scan state plus subscriber fan-out."""

    scan_id: str
    requested_url: str
    status: ScanStatus = ScanStatus.QUEUED
    stages: dict[StageKey, StageRun] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    problem: ProblemDetail | None = None
    _subscribers: list[asyncio.Queue[ProgressEvent | None]] = field(default_factory=list)
    _timers: dict[StageKey, Stopwatch] = field(default_factory=dict)
    _created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for stage in IMPLEMENTED_STAGES:
            self.stages[stage.key] = StageRun(
                key=stage.key, label=stage.label, status=StageStatus.PENDING
            )

    # --- state ------------------------------------------------------------------------

    def snapshot(self) -> ScanJobState:
        return ScanJobState(
            scan_id=self.scan_id,
            status=self.status,
            requested_url=self.requested_url,
            created_at=self._created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            progress=self._progress(),
            stages=[self.stages[stage.key] for stage in IMPLEMENTED_STAGES],
            problem=self.problem,
        )

    def stage_runs(self) -> list[StageRun]:
        """Every declared stage, including ones this build does not implement.

        Unimplemented stages are reported as skipped with a reason so a stored result explains
        which parts of the pipeline did not run.
        """
        runs: list[StageRun] = []
        for stage in STAGES:
            if stage.key in self.stages:
                runs.append(self.stages[stage.key])
            else:
                runs.append(
                    StageRun(
                        key=stage.key,
                        label=stage.label,
                        status=StageStatus.SKIPPED,
                        skip_reason="Not implemented in this build.",
                    )
                )
        return runs

    def _progress(self) -> StageProgress:
        completed = [
            stage
            for stage in IMPLEMENTED_STAGES
            if self.stages[stage.key].status
            in (StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED)
        ]
        running = next(
            (
                stage
                for stage in IMPLEMENTED_STAGES
                if self.stages[stage.key].status is StageStatus.RUNNING
            ),
            None,
        )
        return StageProgress(
            current_stage=running.key if running else None,
            current_stage_label=running.label if running else None,
            completed_weight=sum(stage.weight for stage in completed),
            total_weight=total_weight(),
            stages_completed=len(completed),
            stages_total=len(IMPLEMENTED_STAGES),
        )

    # --- StageSink implementation -------------------------------------------------------

    async def stage_started(self, key: StageKey) -> None:
        self._timers[key] = Stopwatch()
        self._update(key, status=StageStatus.RUNNING, started_at=utc_now())
        await self._emit_stage(key, "started")

    async def stage_completed(self, key: StageKey) -> None:
        self._update(key, status=StageStatus.COMPLETED, duration_ms=self._elapsed(key))
        await self._emit_stage(key, "completed")
        await self._emit_progress()

    async def stage_failed(self, key: StageKey, code: ErrorCode, detail: str) -> None:
        self._update(
            key,
            status=StageStatus.FAILED,
            duration_ms=self._elapsed(key),
            error_code=code,
            error_detail=detail,
        )
        await self._emit_stage(key, "failed")
        await self._emit_progress()

    async def stage_skipped(self, key: StageKey, reason: str) -> None:
        self._update(key, status=StageStatus.SKIPPED, skip_reason=reason)
        await self._emit_stage(key, "skipped")
        await self._emit_progress()

    # --- lifecycle ---------------------------------------------------------------------

    async def finalize_pending(self, reason: str, exclude: Collection[StageKey] = ()) -> None:
        """Mark stages that never started as skipped, with a reason.

        Without this, a collector that legitimately does not run an optional stage would leave
        progress permanently short of its total - a progress bar that stalls at 81% and a result
        that silently omits what happened to those stages.

        ``exclude`` covers stages that are about to run, so the caller's own stage is not marked
        skipped moments before it starts.
        """
        for stage in IMPLEMENTED_STAGES:
            if stage.key in exclude:
                continue
            if self.stages[stage.key].status is StageStatus.PENDING:
                await self.stage_skipped(stage.key, reason)

    async def mark_running(self) -> None:
        self.status = ScanStatus.RUNNING
        self.started_at = utc_now()
        await self._publish(
            ProgressEvent("status", {"scan_id": self.scan_id, "status": self.status})
        )

    async def mark_finished(self, status: ScanStatus) -> None:
        self.status = status
        self.finished_at = utc_now()
        await self._publish(
            ProgressEvent(
                "done",
                {
                    "scan_id": self.scan_id,
                    "status": status.value,
                    "result_url": f"/api/v1/scans/{self.scan_id}/result",
                },
            )
        )
        await self._close_subscribers()

    async def mark_failed(self, problem: ProblemDetail) -> None:
        self.status = ScanStatus.FAILED
        self.finished_at = utc_now()
        self.problem = problem
        await self._publish(
            ProgressEvent("error", problem.model_dump(mode="json", exclude_none=True))
        )
        await self._close_subscribers()

    # --- subscription -------------------------------------------------------------------

    async def subscribe(self) -> AsyncIterator[ProgressEvent]:
        """Yield a state snapshot, then live events until the scan reaches a terminal state.

        The snapshot comes first so a client that connects late - or reconnects - never misses
        the scan.
        """
        queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
        self._subscribers.append(queue)
        try:
            yield ProgressEvent("snapshot", self.snapshot().model_dump(mode="json"))
            if self.status.is_terminal:
                yield self._terminal_event()
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
                except TimeoutError:
                    yield ProgressEvent("heartbeat", {})
                    continue
                if event is None:
                    return
                yield event
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def _terminal_event(self) -> ProgressEvent:
        if self.problem is not None:
            return ProgressEvent("error", self.problem.model_dump(mode="json", exclude_none=True))
        return ProgressEvent(
            "done",
            {
                "scan_id": self.scan_id,
                "status": self.status.value,
                "result_url": f"/api/v1/scans/{self.scan_id}/result",
            },
        )

    async def _close_subscribers(self) -> None:
        for queue in list(self._subscribers):
            await self._offer(queue, None)

    # --- internals ---------------------------------------------------------------------

    def _update(self, key: StageKey, **changes: object) -> None:
        current = self.stages.get(key) or StageRun(
            key=key, label=label_for(key), status=StageStatus.PENDING
        )
        self.stages[key] = current.model_copy(update=changes)

    def _elapsed(self, key: StageKey) -> float | None:
        watch = self._timers.get(key)
        return watch.elapsed_ms() if watch else None

    async def _emit_stage(self, key: StageKey, transition: str) -> None:
        run = self.stages[key]
        await self._publish(
            ProgressEvent(
                "stage",
                {
                    "scan_id": self.scan_id,
                    "stage": key.value,
                    "label": run.label,
                    "status": transition,
                    "duration_ms": run.duration_ms,
                    "error_code": run.error_code.value if run.error_code else None,
                },
            )
        )

    async def _emit_progress(self) -> None:
        progress = self._progress()
        await self._publish(
            ProgressEvent("progress", {"scan_id": self.scan_id, **progress.model_dump(mode="json")})
        )

    async def _publish(self, event: ProgressEvent) -> None:
        for queue in list(self._subscribers):
            await self._offer(queue, event)

    async def _offer(
        self, queue: asyncio.Queue[ProgressEvent | None], item: ProgressEvent | None
    ) -> None:
        """Never let a slow consumer stall the scan.

        A full queue means a subscriber is not keeping up; dropping an intermediate frame is
        acceptable because the next snapshot or progress event carries the full state anyway.
        """
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.debug("progress subscriber queue full; frame dropped")
