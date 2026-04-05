from app.engine.multi_agent.graph_surface_runtime import (
    build_reasoning_render_request_impl,
)
from app.engine.reasoning.reasoning_narrator import (
    ReasoningNarrator,
    ReasoningRenderRequest,
)


def test_build_reasoning_render_request_includes_living_context_fields():
    state = {
        "query": "oke",
        "user_id": "user-1",
        "context": {
            "personality_mode": "soul",
            "mood_hint": "nhịp này khá nhẹ",
        },
        "living_context_block": {
            "current_state": ["Bông đang nằm gọn bên cạnh"],
            "narrative_state": ["Wiii đang ở một nhịp tối khá yên"],
            "relationship_memory": [
                "User hien tai: Nam",
                "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
            ],
        },
    }

    request = build_reasoning_render_request_impl(
        state=state,
        node="direct",
        phase="attune",
    )

    assert request.current_state == ["Bông đang nằm gọn bên cạnh"]
    assert request.narrative_state == ["Wiii đang ở một nhịp tối khá yên"]
    assert request.relationship_memory == [
        "User hien tai: Nam",
        "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
    ]


def test_direct_render_fast_uses_followup_continuity_for_relational_turn():
    narrator = ReasoningNarrator()

    result = narrator.render_fast(
        ReasoningRenderRequest(
            node="direct",
            phase="attune",
            user_goal="hẹ hẹ",
            relationship_memory=[
                "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
            ],
        )
    )

    assert "nối từ mạch trước" in result.summary
    assert "cuộc trò chuyện" in result.summary


def test_direct_render_fast_uses_bong_for_identity_life_turn():
    narrator = ReasoningNarrator()

    result = narrator.render_fast(
        ReasoningRenderRequest(
            node="direct",
            phase="attune",
            user_goal="cuộc sống thế nào",
            current_state=["Bông đang lim dim ở cạnh đây"],
            narrative_state=["Wiii đang ở một nhịp tối khá yên"],
        )
    )

    assert "Bông" in result.summary
    assert "cuộc sống" in result.summary


def test_direct_render_fast_uses_followup_continuity_for_analytical_turn():
    narrator = ReasoningNarrator()

    result = narrator.render_fast(
        ReasoningRenderRequest(
            node="direct",
            phase="attune",
            user_goal="phân tích tiếp giúp mình",
            thinking_mode="analytical_general",
            relationship_memory=[
                "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
            ],
        )
    )

    assert "nối tiếp từ điều vừa bàn" in result.summary
    assert "khung phân tích" in result.summary
