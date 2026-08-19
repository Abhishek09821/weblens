"""Target normalization and the network guard.

WebLens accepts a URL from an unauthenticated caller and fetches it, which makes this module
the most security-relevant code in the backend. Two rules shape it:

1. **Resolve first, then judge.** Host names are resolved to addresses before any connection,
   and every resolved address must be publicly routable. Checking the string form of a host is
   not enough - ``http://2130706433/``, ``http://0x7f.1/``, ``http://localtest.me/`` and a DNS
   record pointing at ``169.254.169.254`` all look fine as text and all resolve somewhere they
   must not reach.
2. **Re-check every hop.** A public host is allowed to redirect, and a redirect to an internal
   address is exactly the attack this guard exists to stop, so each hop is validated again.

The fetched URL and the stored URL are deliberately different objects: ``fetch_url`` keeps the
query string as given (or we would be scanning a different page), while ``display_url`` is
redacted and is the only form that reaches evidence, results, logs, or reports.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from weblens.config import Settings
from weblens.domain.errors import DnsFailureError, TargetBlockedError, TargetValidationError
from weblens.logging import get_logger
from weblens.utils.urls import default_port, redact_url

logger = get_logger(__name__)

_ASCII_HOST = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")
_FORBIDDEN_IN_URL = re.compile(r"[\s\x00-\x1f\x7f]")
ALLOWED_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class NormalizedTarget:
    """A validated, resolved target."""

    requested_url: str
    """As submitted, redacted. Safe to store and display."""
    fetch_url: str
    """What we actually request. May contain credentials-in-query; never persisted."""
    display_url: str
    """Normalized and redacted. This is what goes into evidence and results."""
    scheme: str
    host: str
    port: int
    path: str
    resolved_ips: tuple[str, ...]

    @property
    def origin(self) -> str:
        if self.port == default_port(self.scheme):
            return f"{self.scheme}://{self.host}"
        return f"{self.scheme}://{self.host}:{self.port}"


class Resolver(Protocol):
    """Injected so the guard's decision table can be tested without DNS."""

    async def resolve(self, host: str) -> list[str]: ...


class SystemResolver:
    async def resolve(self, host: str) -> list[str]:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        # dict.fromkeys preserves resolution order while de-duplicating.
        return list(dict.fromkeys(str(info[4][0]) for info in infos))


