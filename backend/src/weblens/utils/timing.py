"""Timing helpers.

Durations are measured with :func:`time.perf_counter` (monotonic, unaffected by clock
adjustments) while timestamps use timezone-aware UTC. Mixing the two up produces the kind
of nonsense negative durations that make a report untrustworthy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


@dataclass
class Stopwatch:
    """Measures elapsed wall time in milliseconds."""

    _start: float = field(default_factory=time.perf_counter)

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)

    def reset(self) -> None:
        self._start = time.perf_counter()


@dataclass
class Budget:
    """A wall-clock allowance for a whole scan.

    Stages consult :meth:`remaining_ms` before starting. When the budget is spent, they
    are recorded as skipped with a reason rather than being silently truncated, so a
    partial scan always explains itself.
    """

    total_ms: float
    _watch: Stopwatch = field(default_factory=Stopwatch)

    def remaining_ms(self) -> float:
        return max(0.0, self.total_ms - self._watch.elapsed_ms())

    def spent_ms(self) -> float:
        return self._watch.elapsed_ms()

    def exhausted(self) -> bool:
        return self.remaining_ms() <= 0

    def allowance_ms(self, requested_ms: float) -> float:
        """The smaller of what a stage wants and what the budget has left."""
        return min(requested_ms, self.remaining_ms())
