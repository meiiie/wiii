"""
Contact Extraction Tool — Sprint 196: "Thợ Săn Chuyên Nghiệp"

Extracts structured contact information from any web page URL
using Jina Reader for page-to-markdown conversion + regex extraction.

Gate: enable_contact_extraction
"""

import json
import logging
import re
from typing import Optional

import httpx
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# Jina Reader endpoint
_JINA_READER_URL = "https://r.jina.ai/"
_JINA_TIMEOUT = 25
_JINA_MAX_CHARS = 20000
_JINA_MAX_RETRIES = 1

# Contact extraction patterns
_VN_PHONE_REGEX = re.compile(r'(?<!\d)(0[1-9]\d{8,9})(?!\d)')
_INTL_PHONE_REGEX = re.compile(r'(\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4})')
_EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_ZALO_REGEX = re.compile(r'[Zz]alo[:\s./]*(?:0[1-9]\d{8,9})', re.IGNORECASE)
_VIBER_REGEX = re.compile(r'[Vv]iber[:\s./]*(?:\+?\d[\d\s.-]{8,15})', re.IGNORECASE)
_FACEBOOK_REGEX = re.compile(
    r'(?:facebook\.com|fb\.com)/[\w.]+',
    re.IGNORECASE,
)

# Vietnamese address line detection — keywords trigger candidate lines
_ADDRESS_KEYWORDS = [
    "địa chỉ", "dia chi", "address", "trụ sở", "tru so",
    "chi nhánh", "chi nhanh", "văn phòng", "van phong",
    "số nhà", "so nha", "số", "đường", "duong", "phường", "phuong",
    "quận", "quan", "huyện", "huyen", "tp.", "tp ",
    "hà nội", "ha noi", "hcm", "hồ chí minh", "đà nẵng", "da nang",
    "hải phòng", "hai phong", "cần thơ", "can tho",
]

# Sprint 198b: Structural address patterns — must match >=2 to confirm address
_ADDRESS_STRUCTURAL_PATTERNS = [
    re.compile(r'\d+[A-Za-z]?(?:/\d+)?(?:\s|,)'),                              # house number: 123, 123A, 79/63
    re.compile(r'(?:đường|duong|phố|pho)\s+\w+', re.IGNORECASE),               # đường Nguyễn Huệ
    re.compile(r'(?:phường|phuong|P\.)\s*\w+', re.IGNORECASE),                  # phường 5, P.5
    re.compile(r'(?:quận|quan|Q\.)\s*\w+', re.IGNORECASE),                      # quận 1, Q.1
    re.compile(r'(?:huyện|huyen|H\.)\s*\w+', re.IGNORECASE),                    # huyện Bình Chánh
    re.compile(r'(?:thành phố|tp\.|tp )\s*\w+', re.IGNORECASE),                 # TP.HCM
    re.compile(r'(?:tỉnh|tinh)\s+\w+', re.IGNORECASE),                          # tỉnh Đồng Nai
    re.compile(r'(?:tòa nhà|toa nha)\s+\w+', re.IGNORECASE),                    # tòa nhà ABC
    re.compile(r'(?:lầu|lau|tầng|tang)\s+\d+', re.IGNORECASE),                  # lầu 5, tầng 12
    re.compile(
        r'(?:hà nội|ha noi|hcm|hồ chí minh|đà nẵng|da nang|hải phòng|hai phong|cần thơ|can tho)',
        re.IGNORECASE,
    ),
]
_ADDRESS_MIN_LENGTH = 10
_ADDRESS_MAX_LENGTH = 300
_ADDRESS_MIN_STRUCTURAL_SCORE = 2


