"""Collection unit tests: robots parsing, HTML inventory, URL redaction, ULIDs."""

from __future__ import annotations

import pytest

from weblens.collection.robots import RobotsPolicy
from weblens.collection.static_html import parse_static_html
from weblens.utils.ids import is_ulid, new_ulid
from weblens.utils.text import sanitize_excerpt, slugify
from weblens.utils.urls import is_same_origin, origin_of, redact_url

# --- robots -----------------------------------------------------------------------------

ROBOTS = """
# comment
User-agent: *
Disallow: /private
Disallow: /tmp/*.json$
Allow: /private/public

User-agent: weblens
Disallow: /no-weblens

Sitemap: https://example.test/sitemap.xml
"""


@pytest.mark.parametrize(
    ("path", "agent", "expected"),
    [
        ("/", "weblens", True),
        ("/no-weblens", "weblens", False),
        ("/private", "weblens", True),  # our own group replaces the wildcard group entirely
        ("/private", "othercrawler", False),
        ("/private/public", "othercrawler", True),
        ("/tmp/data.json", "othercrawler", False),
        ("/tmp/data.txt", "othercrawler", True),
    ],
)
def test_robots_evaluation(path: str, agent: str, expected: bool) -> None:
    allowed, _directive, _group = RobotsPolicy.parse(ROBOTS).evaluate(path, agent)
    assert allowed is expected


def test_robots_collects_sitemaps() -> None:
    assert RobotsPolicy.parse(ROBOTS).sitemaps == ["https://example.test/sitemap.xml"]


def test_empty_disallow_permits_everything() -> None:
    allowed, directive, _ = RobotsPolicy.parse("User-agent: *\nDisallow:").evaluate("/anything")
    assert allowed is True
    assert directive is None


def test_empty_robots_file_permits_everything() -> None:
    allowed, _, _ = RobotsPolicy.parse("").evaluate("/anything")
    assert allowed is True


def test_html_served_instead_of_robots_is_not_mistaken_for_rules() -> None:
    """Many hosts return an HTML error page for /robots.txt. It must yield no rules."""
    policy = RobotsPolicy.parse("<!doctype html><html><body>404</body></html>")
    allowed, directive, _ = policy.evaluate("/private")
    assert allowed is True
    assert directive is None


def test_longest_match_wins_and_allow_breaks_ties() -> None:
    policy = RobotsPolicy.parse("User-agent: *\nDisallow: /a\nAllow: /a\n")
    allowed, _, _ = policy.evaluate("/a")
    assert allowed is True


# --- static HTML inventory ---------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en" dir="ltr"><head><meta charset="utf-8">
<title>  Inventory  </title>
<script src="/app.js" type="module" integrity="sha384-abc" crossorigin="anonymous"></script>
<script>window.x = 1;</script>
<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>
<script type="application/ld+json">{ not json }</script>
<link rel="stylesheet" href="/style.css">
<style>.a{color:red}</style>
</head>
<body>
<header><nav><a href="/a">a</a><a href="https://other.test/b">b</a></nav></header>
<main>
  <h1>One</h1><h2>Two</h2>
  <img src="/x.png" alt="described"><img src="/y.png"><img src="/z.png" alt="">
  <form action="/submit" method="post">
    <input type="text" aria-label="Name"><input type="password">
  </form>
  <svg></svg><video></video><picture></picture>
  <iframe src="https://embed.test/f"></iframe>
  <div style="color:blue" tabindex="3">styled</div>
