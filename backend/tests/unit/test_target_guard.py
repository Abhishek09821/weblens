"""Target guard decision table.

This is the highest-value test file in the backend: the guard is what stops an unauthenticated
API that fetches arbitrary URLs from becoming an internal network probe. DNS is stubbed so the
whole table runs offline and deterministically.
"""

from __future__ import annotations

import pytest

from tests.conftest import StubResolver
from weblens.collection.target import TargetGuard, blocked_reason
from weblens.config import Settings
from weblens.domain.errors import DnsFailureError, TargetBlockedError, TargetValidationError

PUBLIC_IP = "93.184.216.34"

RESOLUTIONS = {
    "example.com": [PUBLIC_IP],
    "public.example": [PUBLIC_IP],
    "internal.example": ["10.0.0.5"],
    "loopback.example": ["127.0.0.1"],
    "metadata.example": ["169.254.169.254"],
    "cgnat.example": ["100.64.1.1"],
    "mapped.example": ["::ffff:127.0.0.1"],
    "ipv6-loopback.example": ["::1"],
    "multi.example": [PUBLIC_IP, "192.168.1.1"],
    "xn--bcher-kva.example": [PUBLIC_IP],
    "decimal.example": ["127.0.0.1"],
}


def make_guard(**overrides: object) -> TargetGuard:
    settings = Settings(**overrides)  # type: ignore[arg-type]
    return TargetGuard(settings, resolver=StubResolver(RESOLUTIONS))


# --- normalization ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com/"),
        ("  example.com  ", "https://example.com/"),
        ("http://example.com", "http://example.com/"),
        ("https://example.com", "https://example.com/"),
        ("https://example.com/path?a=1", "https://example.com/path?a=1"),
        ("https://EXAMPLE.com/", "https://example.com/"),
        ("https://example.com./", "https://example.com/"),
        ("https://example.com:443/", "https://example.com/"),
        ("http://example.com:80/", "http://example.com/"),
        ("https://example.com/#fragment", "https://example.com/"),
    ],
)
async def test_normalizes_url(raw: str, expected: str) -> None:
    target = await make_guard().prepare(raw)
    assert target.fetch_url == expected


async def test_bare_host_assumes_https() -> None:
    target = await make_guard().prepare("example.com")
    assert target.scheme == "https"
    assert target.port == 443


async def test_punycode_conversion() -> None:
    target = await make_guard().prepare("https://bücher.example/")
    assert target.host == "xn--bcher-kva.example"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:pass@example.com/",
        "https://example.com:22/",
        "https://localhost/",
        "https://intranet/",
        "https://example.com\n/evil",
        "https://exa mple.com/",
        "https:///nohost",
    ],
)
async def test_rejects_invalid_urls(raw: str) -> None:
    with pytest.raises(TargetValidationError):
        await make_guard().prepare(raw)


async def test_extra_port_can_be_allowed() -> None:
    guard = make_guard(allowed_extra_ports=[8443])
    target = await guard.prepare("https://example.com:8443/")
    assert target.port == 8443


# --- address policy --------------------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "internal.example",
        "loopback.example",
        "metadata.example",
        "cgnat.example",
        "mapped.example",
        "ipv6-loopback.example",
        "decimal.example",
    ],
)
async def test_blocks_non_public_resolutions(host: str) -> None:
    with pytest.raises(TargetBlockedError):
        await make_guard().prepare(f"https://{host}/")


async def test_blocks_when_any_resolved_address_is_private() -> None:
    """A host that resolves to both a public and a private address is not scannable.

    Which address a connection actually uses is not ours to predict, so the safe reading is
    that any private answer disqualifies the host.
    """
    with pytest.raises(TargetBlockedError):
        await make_guard().prepare("https://multi.example/")


@pytest.mark.parametrize(
    "literal",
    [
        "https://127.0.0.1/",
        "https://10.1.2.3/",
        "https://192.168.0.1/",
        "https://169.254.169.254/",
        "https://[::1]/",
        "https://0.0.0.0/",
    ],
)
async def test_blocks_ip_literals(literal: str) -> None:
    with pytest.raises(TargetBlockedError):
        await make_guard().prepare(literal)


async def test_allows_public_ip_literal() -> None:
    target = await make_guard().prepare(f"https://{PUBLIC_IP}/")
    assert target.host == PUBLIC_IP


async def test_dns_failure_is_reported_as_such() -> None:
    with pytest.raises(DnsFailureError):
        await make_guard().prepare("https://nonexistent.example/")


async def test_allow_private_targets_override() -> None:
    """The test-only escape hatch must work, and must be off by default."""
    assert Settings().allow_private_targets is False
    guard = make_guard(allow_private_targets=True)
    target = await guard.prepare("https://loopback.example/")
    assert target.resolved_ips == ("127.0.0.1",)


async def test_redirect_hop_is_revalidated() -> None:
    """A public host redirecting inward is the attack this guard exists to stop."""
    guard = make_guard()
    await guard.validate_hop("https://public.example/")
    with pytest.raises(TargetBlockedError):
        await guard.validate_hop("https://loopback.example/")


@pytest.mark.parametrize(
    ("address", "expected_reason"),
    [
        (PUBLIC_IP, None),
        ("127.0.0.1", "loopback"),
        ("10.0.0.1", "private"),
        ("172.16.0.1", "private"),
        ("192.168.1.1", "private"),
        ("169.254.169.254", "link-local"),
        ("100.64.0.1", "shared address space (CGNAT)"),
        ("224.0.0.1", "multicast"),
        ("0.0.0.0", "unspecified"),
        ("::1", "loopback"),
        ("fe80::1", "link-local"),
        ("::ffff:10.0.0.1", "private"),
        ("not-an-ip", "unparseable address"),
    ],
)
def test_blocked_reason_table(address: str, expected_reason: str | None) -> None:
    assert blocked_reason(address) == expected_reason


# --- redaction --------------------------------------------------------------------------


async def test_display_url_is_redacted_but_fetch_url_is_not() -> None:
    """We must fetch the URL as given, and store only a redacted form.

    Redacting the fetch URL would scan a different page; storing the raw one would persist a
    credential into evidence, results, and downloadable reports.
    """
    guard = make_guard()
    target = await guard.prepare("https://example.com/api?access_token=supersecret&page=2")
    assert "supersecret" in target.fetch_url
    assert "supersecret" not in target.display_url
    assert "supersecret" not in target.requested_url
    assert "page=2" in target.display_url
