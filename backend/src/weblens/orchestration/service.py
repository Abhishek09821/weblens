"""Scan service: admission control, job scheduling, and failure translation.

Sits between the API and the pipeline so routes stay thin and the politeness rules live in one
place. Three admission checks run before a scan is accepted, all configurable:

* a global concurrency cap, because browser work is the scarce resource;
* one scan per host at a time;
* a minimum interval between scans of the same host.

The last two exist because a tool that hammers the sites it analyzes has no business calling
itself polite.
"""

from __future__ import annotations

import asyncio

from weblens.collection.base import Collector
from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import Settings
from weblens.domain.enums import ScanStatus
from weblens.domain.errors import (
    NavigationTimeoutError,
    ProblemDetail,
    RateLimitedError,
    ResultExpiredError,
    ScanInProgressError,
    ScanNotFoundError,
    WebLensError,
)
from weblens.domain.scan import (
    AnalysisResult,
    ScanAcceptedResponse,
    ScanJobState,
    ScanRequest,
)
from weblens.logging import get_logger, scan_context
from weblens.orchestration.job_store import InMemoryJobStore, Job
from weblens.orchestration.pipeline import ScanPipeline
from weblens.orchestration.progress import ProgressChannel
from weblens.utils.ids import new_ulid
from weblens.utils.timing import utc_now

logger = get_logger(__name__)


class ScanService:
    def __init__(
        self,
        settings: Settings,
        store: InMemoryJobStore,
        guard: TargetGuard,
        collector: Collector,
    ) -> None:
        self._settings = settings
        self._store = store
        self._guard = guard
        self._pipeline = ScanPipeline(settings, collector)
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_scans)

    # --- commands ----------------------------------------------------------------------

    async def submit(self, request: ScanRequest) -> ScanAcceptedResponse:
        """Validate, admit, and schedule a scan. Raises on rejection."""
        target = await self._guard.prepare(request.url)
        await self._admit(target)

        scan_id = new_ulid()
        channel = ProgressChannel(scan_id=scan_id, requested_url=target.requested_url)
        job = Job(
            scan_id=scan_id,
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            host=target.host,
            options=request.options,
            channel=channel,
        )
        await self._store.create(job)
        job.task = asyncio.create_task(self._execute(job, target), name=f"weblens-scan-{scan_id}")

        logger.info("scan accepted", extra={"scan_id": scan_id, "host": target.host})
        return ScanAcceptedResponse(
            scan_id=scan_id,
            status=ScanStatus.QUEUED,
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            created_at=job.created_at,
            links={
                "self": f"/api/v1/scans/{scan_id}",
                "events": f"/api/v1/scans/{scan_id}/events",
                "result": f"/api/v1/scans/{scan_id}/result",
            },
        )

    async def delete(self, scan_id: str) -> None:
        """Release the server-side copy. Idempotent: the desired end state is 'gone'."""
        job = await self._store.get(scan_id)
        if job is not None and job.task is not None and not job.task.done():
            job.task.cancel()
        await self._store.delete(scan_id)

    # --- queries -----------------------------------------------------------------------

    async def job_state(self, scan_id: str) -> ScanJobState:
        job = await self._require(scan_id)
        return job.channel.snapshot()

    async def result(self, scan_id: str) -> AnalysisResult:
        job = await self._require(scan_id)
        if job.result is not None:
            return job.result
        if job.channel.status.is_terminal:
            # Terminal without a result means the scan failed before assembly.
            raise ResultExpiredError(
                "The scan finished without producing a result. See the job state for the error."
            )
        raise ScanInProgressError(f"Scan {scan_id} is {job.channel.status.value}.")

    async def channel(self, scan_id: str) -> ProgressChannel:
        job = await self._require(scan_id)
        return job.channel

    async def _require(self, scan_id: str) -> Job:
        job = await self._store.get(scan_id)
        if job is None:
            raise ScanNotFoundError(
                f"No scan with id {scan_id} is buffered. Results are released once stored by "
                "the client, so this id may simply have been cleaned up."
            )
        return job

    # --- execution ---------------------------------------------------------------------

    async def _admit(self, target: NormalizedTarget) -> None:
        active = await self._store.active_count()
        if active >= self._settings.max_concurrent_scans:
            raise RateLimitedError(
                f"{active} scans are already running "
                f"(limit {self._settings.max_concurrent_scans}). Try again shortly.",
                retry_after_seconds=10,
            )

        running_for_host, last_seen = await self._store.host_activity(target.host)
        if running_for_host >= self._settings.max_concurrent_scans_per_host:
            raise RateLimitedError(
                f"A scan of {target.host} is already running. WebLens runs one scan per host at "
                "a time to avoid load on the target.",
                retry_after_seconds=15,
            )
        if last_seen is not None:
            elapsed = (utc_now() - last_seen).total_seconds()
            interval = self._settings.min_host_interval_seconds
            if elapsed < interval:
                wait = int(interval - elapsed) + 1
                raise RateLimitedError(
                    f"{target.host} was scanned {int(elapsed)}s ago. WebLens spaces scans of the "
                    f"same host by {int(interval)}s.",
                    retry_after_seconds=wait,
                )

    async def _execute(self, job: Job, target: NormalizedTarget) -> None:
        with scan_context(job.scan_id):
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        self._pipeline.run(job, target),
                        timeout=self._settings.total_scan_budget_seconds,
                    )
            except asyncio.CancelledError:
                await job.channel.mark_finished(ScanStatus.CANCELLED)
                raise
            except TimeoutError:
                budget_error = NavigationTimeoutError(
                    f"The scan exceeded its {self._settings.total_scan_budget_ms} ms budget."
                )
                await job.channel.mark_failed(ProblemDetail.from_error(budget_error))
                logger.warning("scan exceeded budget")
                return
            except WebLensError as error:
                await job.channel.mark_failed(ProblemDetail.from_error(error))
                logger.info("scan failed", extra={"code": error.code.value, "detail": error.detail})
                return
            except Exception:
                logger.exception("scan crashed")
                await job.channel.mark_failed(
                    ProblemDetail.from_error(
                        WebLensError("An unexpected error ended the scan. The incident was logged.")
                    )
                )
                return

            await self._store.set_result(job.scan_id, result)
            await job.channel.mark_finished(result.scan.status)
            logger.info(
                "scan finished",
                extra={
                    "status": result.scan.status.value,
                    "duration_ms": result.scan.duration_ms,
                    "errors": len(result.errors),
                },
            )
