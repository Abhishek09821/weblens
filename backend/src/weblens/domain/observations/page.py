"""Page-level observations: DOM inventory, runtime signals, computed styles, screenshots.

In Phase 0 the DOM slot is filled by parsing the served HTML, which is recorded as
``source = static_html``. Phase 1 fills it from the rendered DOM instead
(``source = rendered_dom``). Analyzers must branch on ``source`` rather than assume: a claim
based on static HTML is a different claim from one based on the rendered page.
"""

from __future__ import annotations

from pydantic import Field

from weblens.domain.enums import DomSource
from weblens.domain.observations.transport import Observation


class MetaTagObservation(Observation):
    name: str | None = None
    """The ``name`` attribute, lowercased."""
    property: str | None = None
    """The ``property`` attribute (Open Graph and friends), lowercased."""
    http_equiv: str | None = None
    charset: str | None = None
    content: str | None = None


class LinkTagObservation(Observation):
    rel: str | None = None
    href: str | None = None
    hreflang: str | None = None
    type: str | None = None
    sizes: str | None = None
    integrity: str | None = None
    crossorigin: str | None = None


class ScriptObservation(Observation):
    src: str | None = None
    """``None`` for an inline script."""
    type: str | None = None
    module: bool = False
    is_async: bool = False
    """Named ``is_async`` rather than aliased to ``async``: a field whose serialized name
    differs from its Python name breaks fixture round-tripping, and fixtures are the basis
    of the analyzer test strategy."""
    defer: bool = False
    integrity: str | None = None
    crossorigin: str | None = None
    inline_length: int | None = None


class HeadingObservation(Observation):
    level: int
    text: str | None = None


class ImageObservation(Observation):
    src: str | None = None
    alt: str | None = None
    """``None`` means the attribute is absent; ``""`` means an intentionally empty alt.
    Accessibility rules treat these differently, so the distinction is preserved."""
    alt_present: bool = False
    loading: str | None = None
    width_attr: str | None = None
    height_attr: str | None = None


class FormObservation(Observation):
    action: str | None = None
    method: str | None = None
    input_count: int = 0
    labelled_input_count: int = 0
    has_password_input: bool = False


class StructuredDataBlock(Observation):
    format: str
    """``json-ld``, ``microdata``, or ``rdfa``."""
    types: list[str] = Field(default_factory=list)
    valid: bool
    parse_error: str | None = None
    raw_length: int | None = None


class DomObservation(Observation):
    """Inventory of the document. Counts are exact; text is bounded."""

    source: DomSource
    title: str | None = None
    lang: str | None = None
    dir: str | None = None
    charset: str | None = None
    meta_tags: list[MetaTagObservation] = Field(default_factory=list)
    link_tags: list[LinkTagObservation] = Field(default_factory=list)
    scripts: list[ScriptObservation] = Field(default_factory=list)
    stylesheets: list[LinkTagObservation] = Field(default_factory=list)
    inline_style_count: int = 0
    inline_style_bytes: int = 0
    headings: list[HeadingObservation] = Field(default_factory=list)
    images: list[ImageObservation] = Field(default_factory=list)
    forms: list[FormObservation] = Field(default_factory=list)
    structured_data: list[StructuredDataBlock] = Field(default_factory=list)
    anchor_count: int = 0
    external_anchor_count: int = 0
    iframe_srcs: list[str] = Field(default_factory=list)
    svg_count: int = 0
    video_count: int = 0
    picture_count: int = 0
    noscript_count: int = 0
    noscript_text_length: int = 0
    landmark_roles: list[str] = Field(default_factory=list)
    element_count: int | None = None
    text_length: int | None = None
    html_bytes: int | None = None
    positive_tabindex_count: int | None = None

    def meta_by_name(self, name: str) -> MetaTagObservation | None:
        wanted = name.lower()
        return next((tag for tag in self.meta_tags if tag.name == wanted), None)

    def meta_by_property(self, prop: str) -> MetaTagObservation | None:
        wanted = prop.lower()
        return next((tag for tag in self.meta_tags if tag.property == wanted), None)

    def links_by_rel(self, rel: str) -> list[LinkTagObservation]:
        wanted = rel.lower()
        return [
            link
            for link in self.link_tags
            if link.rel and wanted in link.rel.lower().replace(",", " ").split()
        ]


# --- Phase 1 onwards -------------------------------------------------------------------
# The models below are filled by the browser collection stages. They are declared here so
# the evidence contract and the fixture format are stable from the start.


class RuntimeObservation(Observation):
    """Runtime signals read from the live page (read-only ``page.evaluate``)."""

    globals_present: list[str] = Field(default_factory=list)
    """Names of well-known global objects that exist. Values are never extracted."""
    service_worker_registered: bool | None = None
    module_script_count: int | None = None
    classic_script_count: int | None = None
    storage_keys: list[str] = Field(default_factory=list)
    """Key names only, never values."""
    wasm_requested: bool | None = None
    hydration_payload_keys: list[str] = Field(default_factory=list)


class StyleValueCount(Observation):
    value: str
    count: int


class StylePropertyDistribution(Observation):
    property: str
    values: list[StyleValueCount] = Field(default_factory=list)


class SampleCoverage(Observation):
    """How much of the page the style sample actually covers.

    Reported alongside every design finding: a claim about "the" border radius of a page
    means little without knowing it came from 1500 of 40000 elements.
    """

    elements_sampled: int
    elements_total: int | None = None
    cap_hit: bool = False


class StyleObservation(Observation):
    coverage: SampleCoverage
    distributions: list[StylePropertyDistribution] = Field(default_factory=list)
    loaded_fonts: list[str] = Field(default_factory=list)
    css_custom_properties: list[str] = Field(default_factory=list)
    media_query_breakpoints: list[str] = Field(default_factory=list)
    keyframe_count: int | None = None


class ViewportMetrics(Observation):
    width: int
    height: int
    document_scroll_width: int | None = None
    has_horizontal_overflow: bool | None = None
    body_font_size_px: float | None = None
    layout_columns_observed: int | None = None


class ConsoleMessage(Observation):
    level: str
    text: str
    location: str | None = None


class ScreenshotArtifact(Observation):
    label: str
    """``viewport`` or ``full_page``."""
    width: int
    height: int
    mime_type: str = "image/png"
    data_base64: str
