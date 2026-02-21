"""
Sprint 88: Response Quality + Memory + Routing Fixes
Sprint 88b: Character-Driven Identity Rewrite
Sprint 88c: Suggestion-Based Identity (suggestions > rigid rules)

Tests:
1. Suggestion-based response style (suggestions + avoid, no hard rules)
2. Routing keywords expansion (compass, PSC, tonnage, etc.)
3. Memory facts limit raised (10 → 20 for 15 fact types)
4. Extraction prompt interest broadening
5. direct_response_node suggestion-based prompt
6. Identity personality rewrite (đáng yêu, thích trò chuyện)
"""

import sys
import types
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Break circular import (graph → services → chat_service → graph)
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.prompts.prompt_loader import PromptLoader


@pytest.fixture(autouse=True)
def _mock_character_state_manager():
    """Prevent build_system_prompt from connecting to PostgreSQL."""
    with patch(
        "app.engine.character.character_state.get_character_state_manager"
    ) as m:
        inst = MagicMock()
        inst.compile_living_state.return_value = ""
        m.return_value = inst
        yield


# =============================================================================
# Phase 1: Character-driven response style
# =============================================================================

class TestSuggestionBasedStyle:
    """Sprint 88c: Suggestion-based, not rule-driven response style."""

    def test_identity_has_response_style(self):
        """Identity should have response_style with suggestions."""
        loader = PromptLoader()
        identity = loader.get_identity().get("identity", {})
        assert "response_style" in identity

    def test_response_style_has_suggestions(self):
        """response_style should have suggestions list."""
        loader = PromptLoader()
        style = loader.get_identity().get("identity", {}).get("response_style", {})
        suggestions = style.get("suggestions", [])
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 5

    def test_no_hard_word_limit_in_identity(self):
        """Identity should NOT have GIỚI HẠN CỨNG or enforcement rules."""
        loader = PromptLoader()
        identity = loader.get_identity().get("identity", {})
        identity_str = str(identity)
        assert "GIỚI HẠN CỨNG" not in identity_str
        assert "enforcement" not in identity_str
        assert "Đếm từ" not in identity_str

    def test_suggestions_cover_simple_and_complex(self):
        """Suggestions should cover both short (simple) and detailed (complex) responses."""
        loader = PromptLoader()
        suggestions = (
            loader.get_identity()
            .get("identity", {})
            .get("response_style", {})
            .get("suggestions", [])
        )
        suggestions_str = " ".join(suggestions)
        assert "ngắn gọn" in suggestions_str or "đơn giản" in suggestions_str
        assert "kỹ thuật" in suggestions_str or "đầy đủ" in suggestions_str

    def test_suggestions_encourage_asking_back(self):
        """Suggestions should encourage asking clarifying questions."""
        loader = PromptLoader()
        suggestions = (
            loader.get_identity()
            .get("identity", {})
            .get("response_style", {})
            .get("suggestions", [])
        )
        suggestions_str = " ".join(suggestions)
        assert "hỏi lại" in suggestions_str

    def test_avoid_forbids_rambling(self):
        """avoid list should include rambling."""
        loader = PromptLoader()
        avoids = (
            loader.get_identity()
            .get("identity", {})
            .get("response_style", {})
            .get("avoid", [])
        )
        has_rambling = any("lan man" in a.lower() for a in avoids)
        assert has_rambling, f"avoid should forbid lan man, got: {avoids}"

    def test_avoid_forbids_forced_metaphors(self):
        """avoid list should include forced metaphors."""
        loader = PromptLoader()
        avoids = (
            loader.get_identity()
            .get("identity", {})
            .get("response_style", {})
            .get("avoid", [])
        )
        has_metaphor = any("ẩn dụ" in a.lower() or "gượng ép" in a.lower() for a in avoids)
        assert has_metaphor, f"avoid should forbid ẩn dụ gượng ép, got: {avoids}"

    def test_build_prompt_includes_suggestions(self):
        """build_system_prompt should include PHONG CÁCH TRẢ LỜI section."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "PHONG CÁCH TRẢ LỜI" in prompt

    def test_build_prompt_includes_avoid(self):
        """build_system_prompt should include QUY TẮC PHONG CÁCH with avoid items."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "QUY TẮC PHONG CÁCH" in prompt
        assert "ẩn dụ gượng ép" in prompt.lower()

    def test_tutor_yaml_no_hard_limit(self):
        """Tutor avoid list should NOT have GIỚI HẠN CỨNG."""
        import yaml
        tutor_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(tutor_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # Sprint 90: must_not → avoid
        avoids = config.get("directives", {}).get("avoid", [])
        for item in avoids:
            assert "GIỚI HẠN CỨNG" not in item, f"Tutor should not have hard limit: {item}"

    def test_tutor_yaml_uses_suggestion_based_style(self):
        """Sprint 90: Tutor uses 'avoid' (suggestion-based) not 'must_not'."""
        import yaml
        tutor_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(tutor_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "avoid" in directives, "Tutor should use suggestion-based 'avoid'"
        assert "must_not" not in directives, "Tutor should NOT have 'must_not' (Sprint 90)"


# =============================================================================
# Phase 2: Personality rewrite
# =============================================================================

class TestPersonalityRewrite:
    """Sprint 88b: Wiii is đáng yêu, thích trò chuyện."""

    def test_personality_summary_has_dang_yeu(self):
        """Personality summary should mention đáng yêu."""
        loader = PromptLoader()
        summary = (
            loader.get_identity()
            .get("identity", {})
            .get("personality", {})
            .get("summary", "")
        )
        assert "Đáng yêu" in summary or "đáng yêu" in summary

    def test_personality_summary_has_character_depth(self):
        """Sprint 93: Personality summary should have unique character traits."""
        loader = PromptLoader()
        summary = (
            loader.get_identity()
            .get("identity", {})
            .get("personality", {})
            .get("summary", "")
        )
        assert "Đáng yêu" in summary or "đáng yêu" in summary

    def test_traits_include_enthusiasm(self):
        """Traits should mention nhiệt tình or chia sẻ."""
        loader = PromptLoader()
        traits = (
            loader.get_identity()
            .get("identity", {})
            .get("personality", {})
            .get("traits", [])
        )
        traits_str = " ".join(traits)
        assert "nhiệt tình" in traits_str or "chia sẻ" in traits_str

    def test_traits_include_empathy(self):
        """Traits should mention lắng nghe or đồng cảm."""
        loader = PromptLoader()
        traits = (
            loader.get_identity()
            .get("identity", {})
            .get("personality", {})
            .get("traits", [])
        )
        traits_str = " ".join(traits)
        assert "lắng nghe" in traits_str or "đồng cảm" in traits_str

    def test_identity_anchor_updated(self):
        """Identity anchor should mention đáng yêu."""
        loader = PromptLoader()
        anchor = loader.get_identity().get("identity", {}).get("identity_anchor", "")
        assert "đáng yêu" in anchor


# =============================================================================
# Phase 3: Routing keywords expansion
# =============================================================================

class TestRoutingKeywords:
    """Sprint 88: New maritime routing keywords."""

    def _load_domain_yaml(self):
        import yaml
        path = Path(__file__).parent.parent.parent / "app" / "domains" / "maritime" / "domain.yaml"
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_compass_keywords(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        assert "compass" in keywords_str.lower()
        assert "la bàn" in keywords_str

    def test_psc_keywords(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        assert "PSC" in keywords_str

    def test_tonnage_keywords(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        assert "tonnage" in keywords_str.lower()
        assert "DWT" in keywords_str

    def test_navigation_instruments(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        for kw in ["radar", "ECDIS", "AIS", "GMDSS"]:
            assert kw in keywords_str, f"Missing keyword: {kw}"

    def test_drill_keywords(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        assert "drill" in keywords_str.lower()

    def test_mandatory_triggers_expanded(self):
        config = self._load_domain_yaml()
        triggers_str = " ".join(config.get("mandatory_search_triggers", []))
        for kw in ["compass", "PSC", "radar", "ECDIS", "tonnage"]:
            assert kw in triggers_str, f"Missing trigger: {kw}"

    def test_vhf_communication_keywords(self):
        config = self._load_domain_yaml()
        keywords_str = " ".join(config.get("routing_keywords", []))
        assert "VHF" in keywords_str


# =============================================================================
# Phase 4: Memory facts limit
# =============================================================================

class TestMemoryFactsLimit:
    """Sprint 88: DEFAULT_USER_FACTS_LIMIT raised from 10 to 20."""

    def test_core_limit_is_20(self):
        from app.engine.semantic_memory.core import SemanticMemoryEngine
        assert SemanticMemoryEngine.DEFAULT_USER_FACTS_LIMIT == 20

    def test_context_limit_is_20(self):
        from app.engine.semantic_memory.context import ContextRetriever
        assert ContextRetriever.DEFAULT_USER_FACTS_LIMIT == 20

    def test_limit_covers_all_fact_types(self):
        from app.engine.semantic_memory.core import SemanticMemoryEngine
        assert SemanticMemoryEngine.DEFAULT_USER_FACTS_LIMIT >= 15


# =============================================================================
# Phase 5: Extraction prompt interest broadening
# =============================================================================

class TestExtractionPrompt:
    """Sprint 88: Interest type description broadened."""

    def test_interest_includes_sports(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)
        prompt = extractor._build_enhanced_prompt("test message")
        assert "thể thao" in prompt

    def test_interest_includes_music(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)
        prompt = extractor._build_enhanced_prompt("test message")
        assert "âm nhạc" in prompt

    def test_mu_example_exists(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)
        prompt = extractor._build_enhanced_prompt("test message")
        assert "MU" in prompt


# =============================================================================
# Phase 6: direct_response_node character-driven
# =============================================================================

class TestDirectNodeSuggestionBased:
    """Sprint 88c: direct_response_node uses suggestion-based prompt."""

    @pytest.mark.asyncio
    async def test_direct_node_prompt_is_character_driven(self):
        """System prompt should describe character, not enforce word limits."""
        from app.engine.multi_agent.graph import direct_response_node

        state = {
            "query": "hôm nay thời tiết đẹp",
            "domain_id": "maritime",
            "domain_config": {"name_vi": "Hàng hải"},
            "context": {},
            "routing_metadata": {"intent": "general", "confidence": 0.8},
        }

        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return MagicMock(content="Đúng rồi, hôm nay thời tiết đẹp!", tool_calls=[])

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = capture_ainvoke

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                    return_value=mock_llm), \
             patch("app.services.output_processor.extract_thinking_from_response",
                   return_value=("Đúng rồi, hôm nay thời tiết đẹp!", None)):
            await direct_response_node(state)

        system_content = captured_messages[0].content
        # Character-driven: đáng yêu, thích trò chuyện
        assert "đáng yêu" in system_content
        assert "đa lĩnh vực" in system_content, "Sprint 99: multi-domain prompt"
        # No hard word limit
        assert "GIỚI HẠN CỨNG" not in system_content
