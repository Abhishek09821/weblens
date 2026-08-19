"""Tests for performance, accessibility, SEO, network, and architecture analyzers.

Covers: performance timings, resource analysis, accessibility structure,
SEO indexability, structured data, network resources, architecture rendering.
"""

from __future__ import annotations

from tests.conftest import (
    make_dom_observation,
    make_evidence,
    make_http_observation,
)
from weblens.analyzers.accessibility.structure import AccessibilityStructureAnalyzer
from weblens.analyzers.architecture.platform import ArchitecturePlatformAnalyzer
from weblens.analyzers.architecture.rendering import ArchitectureRenderingAnalyzer
from weblens.analyzers.base import AnalyzerContext
from weblens.analyzers.network.resources import NetworkResourcesAnalyzer
from weblens.analyzers.network.third_parties import NetworkThirdPartiesAnalyzer
from weblens.analyzers.performance.resources import PerformanceResourcesAnalyzer
from weblens.analyzers.performance.timings import PerformanceTimingsAnalyzer
from weblens.analyzers.seo.indexability import SeoIndexabilityAnalyzer
from weblens.analyzers.seo.structured_data import SeoStructuredDataAnalyzer
from weblens.domain.enums import DomSource, FindingStatus
from weblens.domain.observations import (
    DomObservation,
    FormObservation,
    HeadingObservation,
    ImageObservation,
    NetworkObservation,
    NetworkRequestRecord,
    RobotsObservation,
    RuntimeObservation,
    StructuredDataBlock,
)
from weblens.domain.observations.measurement import LongTaskEntry, PerformanceObservation


class TestPerformanceTimings:
    def test_reports_timing_metrics(self):
        perf = PerformanceObservation(
            ttfb_ms=150.5,
            first_contentful_paint_ms=800.2,
            largest_contentful_paint_ms=1500.0,
            largest_contentful_paint_element="IMG",
            cumulative_layout_shift=0.05,
            dom_content_loaded_ms=600.0,
            load_event_ms=2000.0,
            long_tasks=[LongTaskEntry(start_ms=100, duration_ms=120)],
            total_blocking_estimate_ms=70.0,
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"performance": perf})
        ctx = AnalyzerContext(evidence=evidence)
        output = PerformanceTimingsAnalyzer().analyze(ctx)

        assert len(output.findings) >= 5
        fcp = next(f for f in output.findings if "FCP" in f.name)
        assert fcp.value == 800.2

        lcp = next(f for f in output.findings if "LCP" in f.name)
        assert lcp.value == 1500.0
        assert lcp.details.get("element") == "IMG"


class TestPerformanceResources:
    def test_reports_resource_counts(self):
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://ex.test/app.js", method="GET", resource_type="script", status=200
                ),
                NetworkRequestRecord(
                    url="https://ex.test/style.css",
                    method="GET",
                    resource_type="stylesheet",
                    status=200,
                ),
                NetworkRequestRecord(
                    url="https://cdn.other.com/lib.js",
                    method="GET",
                    resource_type="script",
                    status=200,
                    failed=True,
                    failure_text="net::ERR_BLOCKED",
                ),
            ],
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = PerformanceResourcesAnalyzer().analyze(ctx)

        count_f = next(f for f in output.findings if "Total" in f.name)
        assert count_f.value == 3

        failed_f = next(f for f in output.findings if "Failed" in f.name)
        assert failed_f.value == 1


class TestAccessibilityStructure:
    def test_detects_issues(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            lang=None,
            title=None,
            headings=[
                HeadingObservation(level=2, text="First"),
                HeadingObservation(level=4, text="Skipped"),
            ],
            images=[
                ImageObservation(src="/img.png", alt_present=False),
                ImageObservation(src="/img2.png", alt_present=True, alt="ok"),
            ],
            forms=[FormObservation(input_count=3, labelled_input_count=1)],
            landmark_roles=[],
        )
        evidence = make_evidence(dom=dom)
        ctx = AnalyzerContext(evidence=evidence)
        output = AccessibilityStructureAnalyzer().analyze(ctx)

        # Missing lang
        lang_f = next(f for f in output.findings if "language" in f.name.lower())
        assert lang_f.status == FindingStatus.NOT_DETECTED

        # Missing title
        title_f = next(f for f in output.findings if "title" in f.name.lower())
        assert title_f.status == FindingStatus.NOT_DETECTED

        # Heading hierarchy issue
        heading_f = next(f for f in output.findings if "Heading" in f.name)
        assert heading_f.value >= 1

        # Images without alt
        img_f = next(f for f in output.findings if "alt" in f.name.lower())
        assert img_f.value == 1

    def test_good_structure(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            lang="en",
            title="Good Page",
            headings=[
                HeadingObservation(level=1, text="Main"),
                HeadingObservation(level=2, text="Sub"),
            ],
            images=[ImageObservation(src="/x.png", alt_present=True, alt="desc")],
            landmark_roles=["main", "navigation", "banner"],
        )
        evidence = make_evidence(dom=dom)
        ctx = AnalyzerContext(evidence=evidence)
        output = AccessibilityStructureAnalyzer().analyze(ctx)

        lang_f = next(f for f in output.findings if "language" in f.name.lower())
        assert lang_f.detected is True


