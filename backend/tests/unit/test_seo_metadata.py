"""Pilot analyzer tests.

Every analyzer must satisfy the same four cases (docs/blueprint/12): positive, negative,
degraded, and empty. This file is the template the other analyzers copy.
"""

from __future__ import annotations

import pytest

from tests.conftest import make_dom_observation, make_evidence, make_http_observation
from weblens.analyzers.base import AnalyzerContext
from weblens.analyzers.seo.metadata import SeoMetadataAnalyzer
from weblens.collection.static_html import parse_static_html
from weblens.domain.enums import DomSource, FindingStatus
from weblens.domain.evidence import RawEvidence
from weblens.domain.findings import Finding

RICH_HTML = """<!doctype html>
<html lang="en-GB"><head>
<title>Widgets for Everyone</title>
<meta name="description" content="We make widgets.">
<meta name="robots" content="index,follow">
<meta name="viewport" content="width=device-width">
<meta property="og:title" content="Widgets">
<meta property="og:image" content="https://example.test/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://example.test/widgets">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple.png">
<link rel="alternate" hreflang="fr" href="https://example.test/fr">
</head><body><h1>Widgets</h1></body></html>"""

BARE_HTML = "<!doctype html><html><head></head><body><p>nothing here</p></body></html>"


def run(evidence: RawEvidence) -> dict[str, Finding]:
    output = SeoMetadataAnalyzer().analyze(AnalyzerContext(evidence=evidence))
    return {finding.id: finding for finding in output.findings}


# --- case 1: positive -------------------------------------------------------------------


def test_detects_metadata_with_evidence() -> None:
    dom = parse_static_html(RICH_HTML, "https://example.test/widgets")
    findings = run(make_evidence(http=make_http_observation(body=RICH_HTML), dom=dom))

    title = findings["seo.metadata:title"]
    assert title.status is FindingStatus.VERIFIED
    assert title.value == "Widgets for Everyone"
    assert title.details["length"] == len("Widgets for Everyone")
    assert title.evidence, "an asserted finding must carry evidence"
    assert title.evidence[0].excerpt == "Widgets for Everyone"

    assert findings["seo.metadata:meta-description"].value == "We make widgets."
    assert findings["seo.metadata:canonical"].value == "https://example.test/widgets"
    assert findings["seo.metadata:robots-meta"].value == "index,follow"
    assert findings["seo.metadata:html-lang"].value == "en-GB"
    assert findings["seo.metadata:open-graph"].value == 2
    assert findings["seo.metadata:twitter-card"].value == 1
    assert findings["seo.metadata:hreflang"].value == 1
    assert findings["seo.metadata:favicon"].value == 2
    assert findings["seo.metadata:h1"].value == 1


def test_payload_mirrors_findings() -> None:
    dom = parse_static_html(RICH_HTML, "https://example.test/widgets")
    output = SeoMetadataAnalyzer().analyze(
        AnalyzerContext(evidence=make_evidence(http=make_http_observation(body=RICH_HTML), dom=dom))
    )
    assert output.data is not None
    metadata = output.data.metadata  # type: ignore[union-attr]
    assert metadata is not None
    assert metadata.title == "Widgets for Everyone"
    assert metadata.description_length == len("We make widgets.")
    assert [entry.key for entry in metadata.open_graph] == ["og:title", "og:image"]


# --- case 2: negative -------------------------------------------------------------------


def test_absent_metadata_is_not_detected_with_a_reason() -> None:
    dom = parse_static_html(BARE_HTML, "https://example.test/")
    findings = run(make_evidence(http=make_http_observation(body=BARE_HTML), dom=dom))

    for finding_id in (
        "seo.metadata:title",
        "seo.metadata:meta-description",
        "seo.metadata:canonical",
        "seo.metadata:open-graph",
        "seo.metadata:html-lang",
    ):
        finding = findings[finding_id]
        assert finding.status is FindingStatus.NOT_DETECTED, finding_id
        assert finding.reason, f"{finding_id} must explain why"
        assert finding.value is None
        assert finding.evidence == []


