"""DOM inventory from the served HTML.

Phase 0 fills the DOM evidence slot from the HTML as delivered, marked
``source = static_html``. Phase 1 replaces this with the rendered DOM
(``source = rendered_dom``) from Playwright. Both fill the same model, and the ``source``
field is what lets an analyzer say "observed in the served HTML" instead of implying it saw
the rendered page.

Built on :mod:`html.parser` from the standard library. A tolerant tree-building parser would
be nicer for deeply broken markup, but this is an inventory pass over head/meta/link/script
plus counts, which a streaming parser handles fine, and it avoids a dependency.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from urllib.parse import urljoin

from weblens.domain.enums import DomSource
from weblens.domain.observations import (
    DomObservation,
    FormObservation,
    HeadingObservation,
    ImageObservation,
    LinkTagObservation,
    MetaTagObservation,
    ScriptObservation,
    StructuredDataBlock,
)
from weblens.utils.text import sanitize_excerpt
from weblens.utils.urls import host_of

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_LANDMARK_TAGS = {
    "header": "banner",
    "nav": "navigation",
    "main": "main",
    "footer": "contentinfo",
    "aside": "complementary",
    "form": "form",
    "section": "region",
}
_MAX_HEADING_TEXT = 200
_MAX_HEADINGS = 100
_MAX_IMAGES = 300
_MAX_TRACKED_TEXT = 2_000_000

Attrs = list[tuple[str, str | None]]


class _InventoryParser(HTMLParser):
    """Single pass over the document, accumulating an inventory."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title: str | None = None
        self.lang: str | None = None
        self.dir: str | None = None
        self.charset: str | None = None
        self.meta_tags: list[MetaTagObservation] = []
        self.link_tags: list[LinkTagObservation] = []
        self.stylesheets: list[LinkTagObservation] = []
        self.scripts: list[ScriptObservation] = []
        self.headings: list[HeadingObservation] = []
        self.images: list[ImageObservation] = []
        self.forms: list[FormObservation] = []
        self.structured_data: list[StructuredDataBlock] = []
        self.iframe_srcs: list[str] = []
        self.landmark_roles: set[str] = set()
        self.anchor_count = 0
        self.external_anchor_count = 0
        self.svg_count = 0
        self.video_count = 0
        self.picture_count = 0
        self.noscript_count = 0
        self.noscript_text_length = 0
        self.inline_style_count = 0
        self.inline_style_bytes = 0
        self.element_count = 0
        self.text_length = 0
        self.positive_tabindex_count = 0
        self.has_microdata = False
        self.has_rdfa = False

        self._base_host = host_of(base_url)
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._heading_level = 0
        self._current_script: ScriptObservation | None = None
        self._script_is_json_ld = False
        self._form_stack: list[FormObservation] = []
        self._in_noscript = False

    # --- HTMLParser hooks --------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: Attrs) -> None:
        self.element_count += 1
        attributes = {key.lower(): (value or "") for key, value in attrs}

        if "itemscope" in attributes or "itemtype" in attributes:
            self.has_microdata = True
        if "vocab" in attributes or "typeof" in attributes:
            self.has_rdfa = True
        if role := attributes.get("role"):
            self.landmark_roles.add(role.strip().lower())
        if landmark := _LANDMARK_TAGS.get(tag):
            self.landmark_roles.add(landmark)
        if tabindex := attributes.get("tabindex"):
            try:
                if int(tabindex) > 0:
                    self.positive_tabindex_count += 1
            except ValueError:
                pass
        if "style" in attributes:
            self.inline_style_count += 1
            self.inline_style_bytes += len(attributes["style"])

        handler = getattr(self, f"_start_{tag}", None)
        if handler is not None:
            handler(attributes)
        elif tag in _HEADING_TAGS:
            self._start_heading(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._capture == "title":
            self.title = self._flush()
        elif tag in _HEADING_TAGS and self._capture == "heading":
            text = self._flush()
            if len(self.headings) < _MAX_HEADINGS:
                self.headings.append(
                    HeadingObservation(
                        level=self._heading_level,
                        text=sanitize_excerpt(text, limit=_MAX_HEADING_TEXT),
                    )
                )
        elif tag == "script":
            self._finish_script()
        elif tag == "style" and self._capture == "style":
            self.inline_style_bytes += len(self._flush() or "")
        elif tag == "form" and self._form_stack:
            self.forms.append(self._form_stack.pop())
        elif tag == "noscript":
            self._in_noscript = False

    def finalize(self) -> None:
        """Flush captures left open by unclosed tags.

        Truncated or malformed markup is common in the wild. Losing a title because the document
        never closed the tag would be reported as "no title", which is a lie about the page.
        """
        if self._capture == "title" and self.title is None:
            self.title = self._flush()
        elif self._capture == "heading":
            text = self._flush()
            if text and len(self.headings) < _MAX_HEADINGS:
                self.headings.append(
                    HeadingObservation(
                        level=self._heading_level,
                        text=sanitize_excerpt(text, limit=_MAX_HEADING_TEXT),
                    )
                )
        elif self._current_script is not None:
            self._finish_script()
        while self._form_stack:
            self.forms.append(self._form_stack.pop())

    def handle_data(self, data: str) -> None:
        if self.text_length < _MAX_TRACKED_TEXT:
            self.text_length += len(data.strip())
        if self._in_noscript:
            self.noscript_text_length += len(data.strip())
        if self._capture is not None:
            self._buffer.append(data)

    # --- per-tag handling --------------------------------------------------------------

    def _start_html(self, attributes: dict[str, str]) -> None:
        self.lang = attributes.get("lang") or None
        self.dir = attributes.get("dir") or None

    def _start_title(self, attributes: dict[str, str]) -> None:
        del attributes
        if self.title is None:
            self._begin("title")

    def _start_meta(self, attributes: dict[str, str]) -> None:
        if charset := attributes.get("charset"):
            self.charset = charset.strip().lower()
        self.meta_tags.append(
            MetaTagObservation(
                name=_lower_or_none(attributes.get("name")),
                property=_lower_or_none(attributes.get("property")),
                http_equiv=_lower_or_none(attributes.get("http-equiv")),
                charset=_lower_or_none(attributes.get("charset")),
                content=attributes.get("content"),
            )
        )

    def _start_link(self, attributes: dict[str, str]) -> None:
        observation = LinkTagObservation(
            rel=_lower_or_none(attributes.get("rel")),
            href=self._absolute(attributes.get("href")),
            hreflang=attributes.get("hreflang"),
            type=_lower_or_none(attributes.get("type")),
            sizes=attributes.get("sizes"),
            integrity=attributes.get("integrity"),
            crossorigin=attributes.get("crossorigin"),
        )
        self.link_tags.append(observation)
        rel_tokens = (observation.rel or "").replace(",", " ").split()
        if "stylesheet" in rel_tokens:
            self.stylesheets.append(observation)

    def _start_script(self, attributes: dict[str, str]) -> None:
        script_type = _lower_or_none(attributes.get("type"))
        self._current_script = ScriptObservation(
            src=self._absolute(attributes.get("src")),
            type=script_type,
            module=script_type == "module",
            integrity=attributes.get("integrity"),
            crossorigin=attributes.get("crossorigin"),
            is_async="async" in attributes,
            defer="defer" in attributes,
        )
        self._script_is_json_ld = script_type == "application/ld+json"
        if self._current_script.src is None:
            self._begin("script")

    def _start_style(self, attributes: dict[str, str]) -> None:
        del attributes
        self._begin("style")

    def _start_a(self, attributes: dict[str, str]) -> None:
        self.anchor_count += 1
        href = attributes.get("href")
        if not href or not self._base_host:
            return
        host = host_of(urljoin(self.base_url, href))
        if host and host != self._base_host:
            self.external_anchor_count += 1

    def _start_img(self, attributes: dict[str, str]) -> None:
        if len(self.images) >= _MAX_IMAGES:
            return
        alt_present = "alt" in attributes
        self.images.append(
            ImageObservation(
                src=self._absolute(attributes.get("src")),
                alt=attributes.get("alt") if alt_present else None,
                alt_present=alt_present,
                loading=_lower_or_none(attributes.get("loading")),
                width_attr=attributes.get("width"),
                height_attr=attributes.get("height"),
            )
        )

    def _start_form(self, attributes: dict[str, str]) -> None:
        self._form_stack.append(
            FormObservation(
                action=self._absolute(attributes.get("action")),
                method=_lower_or_none(attributes.get("method")) or "get",
            )
        )

    def _start_input(self, attributes: dict[str, str]) -> None:
        if not self._form_stack:
            return
        current = self._form_stack[-1]
        labelled = bool(attributes.get("aria-label") or attributes.get("aria-labelledby"))
        self._form_stack[-1] = current.model_copy(
            update={
                "input_count": current.input_count + 1,
                "labelled_input_count": current.labelled_input_count + (1 if labelled else 0),
                "has_password_input": current.has_password_input
                or attributes.get("type", "").lower() == "password",
            }
        )

    def _start_iframe(self, attributes: dict[str, str]) -> None:
        if src := self._absolute(attributes.get("src")):
            self.iframe_srcs.append(src)

    def _start_svg(self, attributes: dict[str, str]) -> None:
        del attributes
        self.svg_count += 1

    def _start_video(self, attributes: dict[str, str]) -> None:
        del attributes
        self.video_count += 1

    def _start_picture(self, attributes: dict[str, str]) -> None:
        del attributes
        self.picture_count += 1

    def _start_noscript(self, attributes: dict[str, str]) -> None:
        del attributes
        self.noscript_count += 1
        self._in_noscript = True

    def _start_heading(self, tag: str) -> None:
        self._heading_level = int(tag[1])
        self._begin("heading")

    # --- helpers ----------------------------------------------------------------------

    def _begin(self, capture: str) -> None:
        self._capture = capture
        self._buffer = []

    def _flush(self) -> str | None:
        text = "".join(self._buffer).strip()
        self._capture = None
        self._buffer = []
        return text or None

    def _finish_script(self) -> None:
        script = self._current_script
        self._current_script = None
        if script is None:
            return
        inline = self._flush() if self._capture == "script" else None
        if inline is not None:
            script = script.model_copy(update={"inline_length": len(inline)})
        self.scripts.append(script)
        if self._script_is_json_ld and inline:
            self.structured_data.append(_parse_json_ld(inline))
        self._script_is_json_ld = False

    def _absolute(self, value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.strip()
        if not candidate or candidate.startswith(("javascript:", "data:")):
            return candidate or None
        try:
            return urljoin(self.base_url, candidate)
        except ValueError:
            return candidate


def parse_static_html(html: str, base_url: str) -> DomObservation:
    """Build a :class:`DomObservation` from the served HTML."""
    parser = _InventoryParser(base_url)
    parser.feed(html)
    parser.close()
    parser.finalize()

    structured = list(parser.structured_data)
    if parser.has_microdata:
        structured.append(StructuredDataBlock(format="microdata", types=[], valid=True))
    if parser.has_rdfa:
        structured.append(StructuredDataBlock(format="rdfa", types=[], valid=True))

    return DomObservation(
        source=DomSource.STATIC_HTML,
        title=parser.title,
        lang=parser.lang,
        dir=parser.dir,
        charset=parser.charset,
        meta_tags=parser.meta_tags,
        link_tags=parser.link_tags,
        scripts=parser.scripts,
        stylesheets=parser.stylesheets,
        inline_style_count=parser.inline_style_count,
        inline_style_bytes=parser.inline_style_bytes,
        headings=parser.headings,
        images=parser.images,
        forms=parser.forms,
        structured_data=structured,
        anchor_count=parser.anchor_count,
        external_anchor_count=parser.external_anchor_count,
        iframe_srcs=parser.iframe_srcs,
        svg_count=parser.svg_count,
        video_count=parser.video_count,
        picture_count=parser.picture_count,
        noscript_count=parser.noscript_count,
        noscript_text_length=parser.noscript_text_length,
        landmark_roles=sorted(parser.landmark_roles),
        element_count=parser.element_count,
        text_length=parser.text_length,
        html_bytes=len(html.encode("utf-8", errors="replace")),
        positive_tabindex_count=parser.positive_tabindex_count,
    )


def _parse_json_ld(raw: str) -> StructuredDataBlock:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return StructuredDataBlock(
            format="json-ld", types=[], valid=False, parse_error=str(exc)[:200], raw_length=len(raw)
        )
    return StructuredDataBlock(
        format="json-ld", types=_collect_types(payload), valid=True, raw_length=len(raw)
    )


def _collect_types(node: object, depth: int = 0) -> list[str]:
    """Collect ``@type`` values, including from ``@graph`` containers."""
    if depth > 6:
        return []
    found: list[str] = []
    if isinstance(node, dict):
        raw_type = node.get("@type")
        if isinstance(raw_type, str):
            found.append(raw_type)
        elif isinstance(raw_type, list):
            found.extend(item for item in raw_type if isinstance(item, str))
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                found.extend(_collect_types(node[key], depth + 1))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_types(item, depth + 1))
    return list(dict.fromkeys(found))


def _lower_or_none(value: str | None) -> str | None:
    return value.strip().lower() if value else None
