"""Error types.

Two distinct things live here, and the difference matters:

*Exceptions* (:class:`WebLensError` and subclasses) abort an operation and become HTTP
problem responses.

*Records* (:class:`ScanError`) are data attached to a result. An analyzer failing is not an
API error - the scan still returns a report with that section marked unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import ErrorCode
from weblens.utils.timing import utc_now


class WebLensError(Exception):
    """Base class for errors that abort an operation."""

    status_code: int = 500
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    title: str = "Unexpected error"
    retryable: bool = False

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail


class TargetValidationError(WebLensError):
    status_code = 400
    code = ErrorCode.INVALID_URL
    title = "The submitted URL could not be used"


class TargetBlockedError(WebLensError):
    """The target resolves somewhere WebLens must not connect to."""

    status_code = 403
    code = ErrorCode.BLOCKED_TARGET
    title = "Target is not publicly routable"


class RobotsDisallowedError(WebLensError):
    status_code = 403
    code = ErrorCode.ROBOTS_DISALLOWED
    title = "The site's robots.txt disallows this path"


class DnsFailureError(WebLensError):
    status_code = 502
    code = ErrorCode.DNS_FAILURE
    title = "The host name could not be resolved"
    retryable = True


class ConnectFailureError(WebLensError):
    status_code = 502
    code = ErrorCode.CONNECT_FAILURE
    title = "The site could not be reached"
    retryable = True


class TlsFailureError(WebLensError):
    status_code = 502
    code = ErrorCode.TLS_FAILURE
    title = "The TLS connection could not be established"
    retryable = True


class NavigationTimeoutError(WebLensError):
    status_code = 502
    code = ErrorCode.NAVIGATION_TIMEOUT
    title = "The site did not respond within the time budget"
    retryable = True


class BrowserUnavailableError(WebLensError):
    status_code = 503
    code = ErrorCode.BROWSER_UNAVAILABLE
    title = "The analysis browser is not available"
    retryable = True


class RateLimitedError(WebLensError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED
    title = "Too many concurrent scans"
    retryable = True

    def __init__(self, detail: str | None = None, retry_after_seconds: int = 5) -> None:
        super().__init__(detail)
        self.retry_after_seconds = retry_after_seconds


class ScanNotFoundError(WebLensError):
    status_code = 404
    code = ErrorCode.SCAN_NOT_FOUND
    title = "No such scan"


class ScanInProgressError(WebLensError):
    status_code = 409
    code = ErrorCode.SCAN_IN_PROGRESS
    title = "The scan has not finished yet"
    retryable = True


class ResultExpiredError(WebLensError):
    status_code = 410
    code = ErrorCode.RESULT_EXPIRED
    title = "The result is no longer buffered"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail
            or "Results are held only until the client stores them, then released. Re-run the scan."
        )


class AiDisabledError(WebLensError):
    status_code = 501
    code = ErrorCode.AI_DISABLED
    title = "The AI explanation layer is not configured"


class ProblemDetail(BaseModel):
    """RFC 9457 problem document."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Stable URI identifying the problem kind.")
    title: str
    status: int
    detail: str | None = None
    code: ErrorCode
    instance: str | None = None
    retryable: bool = False

    @classmethod
    def from_error(cls, error: WebLensError, instance: str | None = None) -> ProblemDetail:
        slug = error.code.value.lower().replace("_", "-")
        return cls(
            type=f"about:weblens/problem/{slug}",
            title=error.title,
            status=error.status_code,
            detail=error.detail,
            code=error.code,
            instance=instance,
            retryable=error.retryable,
        )


class ScanError(BaseModel):
    """A failure recorded on a result rather than raised to the caller."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    scope: Literal["scan", "stage", "analyzer"]
    subject: str = Field(description="Stage key or analyzer id the failure belongs to.")
    message: str
    detail: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
