from app.engine.multi_agent.graph_process import _build_process_result_payload


def test_build_process_result_payload_includes_thinking_lifecycle():
    result = {
        "final_response": "Đây là câu trả lời.",
        "sources": [],
        "tools_used": [],
        "grader_score": 8.5,
        "agent_outputs": {},
        "current_agent": "direct",
        "next_agent": "direct",
        "thinking": "Mình đang khóa ý chính.",
        "thinking_content": "Mình đang khóa ý chính.",
        "routing_metadata": {"final_agent": "direct"},
    }

    payload = _build_process_result_payload(
        result=result,
        trace_id="trace-1",
        trace_summary={},
        tracker=None,
        resolve_public_thinking_content=lambda state, fallback="": state.get("thinking_content") or fallback,
    )

    lifecycle = payload.get("thinking_lifecycle")
    assert isinstance(lifecycle, dict)
    assert lifecycle["final_text"] == "Mình đang khóa ý chính."
    assert payload["thinking_content"] == "Mình đang khóa ý chính."
