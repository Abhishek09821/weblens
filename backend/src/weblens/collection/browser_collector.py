"""Full browser-based evidence collection using Playwright.

Navigates with a real Chromium instance and collects all evidence slots:
DOM, runtime signals, computed styles, network requests, performance timing,
accessibility (axe-core), viewport metrics, console messages, and screenshots.

Bounded by configurable timeouts and caps to prevent unbounded collection.
Partial failures are recorded rather than aborting the entire scan.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any
from urllib.parse import urljoin, urlsplit

from weblens.collection.base import CollectionOutcome, StageSink
from weblens.collection.http_probe import HttpProbe
from weblens.collection.robots import WEBLENS_AGENT_TOKEN, RobotsPolicy
from weblens.collection.static_html import parse_static_html
from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import NEVER_CAPTURED_HEADERS, Settings
from weblens.domain.enums import DomSource, ErrorCode, StageKey
from weblens.domain.errors import (
    BrowserUnavailableError,
    NavigationTimeoutError,
    RobotsDisallowedError,
)
from weblens.domain.evidence import RawEvidence
from weblens.domain.observations import (
    ConsoleMessage,
    CookieAttributes,
    DnsObservation,
    DomObservation,
    HeaderEntry,
    HttpObservation,
    NetworkObservation,
    NetworkRequestRecord,
    PerformanceObservation,
    RobotsObservation,
    RuntimeObservation,
    SampleCoverage,
    ScreenshotArtifact,
    StyleObservation,
    StylePropertyDistribution,
    StyleValueCount,
    TargetObservation,
    ViewportMetrics,
)
from weblens.domain.observations.measurement import AxeObservation, LongTaskEntry
from weblens.domain.scan import RedirectHop, RunContext, ScanOptions
from weblens.logging import get_logger, stage_context
from weblens.utils.urls import host_of, redact_url, registrable_suffix_match
from weblens.version import USER_AGENT

logger = get_logger(__name__)

HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})


class BrowserEvidenceCollector:
    """Full Playwright-based collector satisfying the Collector protocol."""

    collection_mode = "browser"

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

        # Pre-browser stages (DNS, robots) use HTTP probe
        dns = await self._dns_stage(target, sink)
        robots = await self._robots_stage(target, sink)

        # Browser-based collection
        browser_result = await self._browser_stages(target, options, sink)

        evidence = RawEvidence(
            target=target_observation,
            dns=dns,
            robots=robots,
            http=browser_result.get("http"),
            dom=browser_result.get("dom"),
            runtime=browser_result.get("runtime"),
            styles=browser_result.get("styles"),
            network=browser_result.get("network"),
            performance=browser_result.get("performance"),
            accessibility=browser_result.get("accessibility"),
            viewports=browser_result.get("viewports"),
            console=browser_result.get("console"),
            screenshots=browser_result.get("screenshots"),
        )

        run_context = RunContext(
            browser_name="chromium",
            browser_version=browser_result.get("browser_version"),
            user_agent=USER_AGENT,
            viewport=options.viewport,
            wait_strategy=f"domcontentloaded+network_settle({self._settings.settle_timeout_ms}ms)",
            settle_reached=browser_result.get("settle_reached", True),
            collection_mode=self.collection_mode,
        )
        return CollectionOutcome(
            evidence=evidence,
            redirect_chain=browser_result.get("redirect_chain", []),
            run_context=run_context,
        )

    async def _browser_stages(
        self,
        target: NormalizedTarget,
        options: ScanOptions,
        sink: StageSink,
    ) -> dict[str, Any]:
        """Run all browser-based collection stages."""
        result: dict[str, Any] = {}
        network_requests: list[dict[str, Any]] = []
        console_messages: list[ConsoleMessage] = []
        redirect_chain: list[RedirectHop] = []
        cookies_observed: list[CookieAttributes] = []

        try:
            from playwright.async_api import Response, async_playwright
        except ImportError as exc:
            await sink.stage_failed(
                StageKey.BROWSER_LAUNCH, ErrorCode.BROWSER_UNAVAILABLE, str(exc)
            )
            raise BrowserUnavailableError(
                "Playwright is not installed. Run: pip install playwright && "
                "python -m playwright install chromium"
            ) from exc

        # BROWSER LAUNCH
        with stage_context(StageKey.BROWSER_LAUNCH.value):
            await sink.stage_started(StageKey.BROWSER_LAUNCH)
            try:
                pw_manager = async_playwright()
                pw = await pw_manager.start()
                browser = await pw.chromium.launch(headless=True)
                result["browser_version"] = browser.version
            except Exception as exc:
                await sink.stage_failed(
                    StageKey.BROWSER_LAUNCH, ErrorCode.BROWSER_UNAVAILABLE, str(exc)[:200]
                )
                raise BrowserUnavailableError(f"Failed to launch Chromium: {exc}") from exc
            await sink.stage_completed(StageKey.BROWSER_LAUNCH)

        try:
            context = await browser.new_context(
                viewport={
                    "width": options.viewport.width,
                    "height": options.viewport.height,
                },
                user_agent=USER_AGENT,
                locale="en-US",
                timezone_id="UTC",
                ignore_https_errors=False,
            )
            page = await context.new_page()

            # Set up network observation
            request_cap = self._settings.max_network_requests_recorded
            cap_hit = False

            def _on_response(response: Response) -> None:
                nonlocal cap_hit
                if len(network_requests) >= request_cap:
                    cap_hit = True
                    return
                req = response.request
                req_host = host_of(req.url)
                is_same = (
                    registrable_suffix_match(req_host or "", target.host) if req_host else None
                )
                network_requests.append(
                    {
                        "url": redact_url(req.url),
                        "method": req.method,
                        "resource_type": req.resource_type,
                        "status": response.status,
                        "mime_type": response.headers.get("content-type", "").split(";")[0].strip(),
                        "host": req_host,
                        "is_same_origin": (host_of(req.url) == target.host) if req_host else None,
                        "is_same_site": is_same,
                        "headers": dict(response.headers),
                    }
                )

            def _on_request_failed(request: Any) -> None:
                nonlocal cap_hit
                if len(network_requests) >= request_cap:
                    cap_hit = True
                    return
                network_requests.append(
                    {
                        "url": redact_url(request.url),
                        "method": request.method,
                        "resource_type": request.resource_type,
                        "status": None,
                        "failed": True,
                        "failure_text": request.failure,
                        "host": host_of(request.url),
                    }
                )

            page.on("response", _on_response)
            page.on("requestfailed", _on_request_failed)

            # Console messages
            def _on_console(msg: Any) -> None:
                if len(console_messages) < 100:
                    console_messages.append(
                        ConsoleMessage(
                            level=msg.type,
                            text=msg.text[:500],
                            location=str(msg.location) if hasattr(msg, "location") else None,
                        )
                    )

            page.on("console", _on_console)

            # NAVIGATE
            with stage_context(StageKey.NAVIGATE.value):
                await sink.stage_started(StageKey.NAVIGATE)
                settle_reached = True
                try:
                    response = await page.goto(
                        target.fetch_url,
                        wait_until="domcontentloaded",
                        timeout=self._settings.navigation_timeout_ms,
                    )
                except Exception as exc:
                    await sink.stage_failed(
                        StageKey.NAVIGATE, ErrorCode.NAVIGATION_TIMEOUT, str(exc)[:200]
                    )
                    raise NavigationTimeoutError(
                        f"Navigation to {target.display_url} failed: {exc}"
                    ) from exc

                # Bounded settle: wait for network idle with timeout
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=self._settings.settle_timeout_ms,
                    )
                except Exception:
                    settle_reached = False
                    logger.info("network idle not reached within settle timeout")

                result["settle_reached"] = settle_reached
                await sink.stage_completed(StageKey.NAVIGATE)

            # Build HTTP observation from navigation response
            final_url = page.url
            if response is not None:
                http_obs = self._build_http_observation(
                    response, final_url, redirect_chain, cookies_observed
                )
                # Parse cookies from browser context (more reliable than header parsing)
                try:
                    browser_cookies = await context.cookies()
                    for cookie in browser_cookies:
                        cookies_observed.append(CookieAttributes(
                            name=cookie.get("name", ""),
                            secure=cookie.get("secure", False),
                            http_only=cookie.get("httpOnly", False),
                            same_site=cookie.get("sameSite", None),
                            domain=cookie.get("domain", None),
                            path=cookie.get("path", None),
                            expires_present=cookie.get("expires", -1) > 0,
                            persistent=cookie.get("expires", -1) > 0,
                            source_hop_url=redact_url(final_url),
                        ))
                except Exception:
                    logger.debug("cookie extraction from context failed")
                http_obs = http_obs.model_copy(update={"cookies": cookies_observed})
                result["http"] = http_obs
                # Build redirect chain from response chain
                redirected = response.request.redirected_from
                while redirected is not None:
                    resp_for_redirect = await redirected.response()
                    if resp_for_redirect:
                        redirect_chain.append(
                            RedirectHop(
                                url=redact_url(redirected.url),
                                status=resp_for_redirect.status,
                                location=redact_url(final_url),
                                scheme=urlsplit(redirected.url).scheme,
                            )
                        )
                    redirected = redirected.redirected_from
                redirect_chain.reverse()
                result["redirect_chain"] = redirect_chain

            # DOM CAPTURE
            with stage_context(StageKey.DOM_CAPTURE.value):
                await sink.stage_started(StageKey.DOM_CAPTURE)
                try:
                    dom = await self._capture_dom(page, final_url)
                    result["dom"] = dom
                    await sink.stage_completed(StageKey.DOM_CAPTURE)
                except Exception as exc:
                    logger.warning("DOM capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.DOM_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # RUNTIME CAPTURE
            with stage_context(StageKey.RUNTIME_CAPTURE.value):
                await sink.stage_started(StageKey.RUNTIME_CAPTURE)
                try:
                    runtime = await self._capture_runtime(page)
                    result["runtime"] = runtime
                    await sink.stage_completed(StageKey.RUNTIME_CAPTURE)
                except Exception as exc:
                    logger.warning("Runtime capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.RUNTIME_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # STYLE CAPTURE
            with stage_context(StageKey.STYLE_CAPTURE.value):
                await sink.stage_started(StageKey.STYLE_CAPTURE)
                try:
                    styles = await self._capture_styles(page)
                    result["styles"] = styles
                    await sink.stage_completed(StageKey.STYLE_CAPTURE)
                except Exception as exc:
                    logger.warning("Style capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.STYLE_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # PERFORMANCE CAPTURE
            with stage_context(StageKey.PERF_CAPTURE.value):
                await sink.stage_started(StageKey.PERF_CAPTURE)
                try:
                    perf = await self._capture_performance(page)
                    result["performance"] = perf
                    await sink.stage_completed(StageKey.PERF_CAPTURE)
                except Exception as exc:
                    logger.warning("Performance capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.PERF_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # NETWORK CAPTURE (finalize observed requests)
            with stage_context(StageKey.NETWORK_CAPTURE.value):
                await sink.stage_started(StageKey.NETWORK_CAPTURE)
                try:
                    network_obs = self._build_network_observation(network_requests, cap_hit)
                    result["network"] = network_obs
                    await sink.stage_completed(StageKey.NETWORK_CAPTURE)
                except Exception as exc:
                    logger.warning("Network capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.NETWORK_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # ACCESSIBILITY CAPTURE
            with stage_context(StageKey.A11Y_CAPTURE.value):
                await sink.stage_started(StageKey.A11Y_CAPTURE)
                try:
                    a11y = await self._capture_accessibility(page)
                    result["accessibility"] = a11y
                    await sink.stage_completed(StageKey.A11Y_CAPTURE)
                except Exception as exc:
                    logger.warning("Accessibility capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.A11Y_CAPTURE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # RESPONSIVE PROBE
            with stage_context(StageKey.RESPONSIVE_PROBE.value):
                await sink.stage_started(StageKey.RESPONSIVE_PROBE)
                try:
                    viewports = await self._capture_viewports(page, options)
                    result["viewports"] = viewports
                    await sink.stage_completed(StageKey.RESPONSIVE_PROBE)
                except Exception as exc:
                    logger.warning("Responsive probe failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.RESPONSIVE_PROBE, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # SCREENSHOT
            with stage_context(StageKey.SCREENSHOT.value):
                await sink.stage_started(StageKey.SCREENSHOT)
                try:
                    screenshots = await self._capture_screenshots(page, options)
                    result["screenshots"] = screenshots
                    await sink.stage_completed(StageKey.SCREENSHOT)
                except Exception as exc:
                    logger.warning("Screenshot capture failed", extra={"error": str(exc)[:200]})
                    await sink.stage_failed(
                        StageKey.SCREENSHOT, ErrorCode.INTERNAL_ERROR, str(exc)[:200]
                    )

            # Console messages
            result["console"] = console_messages if console_messages else []

        finally:
            try:
                await context.close()
                await browser.close()
                await pw.stop()
            except Exception:
                logger.debug("browser cleanup error (non-fatal)")

        return result

    # --- Pre-browser stages ---

    async def _dns_stage(self, target: NormalizedTarget, sink: StageSink) -> DnsObservation:
        with stage_context(StageKey.DNS.value):
            await sink.stage_started(StageKey.DNS)
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

    # --- Browser stage helpers ---

    def _build_http_observation(
        self,
        response: Any,
        final_url: str,
        redirect_chain: list[RedirectHop],
        cookies: list[CookieAttributes],
    ) -> HttpObservation:
        """Build HTTP observation from Playwright navigation response."""
        headers = []
        for name, value in response.headers.items():
            lowered = name.lower()
            if lowered in NEVER_CAPTURED_HEADERS:
                continue
            headers.append(HeaderEntry(name=lowered, value=value))

        content_type = response.headers.get("content-type", "")
        ct_value = content_type.split(";")[0].strip().lower() if content_type else None

        return HttpObservation(
            hops=[],
            final_url=redact_url(final_url),
            status=response.status,
            headers=headers,
            cookies=cookies,
            content_type=ct_value,
            charset="utf-8",
            body_text=None,
            body_bytes=None,
            elapsed_ms=None,
        )

    async def _capture_dom(self, page: Any, final_url: str) -> DomObservation:
        """Capture DOM from the rendered page."""
        html_content = await page.content()
        # Parse with our static HTML parser but mark as rendered DOM
        dom = parse_static_html(html_content, base_url=final_url)
        # Override source since this came from rendered page
        dom = dom.model_copy(update={"source": DomSource.RENDERED_DOM})
        return dom

    async def _capture_runtime(self, page: Any) -> RuntimeObservation:
        """Capture JavaScript runtime signals via page.evaluate."""
        runtime_data = await page.evaluate("""() => {
            const globals = [];
            const knownGlobals = [
                'React', '__REACT_DEVTOOLS_GLOBAL_HOOK__', '__NEXT_DATA__',
                'next', '__nuxt', '__VUE__', 'Vue', '__vue_app__',
                'angular', 'ng', '__SVELTE_HMR_ADAPTER__',
                'Ember', 'jQuery', '$', '_', 'Backbone',
                'gsap', 'THREE', 'PIXI', 'Phaser',
                '__GATSBY', '__remixContext', '__REDUX_DEVTOOLS_EXTENSION__',
                'webpackChunk', '__webpack_modules__', '__webpack_require__',
                'Turbo', 'Stimulus',
                'ga', 'gtag', 'dataLayer', '_gaq', 'fbq', 'twq',
                'Shopify', 'woocommerce_params',
                '__PRELOADED_STATE__', '__INITIAL_STATE__',
                '__APP_INITIAL_STATE__', 'window.__DATA__',
            ];
            for (const name of knownGlobals) {
                try {
                    if (eval('typeof ' + name) !== 'undefined') {
                        globals.push(name);
                    }
                } catch(e) {}
            }

            let sw = null;
            try { sw = !!navigator.serviceWorker?.controller; } catch(e) {}

            const scripts = document.querySelectorAll('script');
            let moduleCount = 0, classicCount = 0;
            scripts.forEach(s => {
                if (s.type === 'module') moduleCount++;
                else classicCount++;
            });

            const storageKeys = [];
            try {
                for (let i = 0; i < Math.min(localStorage.length, 50); i++) {
                    storageKeys.push(localStorage.key(i));
                }
            } catch(e) {}

            let wasm = false;
            try {
                const entries = performance.getEntriesByType('resource');
                wasm = entries.some(e => e.name.endsWith('.wasm'));
            } catch(e) {}

            // Hydration payload detection
            const hydrationKeys = [];
            const hydrationIds = [
                '__NEXT_DATA__', '__NUXT__', '__INITIAL_STATE__',
                '__PRELOADED_STATE__', '__remixContext', '__APOLLO_STATE__',
            ];
            for (const id of hydrationIds) {
                try {
                    if (eval('typeof ' + id) !== 'undefined') {
                        hydrationKeys.push(id);
                    }
                } catch(e) {}
            }

            return {
                globals, sw, moduleCount, classicCount,
                storageKeys, wasm, hydrationKeys
            };
        }""")

        return RuntimeObservation(
            globals_present=runtime_data.get("globals", []),
            service_worker_registered=runtime_data.get("sw"),
            module_script_count=runtime_data.get("moduleCount"),
            classic_script_count=runtime_data.get("classicCount"),
            storage_keys=runtime_data.get("storageKeys", [])[:50],
            wasm_requested=runtime_data.get("wasm"),
            hydration_payload_keys=runtime_data.get("hydrationKeys", []),
        )

    async def _capture_styles(self, page: Any) -> StyleObservation:
        """Capture computed styles from sampled elements."""
        cap = self._settings.max_style_samples
        style_data = await page.evaluate(f"""() => {{
            const cap = {cap};
            const elements = document.querySelectorAll('*');
            const total = elements.length;
            const sampled = Math.min(total, cap);

            const props = [
                'color', 'background-color', 'font-family', 'font-size',
                'font-weight', 'line-height', 'border-radius',
                'box-shadow', 'padding-top', 'padding-right',
                'padding-bottom', 'padding-left', 'margin-top',
                'margin-right', 'margin-bottom', 'margin-left',
                'display', 'position', 'gap', 'transition', 'animation',
            ];

            const distributions = {{}};
            for (const p of props) distributions[p] = {{}};

            for (let i = 0; i < sampled; i++) {{
                const el = elements[i];
                try {{
                    const cs = getComputedStyle(el);
                    for (const p of props) {{
                        const v = cs.getPropertyValue(p);
                        if (v && v !== 'none' && v !== 'normal' && v !== '0px'
                            && v !== 'auto' && v !== 'static' && v !== 'block') {{
                            distributions[p][v] = (distributions[p][v] || 0) + 1;
                        }}
                    }}
                }} catch(e) {{}}
            }}

            // Loaded fonts
            const fonts = [];
            try {{
                document.fonts.forEach(f => {{
                    if (f.status === 'loaded') fonts.push(f.family);
                }});
            }} catch(e) {{}}

            // CSS custom properties from :root
            const customProps = [];
            try {{
                const rootStyles = getComputedStyle(document.documentElement);
                const sheets = document.styleSheets;
                for (let s = 0; s < sheets.length; s++) {{
                    try {{
                        const rules = sheets[s].cssRules;
                        for (let r = 0; r < rules.length; r++) {{
                            if (rules[r].selectorText === ':root') {{
                                const style = rules[r].style;
                                for (let j = 0; j < style.length; j++) {{
                                    if (style[j].startsWith('--')) customProps.push(style[j]);
                                }}
                            }}
                        }}
                    }} catch(e) {{}}
                }}
            }} catch(e) {{}}

            // Media queries / breakpoints
            const breakpoints = [];
            try {{
                for (let s = 0; s < document.styleSheets.length; s++) {{
                    try {{
                        const rules = document.styleSheets[s].cssRules;
                        for (let r = 0; r < rules.length; r++) {{
                            if (rules[r] instanceof CSSMediaRule) {{
                                const mq = rules[r].conditionText || rules[r].media?.mediaText;
                                if (mq && !breakpoints.includes(mq)) breakpoints.push(mq);
                            }}
                        }}
                    }} catch(e) {{}}
                }}
            }} catch(e) {{}}

            // Keyframes count
            let keyframes = 0;
            try {{
                for (let s = 0; s < document.styleSheets.length; s++) {{
                    try {{
                        const rules = document.styleSheets[s].cssRules;
                        for (let r = 0; r < rules.length; r++) {{
                            if (rules[r] instanceof CSSKeyframesRule) keyframes++;
                        }}
                    }} catch(e) {{}}
                }}
            }} catch(e) {{}}

            return {{
                total, sampled, capHit: sampled >= cap,
                distributions, fonts: [...new Set(fonts)],
                customProps: customProps.slice(0, 100),
                breakpoints: breakpoints.slice(0, 50),
                keyframes
            }};
        }}""")

        distributions = []
        for prop, value_counts in style_data.get("distributions", {}).items():
            values = sorted(
                [StyleValueCount(value=v, count=c) for v, c in value_counts.items()],
                key=lambda x: x.count,
                reverse=True,
            )[:30]  # Top 30 per property
            if values:
                distributions.append(StylePropertyDistribution(property=prop, values=values))

        return StyleObservation(
            coverage=SampleCoverage(
                elements_sampled=style_data.get("sampled", 0),
                elements_total=style_data.get("total"),
                cap_hit=style_data.get("capHit", False),
            ),
            distributions=distributions,
            loaded_fonts=style_data.get("fonts", []),
            css_custom_properties=style_data.get("customProps", []),
            media_query_breakpoints=style_data.get("breakpoints", []),
            keyframe_count=style_data.get("keyframes"),
        )

    async def _capture_performance(self, page: Any) -> PerformanceObservation:
        """Capture performance timing from the browser."""
        perf_data = await page.evaluate("""() => {
            const nav = performance.getEntriesByType('navigation')[0];
            const paint = performance.getEntriesByType('paint');
            const fcp = paint.find(e => e.name === 'first-contentful-paint');

            // LCP via PerformanceObserver entries
            let lcp = null;
            let lcpElement = null;
            try {
                const entries = performance.getEntriesByType('largest-contentful-paint');
                if (entries.length > 0) {
                    const last = entries[entries.length - 1];
                    lcp = last.startTime;
                    lcpElement = last.element?.tagName || null;
                }
            } catch(e) {}

            // CLS
            let cls = 0;
            try {
                const entries = performance.getEntriesByType('layout-shift');
                for (const entry of entries) {
                    if (!entry.hadRecentInput) cls += entry.value;
                }
            } catch(e) {}

            // Long tasks
            const longTasks = [];
            try {
                const entries = performance.getEntriesByType('longtask');
                for (const entry of entries) {
                    longTasks.push({start: entry.startTime, duration: entry.duration});
                }
            } catch(e) {}

            // Resource totals
            const resources = performance.getEntriesByType('resource');
            let transferTotal = 0, decodedTotal = 0, renderBlocking = 0;
            for (const r of resources) {
                transferTotal += r.transferSize || 0;
                decodedTotal += r.decodedBodySize || 0;
                if (r.renderBlockingStatus === 'blocking') renderBlocking++;
            }

            return {
                ttfb: nav ? nav.responseStart - nav.requestStart : null,
                dcl: nav ? nav.domContentLoadedEventEnd - nav.startTime : null,
                domInteractive: nav ? nav.domInteractive - nav.startTime : null,
                loadEvent: nav ? nav.loadEventEnd - nav.startTime : null,
                fcp: fcp ? fcp.startTime : null,
                lcp, lcpElement,
                cls: cls || null,
                longTasks,
                transferTotal, decodedTotal,
                requestCount: resources.length,
                renderBlocking
            };
        }""")

        long_tasks = [
            LongTaskEntry(start_ms=lt["start"], duration_ms=lt["duration"])
            for lt in perf_data.get("longTasks", [])
        ]
        tbt = sum(max(0, lt.duration_ms - 50) for lt in long_tasks)

        return PerformanceObservation(
            ttfb_ms=perf_data.get("ttfb"),
            dom_content_loaded_ms=perf_data.get("dcl"),
            dom_interactive_ms=perf_data.get("domInteractive"),
            load_event_ms=perf_data.get("loadEvent"),
            first_contentful_paint_ms=perf_data.get("fcp"),
            largest_contentful_paint_ms=perf_data.get("lcp"),
            largest_contentful_paint_element=perf_data.get("lcpElement"),
            cumulative_layout_shift=perf_data.get("cls"),
            long_tasks=long_tasks,
            total_blocking_estimate_ms=tbt if long_tasks else None,
            transfer_bytes_total=perf_data.get("transferTotal"),
            decoded_bytes_total=perf_data.get("decodedTotal"),
            request_count=perf_data.get("requestCount"),
            render_blocking_request_count=perf_data.get("renderBlocking"),
        )

    def _build_network_observation(
        self, requests: list[dict[str, Any]], cap_hit: bool
    ) -> NetworkObservation:
        """Build network observation from collected requests."""
        records = []
        for req in requests:
            headers_list = []
            raw_headers = req.get("headers", {})
            if isinstance(raw_headers, dict):
                for name, value in raw_headers.items():
                    lowered = name.lower()
                    if lowered in NEVER_CAPTURED_HEADERS:
                        continue
                    headers_list.append(HeaderEntry(name=lowered, value=str(value)))

            records.append(
                NetworkRequestRecord(
                    url=req["url"],
                    method=req.get("method", "GET"),
                    resource_type=req.get("resource_type", "other"),
                    status=req.get("status"),
                    mime_type=req.get("mime_type"),
                    host=req.get("host"),
                    is_same_origin=req.get("is_same_origin"),
                    is_same_site=req.get("is_same_site"),
                    selected_headers=headers_list,
                    failed=req.get("failed", False),
                    failure_text=req.get("failure_text"),
                )
            )
        return NetworkObservation(requests=records, cap_hit=cap_hit)

    async def _capture_accessibility(self, page: Any) -> AxeObservation:
        """Run axe-core for accessibility analysis."""
        # Inject axe-core via CDN and run
        try:
            await page.evaluate("""() => {
                return new Promise((resolve, reject) => {
                    if (window.axe) { resolve(); return; }
                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js';
                    script.onload = resolve;
                    script.onerror = reject;
                    document.head.appendChild(script);
                });
            }""")

            results = await page.evaluate("""() => {
                return axe.run(document, {
                    runOnly: ['wcag2a', 'wcag2aa', 'best-practice'],
                    resultTypes: ['violations', 'passes', 'incomplete', 'inapplicable']
                });
            }""")
        except Exception as exc:
            return AxeObservation(
                engine_version="4.9.1",
                error=f"axe-core execution failed: {str(exc)[:200]}",
            )

        from weblens.domain.observations.measurement import AxeNode, AxeViolation

        violations = []
        for v in results.get("violations", []):
            nodes = []
            for node in v.get("nodes", [])[:5]:  # Sample up to 5 nodes
                target = node.get("target", [])
                nodes.append(
                    AxeNode(
                        target=target[:3] if target else [],
                        html_excerpt=(node.get("html", ""))[:200],
                        failure_summary=node.get("failureSummary", "")[:300],
                    )
                )
            violations.append(
                AxeViolation(
                    rule_id=v["id"],
                    impact=v.get("impact"),
                    description=v.get("description", ""),
                    help_text=v.get("help", ""),
                    help_url=v.get("helpUrl"),
                    tags=v.get("tags", []),
                    node_count=len(v.get("nodes", [])),
                    sample_nodes=nodes,
                )
            )

        return AxeObservation(
            engine_version="4.9.1",
            violations=violations,
            passes_count=len(results.get("passes", [])),
            incomplete_count=len(results.get("incomplete", [])),
            inapplicable_count=len(results.get("inapplicable", [])),
            rules_run_count=(
                len(results.get("violations", []))
                + len(results.get("passes", []))
                + len(results.get("incomplete", []))
                + len(results.get("inapplicable", []))
            ),
        )

    async def _capture_viewports(self, page: Any, options: ScanOptions) -> list[ViewportMetrics]:
        """Capture viewport metrics at different widths."""
        viewports = []
        for width in options.responsive_widths:
            await page.set_viewport_size({"width": width, "height": options.viewport.height})
            await asyncio.sleep(0.3)  # Allow reflow

            metrics = await page.evaluate("""() => {
                return {
                    scrollWidth: document.documentElement.scrollWidth,
                    bodyFontSize: parseFloat(getComputedStyle(document.body).fontSize),
                };
            }""")

            viewports.append(
                ViewportMetrics(
                    width=width,
                    height=options.viewport.height,
                    document_scroll_width=metrics.get("scrollWidth"),
                    has_horizontal_overflow=(metrics.get("scrollWidth", width) > width),
                    body_font_size_px=metrics.get("bodyFontSize"),
                )
            )

        # Restore original viewport
        await page.set_viewport_size(
            {
                "width": options.viewport.width,
                "height": options.viewport.height,
            }
        )
        return viewports

    async def _capture_screenshots(
        self, page: Any, options: ScanOptions
    ) -> list[ScreenshotArtifact]:
        """Capture viewport and optionally full-page screenshots."""
        screenshots = []

        if options.include_screenshot:
            data = await page.screenshot(type="png")
            screenshots.append(
                ScreenshotArtifact(
                    label="viewport",
                    width=options.viewport.width,
                    height=options.viewport.height,
                    data_base64=base64.b64encode(data).decode("ascii"),
                )
            )

        if options.include_full_page_screenshot:
            data = await page.screenshot(type="png", full_page=True)
            # Get actual dimensions
            dims = await page.evaluate("""() => ({
                w: document.documentElement.scrollWidth,
                h: document.documentElement.scrollHeight
            })""")
            screenshots.append(
                ScreenshotArtifact(
                    label="full_page",
                    width=dims.get("w", options.viewport.width),
                    height=dims.get("h", options.viewport.height),
                    data_base64=base64.b64encode(data).decode("ascii"),
                )
            )

        return screenshots