class TestSeoIndexability:
    def test_robots_allowed(self):
        http = make_http_observation(headers={"content-type": "text/html"})
        robots = RobotsObservation(
            url="https://example.test/robots.txt",
            fetched=True,
            status=200,
            allowed=True,
            sitemaps=["https://example.test/sitemap.xml"],
        )
        evidence = make_evidence(http=http, robots=robots)
        ctx = AnalyzerContext(evidence=evidence)
        output = SeoIndexabilityAnalyzer().analyze(ctx)

        allowed_f = next(f for f in output.findings if "allows" in f.name.lower())
        assert allowed_f.detected is True

        sitemap_f = next(f for f in output.findings if "Sitemap" in f.name)
        assert sitemap_f.value == 1


class TestSeoStructuredData:
    def test_detects_jsonld(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            structured_data=[
                StructuredDataBlock(
                    format="json-ld", types=["Organization", "WebSite"], valid=True
                ),
                StructuredDataBlock(format="json-ld", types=["Article"], valid=True),
            ],
        )
        evidence = make_evidence(dom=dom)
        ctx = AnalyzerContext(evidence=evidence)
        output = SeoStructuredDataAnalyzer().analyze(ctx)

        sd_f = next(f for f in output.findings if "blocks" in f.name.lower())
        assert sd_f.value == 2

    def test_no_structured_data(self):
        dom = make_dom_observation()
        evidence = make_evidence(dom=dom)
        ctx = AnalyzerContext(evidence=evidence)
        output = SeoStructuredDataAnalyzer().analyze(ctx)
        assert output.findings[0].status == FindingStatus.NOT_DETECTED


class TestNetworkResources:
    def test_domain_breakdown(self):
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://example.test/app.js",
                    method="GET",
                    resource_type="script",
                    host="example.test",
                ),
                NetworkRequestRecord(
                    url="https://cdn.example.test/lib.js",
                    method="GET",
                    resource_type="script",
                    host="cdn.example.test",
                ),
                NetworkRequestRecord(
                    url="https://analytics.third.com/track",
                    method="GET",
                    resource_type="xhr",
                    host="analytics.third.com",
                ),
            ]
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = NetworkResourcesAnalyzer().analyze(ctx)

        domain_f = next(f for f in output.findings if "domain" in f.name.lower())
        assert domain_f.value == 3


class TestNetworkThirdParties:
    def test_third_party_ratio(self):
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://example.test/app.js",
                    method="GET",
                    resource_type="script",
                    host="example.test",
                ),
                NetworkRequestRecord(
                    url="https://cdn.external.com/lib.js",
                    method="GET",
                    resource_type="script",
                    host="cdn.external.com",
                ),
                NetworkRequestRecord(
                    url="https://api.external.com/data",
                    method="GET",
                    resource_type="xhr",
                    host="api.external.com",
                ),
            ]
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = NetworkThirdPartiesAnalyzer().analyze(ctx)

        ratio_f = next(f for f in output.findings if "ratio" in f.name.lower())
        assert ratio_f.value > 60  # 2/3 are third party


class TestArchitectureRendering:
    def test_detects_ssr(self):
        runtime = RuntimeObservation(
            globals_present=["__NEXT_DATA__", "React"],
            hydration_payload_keys=["__NEXT_DATA__"],
        )
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            text_length=5000,
            element_count=200,
        )
        http = make_http_observation()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = ArchitectureRenderingAnalyzer().analyze(ctx)

        strategy_f = next(f for f in output.findings if "strategy" in f.name.lower())
        assert "server_rendered" in str(strategy_f.value)


class TestArchitecturePlatform:
    def test_detects_vercel(self):
        http = make_http_observation(
            headers={
                "x-vercel-id": "iad1::abc123",
                "content-type": "text/html",
            }
        )
        evidence = make_evidence(http=http)
        evidence = evidence.model_copy(update={"dns": None})
        ctx = AnalyzerContext(evidence=evidence)
        output = ArchitecturePlatformAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings if f.detected]
        assert any("Vercel" in n for n in names)
