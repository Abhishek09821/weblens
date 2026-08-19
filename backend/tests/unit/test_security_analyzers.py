"""Tests for security analyzers.

Covers: headers, cookies, mixed content, exposure, scoring.
"""

from __future__ import annotations

from tests.conftest import TEST_URL, make_dom_observation, make_evidence, make_http_observation
from weblens.analyzers.base import AnalyzerContext
from weblens.analyzers.security.cookies import SecurityCookiesAnalyzer
from weblens.analyzers.security.exposure import SecurityExposureAnalyzer
from weblens.analyzers.security.headers import SecurityHeadersAnalyzer
from weblens.analyzers.security.mixed_content import SecurityMixedContentAnalyzer
from weblens.analyzers.security.scoring import SecurityScoringAnalyzer
from weblens.analyzers.security.third_party import SecurityThirdPartyAnalyzer
from weblens.domain.enums import DomSource, FindingStatus
from weblens.domain.observations import (
    CookieAttributes,
    DomObservation,
    NetworkObservation,
    NetworkRequestRecord,
    ScriptObservation,
)


class TestSecurityHeaders:
    def test_detects_full_security_headers(self):
        http = make_http_observation(
            headers={
                "content-type": "text/html",
                "strict-transport-security": "max-age=31536000; includeSubDomains",
                "content-security-policy": "default-src 'self'; script-src 'self'",
                "x-content-type-options": "nosniff",
                "x-frame-options": "DENY",
                "referrer-policy": "strict-origin-when-cross-origin",
                "permissions-policy": "geolocation=(), camera=()",
            }
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityHeadersAnalyzer().analyze(ctx)

        detected_names = [f.name for f in output.findings if f.detected]
        assert "Strict-Transport-Security (HSTS)" in detected_names
        assert "Content-Security-Policy" in detected_names
        assert "X-Content-Type-Options" in detected_names
        assert "X-Frame-Options" in detected_names
        assert "Referrer-Policy" in detected_names
        assert "Permissions-Policy" in detected_names

    def test_reports_missing_headers(self):
        http = make_http_observation(headers={"content-type": "text/html"})
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityHeadersAnalyzer().analyze(ctx)

        not_detected = [f for f in output.findings if f.status == FindingStatus.NOT_DETECTED]
        assert len(not_detected) >= 5  # HSTS, CSP, XCTO, XFO, RP, PP

    def test_hsts_includesubdomains_detail(self):
        http = make_http_observation(
            headers={
                "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
                "content-type": "text/html",
            }
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityHeadersAnalyzer().analyze(ctx)
        hsts = next(f for f in output.findings if "HSTS" in f.name)
        assert hsts.details.get("include_subdomains") is True


class TestSecurityCookies:
    def test_reports_insecure_cookies(self):
        http = make_http_observation(headers={"content-type": "text/html"})
        http = http.model_copy(
            update={
                "cookies": [
                    CookieAttributes(
                        name="session",
                        secure=False,
                        http_only=False,
                        same_site=None,
                        source_hop_url=TEST_URL,
                    ),
                    CookieAttributes(
                        name="pref",
                        secure=True,
                        http_only=True,
                        same_site="Lax",
                        source_hop_url=TEST_URL,
                    ),
                ]
            }
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityCookiesAnalyzer().analyze(ctx)

        insecure = next((f for f in output.findings if "Secure" in f.name), None)
        assert insecure is not None
        assert insecure.value == 1

    def test_no_cookies_detected(self):
        http = make_http_observation(headers={"content-type": "text/html"})
        http = http.model_copy(update={"cookies": []})
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityCookiesAnalyzer().analyze(ctx)
        assert output.findings[0].status == FindingStatus.NOT_DETECTED


class TestSecurityMixedContent:
    def test_detects_mixed_content(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            scripts=[ScriptObservation(src="http://evil.com/script.js")],
        )
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="http://cdn.example.com/image.png",
                    method="GET",
                    resource_type="image",
                    status=200,
                )
            ]
        )
        http = make_http_observation()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityMixedContentAnalyzer().analyze(ctx)
        mixed = next(f for f in output.findings if "mixed" in f.name.lower())
        assert mixed.detected is True

    def test_no_mixed_content_on_clean_page(self):
        dom = make_dom_observation()
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://cdn.example.com/image.png",
                    method="GET",
                    resource_type="image",
                    status=200,
                )
            ]
        )
        http = make_http_observation()
        evidence = make_evidence(dom=dom, http=http)
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityMixedContentAnalyzer().analyze(ctx)
        mixed = next(f for f in output.findings if "mixed" in f.name.lower())
        assert mixed.detected is False


class TestSecurityExposure:
    def test_detects_server_version(self):
        http = make_http_observation(
            headers={
                "server": "Apache/2.4.51",
                "content-type": "text/html",
            }
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityExposureAnalyzer().analyze(ctx)
        found = next((f for f in output.findings if "Server" in f.name), None)
        assert found is not None
        assert "Apache" in str(found.value)

    def test_no_version_disclosure(self):
        http = make_http_observation(
            headers={
                "server": "cloudflare",
                "content-type": "text/html",
            }
        )
        evidence = make_evidence(http=http)
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityExposureAnalyzer().analyze(ctx)
        not_detected = [f for f in output.findings if f.status == FindingStatus.NOT_DETECTED]
        assert len(not_detected) == 1


class TestSecurityThirdParty:
    def test_detects_cross_origin_scripts(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            scripts=[
                ScriptObservation(src="https://cdn.third-party.com/lib.js", integrity=None),
                ScriptObservation(src="https://example.test/app.js"),
            ],
        )
        network = NetworkObservation(requests=[])
        evidence = make_evidence(dom=dom)
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = SecurityThirdPartyAnalyzer().analyze(ctx)
        co = next((f for f in output.findings if "Cross-origin" in f.name), None)
        assert co is not None
        assert co.value == 1


class TestSecurityScoring:
    def test_computes_score(self):
        # First run the headers analyzer to produce findings
        http = make_http_observation(
            headers={
                "content-type": "text/html",
                "strict-transport-security": "max-age=31536000",
                "content-security-policy": "default-src 'self'",
                "x-content-type-options": "nosniff",
                "x-frame-options": "DENY",
                "referrer-policy": "no-referrer",
                "permissions-policy": "geolocation=()",
            }
        )
        evidence = make_evidence(http=http)
        http = http.model_copy(update={"cookies": []})
        evidence = evidence.model_copy(update={"http": http})

        # Run dependent analyzers first
        from weblens.analyzers.security.cookies import SecurityCookiesAnalyzer
        from weblens.analyzers.security.exposure import SecurityExposureAnalyzer
        from weblens.analyzers.security.headers import SecurityHeadersAnalyzer

        produced = {}
        for analyzer_cls in [
            SecurityHeadersAnalyzer,
            SecurityCookiesAnalyzer,
            SecurityExposureAnalyzer,
        ]:
            a = analyzer_cls()
            ctx = AnalyzerContext(evidence=evidence, findings=produced)
            out = a.analyze(ctx)
            for f in out.findings:
                produced[f.id] = f

        # Now run scoring
        ctx = AnalyzerContext(evidence=evidence, findings=produced)
        output = SecurityScoringAnalyzer().analyze(ctx)

        assert output.data is not None
        score = output.data.score
        assert score is not None
        assert score.percentage > 50  # Good headers should score above 50%
        assert score.band.value in ("strong", "good", "moderate")
        assert len(score.rules) > 0
