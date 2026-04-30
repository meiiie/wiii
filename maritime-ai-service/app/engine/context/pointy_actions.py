"""Wiii Pointy — canonical action names + Python-side schema reference.

This module documents the V1 ``ui.*`` action contract that the Wiii Pointy
host bundle (``wiii-desktop/src/pointy-host/``) implements on the LMS parent
page. Wiii's :class:`~app.engine.context.action_bridge.HostActionBridge` is
already generic — it accepts whatever ``HostCapabilities.tools[]`` declares.

This file exists as:

1. A single source of truth for action names so the backend never typos
   ``ui.highlights`` vs ``ui.highlight``.
2. A reference shape for ``HostActionDefinition`` payloads that the LMS
   parent should emit via ``wiii:capabilities``.

V1 is tutor-safe: highlight/scroll/tour plus fail-closed safe-click. ``ui.click``
only works for host elements explicitly marked ``data-wiii-click-safe="true"``.
No auto-fill.
"""
from __future__ import annotations

from typing import Any

POINTY_VERSION = 1

POINTY_ACTION_CURSOR_MOVE = "ui.cursor_move"
POINTY_ACTION_HIGHLIGHT = "ui.highlight"
POINTY_ACTION_SCROLL_TO = "ui.scroll_to"
POINTY_ACTION_NAVIGATE = "ui.navigate"
POINTY_ACTION_SHOW_TOUR = "ui.show_tour"
POINTY_ACTION_CLICK = "ui.click"

POINTY_ACTIONS: tuple[str, ...] = (
    POINTY_ACTION_CURSOR_MOVE,
    POINTY_ACTION_HIGHLIGHT,
    POINTY_ACTION_SCROLL_TO,
    POINTY_ACTION_NAVIGATE,
    POINTY_ACTION_SHOW_TOUR,
    POINTY_ACTION_CLICK,
)


def reference_capabilities() -> dict[str, Any]:
    """Return a reference ``wiii:capabilities`` payload for the LMS parent.

    The LMS team is expected to emit a payload of this shape after the
    iframe loads. Wiii's frontend forwards it into ``HostCapabilities`` and
    the backend exposes the tools to the AI via ``generate_host_action_tools``.

    The shape mirrors :class:`HostCapabilities` — keep them in sync.
    """
    return {
        "host_type": "lms",
        "host_name": "Wiii Pointy host",
        "version": str(POINTY_VERSION),
        "surfaces": ["page"],
        "tools": [
            {
                "name": POINTY_ACTION_CURSOR_MOVE,
                "description": (
                    "Show Wiii's collaborative cursor moving on the host page. "
                    "This is presence-only: no highlight, no click, no mutation."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "Stable data-wiii-id or CSS selector to move the cursor toward.",
                        },
                        "x": {
                            "type": "number",
                            "description": "Viewport X coordinate, or 0..1 when coordinate_space=normalized.",
                        },
                        "y": {
                            "type": "number",
                            "description": "Viewport Y coordinate, or 0..1 when coordinate_space=normalized.",
                        },
                        "coordinate_space": {
                            "type": "string",
                            "description": "viewport | normalized.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Short cursor label, for example Wiii.",
                        },
                        "duration_ms": {
                            "type": "number",
                            "description": "Movement duration in milliseconds.",
                        },
                    },
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
            {
                "name": POINTY_ACTION_HIGHLIGHT,
                "description": (
                    "Trỏ và làm nổi bật một phần tử trên trang để hướng dẫn người dùng. "
                    "Không tự click — chỉ chỉ đường."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": (
                                'CSS selector hoặc [data-wiii-id="..."]; '
                                "ưu tiên data-wiii-id vì ổn định hơn."
                            ),
                        },
                        "message": {
                            "type": "string",
                            "description": "Tooltip hiển thị bên cạnh element (tiếng Việt).",
                        },
                        "duration_ms": {
                            "type": "number",
                            "description": "Thời gian giữ spotlight (mặc định 2200ms).",
                        },
                    },
                    "required": ["selector"],
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
            {
                "name": POINTY_ACTION_SCROLL_TO,
                "description": "Cuộn trang đến một phần tử cụ thể.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "block": {
                            "type": "string",
                            "description": "start | center | end (mặc định center).",
                        },
                    },
                    "required": ["selector"],
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
            {
                "name": POINTY_ACTION_NAVIGATE,
                "description": (
                    "Chuyển đến route nội bộ (ưu tiên) hoặc URL tuyệt đối an toàn. "
                    "Không phá session người dùng."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "route": {
                            "type": "string",
                            "description": "Route nội bộ, ví dụ: /courses/123",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL http(s) tuyệt đối.",
                        },
                    },
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
            {
                "name": POINTY_ACTION_SHOW_TOUR,
                "description": (
                    "Chạy hướng dẫn nhiều bước, mỗi bước trỏ + highlight một element."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "description": "Danh sách bước { selector, message, duration_ms? }.",
                        },
                        "start_at": {
                            "type": "number",
                            "description": "Bước bắt đầu (mặc định 0).",
                        },
                    },
                    "required": ["steps"],
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
            {
                "name": POINTY_ACTION_CLICK,
                "description": (
                    "Click an LMS element only when host context marks it "
                    'data-wiii-click-safe="true". Fail closed for unsafe, disabled, '
                    "payment, enrollment, submit, destructive, or unlisted targets."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": (
                                "Stable data-wiii-id or CSS selector from available_targets. "
                                "Use only when the target has click_safe=true."
                            ),
                        },
                        "message": {
                            "type": "string",
                            "description": "Short tooltip shown just before the click.",
                        },
                    },
                    "required": ["selector"],
                },
                "surface": "page",
                "mutates_state": False,
                "requires_confirmation": False,
            },
        ],
    }


__all__ = [
    "POINTY_VERSION",
    "POINTY_ACTION_CURSOR_MOVE",
    "POINTY_ACTION_HIGHLIGHT",
    "POINTY_ACTION_SCROLL_TO",
    "POINTY_ACTION_NAVIGATE",
    "POINTY_ACTION_SHOW_TOUR",
    "POINTY_ACTION_CLICK",
    "POINTY_ACTIONS",
    "reference_capabilities",
]
