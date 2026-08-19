"""Measurement observations: network ledger, performance entries, accessibility results.

Filled by the browser stages from Phase 1 onwards. Declared now so the evidence contract
and the committed fixture format do not change when those stages land.
"""

from __future__ import annotations

from pydantic import Field

from weblens.domain.observations.transport import HeaderEntry, Observation


class NetworkRequestRecord(Observation):
    """One request/response pair observed during navigation.

    ``Set-Cookie`` values and authorization headers are never captured; only the selected
    cache/CORS/security headers listed by the collector reach this record.
    """

    url: str
    """Redacted at collection time if it carried credential-ish query parameters."""
    method: str
    resource_type: str
    status: int | None = None
    protocol: str | None = None
    mime_type: str | None = None
    transfer_bytes: int | None = None
    decoded_bytes: int | None = None
    duration_ms: float | None = None
    from_cache: bool | None = None
    initiator_type: str | None = None
    is_same_origin: bool | None = None
    is_same_site: bool | None = None
    host: str | None = None
    selected_headers: list[HeaderEntry] = Field(default_factory=list)
    sets_cookie: bool = False
    """Presence only. Third-party cookie values are never recorded."""
    failed: bool = False
    failure_text: str | None = None


class NetworkObservation(Observation):
    requests: list[NetworkRequestRecord] = Field(default_factory=list)
    cap_hit: bool = False
    """True when ``max_network_requests_recorded`` was reached, so totals are a lower bound
    rather than a count."""
    recorded_until_ms: float | None = None


class LongTaskEntry(Observation):
    start_ms: float
    duration_ms: float


class PerformanceObservation(Observation):
    """Single cold lab run at a bounded settle point. Not field data (see L-PERF-01)."""

    ttfb_ms: float | None = None
    dom_content_loaded_ms: float | None = None
    dom_interactive_ms: float | None = None
    load_event_ms: float | None = None
    first_contentful_paint_ms: float | None = None
    largest_contentful_paint_ms: float | None = None
    largest_contentful_paint_element: str | None = None
    cumulative_layout_shift: float | None = None
    long_tasks: list[LongTaskEntry] = Field(default_factory=list)
    total_blocking_estimate_ms: float | None = None
    transfer_bytes_total: int | None = None
    decoded_bytes_total: int | None = None
    request_count: int | None = None
    render_blocking_request_count: int | None = None


class AxeNode(Observation):
    target: list[str] = Field(default_factory=list)
    html_excerpt: str | None = None
    failure_summary: str | None = None


class AxeViolation(Observation):
    rule_id: str
    impact: str | None = None
    description: str
    help_text: str
    help_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    node_count: int
    sample_nodes: list[AxeNode] = Field(default_factory=list)


class AxeObservation(Observation):
    """Results from the vendored, pinned axe-core build.

    ``engine_version`` is recorded because rule sets change between versions, so a stored
    result is only interpretable against the engine that produced it.
    """

    engine_name: str = "axe-core"
    engine_version: str
    violations: list[AxeViolation] = Field(default_factory=list)
    passes_count: int | None = None
    incomplete_count: int | None = None
    inapplicable_count: int | None = None
    rules_run_count: int | None = None
    error: str | None = None
