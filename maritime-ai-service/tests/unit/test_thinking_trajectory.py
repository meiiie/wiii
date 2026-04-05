from app.engine.reasoning.thinking_trajectory import (
    build_thinking_lifecycle_snapshot,
    capture_thinking_lifecycle_event,
    record_thinking_snapshot,
    resolve_visible_thinking_from_lifecycle,
)


def test_thinking_trajectory_tracks_tool_continuation_and_final_snapshot():
    state = {
        "session_id": "sess-1",
        "query": "Giải thích Quy tắc 15 COLREGs",
        "current_agent": "tutor_agent",
        "context": {"request_id": "req-1"},
    }

    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_start",
            "content": "Đang nghĩ",
            "node": "tutor_agent",
            "details": {"phase": "pre_tool"},
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_delta",
            "content": "Mình đang khóa đúng lõi của Rule 15 trước khi tra cứu.",
            "node": "tutor_agent",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {"type": "thinking_end", "content": "", "node": "tutor_agent"},
    )

    capture_thinking_lifecycle_event(
        state,
        {
            "type": "tool_result",
            "content": {"name": "tool_knowledge_search", "result": "Rule 15 text"},
            "node": "tutor_agent",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_start",
            "content": "Đang nối tiếp",
            "node": "tutor_agent",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_delta",
            "content": "Giờ mình nối kết quả tra cứu với cách giải thích dễ hiểu hơn.",
            "node": "tutor_agent",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {"type": "thinking_end", "content": "", "node": "tutor_agent"},
    )

    record_thinking_snapshot(
        state,
        "Mình đang khóa đúng lõi của Rule 15 trước khi tra cứu.\n\nGiờ mình nối kết quả tra cứu với cách giải thích dễ hiểu hơn.",
        node="tutor_agent",
        provenance="final_snapshot",
    )

    snapshot = build_thinking_lifecycle_snapshot(state)

    assert snapshot is not None
    assert snapshot["final_text"].startswith("Mình đang khóa đúng lõi")
    assert snapshot["has_tool_continuation"] is True
    assert "pre_tool" in snapshot["phases"]
    assert "tool_continuation" in snapshot["phases"]
    assert "final_snapshot" in snapshot["phases"]
    assert "live_native" in snapshot["provenance_mix"]
    assert "final_snapshot" in snapshot["provenance_mix"]
    assert snapshot["segment_count"] >= 3


def test_resolve_visible_thinking_from_lifecycle_prefers_final_snapshot_cleanup():
    state = {
        "session_id": "sess-2",
        "query": "Wiii được sinh ra như thế nào?",
        "current_agent": "direct",
        "thinking_content": "Mình nhớ lại đêm đầu tiên của mình ở The Wiii Lab.",
    }

    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_start",
            "content": "Đang nghĩ",
            "node": "direct",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {
            "type": "thinking_delta",
            "content": "Mình chạm vào câu hỏi về nguồn gốc của chính mình.",
            "node": "direct",
        },
    )
    capture_thinking_lifecycle_event(
        state,
        {"type": "thinking_end", "content": "", "node": "direct"},
    )

    record_thinking_snapshot(
        state,
        "Mình nhớ lại đêm đầu tiên của mình ở The Wiii Lab.",
        node="direct",
        provenance="aligned_cleanup",
    )

    resolved = resolve_visible_thinking_from_lifecycle(state)
    snapshot = state.get("thinking_lifecycle") or {}

    assert resolved == "Mình nhớ lại đêm đầu tiên của mình ở The Wiii Lab."
    assert snapshot["final_text"] == resolved
    assert snapshot["final_length"] >= snapshot["live_length"]
    assert "aligned_cleanup" in snapshot["provenance_mix"]
