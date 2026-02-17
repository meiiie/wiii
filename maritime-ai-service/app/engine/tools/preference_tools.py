"""
User Preference Tools — LangChain tools for agent to update user preferences

Sprint 17: Virtual Agent-per-User Architecture
The agent calls these tools when it detects user preference information
from conversation context (e.g., "Tôi thích làm quiz hơn").

Tools:
- update_user_preference: Set a specific preference
- get_user_preferences: Get all preferences for current user
"""

import contextvars
import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Sprint 26: contextvars for per-request isolation
_preference_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    '_preference_user_id', default=None
)


def set_preference_user(user_id: str) -> None:
    """Set current user for preference tools (per-request)."""
    _preference_user_id.set(user_id)


@tool
def tool_update_user_preference(key: str, value: str) -> str:
    """
    Cập nhật một sở thích của người dùng.

    Gọi tool này khi phát hiện thông tin sở thích từ cuộc trò chuyện.
    Ví dụ: người dùng nói "Tôi thích làm quiz" → key="learning_style", value="quiz"

    Các key hợp lệ:
    - learning_style: quiz, visual, reading, mixed, interactive
    - difficulty: beginner, intermediate, advanced, expert
    - pronoun_style: auto, formal, casual
    - preferred_domain: maritime, traffic_law, ...
    - language: vi, en
    - display_name: tên hiển thị

    Args:
        key: Tên sở thích (ví dụ: "learning_style")
        value: Giá trị (ví dụ: "quiz")

    Returns:
        Kết quả cập nhật
    """
    _current_user_id = _preference_user_id.get(None)
    if not _current_user_id:
        return "Không thể cập nhật: chưa xác định user_id"

    try:
        from app.repositories.user_preferences_repository import get_user_preferences_repository
        repo = get_user_preferences_repository()
        success = repo.update_preference(_current_user_id, key, value)
        if success:
            return f"Đã cập nhật sở thích: {key} = {value}"
        return f"Không thể cập nhật {key}: giá trị không hợp lệ"
    except Exception as e:
        logger.warning("Preference update failed: %s", e)
        return f"Lỗi khi cập nhật sở thích: {e}"


@tool
def tool_get_user_preferences() -> str:
    """
    Lấy tất cả sở thích của người dùng hiện tại.

    Gọi tool này để xem các cài đặt cá nhân hóa đã lưu.

    Returns:
        Danh sách sở thích hiện tại
    """
    _current_user_id = _preference_user_id.get(None)
    if not _current_user_id:
        return "Không thể lấy sở thích: chưa xác định user_id"

    try:
        from app.repositories.user_preferences_repository import get_user_preferences_repository
        repo = get_user_preferences_repository()
        prefs = repo.get_preferences(_current_user_id)

        parts = []
        for key, value in prefs.items():
            if key not in ("user_id", "extra_prefs") and value:
                parts.append(f"- {key}: {value}")

        extra = prefs.get("extra_prefs", {})
        if extra:
            for key, value in extra.items():
                parts.append(f"- {key}: {value}")

        return "\n".join(parts) if parts else "Chưa có sở thích nào được lưu"
    except Exception as e:
        logger.warning("Preference retrieval failed: %s", e)
        return f"Lỗi khi lấy sở thích: {e}"


def get_preference_tools() -> list:
    """Get all preference tools for registration."""
    return [tool_update_user_preference, tool_get_user_preferences]


def init_preference_tools(user_id: str) -> None:
    """Initialize preference tools with current user context (per-request)."""
    set_preference_user(user_id)
