"""Regression tests for assembling partial analyzer payloads into V2 sections."""

from weblens.domain.enums import FindingStatus
from weblens.domain.sections import DetectedProduct, TechnologyPayload
from weblens.orchestration.pipeline import _merge_payload


def product(name: str, finding_id: str) -> DetectedProduct:
    return DetectedProduct(
        name=name,
        categories=["frontend"],
        status=FindingStatus.VERIFIED,
        finding_id=finding_id,
    )


def test_partial_technology_payloads_accumulate_without_erasing_fields() -> None:
    react = product("React", "technology.framework:react")
    vite = product("Vite", "technology.stack:vite")

    merged = _merge_payload(None, TechnologyPayload(products=[react]))
    merged = _merge_payload(
        merged,
        TechnologyPayload(products=[vite], static_vs_rendered_element_delta=12),
    )
    merged = _merge_payload(
        merged,
        TechnologyPayload(products=[react], network_cap_hit=True),
    )

    assert isinstance(merged, TechnologyPayload)
    assert [item.name for item in merged.products] == ["React", "Vite"]
    assert merged.static_vs_rendered_element_delta == 12
    assert merged.network_cap_hit is True
