"""URL normalization, redaction, and origin comparison.

Redaction runs before any evidence object is constructed, so credentials that appear in a
query string never enter the evidence graph, the result payload, the logs, or a report.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from weblens.config import SENSITIVE_QUERY_PARAMS

REDACTED = "[REDACTED]"
DEFAULT_PORTS = {"http": 80, "https": 443}


def redact_url(url: str) -> str:
    """Replace sensitive query-parameter values and any userinfo component."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return REDACTED
    if not parts.query and "@" not in parts.netloc:
        return url

    netloc = parts.netloc
    if "@" in netloc:
        netloc = f"{REDACTED}@{netloc.rsplit('@', 1)[1]}"

    if parts.query:
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        redacted = [
            (key, REDACTED if key.lower() in SENSITIVE_QUERY_PARAMS else value)
            for key, value in pairs
        ]
        query = urlencode(redacted, safe="[]")
    else:
        query = parts.query

    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def default_port(scheme: str) -> int:
    return DEFAULT_PORTS.get(scheme.lower(), 443)


def origin_of(url: str) -> str | None:
    """``scheme://host[:port]`` with the default port omitted, or ``None`` if unparseable."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if not parts.scheme or not parts.hostname:
        return None
    port = parts.port
    if port is None or port == default_port(parts.scheme):
        return f"{parts.scheme}://{parts.hostname}"
    return f"{parts.scheme}://{parts.hostname}:{port}"


def host_of(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def is_same_origin(a: str, b: str) -> bool:
    origin_a, origin_b = origin_of(a), origin_of(b)
    return origin_a is not None and origin_a == origin_b


def registrable_suffix_match(host_a: str, host_b: str) -> bool:
    """True when two hosts share their last two labels.

    A deliberate approximation of "same site" that does not need a public suffix list.
    It is only used for coarse first-party/third-party grouping in the network ledger,
    never for a security judgement, and the approximation is documented in the finding
    that uses it.
    """
    labels_a = host_a.lower().rstrip(".").split(".")
    labels_b = host_b.lower().rstrip(".").split(".")
    if len(labels_a) < 2 or len(labels_b) < 2:
        return labels_a == labels_b
    return labels_a[-2:] == labels_b[-2:]


def is_http_scheme(url: str) -> bool:
    try:
        return urlsplit(url).scheme.lower() in ("http", "https")
    except ValueError:
        return False


def is_insecure_http(url: str) -> bool:
    """True only for an explicit ``http://`` URL (used for mixed-content observations)."""
    try:
        return urlsplit(url).scheme.lower() == "http"
    except ValueError:
        return False