</main>
<noscript>Enable JavaScript</noscript>
</body></html>"""


def test_html_inventory() -> None:
    dom = parse_static_html(PAGE, "https://example.test/page")

    assert dom.title == "Inventory"
    assert dom.lang == "en"
    assert dom.dir == "ltr"
    assert dom.charset == "utf-8"

    scripts = dom.scripts
    assert len(scripts) == 4
    external = next(s for s in scripts if s.src)
    assert external.src == "https://example.test/app.js"
    assert external.module is True
    assert external.integrity == "sha384-abc"
    assert external.crossorigin == "anonymous"
    inline = next(s for s in scripts if s.src is None and s.type is None)
    assert inline.inline_length is not None
    assert inline.inline_length > 0

    assert len(dom.stylesheets) == 1
    assert dom.inline_style_count == 1  # the style="" attribute
    assert dom.inline_style_bytes > 0

    assert [h.level for h in dom.headings] == [1, 2]
    assert dom.anchor_count == 2
    assert dom.external_anchor_count == 1
    assert dom.svg_count == 1
    assert dom.video_count == 1
    assert dom.picture_count == 1
    assert dom.noscript_count == 1
    assert dom.noscript_text_length > 0
    assert dom.iframe_srcs == ["https://embed.test/f"]
    assert dom.positive_tabindex_count == 1
    assert {"banner", "navigation", "main"} <= set(dom.landmark_roles)


def test_alt_absent_and_empty_are_distinguished() -> None:
    """An empty alt is a decision; a missing alt is an omission. Never conflate them."""
    dom = parse_static_html(PAGE, "https://example.test/")
    described, missing, decorative = dom.images
    assert (described.alt_present, described.alt) == (True, "described")
    assert (missing.alt_present, missing.alt) == (False, None)
    assert (decorative.alt_present, decorative.alt) == (True, "")


def test_form_inventory() -> None:
    dom = parse_static_html(PAGE, "https://example.test/")
    form = dom.forms[0]
    assert form.action == "https://example.test/submit"
    assert form.method == "post"
    assert form.input_count == 2
    assert form.labelled_input_count == 1
    assert form.has_password_input is True


def test_structured_data_validity_is_reported_per_block() -> None:
    dom = parse_static_html(PAGE, "https://example.test/")
    json_ld = [block for block in dom.structured_data if block.format == "json-ld"]
    assert len(json_ld) == 2
    assert json_ld[0].valid is True
    assert json_ld[0].types == ["Organization"]
    assert json_ld[1].valid is False
    assert json_ld[1].parse_error


def test_malformed_html_does_not_raise() -> None:
    dom = parse_static_html("<html><head><title>unclosed", "https://example.test/")
    assert dom.title == "unclosed"


# --- redaction and helpers ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "must_not_contain"),
    [
        ("https://x.test/?access_token=abc123", "abc123"),
        ("https://x.test/?token=abc123", "abc123"),
        ("https://x.test/?api_key=abc123", "abc123"),
        ("https://x.test/?signature=abc123", "abc123"),
        ("https://x.test/?password=abc123", "abc123"),
        ("https://user:pw@x.test/", "pw"),
    ],
)
def test_redaction(url: str, must_not_contain: str) -> None:
    assert must_not_contain not in redact_url(url)


def test_redaction_preserves_harmless_parameters() -> None:
    assert redact_url("https://x.test/?page=2&sort=asc") == "https://x.test/?page=2&sort=asc"


def test_origin_helpers() -> None:
    assert origin_of("https://x.test:443/a") == "https://x.test"
    assert origin_of("https://x.test:8443/a") == "https://x.test:8443"
    assert is_same_origin("https://x.test/a", "https://x.test/b") is True
    assert is_same_origin("https://x.test/a", "http://x.test/a") is False


def test_ulids_are_sortable_and_valid() -> None:
    earlier = new_ulid(now_ms=1_700_000_000_000)
    later = new_ulid(now_ms=1_700_000_001_000)
    assert earlier < later
    assert is_ulid(earlier)
    assert not is_ulid("nope")
    assert not is_ulid("")
    assert len({new_ulid() for _ in range(500)}) == 500


def test_text_helpers() -> None:
    assert sanitize_excerpt("  a\n\tb  ") == "a b"
    assert sanitize_excerpt("") is None
    assert sanitize_excerpt(None) is None
    assert slugify("Hello, World!") == "hello-world"
