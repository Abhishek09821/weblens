"""Transport-layer observations: target, HTTP, DNS, robots, TLS.

These models are what the collection layer fills in and what analyzers read. They are
Pydantic models (not dataclasses) so a whole ``RawEvidence`` tree can be dumped to JSON and
committed as a test fixture - that is what makes analyzers testable offline.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Observation(BaseModel):
    """Base for observation models: immutable and strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class TargetObservation(Observation):
    requested_url: str
    normalized_url: str
    scheme: str
    host: str
    port: int
    path: str


class DnsObservation(Observation):
    host: str
    resolved_ips: list[str] = Field(default_factory=list)
    resolution_ms: float | None = None
    error: str | None = None


class RobotsObservation(Observation):
    url: str
    fetched: bool
    status: int | None = None
    allowed: bool | None = None
    """``None`` when no verdict could be reached (fetch failed, or the file was unreadable).
    Distinct from ``True``: 'we checked and it is allowed' is not the same claim as
    'we could not check'."""
    matched_directive: str | None = None
    user_agent_group: str | None = None
    sitemaps: list[str] = Field(default_factory=list)
    error: str | None = None


class HeaderEntry(Observation):
    """One response header. Duplicates are preserved as separate entries.

    Collapsing duplicate headers loses information that matters (multiple ``Set-Cookie``
    lines, repeated ``Content-Security-Policy``), so the list keeps them intact.
    """

    name: str
    """Lowercased header name."""
    value: str


class CookieAttributes(Observation):
    """Cookie attributes observed from ``Set-Cookie``. Values are never captured."""

    name: str
    secure: bool
    http_only: bool
    same_site: str | None = None
    domain: str | None = None
    path: str | None = None
    max_age: int | None = None
    expires_present: bool = False
    persistent: bool = False
    source_hop_url: str


class HttpHopObservation(Observation):
    """One response in the redirect chain."""

    url: str
    status: int
    http_version: str | None = None
    headers: list[HeaderEntry] = Field(default_factory=list)
    location: str | None = None
    elapsed_ms: float | None = None


class HttpObservation(Observation):
    """The HTTP exchange for the main document, before any JavaScript runs."""

    hops: list[HttpHopObservation] = Field(default_factory=list)
    final_url: str
    status: int
    http_version: str | None = None
    headers: list[HeaderEntry] = Field(default_factory=list)
    cookies: list[CookieAttributes] = Field(default_factory=list)
    content_type: str | None = None
    charset: str | None = None
    body_text: str | None = None
    body_bytes: int | None = None
    body_truncated: bool = False
    elapsed_ms: float | None = None
    http_origin_redirects_to_https: bool | None = None
    """Result of the optional single HEAD probe of the ``http://`` origin.
    ``None`` means the probe did not run, which keeps rule TLS-02 out of the score."""
    http_origin_redirect_status: int | None = None

    def header(self, name: str) -> str | None:
        """Case-insensitive lookup. Duplicates are joined with ``", "`` per RFC 9110."""
        wanted = name.lower()
        values = [entry.value for entry in self.headers if entry.name == wanted]
        return ", ".join(values) if values else None

    def header_values(self, name: str) -> list[str]:
        wanted = name.lower()
        return [entry.value for entry in self.headers if entry.name == wanted]

    def has_header(self, name: str) -> bool:
        wanted = name.lower()
        return any(entry.name == wanted for entry in self.headers)


class CertificateObservation(Observation):
    subject_common_name: str | None = None
    issuer_common_name: str | None = None
    issuer_organization: str | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None
    days_until_expiry: int | None = None
    subject_alt_name_count: int | None = None
    is_currently_valid: bool | None = None


class TlsObservation(Observation):
    """One negotiated connection. Not a cipher-suite or chain audit (see L-SEC-03)."""

    host: str
    port: int
    protocol: str | None = None
    cipher_name: str | None = None
    cipher_bits: int | None = None
    certificate: CertificateObservation | None = None
    error: str | None = None
