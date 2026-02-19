"""
Shared utilities for search platform adapters.

Sprint 153: "Bảo Vệ" — Security & Reliability Hardening

Consolidates:
- SSRF URL validation (used by product_page_scraper + browser_base)
- VND price parsing (was duplicated in 3 files)
"""

import ipaddress
import logging
import re
import socket
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

# Private/reserved networks that must not be accessed via server-side fetching
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / AWS metadata
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def validate_url_for_scraping(url: str) -> str:
    """Validate URL is safe for server-side fetching. Raises ValueError if not.

    Blocks:
    - Non-HTTP(S) schemes (file://, ftp://, etc.)
    - Missing hostname
    - Private/reserved IPs (SSRF prevention)
    - Unresolvable hostnames

    Returns the original URL if valid.
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme!r}")

    if not parsed.hostname:
        raise ValueError("Missing hostname")

    # Resolve DNS and check all resolved IPs against blocklist
    try:
        resolved = socket.getaddrinfo(parsed.hostname, None, socket.AF_UNSPEC)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {parsed.hostname}")

    for _, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"Blocked private/reserved IP: {ip}")

    return url


def parse_vnd_price(price_str: str) -> Optional[float]:
    """Parse a VND price string to float.

    Handles both '.' and ',' as thousands separators (Vietnamese convention).
    Strips currency symbols (₫, đ, VND, etc.) before parsing.

    Examples:
        "1.234.567" → 1234567.0
        "35.490.000 đ" → 35490000.0
        "1,234,567 VND" → 1234567.0

    Returns None if the string is empty, unparseable, or suspiciously small (<100).
    """
    if not price_str:
        return None
    # Strip currency symbols and whitespace
    cleaned = re.sub(r"[₫đĐVNDvnd\s]", "", price_str)
    # Remove all separators — VND doesn't use decimal fractions
    cleaned = cleaned.replace(".", "").replace(",", "").strip()
    try:
        value = float(cleaned)
        # Sanity: VND prices are typically > 1000
        if value < 100:
            return None
        return value
    except (ValueError, TypeError):
        return None
