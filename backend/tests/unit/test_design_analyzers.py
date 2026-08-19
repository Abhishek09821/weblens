"""Tests for design analyzers.

Covers: color extraction, typography, layout, media, motion.
"""

from __future__ import annotations

from tests.conftest import make_evidence
from weblens.analyzers.base import AnalyzerContext
from weblens.analyzers.design.color import DesignColorAnalyzer
from weblens.analyzers.design.layout import DesignLayoutAnalyzer
from weblens.analyzers.design.media import DesignMediaAnalyzer
from weblens.analyzers.design.motion import DesignMotionAnalyzer
from weblens.analyzers.design.typography import DesignTypographyAnalyzer
from weblens.domain.enums import DomSource
from weblens.domain.observations import (
    DomObservation,
    ImageObservation,
    NetworkObservation,
    NetworkRequestRecord,
    StyleObservation,
    StylePropertyDistribution,
    StyleValueCount,
    ViewportMetrics,
)
from weblens.domain.observations.page import SampleCoverage


def _style_obs(distributions=None, fonts=None, custom_props=None, breakpoints=None, keyframes=0):
    return StyleObservation(
        coverage=SampleCoverage(elements_sampled=500, elements_total=1000),
        distributions=distributions or [],
        loaded_fonts=fonts or [],
        css_custom_properties=custom_props or [],
        media_query_breakpoints=breakpoints or [],
        keyframe_count=keyframes,
    )


class TestDesignColorAnalyzer:
    def test_extracts_colors(self):
        styles = _style_obs(
            distributions=[
                StylePropertyDistribution(
                    property="background-color",
                    values=[
                        StyleValueCount(value="rgb(255, 255, 255)", count=100),
                        StyleValueCount(value="rgb(59, 130, 246)", count=20),
                    ],
                ),
                StylePropertyDistribution(
                    property="color",
                    values=[
                        StyleValueCount(value="rgb(17, 24, 39)", count=80),
                        StyleValueCount(value="rgb(107, 114, 128)", count=30),
                    ],
                ),
            ]
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignColorAnalyzer().analyze(ctx)
        assert len(output.findings) >= 2
        bg_finding = next(f for f in output.findings if "Background" in f.name)
        assert bg_finding.value >= 2


class TestDesignTypographyAnalyzer:
    def test_extracts_fonts(self):
        styles = _style_obs(
            fonts=["Inter", "Inter", "system-ui", "monospace"],
            distributions=[
                StylePropertyDistribution(
                    property="font-family",
                    values=[
                        StyleValueCount(value="Inter, sans-serif", count=50),
                    ],
                ),
                StylePropertyDistribution(
                    property="font-weight",
                    values=[
                        StyleValueCount(value="400", count=40),
                        StyleValueCount(value="700", count=15),
                    ],
                ),
                StylePropertyDistribution(
                    property="font-size",
                    values=[
                        StyleValueCount(value="16px", count=30),
                        StyleValueCount(value="14px", count=20),
                        StyleValueCount(value="24px", count=10),
                    ],
                ),
            ],
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignTypographyAnalyzer().analyze(ctx)

        font_finding = next(f for f in output.findings if "Loaded fonts" in f.name)
        assert "Inter" in font_finding.values

        weight_finding = next(f for f in output.findings if "weight" in f.name.lower())
        assert weight_finding.value >= 2


class TestDesignLayoutAnalyzer:
    def test_extracts_layout(self):
        styles = _style_obs(
            distributions=[
                StylePropertyDistribution(
                    property="display",
                    values=[
                        StyleValueCount(value="flex", count=30),
                        StyleValueCount(value="grid", count=10),
                    ],
                ),
                StylePropertyDistribution(
                    property="border-radius",
                    values=[
                        StyleValueCount(value="4px", count=20),
                        StyleValueCount(value="8px", count=15),
                        StyleValueCount(value="50%", count=5),
                    ],
                ),
            ],
            breakpoints=["(min-width: 768px)", "(min-width: 1024px)"],
        )
        viewports = [
            ViewportMetrics(width=390, height=900, has_horizontal_overflow=False),
            ViewportMetrics(width=768, height=900, has_horizontal_overflow=False),
            ViewportMetrics(width=1440, height=900, has_horizontal_overflow=False),
        ]
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"styles": styles, "viewports": viewports})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignLayoutAnalyzer().analyze(ctx)

        display_finding = next(f for f in output.findings if "Display" in f.name)
        assert "flex" in display_finding.values

        radius_finding = next(f for f in output.findings if "radius" in f.name.lower())
        assert radius_finding.value >= 2

    def test_detects_horizontal_overflow(self):
        styles = _style_obs()
        viewports = [
            ViewportMetrics(width=320, height=900, has_horizontal_overflow=True),
            ViewportMetrics(width=768, height=900, has_horizontal_overflow=False),
        ]
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"styles": styles, "viewports": viewports})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignLayoutAnalyzer().analyze(ctx)
        overflow = next((f for f in output.findings if "overflow" in f.name.lower()), None)
        assert overflow is not None


class TestDesignMediaAnalyzer:
    def test_reports_images(self):
        dom = DomObservation(
            source=DomSource.RENDERED_DOM,
            images=[
                ImageObservation(src="/img1.png", alt_present=True, alt="Logo", loading="lazy"),
                ImageObservation(src="/img2.jpg", alt_present=True, alt="Hero"),
                ImageObservation(src="/img3.webp", alt_present=False, loading="lazy"),
            ],
            svg_count=5,
            video_count=1,
        )
        network = NetworkObservation(
            requests=[
                NetworkRequestRecord(
                    url="https://ex.test/img1.png",
                    method="GET",
                    resource_type="image",
                    mime_type="image/png",
                ),
                NetworkRequestRecord(
                    url="https://ex.test/img2.webp",
                    method="GET",
                    resource_type="image",
                    mime_type="image/webp",
                ),
            ]
        )
        evidence = make_evidence(dom=dom)
        evidence = evidence.model_copy(update={"network": network})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignMediaAnalyzer().analyze(ctx)

        img_finding = next(f for f in output.findings if "Images" in f.name)
        assert img_finding.value == 3
        assert img_finding.details["lazy_loaded"] == 2

        svg_finding = next(f for f in output.findings if "SVG" in f.name)
        assert svg_finding.value == 5


class TestDesignMotionAnalyzer:
    def test_reports_animations(self):
        styles = _style_obs(
            distributions=[
                StylePropertyDistribution(
                    property="transition",
                    values=[
                        StyleValueCount(value="all 0.3s ease", count=15),
                        StyleValueCount(value="opacity 0.2s", count=8),
                    ],
                ),
                StylePropertyDistribution(
                    property="animation",
                    values=[
                        StyleValueCount(value="fadeIn 0.5s ease-in", count=5),
                    ],
                ),
            ],
            keyframes=3,
        )
        evidence = make_evidence()
        evidence = evidence.model_copy(update={"styles": styles})
        ctx = AnalyzerContext(evidence=evidence)
        output = DesignMotionAnalyzer().analyze(ctx)

        transition_f = next(f for f in output.findings if "transition" in f.name.lower())
        assert transition_f.value >= 2

        keyframe_f = next(f for f in output.findings if "keyframe" in f.name.lower())
        assert keyframe_f.value == 3
