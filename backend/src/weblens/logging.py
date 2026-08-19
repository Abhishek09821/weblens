"""Centralised logging.

One handler, one formatter, and a ``contextvars``-backed filter that stamps every record
with the scan and stage it belongs to. That means a scan can be traced end to end without
threading a logger through the collection and analysis layers.

Never logged: target response bodies, cookie values, or captured evidence. Evidence
excerpts exist only inside the result payload, where they are bounded and sanitized.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_scan_id: ContextVar[str | None] = ContextVar("weblens_scan_id", default=None)
_stage: ContextVar[str | None] = ContextVar("weblens_stage", default=None)

_BASE_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "scan_id",
    "stage",
}


class ContextFilter(logging.Filter):
    """Attaches the current scan id and stage to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.scan_id = _scan_id.get()
        record.stage = _stage.get()
        return True


class TextFormatter(logging.Formatter):
    """Human-readable single-line format for local development."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {record.name}"
        context = []
        scan_id = getattr(record, "scan_id", None)
        stage = getattr(record, "stage", None)
        if scan_id:
            context.append(f"scan={scan_id}")
        if stage:
            context.append(f"stage={stage}")
        extras = _extra_fields(record)
        for key, value in extras.items():
            context.append(f"{key}={value}")
        suffix = f" [{' '.join(context)}]" if context else ""
        line = f"{base}{suffix} {record.getMessage()}"
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


class JsonFormatter(logging.Formatter):
    """Structured output for when logs are shipped somewhere."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if scan_id := getattr(record, "scan_id", None):
            payload["scan_id"] = scan_id
        if stage := getattr(record, "stage", None):
            payload["stage"] = stage
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _BASE_RECORD_KEYS and not key.startswith("_")
    }


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Install the WebLens logging configuration. Idempotent."""
    formatter: logging.Formatter = JsonFormatter() if fmt == "json" else TextFormatter()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers; route them through ours instead of duplicating.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def scan_context(scan_id: str, stage: str | None = None) -> Iterator[None]:
    """Bind a scan id (and optionally a stage) for the duration of the block."""
    scan_token = _scan_id.set(scan_id)
    stage_token = _stage.set(stage)
    try:
        yield
    finally:
        _scan_id.reset(scan_token)
        _stage.reset(stage_token)


@contextmanager
def stage_context(stage: str) -> Iterator[None]:
    """Bind the current pipeline stage for the duration of the block."""
    token = _stage.set(stage)
    try:
        yield
    finally:
        _stage.reset(token)
