"""Compact wait-surface helpers for direct and Code Studio lanes.

These helpers generate short public-facing wait beats and labels without
touching execution state, tool orchestration, or streaming control flow.
"""

from __future__ import annotations

from typing import Optional

from app.engine.multi_agent.direct_intent import _looks_identity_selfhood_turn, _normalize_for_intent


def _compact_visible_query(query: str, max_len: int = 72) -> str:
    compact = " ".join((query or "").split())
    lowered = compact.lower()
    if not compact:
        return "câu này"
    if any(marker in lowered for marker in ("mo phong", "simulation", "canvas", "widget", "artifact")):
        return "yêu cầu mô phỏng này"
    if any(marker in lowered for marker in ("visual", "bieu do", "chart", "thong ke")):
        return "yêu cầu trực quan này"
    if len(compact.split()) <= 8:
        return "nhịp này"
    if len(compact) > max_len:
        compact = f"{compact[: max_len - 1].rstrip()}..."
    return "điều bạn vừa hỏi"


def _build_direct_wait_heartbeat_text(
    *,
    query: str,
    phase: str,
    cue: str,
    beat_index: int,
    elapsed_sec: float,
    tool_names: Optional[list[str]] = None,
) -> str:
    """Return a compact Wiii-like wait beat without leaking raw query or tool trace."""
    del phase, beat_index, elapsed_sec, tool_names

    normalized_query = _normalize_for_intent(query)
    if cue == "identity" or _looks_identity_selfhood_turn(query):
        return "Mình giữ câu này thật gần để đáp lại thành thật, không vòng vo hay màu mè."
    if cue in {"social", "personal", "off_topic"}:
        if any(
            token in normalized_query
            for token in ("buon", "met", "nan", "te", "co don", "khoc", "tuyet vong", "ap luc", "bat luc", "kiet suc")
        ):
            return "Mình đang giữ nhịp đáp chậm và thật, để nếu bạn muốn nói tiếp thì câu sau vẫn còn chỗ cho điều đó."
        return "Mình đang giữ nhịp thật gần, để câu đáp ra tự nhiên và đúng với bạn hơn."
    if cue in {"visual", "web", "news", "legal", "analysis", "operator"}:
        return "Mình đang gom vài mốc đáng tin rồi gạn lại thành một hình nhìn ngắn gọn cho bạn."
    if cue in {"datetime", "memory", "lms"}:
        return "Mình đang chốt lại về sự việc có thể xác minh được, để câu trả lời ra vừa chắc vừa gần."
    return "Mình đang gạn lại điều chính yếu, để câu trả lời ra gần và đủ."


def _build_code_studio_wait_heartbeat_text(
    *,
    query: str,
    beat_index: int,
    elapsed_sec: float,
    state: Optional[dict] = None,
) -> str:
    """Return a compact scene-minded wait beat for Code Studio turns."""
    del beat_index, elapsed_sec, state

    normalized_query = _normalize_for_intent(query)
    if any(token in normalized_query for token in ("mo phong", "3d", "canvas", "scene", "simulation")):
        return "Mình đang dựng khung mô phỏng và canvas trước, để khi mở ra bạn nhìn là thấy chuyển động ngay."
    if any(token in normalized_query for token in ("visual", "chart", "bieu do", "thong ke", "so sanh")):
        return "Mình đang dựng phần nhìn trước, để các con số và ý chính đi cùng nhau thay vì bị vỡ ra."
    return "Mình đang lên khung cho một artifact có thể mở ra dùng được ngay, rồi mới gọt tiếp những chi tiết sau."


def _contains_wait_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = str(text or "").strip().lower()
    return any(marker in lowered for marker in markers)


_VISIBLE_PERSONA_LABEL_MARKERS: tuple[str, ...] = (
    "Wiii suy nghĩ",
    "Wiii đang nghĩ",
    "Wiii đã nghĩ",
    "Hmm Wiii",
)


def _thinking_start_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if any(marker in text for marker in _VISIBLE_PERSONA_LABEL_MARKERS) else ""
