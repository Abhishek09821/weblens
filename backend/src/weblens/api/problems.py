"""Exception handlers that render RFC 9457 problem documents.

Every failure the client can see goes through here, so error shape is consistent and stack
traces never reach the wire. Unexpected errors get an incident id that is also logged, which
is what makes a user-reported "something broke" traceable.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from weblens.domain.enums import ErrorCode
from weblens.domain.errors import ProblemDetail, RateLimitedError, WebLensError
from weblens.logging import get_logger
from weblens.utils.ids import new_ulid

logger = get_logger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


def problem_response(problem: ProblemDetail, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WebLensError)
    async def _weblens_error(request: Request, exc: WebLensError) -> JSONResponse:
        problem = ProblemDetail.from_error(exc, instance=request.url.path)
        headers = None
        if isinstance(exc, RateLimitedError):
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        logger.info(
            "request rejected",
            extra={"code": exc.code.value, "status": exc.status_code, "path": request.url.path},
        )
        return problem_response(problem, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problem = ProblemDetail(
            type="about:weblens/problem/invalid-request",
            title="The request body did not match the expected schema",
            status=422,
            detail=_summarize_validation(exc),
            code=ErrorCode.INVALID_REQUEST,
            instance=request.url.path,
            retryable=False,
        )
        return problem_response(problem)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        incident_id = new_ulid()
        logger.exception(
            "unhandled error", extra={"incident_id": incident_id, "path": request.url.path}
        )
        problem = ProblemDetail(
            type="about:weblens/problem/internal-error",
            title="Unexpected error",
            status=500,
            detail=f"An unexpected error occurred. Incident id: {incident_id}",
            code=ErrorCode.INTERNAL_ERROR,
            instance=request.url.path,
            retryable=False,
        )
        return problem_response(problem)


def _summarize_validation(exc: RequestValidationError) -> str:
    """Field-level detail without echoing the submitted values back."""
    parts: list[str] = []
    for error in exc.errors()[:5]:
        location = ".".join(str(item) for item in error.get("loc", ()) if item != "body")
        message = error.get("msg", "invalid value")
        parts.append(f"{location or 'body'}: {message}")
    return "; ".join(parts) or "The request could not be validated."
