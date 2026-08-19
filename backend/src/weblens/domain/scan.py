"""Scan request, metadata, job state, and the result envelope."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import ErrorCode, ScanStatus, SectionKey, StageKey, StageStatus
from weblens.domain.errors import ProblemDetail, ScanError
from weblens.domain.observations import RobotsObservation
from weblens.domain.sections import SectionSet
from weblens.utils.timing import utc_now
from weblens.version import ENGINE_VERSION, SCHEMA_VERSION, USER_AGENT


class Viewport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int = Field(default=1440, ge=320, le=3840)
    height: int = Field(default=900, ge=320, le=2160)


class ScanOptions(BaseModel):
    """Per-scan options. ``extra='forbid'`` so an option typo is a 422, not a silent no-op."""

    model_config = ConfigDict(extra="forbid")

    include_screenshot: bool = True
    include_full_page_screenshot: bool = False
    viewport: Viewport = Field(default_factory=Viewport)
    responsive_widths: list[int] = Field(default_factory=lambda: [390, 768, 1440], max_length=6)
    sections: list[SectionKey] | None = Field(
        default=None, description="Restrict analysis to these sections. None means all."
    )


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(
        min_length=3,
        max_length=2048,
        description="Public http(s) URL. Normalized and guarded server-side.",
    )
    options: ScanOptions = Field(default_factory=ScanOptions)


class RedirectHop(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    status: int
    location: str | None = None
    scheme: str


class TargetInfo(BaseModel):
    """What we ended up analyzing, which is not always what was requested."""

    model_config = ConfigDict(extra="forbid")

    requested_url: str
    normalized_url: str
    final_url: str | None = None
    host: str
    port: int
    scheme: str
    resolved_ips: list[str] = Field(default_factory=list)
    redirect_chain: list[RedirectHop] = Field(default_factory=list)
    http_status: int | None = None
    document_title: str | None = None
    robots: RobotsObservation | None = None


class RunContext(BaseModel):
    """The conditions the measurements were taken under.

    Performance and design numbers are meaningless without this, so it travels with every
    result and is printed in every report.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    browser_name: str | None = None
    browser_version: str | None = None
    user_agent: str = USER_AGENT
    viewport: Viewport = Field(default_factory=Viewport)
    device_scale_factor: float = 1.0
    wait_strategy: str = Field(description="e.g. 'domcontentloaded+network_idle(5000ms)'.")
    settle_reached: bool | None = None
    network_throttling: str = "none"
    cpu_throttling: str = "none"
    locale: str = "en-US"
    timezone: str = "UTC"
    collection_mode: str = Field(
        description="'http_only' or 'browser'. Tells the reader which evidence base was used."
    )


class StageRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StageKey
    label: str
    status: StageStatus
    started_at: datetime | None = None
    duration_ms: float | None = None
    error_code: ErrorCode | None = None
    error_detail: str | None = None
    skip_reason: str | None = None


class ScanMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    status: ScanStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None
    engine_version: str = ENGINE_VERSION
    schema_version: str = SCHEMA_VERSION
    options: ScanOptions
    run_context: RunContext | None = None
    stages: list[StageRun] = Field(default_factory=list)


class ScreenshotRef(BaseModel):
    """Screenshot metadata plus inline data.

    The client moves the bytes into its own IndexedDB store as a Blob and does not keep them
    in the result record, which is why this is a separate top-level list rather than being
    buried inside the design payload.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    width: int
    height: int
    mime_type: str = "image/png"
    data_base64: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    scan: ScanMetadata
    target: TargetInfo
    sections: SectionSet
    errors: list[ScanError] = Field(default_factory=list)
    screenshots: list[ScreenshotRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# --- Transport-only models (job lifecycle) ---------------------------------------------


class StageProgress(BaseModel):
    """Progress derived from stages that actually completed.

    There is no interpolation and no time-based estimate here on purpose: the requirement
    is honest progress, and the simplest way to guarantee it is to have no mechanism
    capable of faking it.
    """

    model_config = ConfigDict(extra="forbid")

    current_stage: StageKey | None = None
    current_stage_label: str | None = None
    completed_weight: int = 0
    total_weight: int = 0
    stages_completed: int = 0
    stages_total: int = 0


class ScanJobState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    status: ScanStatus
    requested_url: str
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: StageProgress = Field(default_factory=StageProgress)
    stages: list[StageRun] = Field(default_factory=list)
    problem: ProblemDetail | None = None


class ScanAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    status: ScanStatus
    requested_url: str
    normalized_url: str
    created_at: datetime
    links: dict[str, str]
