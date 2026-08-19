"""Ephemeral job store.

The browser is the system of record (docs/blueprint/09). This store is a transport buffer: it
holds a result only until the client confirms it has persisted it, then releases it. Nothing
here survives a restart, and that is the design, not an oversight.

Two bounds keep memory predictable: a TTL and a cap on retained results with least-recently-
used eviction. Both are configurable, and eviction is logged so a client hitting a 410
has an explanation on the server side too.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from weblens.config import Settings
from weblens.domain.scan import AnalysisResult, ScanOptions
from weblens.logging import get_logger
from weblens.orchestration.progress import ProgressChannel
from weblens.utils.timing import utc_now

logger = get_logger(__name__)


@dataclass
class Job:
    scan_id: str
    requested_url: str
    normalized_url: str
    host: str
    options: ScanOptions
    channel: ProgressChannel
    created_at: datetime = field(default_factory=utc_now)
    result: AnalysisResult | None = None
    task: asyncio.Task[None] | None = None
    completed_at: datetime | None = None

    def expires_at(self, ttl_seconds: int) -> datetime:
        anchor = self.completed_at or self.created_at
        return anchor + timedelta(seconds=ttl_seconds)


class JobStore(Protocol):
    """Seam for a future durable implementation. V1 has exactly one."""

    async def create(self, job: Job) -> None: ...

    async def get(self, scan_id: str) -> Job | None: ...

    async def delete(self, scan_id: str) -> bool: ...

    async def set_result(self, scan_id: str, result: AnalysisResult) -> None: ...

    async def active_count(self) -> int: ...


class InMemoryJobStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = asyncio.Lock()

    async def create(self, job: Job) -> None:
        async with self._lock:
            self._sweep_locked()
            self._jobs[job.scan_id] = job
            self._jobs.move_to_end(job.scan_id)
            self._enforce_cap_locked()

    async def get(self, scan_id: str) -> Job | None:
        async with self._lock:
            self._sweep_locked()
            job = self._jobs.get(scan_id)
            if job is not None:
                self._jobs.move_to_end(scan_id)
            return job

    async def delete(self, scan_id: str) -> bool:
        async with self._lock:
            return self._jobs.pop(scan_id, None) is not None

    async def set_result(self, scan_id: str, result: AnalysisResult) -> None:
        async with self._lock:
            job = self._jobs.get(scan_id)
            if job is None:
                return
            job.result = result
            job.completed_at = utc_now()

    async def active_count(self) -> int:
        async with self._lock:
            return sum(
                1 for job in self._jobs.values() if job.task is not None and not job.task.done()
            )

    async def host_activity(self, host: str) -> tuple[int, datetime | None]:
        """Running scans for a host, and when that host was last scanned.

        Used for politeness admission control: one scan per host at a time, spaced by a
        configurable interval.
        """
        async with self._lock:
            running = 0
            latest: datetime | None = None
            for job in self._jobs.values():
                if job.host != host:
                    continue
                if job.task is not None and not job.task.done():
                    running += 1
                anchor = job.completed_at or job.created_at
                if latest is None or anchor > latest:
                    latest = anchor
            return running, latest

    async def sweep(self) -> int:
        async with self._lock:
            return self._sweep_locked()

    # --- internals ---------------------------------------------------------------------

    def _sweep_locked(self) -> int:
        now = utc_now()
        expired = [
            scan_id
            for scan_id, job in self._jobs.items()
            if job.result is not None and job.expires_at(self._settings.result_ttl_seconds) <= now
        ]
        for scan_id in expired:
            del self._jobs[scan_id]
        if expired:
            logger.info("evicted expired results", extra={"count": len(expired)})
        return len(expired)

    def _enforce_cap_locked(self) -> None:
        cap = self._settings.max_retained_results
        while len(self._jobs) > cap:
            scan_id, job = next(iter(self._jobs.items()))
            if job.task is not None and not job.task.done():
                # Never evict a running scan; move it back and stop trying.
                self._jobs.move_to_end(scan_id)
                if all(
                    candidate.task is not None and not candidate.task.done()
                    for candidate in self._jobs.values()
                ):
                    return
                continue
            del self._jobs[scan_id]
            logger.info("evicted result over retention cap", extra={"evicted_scan_id": scan_id})


async def periodic_sweep(store: InMemoryJobStore, interval_seconds: float = 60.0) -> None:
    """Background eviction loop, started and cancelled by the application lifespan."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await store.sweep()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("job store sweep failed")
