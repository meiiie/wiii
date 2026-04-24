"""
Tests for the conservative evolution slice:
- LivingContextBlockV1 compilation
- deliberate reasoning floors
- conservative fast routing
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs


@pytest.fixture(autouse=True)
def _mock_living_dependencies():
    with (
        patch("app.engine.character.character_state.get_character_state_manager") as mock_state_mgr,
        patch("app.engine.living_agent.identity_core.get_identity_core") as mock_identity_core,
        patch("app.engine.living_agent.narrative_synthesizer.get_brief_context") as mock_narrative,
    ):
        state_mgr = MagicMock()
        state_mgr.compile_living_state.return_value = "Trang thai song: Wiii dang giu nhip on dinh."
        mock_state_mgr.return_value = state_mgr

        identity_core = MagicMock()
        identity_core.get_identity_context.return_value = "Identity insight: Wiii ngay cang day bang scene ro hon."
        mock_identity_core.return_value = identity_core

        mock_narrative.return_value = "Narrative: Wiii dang theo duoi cach day bang visual va simulation co hon."
        yield


def _make_supervisor(llm=None):
    from app.engine.multi_agent.agent_config import AgentConfigRegistry

    with patch.object(AgentConfigRegistry, "get_llm", return_value=llm):
        from app.engine.multi_agent.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        supervisor._get_llm_for_state = MagicMock(return_value=llm)
        return supervisor


class TestLivingContextBlock:
    def test_compile_living_context_block_has_expected_memory_namespaces(self):
        from app.engine.character.living_context import compile_living_context_block

        block = compile_living_context_block(
            "Hay mo phong vat ly con lac co keo tha chuot",
            context={
                "user_name": "Hung",
                "user_facts": ["Thich mo phong va hoc bang visual"],
                "conversation_summary": "Da cung Wiii trao doi ve chart va simulation o cac turn truoc.",
                "is_follow_up": True,
                "total_responses": 7,
            },
            user_id="user-123",
            organization_id="org-demo",
            domain_id="maritime",
        )

        assert block.reasoning_policy.task_class == "simulation_runtime"
        assert block.reasoning_policy.deliberation_level == "max"
        assert block.current_state
        assert [item.namespace for item in block.memory_blocks] == [
            "persona",
            "human",
            "relationship",
            "goals",
            "craft",
            "world",
        ]

    def test_format_prompt_preserves_section_order(self):
        from app.engine.character.living_context import (
            compile_living_context_block,
            format_living_context_prompt,
        )

        block = compile_living_context_block(
            "Explain Kimi linear attention in charts",
            context={"user_name": "Hung"},
            user_id="user-123",
        )
        prompt = format_living_context_prompt(
            block,
            include_memory_blocks=True,
            include_visual_cognition=True,
        )

        assert prompt.index("### core_card") < prompt.index("### current_state")
        assert prompt.index("### current_state") < prompt.index("### narrative_state")
        assert prompt.index("### narrative_state") < prompt.index("### relationship_memory")
        assert prompt.index("### relationship_memory") < prompt.index("### task_mode")
        assert prompt.index("### task_mode") < prompt.index("### reasoning_policy")
        assert prompt.index("### reasoning_policy") < prompt.index("### visual_cognition")
        assert "## Wiii Living Core Bridge" in prompt
        assert "không có nhân cách riêng theo agent hay lane" in prompt
        assert "## Memory Blocks V1" in prompt

    def test_graph_inject_living_context_populates_reasoning_policy(self):
        from app.engine.multi_agent.graph import _inject_living_context

        state = {
            "query": "Explain Kimi linear attention in charts",
            "user_id": "user-123",
            "organization_id": "org-demo",
            "domain_id": "maritime",
            "context": {
                "user_name": "Hung",
                "user_facts": ["Thich visual explanation"],
                "conversation_summary": "Dang tiep tuc chuan hoa Wiii.",
            },
        }

        with patch("app.engine.multi_agent.context_injection.settings") as mock_settings:
            mock_settings.enable_living_core_contract = True
            mock_settings.enable_memory_blocks = True
            mock_settings.enable_deliberate_reasoning = True
            mock_settings.enable_living_visual_cognition = True
            prompt = _inject_living_context(state)

        assert "## Living Context Block V1" in prompt
        assert "## Wiii Living Core Bridge" in prompt
        assert "day van la wiii" in prompt.lower()
        assert state["reasoning_policy"]["deliberation_level"] == "high"
        assert "## Memory Blocks V1" in state["memory_block_context"]

    def test_graph_inject_living_context_still_builds_core_prompt_when_flags_are_off(self):
        from app.engine.multi_agent.graph import _inject_living_context

        state = {
            "query": "Giải thích Quy tắc 15 COLREGs",
            "user_id": "user-123",
            "organization_id": "org-demo",
            "domain_id": "maritime",
            "context": {
                "user_name": "Hung",
                "conversation_summary": "User đang rà lại các quy tắc tránh va.",
            },
        }

        with patch("app.engine.multi_agent.context_injection.settings") as mock_settings:
            mock_settings.enable_living_core_contract = False
            mock_settings.enable_memory_blocks = False
            mock_settings.enable_deliberate_reasoning = False
            mock_settings.enable_living_visual_cognition = False
            prompt = _inject_living_context(state)

        assert "## Living Context Block V1" in prompt
        assert "## Wiii Living Core Bridge" in prompt
        assert "### core_card" in prompt
        assert "### current_state" in prompt
        assert "### reasoning_policy" in prompt
        assert "## Memory Blocks V1" not in prompt
        assert state["reasoning_policy"]["task_class"] in {"pedagogical_explanation", "general_reasoning"}


class TestConservativeFastRouting:
    @pytest.mark.asyncio
    async def test_social_query_skips_llm_when_fast_routing_enabled(self):
        from app.engine.multi_agent import supervisor as supervisor_module

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock()
        supervisor = _make_supervisor(mock_llm)
        state = {
            "query": "chao",
            "context": {},
            "domain_config": {},
        }

        with patch.object(supervisor_module.settings, "enable_conservative_fast_routing", True):
            result = await supervisor.route(state)

        assert result == "direct"
        assert state["routing_metadata"]["method"] == "conservative_fast_path"
        mock_llm.with_structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_web_query_falls_through_to_supervisor_llm(self):
        from app.engine.multi_agent import supervisor as supervisor_module
        from app.engine.structured_schemas import RoutingDecision

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            return_value=RoutingDecision(
                agent="DIRECT",
                intent="web_search",
                confidence=0.95,
                reasoning="Fresh news requires direct web-search capable lane.",
            )
        )
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        supervisor = _make_supervisor(mock_llm)
        state = {
            "query": "Tin tuc hang hai hom nay",
            "context": {},
            "domain_config": {},
        }

        with (
            patch.object(supervisor_module.settings, "enable_conservative_fast_routing", True),
            patch.object(supervisor_module.StructuredInvokeService, "ainvoke", AsyncMock(return_value=mock_structured.ainvoke.return_value)),
        ):
            result = await supervisor.route(state)

        assert result == "direct"
        assert state["routing_metadata"]["method"] != "conservative_fast_path"
        assert state["routing_metadata"]["intent"] == "web_search"
        mock_llm.with_structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_quiz_creation_request_routes_code_studio(self):
        from app.engine.multi_agent import supervisor as supervisor_module
        from app.engine.structured_schemas import RoutingDecision

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            return_value=RoutingDecision(
                agent="CODE_STUDIO_AGENT",
                intent="code_execution",
                confidence=0.95,
                reasoning="Quiz creation is an artifact generation task.",
            )
        )
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        supervisor = _make_supervisor(mock_llm)
        state = {
            "query": "Tao cho minh quizz gom 30 cau hoi ve tieng Trung de luyen tap duoc khong?",
            "context": {},
            "domain_config": {"routing_keywords": ["colregs", "solas"]},
        }

        with (
            patch.object(supervisor_module.settings, "enable_conservative_fast_routing", True),
            patch.object(supervisor_module.StructuredInvokeService, "ainvoke", AsyncMock(return_value=mock_structured.ainvoke.return_value)),
        ):
            result = await supervisor.route(state)

        assert result == "code_studio_agent"
        assert state["routing_metadata"]["method"] != "conservative_fast_path"
        assert state["routing_metadata"]["intent"] == "code_execution"
        mock_llm.with_structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_pedagogical_query_still_falls_through_to_supervisor_llm(self):
        from app.engine.multi_agent import supervisor as supervisor_module
        from app.engine.structured_schemas import RoutingDecision

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            return_value=RoutingDecision(
                agent="TUTOR_AGENT",
                intent="learning",
                confidence=0.95,
                reasoning="Pedagogical explanation with domain relevance",
            )
        )
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        supervisor = _make_supervisor(mock_llm)
        state = {
            "query": "Giai thich Rule 15 COLREGs",
            "context": {},
            "domain_config": {"routing_keywords": ["colregs"]},
        }

        with (
            patch.object(supervisor_module.settings, "enable_conservative_fast_routing", True),
            patch.object(supervisor_module.StructuredInvokeService, "ainvoke", AsyncMock(return_value=mock_structured.ainvoke.return_value)),
        ):
            result = await supervisor.route(state)

        assert result == "tutor_agent"
        mock_llm.with_structured_output.assert_not_called()
        assert state["routing_metadata"]["method"] != "conservative_fast_path"
