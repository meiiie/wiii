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
        query="Mô phỏng được chứ?",
    )

    assert "Code Studio" in reasoning
    assert "đáp tạm bằng lời" in reasoning


def test_social_fast_path_reasoning_is_house_friendly():
    reasoning = _finalize_routing_reasoning(
        raw_reasoning="obvious social turn",
        method="always_on_social_fast_path",
        chosen_agent="direct",
        intent="social",
        query="hẹ hẹ",
    )

    assert "xã giao" in reasoning
    assert "cuộc trò chuyện tự nhiên" in reasoning


# test_supervisor_completion_line removed — LLM-first: no hardcoded completion lines.


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
            "Tra cứu",
            "Giải thích",
            {},
            state,
            llm=fake_llm,
        )

    assert chosen == "direct"
    assert mock_invoke.call_args.kwargs["provider"] is None
