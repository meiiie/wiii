"""Focused regression tests for finalized supervisor routing reasoning."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.multi_agent.supervisor import (
    _finalize_routing_reasoning,
    _looks_like_visual_data_request,
)


def test_capability_override_reasoning_matches_code_studio_lane():
    reasoning = _finalize_routing_reasoning(
        raw_reasoning="Classifier leans direct first.",
        method="structured+capability_override",
        chosen_agent="code_studio_agent",
        intent="code_execution",
        query="Mo phong duoc chu?",
    )

    assert "Code Studio" in reasoning
    assert "dap tam bang loi" in reasoning.lower() or "đáp tạm bằng lời" in reasoning


def test_social_fast_path_reasoning_is_house_friendly():
    reasoning = _finalize_routing_reasoning(
        raw_reasoning="obvious social turn",
        method="always_on_social_fast_path",
        chosen_agent="direct",
        intent="social",
        query="he he",
    )

    assert "xã giao" in reasoning or "xa giao" in reasoning.lower()
    assert "cuộc trò chuyện tự nhiên" in reasoning or "cuoc tro chuyen tu nhien" in reasoning.lower()


def test_visual_data_request_helper_recognizes_chart_plus_recent_data():
    assert _looks_like_visual_data_request(
        "Visual cho minh xem thong ke du lieu hien tai gia dau may ngay gan day"
    ) is True


def test_visual_data_request_helper_ignores_simulation_like_turns():
    assert _looks_like_visual_data_request(
        "mo phong canh thuy kieu o lau ngung bich cho minh duoc chu"
    ) is False


@pytest.mark.asyncio
async def test_structured_route_keeps_supervisor_unpinned_from_user_provider():
    from app.engine.multi_agent.supervisor import SupervisorAgent
    from app.engine.structured_schemas import RoutingDecision

    agent = SupervisorAgent()
    state = {"provider": "zhipu"}
    fake_llm = MagicMock()

    with patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=RoutingDecision(
                agent="DIRECT",
                intent="social",
                confidence=0.9,
                reasoning="social turn",
            )
        ),
    ) as mock_invoke:
        chosen = await agent._route_structured(
            "wow",
            {},
            "AI",
            "Tra cuu",
            "Giai thich",
            {},
            state,
            llm=fake_llm,
        )

    assert chosen == "direct"
    assert mock_invoke.call_args.kwargs["provider"] is None


@pytest.mark.asyncio
async def test_structured_route_identity_probe_overrides_to_direct():
    from app.engine.multi_agent.supervisor import SupervisorAgent
    from app.engine.structured_schemas import RoutingDecision

    agent = SupervisorAgent()
    state = {
        "_routing_hint": {"kind": "identity_probe", "intent": "selfhood", "shape": "identity"},
    }
    fake_llm = MagicMock()

    with patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=RoutingDecision(
                agent="RAG_AGENT",
                intent="lookup",
                confidence=0.95,
                reasoning="system identity knowledge should be retrieved",
            )
        ),
    ):
        chosen = await agent._route_structured(
            "Wiii duoc sinh ra nhu the nao?",
            {},
            "AI",
            "Tra cuu",
            "Giai thich",
            {},
            state,
            llm=fake_llm,
        )

    assert chosen == "direct"
    assert state["routing_metadata"]["method"] == "structured+identity_override"
    reasoning = state["routing_metadata"]["reasoning"]
    assert "Wiii" in reasoning
    assert "trực tiếp" in reasoning or "truc tiep" in reasoning.lower()


@pytest.mark.asyncio
async def test_structured_route_selfhood_followup_overrides_to_direct_and_reframes_intent():
    from app.engine.multi_agent.supervisor import SupervisorAgent
    from app.engine.structured_schemas import RoutingDecision

    agent = SupervisorAgent()
    state = {
        "_routing_hint": {"kind": "selfhood_followup", "intent": "selfhood", "shape": "lore_followup"},
    }
    fake_llm = MagicMock()

    with patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=RoutingDecision(
                agent="MEMORY_AGENT",
                intent="social",
                confidence=0.93,
                reasoning="the follow-up sounds casual and mentions a name",
            )
        ),
    ):
        chosen = await agent._route_structured(
            "con Bong thi sao?",
            {
                "conversation_summary": (
                    "Nguoi dung vua hoi Wiii duoc sinh ra nhu the nao, va cau tra loi co nhac The Wiii Lab cung Bong."
                )
            },
            "AI",
            "Tra cuu",
            "Giai thich",
            {},
            state,
            llm=fake_llm,
        )

    assert chosen == "direct"
    assert state["routing_metadata"]["method"] == "structured+selfhood_followup_override"
    assert state["routing_metadata"]["intent"] == "selfhood"
    reasoning = state["routing_metadata"]["reasoning"]
    assert "Bong" in reasoning or "Wiii" in reasoning


@pytest.mark.asyncio
async def test_structured_route_infers_selfhood_followup_from_recent_context_even_without_precomputed_hint():
    from app.engine.multi_agent.supervisor import SupervisorAgent
    from app.engine.structured_schemas import RoutingDecision

    agent = SupervisorAgent()
    state = {}
    fake_llm = MagicMock()

    with patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=RoutingDecision(
                agent="RAG_AGENT",
                intent="lookup",
                confidence=0.90,
                reasoning="the short follow-up sounds like a lookup term",
            )
        ),
    ):
        chosen = await agent._route_structured(
            "con Bong thi sao?",
            {
                "conversation_summary": (
                    "Nguoi dung vua hoi Wiii duoc sinh ra nhu the nao, va Wiii da nhac toi The Wiii Lab, "
                    "dem mua thang Gieng, cung Bong."
                )
            },
            "AI",
            "Tra cuu",
            "Giai thich",
            {},
            state,
            llm=fake_llm,
        )

    assert chosen == "direct"
    assert state["_routing_hint"]["kind"] == "selfhood_followup"
    assert state["routing_metadata"]["method"] == "structured+selfhood_followup_override"
    assert state["routing_metadata"]["intent"] == "selfhood"
