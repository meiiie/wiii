from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.subagents.search.curation import (
    CuratedProduct,
    CuratedProductSelection,
    curate_with_llm,
)
from app.engine.multi_agent.subagents.aggregator import _llm_decision
from app.engine.multi_agent.subagents.report import ReportVerdict, SubagentReport
from app.engine.multi_agent.subagents.result import SubagentResult
from app.engine.multi_agent.subagents.search.workers_runtime import (
    synthesize_response_impl,
)


@pytest.mark.asyncio
async def test_curate_with_llm_forwards_provider_and_requested_model():
    products = [
        {
            "title": "Tai nghe A",
            "price": "500000",
            "platform": "Shopee",
        }
    ]

    with patch(
        "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
        return_value=object(),
    ) as mock_get_llm, patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=CuratedProductSelection(
                selected=[
                    CuratedProduct(
                        index=0,
                        relevance_score=0.91,
                        reason="Khớp nhu cầu",
                        highlight="Giá tốt",
                    )
                ],
                reasoning="",
                total_evaluated=1,
            )
        ),
    ):
        result = await curate_with_llm(
            query="tim tai nghe tot",
            products=products,
            provider_override="openrouter",
            requested_model="qwen/qwen3.6-plus:free",
        )

    assert result is not None
    assert mock_get_llm.call_args.kwargs["provider_override"] == "openrouter"
    assert mock_get_llm.call_args.kwargs["requested_model"] == "qwen/qwen3.6-plus:free"


class _FakeLLM:
    async def ainvoke(self, _messages):
        return SimpleNamespace(content="Bang tong hop san pham")


@pytest.mark.asyncio
async def test_synthesize_response_impl_forwards_provider_and_requested_model():
    state = {
        "query": "tim tai nghe bluetooth",
        "provider": "openrouter",
        "model": "qwen/qwen3.6-plus:free",
        "thinking_effort": "light",
        "curated_products": [
            {
                "title": "Tai nghe B",
                "price": "700000",
                "platform": "Shopee",
                "link": "https://example.com/b",
            }
        ],
        "platforms_searched": ["Shopee"],
        "platform_errors": [],
        "context": {},
        "user_id": "test-user",
        "organization_id": None,
    }

    with patch(
        "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
        return_value=_FakeLLM(),
    ) as mock_get_llm:
        result = await synthesize_response_impl(
            state,
            chunk_size=32,
            chunk_delay=0.0,
            get_event_queue=lambda _bus_id: None,
            push=AsyncMock(),
            render_search_narration=AsyncMock(
                return_value=SimpleNamespace(summary="Tong hop xong")
            ),
            emit_search_narration=AsyncMock(),
        )

    assert result["final_response"] == "Bang tong hop san pham"
    assert mock_get_llm.call_args.kwargs["provider_override"] == "openrouter"
    assert mock_get_llm.call_args.kwargs["requested_model"] == "qwen/qwen3.6-plus:free"


@pytest.mark.asyncio
async def test_aggregator_llm_decision_forwards_provider_and_requested_model():
    reports = [
        SubagentReport(
            agent_name="rag_agent",
            agent_type="retrieval",
            result=SubagentResult(
                confidence=0.6,
                output="Tai lieu A",
            ),
            verdict=ReportVerdict.PARTIAL,
            relevance_score=0.6,
            summary="Tai lieu lien quan",
        ),
        SubagentReport(
            agent_name="tutor_agent",
            agent_type="teaching",
            result=SubagentResult(
                confidence=0.55,
                output="Giai thich B",
            ),
            verdict=ReportVerdict.PARTIAL,
            relevance_score=0.55,
            summary="Giai thich bo sung",
        ),
    ]
    state = {
        "provider": "openrouter",
        "model": "qwen/qwen3.6-plus:free",
        "thinking_effort": "light",
    }

    with patch(
        "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
        return_value=object(),
    ) as mock_get_llm, patch(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        new=AsyncMock(
            return_value=SimpleNamespace(
                action="use_best",
                primary_agent="rag_agent",
                secondary_agents=["tutor_agent"],
                reasoning="rag_agent manh hon",
                re_route_target=None,
                confidence=0.82,
            )
        ),
    ):
        decision = await _llm_decision(reports, "giai thich quy tac 15", state)

    assert decision.primary_agent == "rag_agent"
    assert mock_get_llm.call_args.kwargs["provider_override"] == "openrouter"
    assert mock_get_llm.call_args.kwargs["requested_model"] == "qwen/qwen3.6-plus:free"
