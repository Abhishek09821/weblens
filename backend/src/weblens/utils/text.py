"""Text handling for evidence excerpts.

Everything a target sends us is untrusted input that will end up in a JSON payload, a
React tree, and a Markdown table. Sanitizing once, here, at the point where evidence is
created, is the only place it can be done reliably.
"""

from __future__ import annotations

import re
import unicodedata

MAX_EXCERPT_CHARS = 400
TRUNCATION_MARKER = "…[truncated]"

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RUN = re.compile(r"\s+")


def sanitize_excerpt(value: str | None, limit: int = MAX_EXCERPT_CHARS) -> str | None:
    """Collapse whitespace, strip control characters, and hard-truncate.

    Control characters are removed rather than escaped because they carry no analytical
    value and are a terminal/log injection vector. Newlines collapse to spaces so an
    excerpt can never break out of a Markdown table row.
    """
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value)
    cleaned = _CONTROL_CHARS.sub("", normalized)
    collapsed = _WHITESPACE_RUN.sub(" ", cleaned).strip()
    if not collapsed:
        return None
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def slugify(value: str, *, max_length: int = 60) -> str:
    """Lowercase ``[a-z0-9.-]`` slug, used for finding ids and file names."""
    ascii_form = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9.-]+", "-", ascii_form).strip("-.").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length] or "unknown"


def text_length(value: str | None) -> int | None:
    """Grapheme-naive character count, or ``None`` when the value is absent.

    ``None`` and ``0`` mean different things (absent vs present-but-empty) and callers
    depend on that distinction, so this never coerces one into the other.
    """
    return None if value is None else len(value)
