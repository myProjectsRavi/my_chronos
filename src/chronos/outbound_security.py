"""Validation helpers for operator-configured outbound HTTPS endpoints.

These helpers are intentionally narrower than the untrusted webhook delivery
boundary in :mod:`chronos.webhooks`. Public webhook URLs require DNS resolution
and connection pinning there. This module is for destinations explicitly chosen
by the CHRONOS operator, such as telemetry and an experimental plugin registry.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from urllib.parse import urlsplit


def _normalized_allowed_hosts(hosts: Iterable[str] | None) -> set[str] | None:
    if hosts is None:
        return None
    return {host.strip().lower().rstrip(".") for host in hosts if host.strip()}


def validate_operator_https_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] | None = None,
) -> str:
    """Validate an operator-configured HTTPS destination.

    The URL must use HTTPS, contain no embedded credentials or fragment, and
    must not target localhost or a literal non-global IP address. Callers may
    additionally supply an exact hostname allowlist.

    This function does not claim to pin DNS. It must not be used as the sole
    SSRF boundary for URLs supplied by untrusted remote users; use the pinned
    webhook transport in ``chronos.webhooks`` for that threat model.
    """

    candidate = url.strip()
    if not candidate:
        raise ValueError("Outbound URL cannot be empty")

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "https":
        raise ValueError("Outbound URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Outbound URL must not contain embedded credentials")
    if parsed.fragment:
        raise ValueError("Outbound URL fragments are not allowed")

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError("Outbound URL must include a hostname")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local outbound destinations are not allowed")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Outbound destination must be a globally routable address")

    normalized_allowed = _normalized_allowed_hosts(allowed_hosts)
    if normalized_allowed is not None:
        if not normalized_allowed:
            raise ValueError("Outbound destination allowlist is empty")
        if host not in normalized_allowed:
            raise ValueError("Outbound destination is not in the configured allowlist")

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Outbound URL contains an invalid port") from exc

    return candidate