def test_not_detected_is_not_a_claim_that_something_is_missing_from_the_site() -> None:
    """The favicon reason must acknowledge the convention we did not probe.

    A site can serve /favicon.ico without declaring it. Saying "no favicon" would be a claim we
    have not earned; the finding says what was observed and what was not checked.
    """
    dom = parse_static_html(BARE_HTML, "https://example.test/")
    finding = run(make_evidence(dom=dom))["seo.metadata:favicon"]
    assert "favicon.ico" in (finding.reason or "")


# --- case 3: degraded -------------------------------------------------------------------


def test_missing_dom_yields_unable_to_verify() -> None:
    findings = run(make_evidence(http=make_http_observation(), dom=None))
    assert findings
    for finding in findings.values():
        assert finding.status is FindingStatus.UNABLE_TO_VERIFY
        assert finding.reason
        assert finding.value is None


def test_static_html_source_is_recorded_as_a_limitation() -> None:
    """A claim from served HTML must not read as a claim about the rendered page."""
    dom = parse_static_html(RICH_HTML, "https://example.test/")
    assert dom.source is DomSource.STATIC_HTML
    finding = run(make_evidence(dom=dom))["seo.metadata:title"]
    assert any("as served" in limitation for limitation in finding.limitations)


def test_rendered_dom_carries_no_static_limitation() -> None:
    dom = make_dom_observation(source=DomSource.RENDERED_DOM, title="Rendered")
    finding = run(make_evidence(dom=dom))["seo.metadata:title"]
    assert finding.limitations == []


# --- case 4: empty ----------------------------------------------------------------------


def test_empty_evidence_does_not_raise() -> None:
    findings = run(make_evidence())
    assert len(findings) == 11
    assert all(f.status is FindingStatus.UNABLE_TO_VERIFY for f in findings.values())


def test_empty_dom_reports_absence_not_failure() -> None:
    """An empty-but-collected DOM is 'not detected', never 'unable to verify'."""
    findings = run(make_evidence(dom=make_dom_observation(title=None, lang=None)))
    assert findings["seo.metadata:title"].status is FindingStatus.NOT_DETECTED


# --- cross-cutting invariants -----------------------------------------------------------


@pytest.mark.parametrize("html", [RICH_HTML, BARE_HTML], ids=["rich", "bare"])
def test_determinism(html: str) -> None:
    evidence = make_evidence(dom=parse_static_html(html, "https://example.test/"))
    first = SeoMetadataAnalyzer().analyze(AnalyzerContext(evidence=evidence))
    second = SeoMetadataAnalyzer().analyze(AnalyzerContext(evidence=evidence))
    assert [f.model_dump() for f in first.findings] == [f.model_dump() for f in second.findings]


def test_finding_ids_are_namespaced_and_unique() -> None:
    output = SeoMetadataAnalyzer().analyze(
        AnalyzerContext(evidence=make_evidence(dom=parse_static_html(RICH_HTML, "https://x.test/")))
    )
    ids = [finding.id for finding in output.findings]
    assert len(ids) == len(set(ids))
    assert all(finding_id.startswith("seo.metadata:") for finding_id in ids)
    assert all(finding.source == "seo.metadata" for finding in output.findings)


def test_no_interpretations_from_a_factual_analyzer() -> None:
    """Only interpretation analyzers may emit subjective statements."""
    output = SeoMetadataAnalyzer().analyze(
        AnalyzerContext(evidence=make_evidence(dom=parse_static_html(RICH_HTML, "https://x.test/")))
    )
    assert output.interpretations == []


def test_normal_and_degraded_paths_cover_the_same_fields() -> None:
    """Both paths are driven by one table, so they cannot drift apart.

    Before this was a single table, adding a field meant updating two lists by hand; forgetting the
    second silently dropped the field from the degraded report.
    """
    from weblens.analyzers.seo.metadata import FIELD_SPECS

    normal = run(make_evidence(dom=parse_static_html(RICH_HTML, "https://example.test/")))
    degraded = run(make_evidence(dom=None))

    assert set(normal) == set(degraded)
    assert len(normal) == len(FIELD_SPECS)


def test_every_field_spec_has_a_usable_absent_reason() -> None:
    from weblens.analyzers.seo.metadata import FIELD_SPECS

    for spec in FIELD_SPECS:
        assert spec.absent_reason.endswith("."), spec.slug
        assert len(spec.absent_reason) > 20, spec.slug
        assert spec.name
        assert spec.category
