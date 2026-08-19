"""HTTP probing: the document as served, before any JavaScript runs.

Redirects are followed manually rather than by httpx, for two reasons: every hop must be
re-validated by the target guard, and the header set of each hop is evidence in its own right
(HSTS on the redirect, cookies set mid-chain, the shape of the chain itself).

The response body is read as a bounded stream so an enormous document cannot exhaust memory;
when the cap is hit, ``body_truncated`` records it rather than pretending the body was short.
"""

from __future__ import annotations

from http.cookies import SimpleCookie
from urllib.parse import urljoin

import httpx

from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import NEVER_CAPTURED_HEADERS, Settings
from weblens.domain.errors import (
    ConnectFailureError,
    TargetBlockedError,
    TargetValidationError,
    TlsFailureError,
    WebLensError,
)
from weblens.domain.observations import (
    CookieAttributes,
    HeaderEntry,
    HttpHopObservation,
    HttpObservation,
)
from weblens.domain.scan import RedirectHop
from weblens.logging import get_logger
from weblens.utils.timing import Stopwatch
from weblens.utils.urls import redact_url
from weblens.version import USER_AGENT

logger = get_logger(__name__)

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
"""Note the absence of ``Accept-Encoding``.

httpx advertises exactly the encodings it can decode. Overriding the header to claim support
for something we cannot decompress makes a server return a body we then read as binary noise -
and an analyzer would faithfully report "no title found" about a page that has one. Advertising
capabilities we do not have is a way to lie to ourselves, so we let the client decide.
"""


