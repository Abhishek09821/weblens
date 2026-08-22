"""Traffic signals analyzer.

Detects analytics/tracking tools and ad networks from observed network requests
and script URLs. These are verifiable signals about how the site measures its
own traffic — they do not estimate visit counts.
"""

from __future__ import annotations

from weblens.analyzers.base import AnalyzerContext, AnalyzerOutput, FindingBuilder
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "traffic.signals"

# Known analytics/tracking domains and their product names.
_ANALYTICS_DOMAINS: dict[str, str] = {
    "google-analytics.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "analytics.google.com": "Google Analytics",
    "connect.facebook.net": "Meta Pixel",
    "snap.licdn.com": "LinkedIn Insight Tag",
    "bat.bing.com": "Microsoft Clarity / Bing UET",
    "clarity.ms": "Microsoft Clarity",
    "cdn.segment.com": "Segment",
    "cdn.mxpnl.com": "Mixpanel",
    "js.hs-analytics.net": "HubSpot Analytics",
    "plausible.io": "Plausible Analytics",
    "cdn.usefathom.com": "Fathom Analytics",
    "static.hotjar.com": "Hotjar",
    "js.intercomcdn.com": "Intercom",
    "widget.intercom.io": "Intercom",
    "rum-static.pingdom.net": "Pingdom RUM",
    "js.sentry-cdn.com": "Sentry",
    "browser.sentry-cdn.com": "Sentry",
    "www.datadoghq-browser-agent.com": "Datadog RUM",
    "rum.browser-intake-datadoghq.com": "Datadog RUM",
    "cdn.amplitude.com": "Amplitude",
    "heapanalytics.com": "Heap",
    "t.co": "Twitter/X Analytics",
    "analytics.tiktok.com": "TikTok Pixel",
    "sc-static.net": "Snapchat Pixel",
}


class TrafficSignalsAnalyzer:
    """Detects analytics and tracking services from network evidence."""

    id = ANALYZER_ID
    section = SectionKey.TRAFFIC
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.NETWORK})
    depends_on = frozenset[str]()

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        fb = FindingBuilder(self.id)
        findings = []

        network = ctx.evidence.network
        if network is None:
            findings.append(
                fb.unable_to_verify(
                    "analytics-services",
                    category="analytics",
                    name="Analytics and tracking services",
                    reason="Network evidence was not collected.",
                )
            )
            return AnalyzerOutput(findings=findings)

        detected: list[tuple[str, str, str]] = []  # (product, domain, url)

        for request in network.requests:
            req_domain = _extract_domain(request.url)
            for analytics_domain, product in _ANALYTICS_DOMAINS.items():
                if analytics_domain in req_domain:
                    detected.append((product, analytics_domain, request.url))
                    break

        if not detected:
            findings.append(
                fb.not_detected(
                    "analytics-services",
                    category="analytics",
                    name="Analytics and tracking services",
                    reason=(
                        "No known analytics or tracking domains were observed in network requests."
                    ),
                    limitations=[
                        "Server-side analytics (e.g. log-based) cannot be detected externally.",
                        "Self-hosted analytics on the same domain are not "
                        "identified by domain matching.",
                    ],
                )
            )
        else:
            # Deduplicate by product name
            seen_products: dict[str, tuple[str, str]] = {}
            for product, domain, url in detected:
                if product not in seen_products:
                    seen_products[product] = (domain, url)

            evidence_refs = [
                EvidenceRef(
                    kind=EvidenceKind.NETWORK_REQUEST,
                    source=f"network.requests[{domain}]",
                    excerpt=url[:200],
                    location=url,
                )
                for product, (domain, url) in seen_products.items()
            ]

            findings.append(
                fb.detected(
                    "analytics-services",
                    category="analytics",
                    name="Analytics and tracking services",
                    value=len(seen_products),
                    values=sorted(seen_products.keys()),
                    confidence=Confidence.DEFINITIVE,
                    evidence=evidence_refs,
                    unit="services",
                    limitations=[
                        "Only client-side analytics loaded during a single "
                        "page visit are detected.",
                        "Server-side analytics cannot be observed from outside.",
                    ],
                )
            )

            # Individual findings per detected service
            for product, (domain, url) in seen_products.items():
                findings.append(
                    fb.detected(
                        f"analytics-{_slugify(product)}",
                        category="analytics",
                        name=product,
                        value=product,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.NETWORK_REQUEST,
                                source=f"network.requests[{domain}]",
                                excerpt=url[:200],
                                location=url,
                            )
                        ],
                    )
                )

        return AnalyzerOutput(findings=findings)


def _extract_domain(url: str) -> str:
    """Extract domain from a URL for matching."""
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _slugify(text: str) -> str:
    """Create a slug from a product name."""
    return text.lower().replace(" ", "-").replace("/", "-").replace(".", "-")[:30].rstrip("-")
