"""
Link Preview Service — OG metadata fetcher for URL previews.
Sprint 166: SSRF-safe, cached, async.
"""
import asyncio
import hashlib
import logging
import re
import time
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx

from app.core.constants import PREVIEW_SNIPPET_MAX_LENGTH, PREVIEW_TITLE_MAX_LENGTH

logger = logging.getLogger(__name__)

# Cache: {url_hash: (timestamp, result)}
_og_cache: Dict[str, tuple] = {}
_CACHE_TTL = 900  # 15 minutes
_CACHE_MAX = 200
_FETCH_TIMEOUT = 5.0
_MAX_BODY_BYTES = 256_000  # 256 KB of HTML is enough for OG tags


class _OGParser(HTMLParser):
    """Minimal parser extracting og:* and basic <title> from HTML head."""

    def __init__(self) -> None:
        super().__init__()
        self.og: Dict[str, str] = {}
        self._in_title = False
        self._title_text = ""
        self._in_head = True

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "head":
            self._in_head = True
        if tag == "title" and self._in_head:
            self._in_title = True
        if tag == "meta" and self._in_head:
            a = dict(attrs)
            prop = a.get("property", a.get("name", "")).lower()
            content = a.get("content", "")
            if prop.startswith("og:") and content:
                self.og[prop] = content
            elif prop == "description" and "og:description" not in self.og and content:
                self.og["og:description"] = content

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "head":
            self._in_head = False


def _is_private_ip(hostname: str) -> bool:
    """SSRF prevention: block private/reserved IPs."""
    try:
        ip = ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


def _validate_url(url: str) -> bool:
    """Validate URL for safety: must be http(s), not private IP."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        if _is_private_ip(hostname):
            return False
        # Block common internal hostnames
        lower = hostname.lower()
        if lower in ("localhost", "127.0.0.1", "0.0.0.0", "[::]", "[::1]"):
            return False
        if lower.endswith(".local") or lower.endswith(".internal"):
            return False
        return True
    except Exception:
        return False


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def _evict_stale() -> None:
    """Remove expired entries and cap size."""
    now = time.time()
    expired = [k for k, (ts, _) in _og_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        _og_cache.pop(k, None)
    # Cap size
    if len(_og_cache) > _CACHE_MAX:
        oldest = sorted(_og_cache.items(), key=lambda x: x[1][0])
        for k, _ in oldest[: len(_og_cache) - _CACHE_MAX]:
            _og_cache.pop(k, None)


async def fetch_link_preview(url: str) -> Optional[Dict[str, str]]:
    """
    Fetch og:title, og:description, og:image from URL.
    Returns dict with keys: title, description, image_url, url.
    Returns None on failure or unsafe URL.
    """
    if not _validate_url(url):
        return None

    key = _cache_key(url)
    cached = _og_cache.get(key)
    if cached:
        ts, result = cached
        if time.time() - ts < _CACHE_TTL:
            return result

    _evict_stale()

    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
        ) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "WiiiBot/1.0 (+https://wiii.ai)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type.lower():
                return None

            body = resp.text[:_MAX_BODY_BYTES]

        parser = _OGParser()
        parser.feed(body)

        og = parser.og
        title = og.get("og:title", parser._title_text or "").strip()
        if not title:
            return None

        result: Dict[str, str] = {
            "title": title[:PREVIEW_TITLE_MAX_LENGTH],
            "description": og.get("og:description", "")[:PREVIEW_SNIPPET_MAX_LENGTH],
            "image_url": og.get("og:image", ""),
            "url": og.get("og:url", url),
        }

        _og_cache[key] = (time.time(), result)
        return result

    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.debug("Link preview fetch failed for %s: %s", url, exc)
        return None


def clear_cache() -> None:
    """Clear the OG metadata cache (for testing)."""
    _og_cache.clear()
