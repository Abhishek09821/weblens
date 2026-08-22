"""SEO metadata analyzer.

The Phase 0 pilot analyzer, and the reference implementation for the ones that follow.

The shape worth copying is the declarative field table: each observable property is described once,
with the reason to give when it is absent, and both the normal path and the degraded path are driven
from that single table. An earlier version listed the fields twice - once for findings, once for the
"evidence not collected" case - and keeping two lists in step by hand is precisely how a tool starts
silently omitting checks it claims to perform.

Also worth copying:

* every asserted finding carries an :class:`EvidenceRef` built by a shared factory;
* absence is a finding with a reason, not a gap in the output;
* when the DOM came from served HTML rather than a rendered page, that is recorded as a limitation
  on the findings it affects. Metadata injected by client-side JavaScript is invisible to that pass,
  and the report says so instead of implying the page has no title.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    attribute_evidence,
    element_evidence,
    meta_evidence,
)
from weblens.domain.enums import DomSource, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.findings import Finding, FindingValue
from weblens.domain.observations import DomObservation
from weblens.domain.sections import (
    HreflangEntry,
    KeyValueObservation,
    MetadataObservation,
    TechnologyPayload,
)
from weblens.utils.text import text_length

ANALYZER_ID = "seo.metadata"

CATEGORY_DOCUMENT = "document"
CATEGORY_SOCIAL = "social"
CATEGORY_INTERNATIONALIZATION = "internationalization"

STATIC_HTML_LIMITATION = (
    "Observed in the HTML as served. Metadata added by client-side JavaScript after load "
    "would not appear in this pass."
)

DEGRADED_REASON = "The document inventory was not collected, so metadata could not be read."

OPEN_GRAPH_PREFIX = "og:"
TWITTER_PREFIX = "twitter:"


@dataclass(frozen=True)
class _Observed:
    """What an extractor found, ready to become an asserted finding."""

    value: FindingValue
    evidence: list[EvidenceRef]
    values: list[str] = field(default_factory=list)
    unit: str | None = None
    details: dict[str, FindingValue | list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class _FieldSpec:
    """One observable property, described once."""

    slug: str
    category: str
    name: str
    absent_reason: str
    extract: Callable[[DomObservation, str | None], _Observed | None]


# --- extractors -------------------------------------------------------------------------


def _meta_content(dom: DomObservation, name: str) -> str | None:
    tag = dom.meta_by_name(name)
    if tag is None or tag.content is None:
        return None
    return tag.content.strip() or None


def _first_link_href(dom: DomObservation, rel: str) -> str | None:
    return next((link.href for link in dom.links_by_rel(rel) if link.href), None)


def _prefixed_properties(dom: DomObservation, prefix: str) -> list[KeyValueObservation]:
    return [
        KeyValueObservation(key=tag.property, value=tag.content)
        for tag in dom.meta_tags
        if tag.property and tag.property.startswith(prefix)
    ]


def _prefixed_names(dom: DomObservation, prefix: str) -> list[KeyValueObservation]:
    return [
        KeyValueObservation(key=tag.name, value=tag.content)
        for tag in dom.meta_tags
        if tag.name and tag.name.startswith(prefix)
    ]


def _hreflang(dom: DomObservation) -> list[HreflangEntry]:
    return [
        HreflangEntry(hreflang=link.hreflang, href=link.href)
        for link in dom.link_tags
        if link.hreflang
    ]


def _favicons(dom: DomObservation) -> list[str]:
    hrefs = [
        link.href
        for link in dom.link_tags
        if link.href
        and any("icon" in token for token in (link.rel or "").replace(",", " ").split())
    ]
    return list(dict.fromkeys(hrefs))


def _h1_texts(dom: DomObservation) -> list[str]:
    return [heading.text for heading in dom.headings if heading.level == 1 and heading.text]


def _text_meta(
    name: str, descriptor: str, *, with_length: bool = False
) -> Callable[[DomObservation, str | None], _Observed | None]:
    def extract(dom: DomObservation, url: str | None) -> _Observed | None:
        content = _meta_content(dom, name)
        if content is None:
            return None
        return _Observed(
            value=content,
            evidence=[meta_evidence(descriptor, content, url=url)],
            details={"length": text_length(content)} if with_length else {},
        )

    return extract


def _title(dom: DomObservation, url: str | None) -> _Observed | None:
    if not dom.title:
        return None
    return _Observed(
        value=dom.title,
        evidence=[element_evidence("title", dom.title, url=url)],
        details={"length": text_length(dom.title)},
    )


def _canonical(dom: DomObservation, url: str | None) -> _Observed | None:
    href = _first_link_href(dom, "canonical")
    if href is None:
        return None
    return _Observed(value=href, evidence=[element_evidence("link[rel=canonical]", href, url=url)])


def _headings(dom: DomObservation, url: str | None) -> _Observed | None:
    texts = _h1_texts(dom)
    if not texts:
        return None
    return _Observed(
        value=len(texts),
        unit="count",
        values=texts[:10],
        evidence=[element_evidence("headings[level=1]", texts[0], url=url)],
    )


def _favicon(dom: DomObservation, url: str | None) -> _Observed | None:
    hrefs = _favicons(dom)
    if not hrefs:
        return None
    return _Observed(
        value=len(hrefs),
        unit="count",
        values=hrefs[:10],
        evidence=[element_evidence("link[rel~=icon]", hrefs[0], url=url)],
    )


def _open_graph(dom: DomObservation, url: str | None) -> _Observed | None:
    tags = _prefixed_properties(dom, OPEN_GRAPH_PREFIX)
    if not tags:
        return None
    return _Observed(
        value=len(tags),
        unit="count",
        values=[tag.key for tag in tags],
        evidence=[meta_evidence(f"property={tags[0].key}", tags[0].value, url=url)],
    )


def _twitter(dom: DomObservation, url: str | None) -> _Observed | None:
    tags = _prefixed_names(dom, TWITTER_PREFIX)
    if not tags:
        return None
    return _Observed(
        value=len(tags),
        unit="count",
        values=[tag.key for tag in tags],
        evidence=[meta_evidence(f"name={tags[0].key}", tags[0].value, url=url)],
    )


def _lang(dom: DomObservation, url: str | None) -> _Observed | None:
    del url
    if not dom.lang:
        return None
    return _Observed(value=dom.lang, evidence=[attribute_evidence("html[lang]", dom.lang)])


def _alternates(dom: DomObservation, url: str | None) -> _Observed | None:
    entries = _hreflang(dom)
    if not entries:
        return None
    return _Observed(
        value=len(entries),
        unit="count",
        values=[entry.hreflang for entry in entries][:20],
        evidence=[element_evidence("link[rel=alternate][hreflang]", entries[0].href, url=url)],
    )


# --- the field table ---------------------------------------------------------------------

FIELD_SPECS: tuple[_FieldSpec, ...] = (
    _FieldSpec(
        "title",
        CATEGORY_DOCUMENT,
        "Document title",
        "No non-empty <title> element was present in the document.",
        _title,
    ),
    _FieldSpec(
        "meta-description",
        CATEGORY_DOCUMENT,
        "Meta description",
        'No <meta name="description"> with content was present.',
        _text_meta("description", "name=description", with_length=True),
    ),
    _FieldSpec(
        "canonical",
        CATEGORY_DOCUMENT,
        "Canonical URL",
        'No <link rel="canonical"> element was present.',
        _canonical,
    ),
    _FieldSpec(
        "robots-meta",
        CATEGORY_DOCUMENT,
        "Robots meta directive",
        'No <meta name="robots"> element was present. Crawlers apply their defaults when no '
        "directive is published.",
        _text_meta("robots", "name=robots"),
    ),
    _FieldSpec(
        "viewport-meta",
        CATEGORY_DOCUMENT,
        "Viewport meta tag",
        'No <meta name="viewport"> element was present.',
        _text_meta("viewport", "name=viewport"),
    ),
    _FieldSpec(
        "h1",
        CATEGORY_DOCUMENT,
        "Top-level headings (h1)",
        "No <h1> element with text content was present.",
        _headings,
    ),
    _FieldSpec(
        "favicon",
        CATEGORY_DOCUMENT,
        "Favicon declarations",
        "No icon <link> element was declared. A site may still serve /favicon.ico by convention, "
        "which this check does not request.",
        _favicon,
    ),
    _FieldSpec(
        "open-graph",
        CATEGORY_SOCIAL,
        "Open Graph metadata",
        'No <meta property="og:*"> tags were present.',
        _open_graph,
    ),
    _FieldSpec(
        "twitter-card",
        CATEGORY_SOCIAL,
        "Twitter card metadata",
        'No <meta name="twitter:*"> tags were present.',
        _twitter,
    ),
    _FieldSpec(
        "html-lang",
        CATEGORY_INTERNATIONALIZATION,
        "Document language",
        "The <html> element had no lang attribute.",
        _lang,
    ),
    _FieldSpec(
        "hreflang",
        CATEGORY_INTERNATIONALIZATION,
        "hreflang alternates",
        'No <link rel="alternate" hreflang> elements were present.',
        _alternates,
    ),
)


class SeoMetadataAnalyzer:
    """Reads document metadata from the DOM inventory."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        if dom is None:
            # Defensive: the pipeline skips analyzers whose required slots are missing, but an
            # analyzer must degrade rather than raise if called directly.
            return AnalyzerOutput(findings=self._degraded())

        limitations = [STATIC_HTML_LIMITATION] if dom.source is DomSource.STATIC_HTML else []
        page_url = ctx.evidence.http.final_url if ctx.evidence.http else None

        findings = [self._finding(spec, dom, page_url, limitations) for spec in FIELD_SPECS]

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(
                metadata=self._payload(dom),
                structured_data=list(dom.structured_data),
            ),
            limitations=limitations,
        )

    def _finding(
        self,
        spec: _FieldSpec,
        dom: DomObservation,
        page_url: str | None,
        limitations: list[str],
    ) -> Finding:
        observed = spec.extract(dom, page_url)
        if observed is None:
            return self._build.not_detected(
                spec.slug,
                category=spec.category,
                name=spec.name,
                reason=spec.absent_reason,
                limitations=limitations,
            )
        return self._build.detected(
            spec.slug,
            category=spec.category,
            name=spec.name,
            value=observed.value,
            values=observed.values,
            unit=observed.unit,
            details=observed.details,
            evidence=observed.evidence,
            limitations=limitations,
        )

    def _degraded(self) -> list[Finding]:
        """Same fields, reported as unverifiable. Driven by the same table as the normal path."""
        return [
            self._build.unable_to_verify(
                spec.slug, category=spec.category, name=spec.name, reason=DEGRADED_REASON
            )
            for spec in FIELD_SPECS
        ]

    def _payload(self, dom: DomObservation) -> MetadataObservation:
        description = _meta_content(dom, "description")
        return MetadataObservation(
            title=dom.title,
            title_length=text_length(dom.title),
            description=description,
            description_length=text_length(description),
            canonical=_first_link_href(dom, "canonical"),
            robots_meta=_meta_content(dom, "robots"),
            viewport_meta=_meta_content(dom, "viewport"),
            charset=dom.charset,
            lang=dom.lang,
            h1_texts=_h1_texts(dom)[:10],
            open_graph=_prefixed_properties(dom, OPEN_GRAPH_PREFIX),
            twitter=_prefixed_names(dom, TWITTER_PREFIX),
            hreflang=_hreflang(dom),
            favicons=_favicons(dom),
        )
