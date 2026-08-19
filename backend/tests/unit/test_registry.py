"""Registry consistency.

The registry is the single source of truth behind ``/capabilities``, the pipeline, and the
frontend's section states. If it is wrong, WebLens misreports what it examined - which is worse
than a crash.
"""

from __future__ import annotations

from weblens.domain.enums import SectionKey
from weblens.orchestration import registry


def test_registry_validates() -> None:
    registry.validate_registry()


def test_every_section_has_at_least_one_declared_analyzer() -> None:
    for section in SectionKey:
        assert registry.entries_for_section(section), f"{section.value} has no analyzers declared"


def test_analyzer_ids_are_section_prefixed() -> None:
    for entry in registry.all_entries():
        assert entry.id.startswith(f"{entry.section.value}."), entry.id


def test_ids_are_unique() -> None:
    ids = [entry.id for entry in registry.all_entries()]
    assert len(ids) == len(set(ids))


def test_dependencies_resolve_to_known_analyzers() -> None:
    known = {entry.id for entry in registry.all_entries()}
    for entry in registry.all_entries():
        assert entry.depends_on <= known, entry.id


def test_dependencies_stay_within_a_section() -> None:
    """Cross-section dependencies would make section status meaningless.

    A section's status is computed from its own analyzer runs, so an analyzer that silently
    depended on another section could report ``complete`` while its inputs were missing.
    """
    for entry in registry.all_entries():
        for dependency in entry.depends_on:
            assert registry.get(dependency).section is entry.section, entry.id


def test_implemented_entries_are_topologically_ordered() -> None:
    ordered = registry.implemented_entries()
    seen: set[str] = set()
    for entry in ordered:
        assert entry.depends_on & {e.id for e in ordered} <= seen, entry.id
        seen.add(entry.id)


def test_aggregators_declare_their_inputs() -> None:
    """The two aggregating analyzers must consume findings, not raw evidence."""
    for aggregator_id in ("security.scoring", "design.interpretation"):
        entry = registry.get(aggregator_id)
        assert entry.depends_on, f"{aggregator_id} must declare dependencies"
        assert not entry.requires, f"{aggregator_id} should consume findings, not evidence slots"


def test_implemented_analyzers_expose_the_expected_interface() -> None:
    for entry in registry.implemented_entries():
        assert entry.factory is not None
        analyzer = entry.factory()
        assert analyzer.id == entry.id
        assert analyzer.section is entry.section
        assert analyzer.version == entry.version
        assert analyzer.requires == entry.requires
        assert hasattr(analyzer, "analyze")


def test_unimplemented_entries_declare_a_phase() -> None:
    for entry in registry.all_entries():
        if not entry.implemented:
            assert entry.phase > 0, entry.id
            assert entry.version == "0.0.0", entry.id


def test_phase_zero_ships_exactly_the_pilot_analyzer() -> None:
    """Guards against accidentally shipping a half-built analyzer as implemented."""
    implemented = [entry.id for entry in registry.implemented_entries()]
    # All analyzers except design.interpretation are now implemented
    assert len(implemented) >= 25
    assert "seo.metadata" in implemented
    assert "security.headers" in implemented
    assert "technology.stack" in implemented
    assert "performance.timings" in implemented