class TargetGuard:
    def __init__(self, settings: Settings, resolver: Resolver | None = None) -> None:
        self._settings = settings
        self._resolver = resolver or SystemResolver()

    # --- public API --------------------------------------------------------------------

    async def prepare(self, raw_url: str) -> NormalizedTarget:
        """Normalize, resolve, and guard a submitted URL."""
        scheme, host, port, path, query = self._parse(raw_url)
        ips = await self._resolve_and_check(host)
        fetch_url = urlunsplit((scheme, self._netloc(host, port, scheme), path, query, ""))
        return NormalizedTarget(
            requested_url=redact_url(raw_url.strip()),
            fetch_url=fetch_url,
            display_url=redact_url(fetch_url),
            scheme=scheme,
            host=host,
            port=port,
            path=path,
            resolved_ips=tuple(ips),
        )

    async def validate_hop(self, url: str) -> None:
        """Validate a redirect target before following it."""
        scheme, host, _port, _path, _query = self._parse(url)
        del scheme
        await self._resolve_and_check(host)

    # --- normalization ----------------------------------------------------------------

    def _parse(self, raw_url: str) -> tuple[str, str, int, str, str]:
        candidate = raw_url.strip()
        if not candidate:
            raise TargetValidationError("No URL was provided.")
        if _FORBIDDEN_IN_URL.search(candidate):
            raise TargetValidationError("The URL contains whitespace or control characters.")
        if "://" not in candidate:
            # A bare host is the common case in a URL box; assume HTTPS and say so.
            candidate = f"https://{candidate}"

        try:
            parts = urlsplit(candidate)
        except ValueError as exc:
            raise TargetValidationError(f"The URL could not be parsed: {exc}") from exc

        scheme = parts.scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise TargetValidationError(
                f"Scheme '{scheme}' is not supported. Use http:// or https://."
            )
        if parts.username or parts.password:
            raise TargetValidationError(
                "URLs containing credentials are not accepted. Remove the user:password part."
            )

        raw_host = parts.hostname
        if not raw_host:
            raise TargetValidationError("The URL has no host name.")
        host = self._normalize_host(raw_host)

        try:
            port = parts.port or default_port(scheme)
        except ValueError as exc:
            raise TargetValidationError("The URL has an invalid port.") from exc
        if port not in self._settings.allowed_ports:
            allowed = ", ".join(str(value) for value in sorted(self._settings.allowed_ports))
            raise TargetValidationError(f"Port {port} is not allowed. Allowed ports: {allowed}.")

        path = parts.path or "/"
        return scheme, host, port, path, parts.query

    def _normalize_host(self, raw_host: str) -> str:
        host = raw_host.strip().rstrip(".").lower()
        if not host:
            raise TargetValidationError("The URL has no host name.")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        if _is_ip_literal(host):
            return host
        if not host.isascii():
            try:
                host = host.encode("idna").decode("ascii")
            except (UnicodeError, UnicodeDecodeError) as exc:
                raise TargetValidationError(
                    "The host name could not be converted to punycode."
                ) from exc
        if not _ASCII_HOST.match(host):
            raise TargetValidationError(f"The host name '{host}' is not valid.")
        if "." not in host:
            # Single-label hosts are internal names ('localhost', 'intranet'), not public sites.
            raise TargetValidationError(
                f"'{host}' is not a public host name. Use a fully qualified domain name."
            )
        return host

    @staticmethod
    def _netloc(host: str, port: int, scheme: str) -> str:
        bracketed = f"[{host}]" if _is_ipv6_literal(host) else host
        if port == default_port(scheme):
            return bracketed
        return f"{bracketed}:{port}"

    # --- resolution and address policy ------------------------------------------------

    async def _resolve_and_check(self, host: str) -> list[str]:
        if _is_ip_literal(host):
            addresses = [host]
        else:
            try:
                addresses = await self._resolver.resolve(host)
            except OSError as exc:
                raise DnsFailureError(
                    f"'{host}' could not be resolved ({exc.strerror or exc})."
                ) from exc
            if not addresses:
                raise DnsFailureError(f"'{host}' did not resolve to any address.")

        if self._settings.allow_private_targets:
            logger.warning("target guard bypassed by allow_private_targets", extra={"host": host})
            return addresses

        for address in addresses:
            if reason := blocked_reason(address):
                raise TargetBlockedError(
                    f"'{host}' resolves to {address}, which is in a blocked range ({reason})."
                )
        return addresses


def blocked_reason(address: str) -> str | None:
    """Return why an address is not scannable, or ``None`` when it is publicly routable."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return "unparseable address"

    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return blocked_reason(str(ip.ipv4_mapped))
        if ip.sixtofour is not None:
            return blocked_reason(str(ip.sixtofour))

    if ip.is_unspecified:
        return "unspecified"
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        # 169.254.0.0/16 covers the cloud instance metadata endpoints.
        return "link-local"
    if ip.is_multicast:
        return "multicast"
    if _is_cgnat(ip):
        # 100.64.0.0/10 is carrier-grade NAT space. Python does not classify it as private,
        # so checking it explicitly keeps the rejection message accurate.
        return "shared address space (CGNAT)"
    if ip.is_private:
        return "private"
    if ip.is_reserved:
        return "reserved"
    if not ip.is_global:
        return "not globally routable"
    return None


_CGNAT_V4 = ipaddress.ip_network("100.64.0.0/10")


def _is_cgnat(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_V4


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _is_ipv6_literal(host: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(host), ipaddress.IPv6Address)
    except ValueError:
        return False
