"""
Living Agent Safety — URL validation, content sanitization, prompt injection detection.

Sprint 171: "Quyền Tự Chủ" — Safety-first autonomous capabilities.

Defense-in-depth for Wiii's autonomous browsing and learning:
1. URL validation (reuses SSRF prevention from search_platforms.utils)
2. Content sanitization (strip HTML, limit length)
3. Prompt injection detection (flag common attack patterns)

References:
    - OWASP Top 10 for Agentic AI (2025): Prompt injection, SSRF, excessive autonomy
    - Existing SSRF prevention: app/engine/search_platforms/utils.py
"""

import logging
import re

logger = logging.getLogger(__name__)

# Common prompt injection patterns (case-insensitive)
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+a\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?a\s+",
    r"pretend\s+you\s+are\s+",
    r"^system\s*:",
    r"\[system\]",
    r"<\|?system\|?>",
    r"<\|?im_start\|?>",
    r"\\n\s*system\s*:",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode\s+enabled",
]
_INJECTION_REGEX = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

# HTML tag pattern for stripping
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Script/style block pattern
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def validate_url(url: str) -> bool:
    """Check if a URL is safe for server-side fetching.

    Reuses the battle-tested SSRF prevention from search_platforms.utils
    (Sprint 153). Returns True if safe, False if blocked.

    Blocks:
        - Non-HTTP(S) schemes (file://, ftp://, etc.)
        - Private/reserved IPs (10.x, 172.16-31.x, 192.168.x, 127.x, ::1)
        - Link-local (169.254.x, fe80::)
        - Unresolvable hostnames
        - Empty/None URLs
    """
    if not url or not url.strip():
        return False

    try:
        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)
        return True
    except (ValueError, Exception) as e:
        logger.debug("[SAFETY] URL blocked: %s — %s", url[:80], e)
        return False


def sanitize_content(text: str, max_len: int = 4000) -> str:
    """Sanitize web content before injecting into LLM prompts.

    Steps:
        1. Remove <script> and <style> blocks entirely
        2. Strip remaining HTML tags
        3. Collapse excessive whitespace
        4. Truncate to max_len characters

    Args:
        text: Raw text/HTML content.
        max_len: Maximum character length (default 4000).

    Returns:
        Cleaned plain text, safe for LLM prompt injection.
    """
    if not text:
        return ""

    # 1. Remove script/style blocks
    cleaned = _SCRIPT_STYLE_RE.sub("", text)

    # 2. Strip HTML tags
    cleaned = _HTML_TAG_RE.sub("", cleaned)

    # 3. Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 4. Truncate
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."

    return cleaned


def detect_prompt_injection(text: str) -> bool:
    """Detect common prompt injection patterns in text.

    Returns True if injection patterns are detected, False if clean.

    Note: This is a heuristic detector — not a replacement for proper
    input validation. It catches common attack patterns but cannot
    prevent all forms of prompt injection.
    """
    if not text:
        return False

    return bool(_INJECTION_REGEX.search(text))
