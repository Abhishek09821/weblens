"""Tests for technology detection analyzers.

Covers: React, Next.js, Vue, Tailwind, common headers, WordPress, jQuery, CDN detection.
"""

from __future__ import annotations

from tests.conftest import (
    make_dom_observation,
    make_evidence,
    make_http_observation,
)
from weblens.analyzers.base import AnalyzerContext
from weblens.analyzers.technology.framework import TechFrameworkAnalyzer
from weblens.analyzers.technology.language import TechLanguageAnalyzer
from weblens.analyzers.technology.stack import TechStackAnalyzer
from weblens.analyzers.technology.styling import TechStylingAnalyzer
from weblens.domain.enums import DomSource, FindingStatus
from weblens.domain.observations import (
    DomObservation,
    NetworkObservation,
    NetworkRequestRecord,
    RuntimeObservation,
    ScriptObservation,
    StyleObservation,
)
from weblens.domain.observations.page import SampleCoverage


class TestTechLanguageAnalyzer:
    def test_detects_php(self):
        http = make_http_observation(
            headers={"x-powered-by": "PHP/8.2.1", "content-type": "text/html"}
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = TechLanguageAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings if f.status == FindingStatus.VERIFIED]
        assert "PHP" in names

    def test_detects_nginx(self):
        http = make_http_observation(
            headers={"server": "nginx/1.25.3", "content-type": "text/html"}
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = TechLanguageAnalyzer().analyze(ctx)
        found = [f for f in output.findings if "nginx" in f.name.lower()]
        assert len(found) == 1
        assert found[0].status == FindingStatus.VERIFIED

    def test_detects_express(self):
        http = make_http_observation(
            headers={"x-powered-by": "Express", "content-type": "text/html"}
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = TechLanguageAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Express" in names

    def test_no_findings_without_http(self):
        evidence = make_evidence()
        ctx = AnalyzerContext(evidence=evidence)
        output = TechLanguageAnalyzer().analyze(ctx)
        assert output.findings == []


class TestTechFrameworkAnalyzer:
    def _make_runtime(self, globals_present=None, hydration_keys=None):
        return RuntimeObservation(
            globals_present=globals_present or [],
            hydration_payload_keys=hydration_keys or [],
        )

    def test_detects_react_from_globals(self):
        runtime = self._make_runtime(globals_present=["React", "__REACT_DEVTOOLS_GLOBAL_HOOK__"])
        evidence = make_evidence(
            dom=make_dom_observation(),
            http=make_http_observation(body="<div data-reactroot>hello</div>"),
        )
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechFrameworkAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "React" in names

    def test_detects_nextjs_from_hydration(self):
        runtime = self._make_runtime(
            globals_present=["__NEXT_DATA__", "next"],
            hydration_keys=["__NEXT_DATA__"],
        )
        dom = make_dom_observation()
        http = make_http_observation(
            body='<script id="__NEXT_DATA__" type="application/json">{}</script>'
        )
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechFrameworkAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Next.js" in names

    def test_detects_vue(self):
        runtime = self._make_runtime(globals_present=["Vue", "__VUE__"])
        evidence = make_evidence(dom=make_dom_observation())
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechFrameworkAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Vue.js" in names

    def test_detects_alpine_from_dom(self):
        html = '<div x-data="{}" x-init="init()">test</div>'
        http = make_http_observation(body=html)
        dom = make_dom_observation()
        evidence = make_evidence(dom=dom, http=http)
        runtime = RuntimeObservation(globals_present=[])
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechFrameworkAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Alpine.js" in names

    def test_no_false_positive_on_empty(self):
        runtime = self._make_runtime()
        evidence = make_evidence(
            dom=make_dom_observation(), http=make_http_observation(body="<div>plain</div>")
        )
        evidence = evidence.model_copy(update={"runtime": runtime})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechFrameworkAnalyzer().analyze(ctx)
        assert len(output.findings) == 0


class TestTechStylingAnalyzer:
    def _make_styles(self, custom_props=None):
        return StyleObservation(
            coverage=SampleCoverage(elements_sampled=100, elements_total=100),
            distributions=[],
            css_custom_properties=custom_props or [],
        )

    def test_detects_tailwind_from_classes(self):
        html = '<div class="flex items-center p-4 text-blue-500 bg-white sm:grid">'
        http = make_http_observation(body=html)
        dom = make_dom_observation()
        styles = self._make_styles()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStylingAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Tailwind CSS" in names

    def test_detects_bootstrap_from_classes(self):
        html = '<div class="container"><div class="row"><div class="col-md-6">x</div></div></div>'
        http = make_http_observation(body=html)
        dom = make_dom_observation()
        styles = self._make_styles()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStylingAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Bootstrap" in names

    def test_detects_material_ui_from_custom_props(self):
        dom = make_dom_observation()
        styles = self._make_styles(custom_props=["--mui-palette-primary-main", "--mui-spacing"])
        http = make_http_observation(body='<div class="MuiButton-root">Click</div>')
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStylingAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Material UI" in names


class TestTechStackAnalyzer:
    def test_detects_google_analytics(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            scripts=[ScriptObservation(src="https://www.google-analytics.com/analytics.js")],
        )
        runtime = RuntimeObservation(globals_present=["ga", "dataLayer"])
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://www.google-analytics.com/analytics.js",
                    method="GET",
                    resource_type="script",
                    status=200,
                )
            ]
        )
        http = make_http_observation()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"runtime": runtime, "network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStackAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Google Analytics" in names

    def test_detects_cloudflare(self):
        http = make_http_observation(headers={"server": "cloudflare", "content-type": "text/html"})
        dom = make_dom_observation()
        runtime = RuntimeObservation(globals_present=[])
        network = NetworkObservation(requests=[])
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"runtime": runtime, "network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStackAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "Cloudflare" in names

    def test_detects_wordpress(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            scripts=[ScriptObservation(src="https://example.test/wp-content/themes/theme/app.js")],
        )
        runtime = RuntimeObservation(globals_present=[])
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://example.test/wp-content/uploads/image.jpg",
                    method="GET",
                    resource_type="image",
                    status=200,
                )
            ]
        )
        http = make_http_observation()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"runtime": runtime, "network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = TechStackAnalyzer().analyze(ctx)
        names = [f.name for f in output.findings]
        assert "WordPress" in names
