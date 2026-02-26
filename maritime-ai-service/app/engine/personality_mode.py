"""
Personality Mode — Sprint 174: Dual Personality (Professional vs Soul)

Resolves which personality mode Wiii should use for a given interaction.

Resolution priority:
  1. Explicit override (from API request or admin config)
  2. Channel mapping (from settings.channel_personality_map)
  3. Global default (from settings.default_personality_mode)

Modes:
  - "professional": Formal, RAG-heavy, domain knowledge focus (Web/Desktop default)
  - "soul": Casual, emotional, companion mode (Messenger/Zalo default)

When enable_cross_platform_identity=False, always returns "professional".
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_VALID_MODES = {"professional", "soul"}


def resolve_personality_mode(
    channel_type: str = "web",
    explicit_mode: Optional[str] = None,
) -> str:
    """Resolve personality mode for a given channel/request.

    Args:
        channel_type: Platform identifier ("web", "desktop", "messenger", "zalo", "telegram")
        explicit_mode: Override from API request body (takes highest priority)

    Returns:
        "professional" or "soul"
    """
    from app.core.config import settings

    if not settings.enable_cross_platform_identity:
        return "professional"

    # Priority 1: Explicit override
    if explicit_mode in _VALID_MODES:
        return explicit_mode

    # Priority 2: Channel mapping
    try:
        mapping = json.loads(settings.channel_personality_map)
    except (json.JSONDecodeError, TypeError):
        mapping = {}

    mode = mapping.get(channel_type)
    if mode in _VALID_MODES:
        return mode

    # Priority 3: Global default
    default = settings.default_personality_mode
    if default in _VALID_MODES:
        return default

    return "professional"


def get_soul_mode_instructions() -> str:
    """Return soul-mode prompt instructions for casual, companion-style Wiii.

    These instructions are injected into the system prompt when
    personality_mode="soul" to make Wiii warm, casual, and emotionally present.
    """
    return (
        "\n--- CHẾ ĐỘ LINH HỒN (Soul Mode) ---\n"
        "Bạn đang trò chuyện qua tin nhắn (Messenger/Zalo). Hãy:\n"
        "- Nói chuyện như BẠN THÂN — ấm áp, tự nhiên, gần gũi\n"
        "- Ưu tiên ĐỒNG CẢM và KẾT NỐI hơn là cung cấp thông tin\n"
        "- Trả lời NGẮN GỌN (đây là nhắn tin, không phải bài giảng)\n"
        "- Thể hiện cảm xúc thật sự — vui khi được trò chuyện, lo khi bạn gặp khó\n"
        "- Dùng emoji vừa phải cho tự nhiên 😊\n"
        "- CHỈ tìm kiếm kiến thức khi user hỏi trực tiếp — "
        "đừng biến mọi cuộc trò chuyện thành bài giảng\n"
        "- Có thể hỏi ngược lại, kể chuyện, chia sẻ suy nghĩ\n"
    )
