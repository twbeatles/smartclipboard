"""URL safety checks for remote title fetches."""

from __future__ import annotations

import ipaddress
import socket

from .cache import BLOCKED_TITLE_HOSTS


def resolve_title_fetch_host_ips(hostname: str, scheme: str) -> list[ipaddress._BaseAddress]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    default_port = 443 if scheme == "https" else 80
    resolved_ips: list[ipaddress._BaseAddress] = []
    seen: set[str] = set()
    addrinfo = socket.getaddrinfo(hostname, default_port, type=socket.SOCK_STREAM)
    for _family, _socktype, _proto, _canonname, sockaddr in addrinfo:
        if not sockaddr:
            continue
        host_value = str(sockaddr[0] or "").strip()
        if not host_value or host_value in seen:
            continue
        seen.add(host_value)
        resolved_ips.append(ipaddress.ip_address(host_value))
    return resolved_ips


def validate_title_fetch_url(url: str) -> tuple[bool, str]:
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "invalid url"

    if parsed.scheme not in {"http", "https"}:
        return False, "invalid scheme"

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "missing hostname"
    if hostname in BLOCKED_TITLE_HOSTS:
        return False, f"blocked metadata hostname: {hostname}"

    try:
        resolved_ips = resolve_title_fetch_host_ips(hostname, parsed.scheme)
    except (socket.gaierror, TypeError, ValueError) as exc:
        return False, f"dns resolution failed: {exc}"

    if not resolved_ips:
        return False, "dns resolution returned no addresses"

    for host_ip in resolved_ips:
        if not host_ip.is_global:
            return False, f"blocked non-global address: {host_ip}"

    return True, "ok"


def is_safe_title_fetch_url(url: str) -> bool:
    return validate_title_fetch_url(url)[0]


def is_blocked_title_fetch_reason(reason: str) -> bool:
    return str(reason or "").startswith("blocked")


__all__ = [
    "resolve_title_fetch_host_ips",
    "validate_title_fetch_url",
    "is_safe_title_fetch_url",
    "is_blocked_title_fetch_reason",
]
