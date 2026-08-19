"""Media usage analysis: SVG, images, video, picture elements.

Reports: image counts, lazy loading usage, SVG/video/picture usage, formats.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "design.media"


class DesignMediaAnalyzer:
    """Analyzes media/image/video usage from DOM."""

    id = ANALYZER_ID
    section = SectionKey.DESIGN
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM, EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        network = ctx.evidence.network
        if dom is None:
            return AnalyzerOutput(findings=[])

        findings = []

        # Image count and lazy loading
        if dom.images:
            total = len(dom.images)
            lazy_count = sum(1 for img in dom.images if img.loading == "lazy")
            finding = self._build.detected(
                "image-count",
                category="media",
                name="Images",
                value=total,
                unit="count",
                details={"lazy_loaded": lazy_count, "eager": total - lazy_count},
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTML_ELEMENT,
                        source="dom.images",
                        excerpt=f"{total} images, {lazy_count} lazy-loaded",
                    )
                ],
            )
            findings.append(finding)

        # SVG usage
        if dom.svg_count > 0:
            finding = self._build.detected(
                "svg-usage",
                category="media",
                name="SVG elements",
                value=dom.svg_count,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTML_ELEMENT,
                        source="dom.svg_count",
                        excerpt=f"{dom.svg_count} SVG elements",
                    )
                ],
            )
            findings.append(finding)

        # Video usage
        if dom.video_count > 0:
            finding = self._build.detected(
                "video-usage",
                category="media",
                name="Video elements",
                value=dom.video_count,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTML_ELEMENT,
                        source="dom.video_count",
                        excerpt=f"{dom.video_count} video elements",
                    )
                ],
            )
            findings.append(finding)

        # Picture elements (responsive images)
        if dom.picture_count > 0:
            finding = self._build.detected(
                "picture-usage",
                category="media",
                name="Picture elements (responsive images)",
                value=dom.picture_count,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTML_ELEMENT,
                        source="dom.picture_count",
                        excerpt=f"{dom.picture_count} picture elements",
                    )
                ],
            )
            findings.append(finding)

        # Image formats from network requests
        if network:
            image_requests = [
                r
                for r in network.requests
                if r.resource_type == "image" or (r.mime_type and "image" in r.mime_type)
            ]
            if image_requests:
                formats: dict[str, int] = {}
                for req in image_requests:
                    fmt = self._detect_format(req.url, req.mime_type)
                    formats[fmt] = formats.get(fmt, 0) + 1
                finding = self._build.detected(
                    "image-formats",
                    category="media",
                    name="Image formats observed",
                    value=len(formats),
                    unit="count",
                    values=[
                        f"{fmt}: {count}"
                        for fmt, count in sorted(formats.items(), key=lambda x: x[1], reverse=True)
                    ],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests[type=image]",
                            excerpt=f"{len(image_requests)} image requests",
                        )
                    ],
                )
                findings.append(finding)

        return AnalyzerOutput(findings=findings)

    def _detect_format(self, url: str, mime_type: str | None) -> str:
        """Detect image format from URL or MIME type."""
        if mime_type:
            mime_lower = mime_type.lower()
            if "webp" in mime_lower:
                return "webp"
            if "avif" in mime_lower:
                return "avif"
            if "svg" in mime_lower:
                return "svg"
            if "png" in mime_lower:
                return "png"
            if "gif" in mime_lower:
                return "gif"
            if "jpeg" in mime_lower or "jpg" in mime_lower:
                return "jpeg"
        url_lower = url.lower().split("?")[0]
        for ext in (".webp", ".avif", ".svg", ".png", ".gif", ".jpg", ".jpeg", ".ico"):
            if url_lower.endswith(ext):
                return ext.lstrip(".")
        return "unknown"