class HttpProbe:
    def __init__(self, settings: Settings, guard: TargetGuard) -> None:
        self._settings = settings
        self._guard = guard

    async def probe(self, target: NormalizedTarget) -> tuple[HttpObservation, list[RedirectHop]]:
        """Fetch the document, following and validating each redirect hop."""
        hops: list[HttpHopObservation] = []
        redirect_chain: list[RedirectHop] = []
        cookies: list[CookieAttributes] = []
        url = target.fetch_url
        watch = Stopwatch()

        async with self._client() as client:
            for _hop_index in range(self._settings.max_redirects + 1):
                response = await self._request(client, "GET", url)
                cookies.extend(_parse_cookies(response, display_url=redact_url(url)))
                location = response.headers.get("location")

                if response.status_code in _REDIRECT_STATUSES and location:
                    hop = _hop_observation(response, url, location)
                    hops.append(hop)
                    redirect_chain.append(
                        RedirectHop(
                            url=hop.url,
                            status=hop.status,
                            location=redact_url(urljoin(url, location)),
                            scheme=httpx.URL(url).scheme,
                        )
                    )
                    await response.aclose()
                    url = urljoin(url, location)
                    await self._validate_hop(url)
                    continue

                body_text, body_bytes, truncated = await self._read_body(response)
                await response.aclose()
                hops.append(_hop_observation(response, url, None))
                observation = HttpObservation(
                    hops=hops,
                    final_url=redact_url(url),
                    status=response.status_code,
                    http_version=response.http_version,
                    headers=_capture_headers(response),
                    cookies=cookies,
                    content_type=_content_type(response),
                    charset=response.charset_encoding,
                    body_text=body_text,
                    body_bytes=body_bytes,
                    body_truncated=truncated,
                    elapsed_ms=watch.elapsed_ms(),
                )
                return observation, redirect_chain

        raise ConnectFailureError(
            f"More than {self._settings.max_redirects} redirects were followed without "
            "reaching a document."
        )

    async def probe_http_origin(self, target: NormalizedTarget) -> tuple[bool | None, int | None]:
        """One HEAD request to the ``http://`` origin to observe upgrade behaviour.

        Supports security rule TLS-02. Returns ``(None, None)`` when the probe is disabled or
        fails, which keeps that rule out of the score rather than assuming an answer.
        """
        if not self._settings.probe_http_downgrade or target.scheme != "https":
            return None, None

        url = f"http://{target.host}{target.path}"
        try:
            async with self._client() as client:
                response = await self._request(client, "HEAD", url)
                await response.aclose()
        except WebLensError:
            return None, None

        location = response.headers.get("location")
        if response.status_code not in _REDIRECT_STATUSES or not location:
            return False, response.status_code
        upgraded = httpx.URL(urljoin(url, location)).scheme == "https"
        return upgraded, response.status_code

    async def fetch_text(self, url: str, *, max_bytes: int = 64 * 1024) -> tuple[int, str] | None:
        """Fetch a small text resource (robots.txt). ``None`` when it cannot be retrieved."""
        try:
            async with self._client(follow_redirects=True) as client:
                response = await self._request(client, "GET", url)
                body = await response.aread()
                await response.aclose()
        except WebLensError:
            return None
        return response.status_code, body[:max_bytes].decode("utf-8", errors="replace")

    # --- internals ---------------------------------------------------------------------

    def _client(self, *, follow_redirects: bool = False) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=follow_redirects,
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
            headers=DEFAULT_REQUEST_HEADERS,
            http2=False,
            max_redirects=self._settings.max_redirects,
        )

    async def _request(self, client: httpx.AsyncClient, method: str, url: str) -> httpx.Response:
        request = client.build_request(method, url)
        try:
            return await client.send(request, stream=True)
        except httpx.ConnectTimeout as exc:
            raise ConnectFailureError(f"Connection to {redact_url(url)} timed out.") from exc
        except httpx.ReadTimeout as exc:
            raise ConnectFailureError(
                f"{redact_url(url)} did not send a response in time."
            ) from exc
        except httpx.ConnectError as exc:
            message = str(exc).lower()
            if "certificate" in message or "ssl" in message or "tls" in message:
                raise TlsFailureError(
                    f"TLS handshake with {redact_url(url)} failed: {exc}"
                ) from exc
            raise ConnectFailureError(f"{redact_url(url)} could not be reached: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ConnectFailureError(f"Request to {redact_url(url)} failed: {exc}") from exc

    async def _validate_hop(self, url: str) -> None:
        try:
            await self._guard.validate_hop(url)
        except (TargetBlockedError, TargetValidationError) as exc:
            raise TargetBlockedError(
                f"The redirect chain leads to a target that cannot be scanned: {exc.detail or exc}"
            ) from exc

    async def _read_body(self, response: httpx.Response) -> tuple[str | None, int, bool]:
        cap = self._settings.max_body_bytes
        chunks: list[bytes] = []
        total = 0
        truncated = False
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total >= cap:
                truncated = True
                break
        raw = b"".join(chunks)[:cap]
        encoding = response.charset_encoding or "utf-8"
        try:
            text = raw.decode(encoding, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return (text or None), total, truncated


def _hop_observation(
    response: httpx.Response, url: str, location: str | None
) -> HttpHopObservation:
    return HttpHopObservation(
        url=redact_url(url),
        status=response.status_code,
        http_version=response.http_version,
        headers=_capture_headers(response),
        location=redact_url(urljoin(url, location)) if location else None,
        elapsed_ms=_elapsed_ms(response),
    )


def _elapsed_ms(response: httpx.Response) -> float | None:
    """``httpx`` only exposes ``elapsed`` once a streamed response is closed."""
    try:
        return round(response.elapsed.total_seconds() * 1000, 2)
    except RuntimeError:
        return None


def _capture_headers(response: httpx.Response) -> list[HeaderEntry]:
    """Capture response headers, dropping the ones we never record.

    Duplicates are preserved: repeated ``Content-Security-Policy`` or ``Link`` headers carry
    meaning that collapsing them would destroy.
    """
    entries: list[HeaderEntry] = []
    for name, value in response.headers.multi_items():
        lowered = name.lower()
        if lowered in NEVER_CAPTURED_HEADERS:
            continue
        entries.append(HeaderEntry(name=lowered, value=value))
    return entries


def _content_type(response: httpx.Response) -> str | None:
    value = response.headers.get("content-type")
    return value.split(";", 1)[0].strip().lower() if value else None


def _parse_cookies(response: httpx.Response, *, display_url: str) -> list[CookieAttributes]:
    """Extract cookie *attributes*. Values are never read or stored."""
    observations: list[CookieAttributes] = []
    for header_value in response.headers.get_list("set-cookie"):
        jar = SimpleCookie()
        try:
            jar.load(header_value)
        except Exception:
            logger.debug("unparseable set-cookie header ignored")
            continue
        for name, morsel in jar.items():
            max_age: int | None = None
            if morsel["max-age"]:
                try:
                    max_age = int(morsel["max-age"])
                except ValueError:
                    max_age = None
            expires_present = bool(morsel["expires"])
            observations.append(
                CookieAttributes(
                    name=name,
                    secure=bool(morsel["secure"]),
                    http_only=bool(morsel["httponly"]),
                    same_site=(morsel["samesite"] or None),
                    domain=(morsel["domain"] or None),
                    path=(morsel["path"] or None),
                    max_age=max_age,
                    expires_present=expires_present,
                    persistent=expires_present or max_age is not None,
                    source_hop_url=display_url,
                )
            )
    return observations
