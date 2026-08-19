"""Analyzers against recorded real-world evidence.

This is the payoff of making ``RawEvidence`` serializable: a real collection run is committed as a
fixture, and from then on analyzer behaviour is validated against actual real-world shapes offline
and deterministically. Fixtures are regenerated deliberately with
``scripts/capture_evidence.py``, never automatically by a test run.

Assertions are structural, not value-based. Whether example.com has a meta description is not ours
to control, and asserting it would make the suite fail for reasons unrelated to our code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from weblens.analyzers.base import AnalyzerContext
from weblens.domain.enums import FindingStatus
from weblens.domain.evidence import RawEvidence
from weblens.orchestration import registry

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "evidence"
FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))


def load(path: Path) -> RawEvidence:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Loading through the model, not as a raw dict: a schema change then breaks loudly here rather
    # than producing subtly wrong analyzer input.
    return RawEvidence.model_validate(payload["evidence"])


def test_fixture_corpus_exists() -> None:
    assert FIXTURES, (
        "No evidence fixtures are committed. Capture one with: "
        "python backend/scripts/capture_evidence.py https://example.com --name static_html_minimal"
    )


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_fixture_round_trips_through_the_model(path: Path) -> None:
    evidence = load(path)
    reloaded = RawEvidence.model_validate(json.loads(evidence.model_dump_json()))
    assert reloaded == evidence


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_every_implemented_analyzer_handles_the_fixture(path: Path) -> None:
    evidence = load(path)

    for entry in registry.implemented_entries():
        assert entry.factory is not None
        analyzer = entry.factory()
        if evidence.missing(entry.requires):
            continue

        output = analyzer.analyze(AnalyzerContext(evidence=evidence))
        assert output.findings, f"{entry.id} produced nothing for {path.stem}"

        ids = [finding.id for finding in output.findings]
        assert len(ids) == len(set(ids)), f"{entry.id} produced duplicate finding ids"

        for finding in output.findings:
            assert finding.id.startswith(f"{entry.id}:")
            assert finding.source == entry.id
            if finding.status in (FindingStatus.VERIFIED, FindingStatus.INFERRED):
                assert finding.evidence, f"{finding.id} asserted without evidence"
            else:
                assert finding.reason, f"{finding.id} is negative without a reason"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_analysis_is_deterministic_for_the_fixture(path: Path) -> None:
    evidence = load(path)
    for entry in registry.implemented_entries():
        assert entry.factory is not None
        if evidence.missing(entry.requires):
            continue
        first = entry.factory().analyze(AnalyzerContext(evidence=evidence))
        second = entry.factory().analyze(AnalyzerContext(evidence=evidence))
        assert [f.model_dump() for f in first.findings] == [f.model_dump() for f in second.findings]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_fixtures_carry_no_credential_material(path: Path) -> None:
    """Redaction happens at collection time, so a fixture must never contain a secret.

    Fixtures are committed to the repository, which makes this the cheapest possible place to catch
    a redaction regression.
    """
    raw = path.read_text(encoding="utf-8").lower()
    for marker in ("access_token=", "api_key=", "password=", 'authorization":', 'set-cookie":'):
        assert marker not in raw, f"{path.name} contains {marker!r}"
