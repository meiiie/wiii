"""On-demand visual page capture via screenshot + Gemini Vision.

Sprint 223: Hybrid Visual Context Engine — Path B.
AI requests screenshot from host, analyzes with Vision LLM.
Feature gate: enable_visual_page_capture
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Optional

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# ── Validation ──


def validate_screenshot_data(data: str) -> bool:
    """Validate screenshot is base64-encoded JPEG or PNG."""
    if not data:
        return False
    pattern = r"^data:image/(jpeg|png);base64,[A-Za-z0-9+/=]+"
    return bool(re.match(pattern, data))


# ── Gemini Vision ──


async def _call_gemini_vision(image_b64: str) -> str:
    """Call Gemini Vision to analyze a screenshot. Reuses Sprint 179 patterns."""
    try:
        from google import genai

        from app.core.config import get_settings

        settings = get_settings()
        client = genai.Client(api_key=settings.google_api_key)

        # Strip data URI prefix if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.google_model,
            contents=[
                {
                    "parts": [
                        {
                            "text": (
                                "Mô tả chi tiết bằng tiếng Việt những gì hiển thị trên trang web này. "
                                "Liệt kê: tiêu đề trang, các mục/bảng/danh sách, số liệu cụ thể, "
                                "trạng thái, deadline. Không thêm thông tin ngoài những gì nhìn thấy."
                            )
                        },
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_bytes}},
                    ]
                }
            ],
        )
        return response.text
    except Exception as e:
        logger.warning("[VISUAL_CAPTURE] Gemini Vision failed: %s", e)
        raise


async def analyze_screenshot(
    image_b64: str,
    max_size: int = 1_048_576,
    timeout: float = 15.0,
) -> str:
    """Analyze a screenshot with Gemini Vision.

    Returns Vietnamese description of page contents.
    Graceful fallback on error.
    """
    if not image_b64:
        return "Không nhận được ảnh chụp trang."

    # Check size
    raw = image_b64.split(",", 1)[-1] if "," in image_b64 else image_b64
    try:
        decoded_size = len(base64.b64decode(raw))
    except Exception:
        decoded_size = len(raw)

    if decoded_size > max_size:
        return f"Ảnh chụp trang quá lớn ({decoded_size:,} bytes, tối đa {max_size:,})."

    try:
        result = await asyncio.wait_for(
            _call_gemini_vision(image_b64),
            timeout=timeout,
        )
        return result
    except TimeoutError:
        return "Không thể phân tích ảnh chụp trang — timeout."
    except Exception as e:
        return f"Không thể phân tích ảnh chụp trang: {e}"


# ── Tool Creation ──


def get_settings():
    """Lazy import settings to avoid circular imports."""
    from app.core.config import get_settings as _get_settings

    return _get_settings()


def create_visual_capture_tool(event_bus_id: str) -> Optional[StructuredTool]:
    """Create the request_page_visual LangChain tool.

    Returns None if feature gate is disabled.
    """
    try:
        if not getattr(get_settings(), "enable_visual_page_capture", False):
            return None
    except Exception:
        return None

    def _request_visual(reason: str = "User requested visual context") -> str:
        """Request a screenshot of the current page from the host application.

        Use this when you need to SEE what the user is looking at — charts,
        diagrams, complex layouts, or when structured data is insufficient.
        """
        request_id = f"vis-{id(reason)}"
        return json.dumps(
            {
                "status": "action_requested",
                "request_id": request_id,
                "action": "capture_screenshot",
                "params": {"reason": reason, "selector": "main"},
            },
            ensure_ascii=False,
        )

    return StructuredTool.from_function(
        func=_request_visual,
        name="request_page_visual",
        description=(
            "Request a screenshot of the page the user is currently viewing. "
            "Use when you need visual context: charts, diagrams, tables, "
            "or when the structured page data doesn't provide enough detail. "
            "Returns a request ID — the screenshot will arrive as an action response."
        ),
    )
