"""SSRF-oriented URL host checks for outbound fetches.

Blocks loopback, private, link-local, multicast, reserved, and well-known
cloud-metadata hostnames. Literal IP hosts are classified with
:mod:`ipaddress`; hostname strings in the blocklist (and ``*.localhost``)
are rejected without DNS lookup so unit tests stay offline.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata",
        "metadata.google.internal",
    }
)


class BlockedURLError(ValueError):
    """Raised when a URL targets a disallowed scheme or private/metadata host."""


def is_blocked_url_host(host: str) -> bool:
    """Return True for loopback/private/link-local/metadata hosts."""
    name = host.strip().lower().rstrip(".")
    if not name:
        return True
    if name in BLOCKED_HOSTNAMES or name.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_http_url_allowed(url: str) -> None:
    """Raise :class:`BlockedURLError` if *url* is not a safe http(s) target."""
    if "\x00" in url:
        raise BlockedURLError("URL contains a null byte")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise BlockedURLError(f"Disallowed URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise BlockedURLError("URL must include a host")
    if is_blocked_url_host(host):
        raise BlockedURLError(f"URL host is not allowed: {host!r}")
