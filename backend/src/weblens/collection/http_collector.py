"""Phase 0 collector: HTTP-only evidence.

Runs the stages that do not need a browser - ``dns``, ``robots``, ``http_probe`` - and fills
the DOM slot by parsing the served HTML. Browser-dependent slots stay ``None``, which is the
signal analyzers use to answer ``unable_to_verify`` instead of guessing.

Phase 1 adds ``BrowserCollector`` alongside this one, satisfying the same ``Collector``
protocol. This class stays: it is the honest fallback when Chromium is unavailable, and it
keeps the HTTP-only sections working in that case.
"""

from __future__ import annotations

from urllib.parse import urljoin

from weblens.collection.base import CollectionOutcome, StageSink
from weblens.collection.http_probe import HttpProbe
from weblens.collection.robots import WEBLENS_AGENT_TOKEN, RobotsPolicy
from weblens.collection.static_html import parse_static_html
from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import Settings
from weblens.domain.enums import ErrorCode, StageKey
from weblens.domain.errors import RobotsDisallowedError, WebLensError
from weblens.domain.evidence import RawEvidence
from weblens.domain.observations import (
    DnsObservation,
    DomObservation,
    HttpObservation,
    RobotsObservation,
    TargetObservation,
)
from weblens.domain.scan import RedirectHop, RunContext, ScanOptions
from weblens.logging import get_logger, stage_context
from weblens.utils.timing import Stopwatch
from weblens.version import USER_AGENT

logger = get_logger(__name__)

HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})


class HttpEvidenceCollector:
    """Collector that uses HTTP requests only."""

    collection_mode = "http_only"

    def __init__(self, settings: Settings, guard: TargetGuard) -> None:
        self._settings = settings
        self._guard = guard
        self._probe = HttpProbe(settings, guard)

    async def collect(
        self,
        target: NormalizedTarget,
        options: ScanOptions,
        sink: StageSink,
    ) -> CollectionOutcome:
        target_observation = TargetObservation(
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            scheme=target.scheme,
            host=target.host,
            port=target.port,
            path=target.path,
        )

        dns = await self._dns_stage(target, sink)
        robots = await self._robots_stage(target, sink)
        http, redirect_chain = await self._http_stage(target, sink)

        dom = self._dom_from(http)

        evidence = RawEvidence(
            target=target_observation,
            dns=dns,
            robots=robots,
            http=http,
            dom=dom,
        )
        run_context = RunContext(
            user_agent=USER_AGENT,
            viewport=options.viewport,
            wait_strategy="http_response_only",
            settle_reached=None,
            collection_mode=self.collection_mode,
        )
        return CollectionOutcome(
            evidence=evidence, redirect_chain=redirect_chain, run_context=run_context
        )

    def _dom_from(self, http: HttpObservation | None) -> DomObservation | None:
        """Build a DOM inventory only when we are confident we have readable HTML.

        Returning ``None`` here is deliberate: analyzers then answer ``unable_to_verify``
        instead of describing a document we could not actually read. Parsing an undecodable or
        non-HTML body would produce an inventory full of absences, which reads exactly like a
        page that genuinely has no title, no headings, and no metadata.
        """
        if http is None or not http.body_text:
            return None
        if not _is_html(http.content_type):
            logger.info(
                "document is not HTML; DOM inventory skipped",
                extra={"content_type": http.content_type},
            )
            return None
        if not _looks_like_markup(http.body_text):
            logger.warning(
                "response body did not look like markup; DOM inventory skipped",
                extra={"content_encoding": http.header("content-encoding")},
            )
            return None
        return parse_static_html(http.body_text, base_url=http.final_url)

    # --- stages ------------------------------------------------------------------------

    async def _dns_stage(self, target: NormalizedTarget, sink: StageSink) -> DnsObservation:
        with stage_context(StageKey.DNS.value):
            await sink.stage_started(StageKey.DNS)
            # Resolution already happened in the guard during validation; recording it here
            # rather than resolving again keeps the request pattern minimal.
            observation = DnsObservation(
                host=target.host, resolved_ips=list(target.resolved_ips), resolution_ms=None
            )
            await sink.stage_completed(StageKey.DNS)
            return observation

    async def _robots_stage(self, target: NormalizedTarget, sink: StageSink) -> RobotsObservation:
        with stage_context(StageKey.ROBOTS.value):
            await sink.stage_started(StageKey.ROBOTS)
            robots_url = urljoin(f"{target.origin}/", "/robots.txt")
            fetched = await self._probe.fetch_text(robots_url)

            if fetched is None:
                await sink.stage_completed(StageKey.ROBOTS)
                return RobotsObservation(
                    url=robots_url,
                    fetched=False,
                    allowed=None,
                    error="robots.txt could not be retrieved",
                )

            status, body = fetched
            if status >= 400:
                # A missing robots.txt means no restrictions were published.
                await sink.stage_completed(StageKey.ROBOTS)
                return RobotsObservation(url=robots_url, fetched=True, status=status, allowed=True)

            policy = RobotsPolicy.parse(body)
            allowed, directive, agent_group = policy.evaluate(target.path, WEBLENS_AGENT_TOKEN)
            observation = RobotsObservation(
                url=robots_url,
                fetched=True,
                status=status,
                allowed=allowed,
                matched_directive=directive,
                user_agent_group=agent_group,
                sitemaps=policy.sitemaps[:20],
            )
            await sink.stage_completed(StageKey.ROBOTS)

            if not allowed and self._settings.respect_robots:
                raise RobotsDisallowedError(
                    f"robots.txt at {robots_url} disallows {target.path} for this agent "
                    f"({directive}). WebLens honours robots.txt."
                )
            return observation

    async def _http_stage(
        self, target: NormalizedTarget, sink: StageSink
    ) -> tuple[HttpObservation, list[RedirectHop]]:
        with stage_context(StageKey.HTTP_PROBE.value):
            await sink.stage_started(StageKey.HTTP_PROBE)
            watch = Stopwatch()
            try:
                observation, redirect_chain = await self._probe.probe(target)
            except WebLensError as exc:
                await sink.stage_failed(StageKey.HTTP_PROBE, exc.code, exc.detail or exc.title)
                raise

            upgraded, upgrade_status = await self._probe.probe_http_origin(target)
            observation = observation.model_copy(
                update={
                    "http_origin_redirects_to_https": upgraded,
                    "http_origin_redirect_status": upgrade_status,
                }
            )
            logger.info(
                "document fetched",
                extra={
                    "status": observation.status,
                    "hops": len(redirect_chain),
                    "elapsed_ms": watch.elapsed_ms(),
                },
            )
            await sink.stage_completed(StageKey.HTTP_PROBE)
            return observation, redirect_chain

    @staticmethod
    def unavailable_reason(code: ErrorCode) -> str:
        return f"HTTP-only collection failed ({code.value})."


def _is_html(content_type: str | None) -> bool:
    return content_type is not None and content_type in HTML_CONTENT_TYPES


def _looks_like_markup(body: str) -> bool:
    """Cheap sanity check that the decoded body is text containing tags.

    Guards against a body we failed to decode (wrong or unsupported content encoding) being
    parsed as if it were HTML. A real HTML document has an angle bracket well within the first
    kilobyte and does not contain NUL bytes.
    """
    head = body[:1024]
    if "\x00" in head:
        return False
    if "<" not in head:
        return False
    replacement_ratio = head.count("\ufffd") / max(len(head), 1)
    return replacement_ratio < 0.05
