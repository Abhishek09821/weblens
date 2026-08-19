"""Scan lifecycle endpoints.

Note what is *not* an error here: a target that responds 404, 403, or 500 is data, recorded on
the result. Only a failure to obtain any response at all produces a 502. Conflating the two
would make WebLens unable to report on exactly the sites people most want reported on.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Response, status
from fastapi.responses import StreamingResponse

from weblens.api.deps import ScanServiceDep
from weblens.domain.errors import ScanNotFoundError
from weblens.domain.scan import AnalysisResult, ScanAcceptedResponse, ScanJobState, ScanRequest
from weblens.logging import get_logger
from weblens.utils.ids import is_ulid

logger = get_logger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post(
    "",
    response_model=ScanAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a URL for analysis",
)
async def create_scan(request: ScanRequest, service: ScanServiceDep) -> ScanAcceptedResponse:
    return await service.submit(request)


@router.get("/{scan_id}", response_model=ScanJobState, summary="Scan status and stage progress")
async def get_scan(scan_id: str, service: ScanServiceDep) -> ScanJobState:
    _validate_id(scan_id)
    return await service.job_state(scan_id)


@router.get(
    "/{scan_id}/result",
    response_model=AnalysisResult,
    summary="Structured analysis result",
    responses={
        409: {"description": "The scan has not finished yet."},
        410: {"description": "The result was released after the retention window."},
    },
)
async def get_result(scan_id: str, service: ScanServiceDep) -> AnalysisResult:
    _validate_id(scan_id)
    return await service.result(scan_id)


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Release the server-side copy of a scan",
)
async def delete_scan(scan_id: str, service: ScanServiceDep) -> Response:
    """Called by the client once the result is stored in IndexedDB.

    Idempotent: an unknown id also returns 204, because the desired end state - no server copy -
    holds either way.
    """
    _validate_id(scan_id)
    await service.delete(scan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{scan_id}/events",
    summary="Server-sent events for scan progress",
    response_class=StreamingResponse,
)
async def scan_events(scan_id: str, service: ScanServiceDep) -> StreamingResponse:
    _validate_id(scan_id)
    channel = await service.channel(scan_id)

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in channel.subscribe():
            if event.event == "heartbeat":
                yield b": ping\n\n"
                continue
            payload = json.dumps(event.data, default=str)
            yield f"event: {event.event}\ndata: {payload}\n\n".encode()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering so stage transitions arrive as they happen.
            "X-Accel-Buffering": "no",
        },
    )


def _validate_id(scan_id: str) -> None:
    """Reject malformed ids before they reach the store.

    Cheap, and it keeps log noise and 500s down when something crawls the API.
    """
    if not is_ulid(scan_id):
        raise ScanNotFoundError(f"'{scan_id}' is not a valid scan id.")