def _fetch_page_markdown(url: str) -> str:
    """Fetch a page via Jina Reader and return markdown content.

    Sprint 198b: 25s timeout, 20k truncation, 1 retry on timeout/5xx.
    """
    for attempt in range(_JINA_MAX_RETRIES + 1):
        try:
            resp = httpx.get(
                f"{_JINA_READER_URL}{url}",
                timeout=_JINA_TIMEOUT,
                headers={"Accept": "text/markdown"},
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text[:_JINA_MAX_CHARS]
            # Retry on 5xx server errors
            if resp.status_code >= 500 and attempt < _JINA_MAX_RETRIES:
                logger.debug("[CONTACT_EXTRACT] Jina Reader %d for %s, retrying", resp.status_code, url)
                continue
            return ""
        except httpx.TimeoutException:
            if attempt < _JINA_MAX_RETRIES:
                logger.debug("[CONTACT_EXTRACT] Jina Reader timeout for %s, retrying", url)
                continue
            logger.debug("[CONTACT_EXTRACT] Jina Reader timeout for %s after %d attempts", url, attempt + 1)
            return ""
        except Exception as e:
            logger.debug("[CONTACT_EXTRACT] Jina Reader failed for %s: %s", url, e)
            return ""
    return ""


def _structural_address_score(line: str) -> int:
    """Count how many structural address components are present in a line.

    Sprint 198b: Replaces keyword-only address validation.
    Requires score >= 2 to confirm a line as a real address.
    """
    score = 0
    for pattern in _ADDRESS_STRUCTURAL_PATTERNS:
        if pattern.search(line):
            score += 1
    return score


def _extract_address(text: str) -> str:
    """Extract physical address from text using Vietnamese address heuristics.

    Sprint 198b: Uses structural scoring to eliminate false positives like
    "Màn hình:LCD..." or "Hy vọng bài viết..." that contain keywords but
    have zero structural address components.
    """
    for line in text.split('\n'):
        line_stripped = line.strip().strip('-').strip('*').strip(':').strip()
        line_lower = line_stripped.lower()
        if any(kw in line_lower for kw in _ADDRESS_KEYWORDS):
            if _ADDRESS_MIN_LENGTH < len(line_stripped) < _ADDRESS_MAX_LENGTH:
                if _structural_address_score(line_stripped) >= _ADDRESS_MIN_STRUCTURAL_SCORE:
                    return line_stripped
    return ""


def _normalize_phones_in_text(text: str) -> str:
    """Normalize phone numbers with spaces/dots/dashes for regex matching.

    Sprint 198b: '090 0123 4567' → '09001234567', '090.123.4567' → '0901234567'
    Only normalizes sequences starting with 0 + digit (Vietnamese phone pattern).
    """
    def _collapse(m):
        return re.sub(r'[\s.\-]', '', m.group(0))

    return re.sub(r'0[1-9][\d\s.\-]{8,14}', _collapse, text)


def _extract_all_contacts(text: str) -> dict:
    """Extract all contact information from text.

    Returns structured dict with phones, international phones, emails,
    Zalo contacts, Viber, Facebook pages, and address.
    """
    contacts = {
        "phones": [],
        "international_phones": [],
        "emails": [],
        "zalo": [],
        "viber": [],
        "facebook": [],
        "address": "",
    }

    if not text:
        return contacts

    # Sprint 198b: Normalize phone numbers with spaces/dots/dashes
    normalized_text = _normalize_phones_in_text(text)

    # Vietnamese phone numbers (search normalized text for better matching)
    vn_phones = _VN_PHONE_REGEX.findall(normalized_text)
    contacts["phones"] = list(dict.fromkeys(vn_phones))[:10]

    # International phone numbers (exclude VN ones already captured) — use original text
    intl_phones = _INTL_PHONE_REGEX.findall(text)
    intl_phones = [p.strip() for p in intl_phones if not p.strip().startswith("0")]
    contacts["international_phones"] = list(dict.fromkeys(intl_phones))[:5]

    # Emails (filter out image/asset false positives) — use original text
    emails = _EMAIL_REGEX.findall(text)
    emails = [
        e for e in emails
        if not e.endswith(('.png', '.jpg', '.gif', '.css', '.js', '.svg', '.ico'))
    ]
    contacts["emails"] = list(dict.fromkeys(emails))[:5]

    # Zalo contacts — use normalized text for phone matching
    zalo_matches = _ZALO_REGEX.findall(normalized_text)
    for z in zalo_matches:
        phone_match = _VN_PHONE_REGEX.search(z)
        if phone_match:
            contacts["zalo"].append(phone_match.group())
    contacts["zalo"] = list(dict.fromkeys(contacts["zalo"]))[:5]

    # Viber contacts — use original text (intl format)
    viber_matches = _VIBER_REGEX.findall(text)
    for v in viber_matches:
        # Extract just the number part
        num = re.sub(r'[Vv]iber[:\s./]*', '', v).strip()
        if num:
            contacts["viber"].append(num)
    contacts["viber"] = list(dict.fromkeys(contacts["viber"]))[:3]

    # Facebook pages
    fb_matches = _FACEBOOK_REGEX.findall(text)
    contacts["facebook"] = list(dict.fromkeys(fb_matches))[:3]

    # Physical address
    contacts["address"] = _extract_address(text)

    return contacts


def tool_extract_contacts_fn(url: str) -> str:
    """Extract contact information from a web page URL.

    Uses Jina Reader to convert the page to markdown, then extracts
    phone numbers, Zalo, email, Viber, Facebook, and physical address.

    Args:
        url: Full URL of the web page to extract contacts from

    Returns:
        JSON with structured contact information.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.enable_contact_extraction:
        return json.dumps(
            {"error": "Contact extraction is not enabled", "url": url, "contacts": {}},
            ensure_ascii=False,
        )

    if not url or not url.startswith(("http://", "https://")):
        return json.dumps(
            {"error": "Invalid URL — must start with http:// or https://", "url": url},
            ensure_ascii=False,
        )

    try:
        markdown = _fetch_page_markdown(url)
        if not markdown:
            return json.dumps(
                {"url": url, "contacts": {}, "error": "Could not fetch page content"},
                ensure_ascii=False,
            )

        contacts = _extract_all_contacts(markdown)

        # Count total contact methods found
        total_contacts = (
            len(contacts["phones"])
            + len(contacts["international_phones"])
            + len(contacts["emails"])
            + len(contacts["zalo"])
            + len(contacts["viber"])
            + len(contacts["facebook"])
            + (1 if contacts["address"] else 0)
        )

        return json.dumps(
            {
                "url": url,
                "contacts": contacts,
                "total_contact_methods": total_contacts,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("[CONTACT_EXTRACT] Failed for %s: %s", url, e)
        return json.dumps(
            {"error": f"Contact extraction failed: {str(e)[:200]}", "url": url},
            ensure_ascii=False,
        )


def get_contact_extraction_tool() -> StructuredTool:
    """Create and return the contact extraction StructuredTool."""
    return StructuredTool.from_function(
        func=tool_extract_contacts_fn,
        name="tool_extract_contacts",
        description=(
            "Trích xuất thông tin liên hệ từ trang web: SĐT, Zalo, email, Viber, "
            "Facebook, địa chỉ. Dùng khi cần lấy thông tin liên hệ từ trang đại lý, "
            "nhà phân phối, hoặc cửa hàng online."
        ),
    )
