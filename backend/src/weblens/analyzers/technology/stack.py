"""Technology stack detection from headers, scripts, network requests, and runtime globals.

Detects: analytics services, CDN/hosting platforms, third-party services, libraries loaded
via CDN, build tools, and other observable technologies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    header_evidence,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import DetectedProduct, TechnologyPayload

ANALYZER_ID = "technology.stack"


@dataclass(frozen=True)
class _TechSignature:
    name: str
    categories: list[str]
    # Each check returns (matched: bool, signal: str, version: str | None)
    header_patterns: list[tuple[str, re.Pattern[str]]] | None = None
    script_patterns: list[re.Pattern[str]] | None = None
    global_names: list[str] | None = None
    network_patterns: list[re.Pattern[str]] | None = None
    meta_generators: list[str] | None = None


# Signature database - deterministic patterns only
SIGNATURES: list[_TechSignature] = [
    # Analytics
    _TechSignature(
        "Google Analytics",
        ["analytics"],
        script_patterns=[re.compile(r"google-analytics\.com/analytics\.js")],
        global_names=["ga", "gtag", "dataLayer"],
        network_patterns=[re.compile(r"google-analytics\.com|googletagmanager\.com")],
    ),
    _TechSignature(
        "Google Tag Manager",
        ["analytics", "tag-manager"],
        script_patterns=[re.compile(r"googletagmanager\.com/gtm\.js")],
        global_names=["dataLayer"],
        network_patterns=[re.compile(r"googletagmanager\.com")],
    ),
    _TechSignature(
        "Facebook Pixel",
        ["analytics"],
        script_patterns=[re.compile(r"connect\.facebook\.net/.*fbevents\.js")],
        global_names=["fbq"],
    ),
    # CDN / Hosting
    _TechSignature(
        "Cloudflare",
        ["cdn", "hosting"],
        header_patterns=[("server", re.compile(r"cloudflare", re.IGNORECASE))],
        network_patterns=[re.compile(r"cdnjs\.cloudflare\.com")],
    ),
    _TechSignature(
        "Vercel",
        ["hosting", "platform"],
        header_patterns=[
            ("server", re.compile(r"vercel", re.IGNORECASE)),
            ("x-vercel-id", re.compile(r".+")),
        ],
    ),
    _TechSignature(
        "Netlify",
        ["hosting", "platform"],
        header_patterns=[
            ("server", re.compile(r"netlify", re.IGNORECASE)),
            ("x-nf-request-id", re.compile(r".+")),
        ],
    ),
    _TechSignature(
        "AWS CloudFront",
        ["cdn"],
        header_patterns=[
            ("x-amz-cf-id", re.compile(r".+")),
            ("via", re.compile(r"cloudfront", re.IGNORECASE)),
            ("server", re.compile(r"CloudFront", re.IGNORECASE)),
        ],
    ),
    _TechSignature(
        "Fastly",
        ["cdn"],
        header_patterns=[
            ("x-served-by", re.compile(r"cache-")),
            ("via", re.compile(r"varnish", re.IGNORECASE)),
        ],
    ),
    _TechSignature(
        "GitHub Pages",
        ["hosting"],
        header_patterns=[("server", re.compile(r"GitHub\.com", re.IGNORECASE))],
    ),
    # Libraries / Services
    _TechSignature(
        "jQuery",
        ["javascript-library"],
        script_patterns=[re.compile(r"jquery[.-](\d[\d.]*)")],
        global_names=["jQuery", "$"],
    ),
    _TechSignature(
        "Lodash",
        ["javascript-library"],
        script_patterns=[re.compile(r"lodash")],
        global_names=["_"],
    ),
    _TechSignature(
        "GSAP",
        ["animation-library"],
        script_patterns=[re.compile(r"gsap")],
        global_names=["gsap"],
    ),
    _TechSignature(
        "Three.js",
        ["3d-library"],
        script_patterns=[re.compile(r"three(\.min)?\.js")],
        global_names=["THREE"],
    ),
    # E-commerce
    _TechSignature(
        "Shopify",
        ["e-commerce", "platform"],
        global_names=["Shopify"],
        script_patterns=[re.compile(r"cdn\.shopify\.com")],
        network_patterns=[re.compile(r"cdn\.shopify\.com")],
    ),
    _TechSignature(
        "WooCommerce",
        ["e-commerce"],
        global_names=["woocommerce_params"],
        script_patterns=[re.compile(r"woocommerce|wc-")],
    ),
    # CMS
    _TechSignature(
        "WordPress",
        ["cms"],
        script_patterns=[re.compile(r"wp-content|wp-includes")],
        network_patterns=[re.compile(r"wp-content|wp-includes|wp-json")],
        meta_generators=["wordpress"],
    ),
    _TechSignature(
        "Drupal",
        ["cms"],
        header_patterns=[
            ("x-drupal-cache", re.compile(r".+")),
            ("x-generator", re.compile(r"drupal", re.IGNORECASE)),
        ],
        script_patterns=[re.compile(r"drupal\.js|drupal\.settings")],
        meta_generators=["drupal"],
    ),
    # Build tools (observable via output patterns)
    _TechSignature(
        "Webpack",
        ["build-tool"],
        global_names=["webpackChunk", "__webpack_modules__", "__webpack_require__"],
        script_patterns=[re.compile(r"webpackChunk|__webpack_require__")],
    ),
    _TechSignature(
        "Vite",
        ["build-tool"],
        script_patterns=[re.compile(r"/@vite/|__vite_")],
        network_patterns=[re.compile(r"/@vite/")],
    ),
    # Fonts
    _TechSignature(
        "Google Fonts",
        ["font-service"],
        network_patterns=[re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com")],
    ),
    _TechSignature(
        "Adobe Fonts",
        ["font-service"],
        network_patterns=[re.compile(r"use\.typekit\.net")],
        script_patterns=[re.compile(r"use\.typekit\.net")],
    ),
]


class TechStackAnalyzer:
    """Detects technologies from headers, script URLs, runtime globals, and network requests."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset(
        {EvidenceSlot.HTTP, EvidenceSlot.DOM, EvidenceSlot.RUNTIME, EvidenceSlot.NETWORK}
    )
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        findings = []
        products: list[DetectedProduct] = []

        http = ctx.evidence.http
        dom = ctx.evidence.dom
        runtime = ctx.evidence.runtime
        network = ctx.evidence.network

        for sig in SIGNATURES:
            signals: list[str] = []
            evidence_refs: list[EvidenceRef] = []
            version: str | None = None

            # Check headers
            if sig.header_patterns and http:
                for header_name, pattern in sig.header_patterns:
                    header_val = http.header(header_name)
                    if header_val and pattern.search(header_val):
                        signals.append(f"Header '{header_name}': {header_val[:80]}")
                        evidence_refs.append(header_evidence(header_name, header_val))

            # Check script URLs
            if sig.script_patterns and dom:
                for script in dom.scripts:
                    if script.src:
                        for pattern in sig.script_patterns:
                            m = pattern.search(script.src)
                            if m:
                                signals.append(f"Script URL: {script.src[:100]}")
                                evidence_refs.append(
                                    EvidenceRef(
                                        kind=EvidenceKind.SCRIPT_URL,
                                        source=f"dom.scripts[src~={pattern.pattern[:40]}]",
                                        excerpt=script.src[:200],
                                    )
                                )
                                if m.groups():
                                    version = m.group(1)
                                break

            # Check runtime globals
            if sig.global_names and runtime:
                for gname in sig.global_names:
                    if gname in runtime.globals_present:
                        signals.append(f"Global: window.{gname}")
                        evidence_refs.append(
                            EvidenceRef(
                                kind=EvidenceKind.RUNTIME_GLOBAL,
                                source=f"runtime.globals_present[{gname}]",
                                excerpt=gname,
                            )
                        )

            # Check network patterns
            if sig.network_patterns and network:
                for req in network.requests[:200]:
                    for pattern in sig.network_patterns:
                        if pattern.search(req.url):
                            signals.append(f"Network request: {req.url[:100]}")
                            evidence_refs.append(
                                EvidenceRef(
                                    kind=EvidenceKind.NETWORK_REQUEST,
                                    source=f"network.requests[url~={pattern.pattern[:40]}]",
                                    excerpt=req.url[:200],
                                )
                            )
                            break
                    if len(signals) > 5:
                        break

            # Check meta generator
            if sig.meta_generators and dom:
                for meta in dom.meta_tags:
                    if meta.name == "generator" and meta.content:
                        for gen_pattern in sig.meta_generators:
                            if gen_pattern.lower() in meta.content.lower():
                                signals.append(f"Meta generator: {meta.content}")
                                evidence_refs.append(
                                    EvidenceRef(
                                        kind=EvidenceKind.META_TAG,
                                        source="dom.meta_tags[name=generator]",
                                        excerpt=meta.content,
                                    )
                                )

            if signals:
                confidence = Confidence.DEFINITIVE if len(signals) >= 2 else Confidence.STRONG
                slug = sig.name.lower().replace(" ", "-").replace(".", "-")
                finding = self._build.detected(
                    slug,
                    category="technology",
                    name=sig.name,
                    value=sig.name,
                    confidence=confidence,
                    evidence=evidence_refs[:5],
                )
                findings.append(finding)
                products.append(
                    DetectedProduct(
                        name=sig.name,
                        categories=sig.categories,
                        version=version,
                        status=finding.status,
                        signal_summary=signals[:5],
                        finding_id=finding.id,
                    )
                )

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(products=products),
        )
