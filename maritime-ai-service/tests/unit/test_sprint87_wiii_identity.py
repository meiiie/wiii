"""
Sprint 87: Wiii Character System — Centralized Identity + BUG #C1 Fix

Tests:
1. wiii_identity.yaml loading
2. BUG #C1 fix — response rules injection into build_system_prompt()
3. get_identity() API
4. Identity anchor in context_manager
5. direct_response_node uses PromptLoader identity
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

from app.prompts.prompt_loader import PromptLoader, get_prompt_loader


# =============================================================================
# Phase 1: wiii_identity.yaml loading
# =============================================================================

class TestWiiiIdentityLoading:
    """Test that wiii_identity.yaml is loaded and cached correctly."""

    def test_load_identity_returns_valid_config(self):
        """PromptLoader._load_identity() should return dict with identity key."""
        loader = PromptLoader()
        identity = loader._load_identity()
        assert isinstance(identity, dict)
        assert "identity" in identity

    def test_identity_has_required_fields(self):
        """Identity config should have name, personality, voice, response_style."""
        loader = PromptLoader()
        identity = loader._load_identity().get("identity", {})
        assert identity.get("name") == "Wiii"
        assert identity.get("created_by") == "The Wiii Lab"
        assert "personality" in identity
        assert "voice" in identity
        assert "response_style" in identity

    def test_identity_personality(self):
        """Personality should have summary and traits."""
        loader = PromptLoader()
        personality = loader._load_identity().get("identity", {}).get("personality", {})
        assert personality.get("summary")
        assert isinstance(personality.get("traits"), list)
        assert len(personality["traits"]) >= 3

    def test_identity_voice(self):
        """Voice config should have language, emoji_usage, formality."""
        loader = PromptLoader()
        voice = loader._load_identity().get("identity", {}).get("voice", {})
        assert voice.get("language") == "vi"
        assert "emoji" in voice.get("emoji_usage", "").lower()
        assert voice.get("formality")

    def test_identity_response_style(self):
        """Response style should have suggestions, avoid (Sprint 88c: suggestion-based)."""
        loader = PromptLoader()
        style = loader._load_identity().get("identity", {}).get("response_style", {})
        assert "suggestions" in style
        assert "avoid" in style
        assert isinstance(style["suggestions"], list)
        assert len(style["suggestions"]) >= 3
        assert isinstance(style["avoid"], list)
        assert len(style["avoid"]) >= 3

    def test_identity_anchor_exists(self):
        """Identity anchor for anti-drift should exist."""
        loader = PromptLoader()
        anchor = loader._load_identity().get("identity", {}).get("identity_anchor", "")
        assert "Wiii" in anchor

    def test_load_identity_fallback_when_missing(self):
        """Should return empty dict when wiii_identity.yaml doesn't exist."""
        loader = PromptLoader(prompts_dir="/nonexistent/path")
        identity = loader._load_identity()
        assert identity == {}

    def test_identity_cached_in_init(self):
        """Identity should be cached as self._identity during __init__."""
        loader = PromptLoader()
        assert hasattr(loader, "_identity")
        assert isinstance(loader._identity, dict)
        assert "identity" in loader._identity


# =============================================================================
# Phase 2: get_identity() API
# =============================================================================

class TestGetIdentity:
    """Test get_identity() method."""

    def test_get_identity_returns_dict(self):
        """get_identity() should return the cached identity dict."""
        loader = PromptLoader()
        identity = loader.get_identity()
        assert isinstance(identity, dict)
        assert "identity" in identity

    def test_get_identity_matches_internal(self):
        """get_identity() should return same object as _identity."""
        loader = PromptLoader()
        assert loader.get_identity() is loader._identity

    def test_get_identity_via_singleton(self):
        """Singleton get_prompt_loader() should expose get_identity()."""
        # Reset singleton for clean test
        import app.prompts.prompt_loader as mod
        old = mod._prompt_loader
        mod._prompt_loader = None
        try:
            loader = get_prompt_loader()
            identity = loader.get_identity()
            assert isinstance(identity, dict)
        finally:
            mod._prompt_loader = old


# =============================================================================
# Phase 3: BUG #C1 fix — response rules injection
# =============================================================================

class TestBugC1Fix:
    """BUG #C1: response_quality in _shared.yaml was NEVER injected. Now fixed."""

    def test_build_system_prompt_contains_identity_section(self):
        """build_system_prompt() output should contain TÍNH CÁCH WIII section."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", user_name="Test")
        assert "TÍNH CÁCH WIII" in prompt

    def test_build_system_prompt_contains_emoji_usage(self):
        """Prompt should include emoji usage instruction from identity."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "EMOJI:" in prompt
        assert "emoji" in prompt.lower()

    def test_build_system_prompt_contains_response_style(self):
        """Prompt should include response style from identity (Sprint 88b: character-driven)."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "PHONG CÁCH TRẢ LỜI" in prompt

    def test_build_system_prompt_contains_avoid_rules(self):
        """Prompt should include avoid rules from identity (Sprint 88c)."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "QUY TẮC PHONG CÁCH:" in prompt
        assert "ẩn dụ gượng ép" in prompt.lower()

    def test_build_system_prompt_contains_personality_summary(self):
        """Prompt should include personality summary."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "Đáng yêu" in prompt or "đáng yêu" in prompt or "thân thiện" in prompt

    def test_identity_rules_present_for_all_roles(self):
        """Identity section should appear for student, teacher, and admin."""
        loader = PromptLoader()
        for role in ["student", "teacher", "admin"]:
            prompt = loader.build_system_prompt(role=role)
            assert "TÍNH CÁCH WIII" in prompt, f"Missing identity for role={role}"

    def test_shared_yaml_no_longer_has_response_quality_data(self):
        """_shared.yaml should no longer contain response_quality data (moved to identity)."""
        shared_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "base" / "_shared.yaml"
        if shared_path.exists():
            import yaml
            with open(shared_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            # response_quality key should not have sub-keys (data moved to identity)
            rq = config.get("response_quality")
            assert rq is None, "response_quality data should be removed from _shared.yaml"


# =============================================================================
# Phase 4: Agent name unification
# =============================================================================

class TestAgentNameUnification:
    """Sprint 87: All agents should use 'Wiii' as name."""

    def test_rag_agent_name_is_wiii(self):
        """RAG agent should have name='Wiii'."""
        import yaml
        rag_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "rag.yaml"
        with open(rag_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["agent"]["name"] == "Wiii"

    def test_memory_agent_name_is_wiii(self):
        """Memory agent should have name='Wiii'."""
        import yaml
        memory_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "memory.yaml"
        with open(memory_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["agent"]["name"] == "Wiii"

    def test_rag_backstory_simplified(self):
        """RAG backstory should be simplified (identity is centralized)."""
        import yaml
        rag_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "rag.yaml"
        with open(rag_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        backstory = config["agent"]["backstory"]
        # Should be shorter than before (was 3 lines, now ~2)
        assert len(backstory.strip()) < 200

    def test_memory_backstory_simplified(self):
        """Memory backstory should be simplified (identity is centralized)."""
        import yaml
        memory_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "memory.yaml"
        with open(memory_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        backstory = config["agent"]["backstory"]
        assert len(backstory.strip()) < 200


# =============================================================================
# Phase 5: Identity anchor in context_manager
# =============================================================================

class TestIdentityAnchor:
    """Sprint 87: Identity anchor injected at compaction for anti-drift."""

    def test_summary_prompt_includes_anchor(self):
        """_build_summary_prompt should include PERSONA REMINDER."""
        from app.engine.context_manager import ConversationCompactor
        compactor = ConversationCompactor()
        messages = [
            {"role": "user", "content": "Xin chào, tôi là Minh"},
            {"role": "assistant", "content": "Chào Minh!"},
        ]
        prompt = compactor._build_summary_prompt(messages, existing_summary="")
        assert "PERSONA REMINDER" in prompt
        assert "Wiii" in prompt

    def test_summary_prompt_with_existing_summary_includes_anchor(self):
        """Anchor should be present even when there's an existing summary."""
        from app.engine.context_manager import ConversationCompactor
        compactor = ConversationCompactor()
        messages = [
            {"role": "user", "content": "Tiếp tục bài học"},
        ]
        prompt = compactor._build_summary_prompt(messages, existing_summary="Minh đang học COLREGs")
        assert "PERSONA REMINDER" in prompt


# =============================================================================
# Phase 7: direct_response_node uses PromptLoader identity
# =============================================================================

class TestDirectNodeUsesIdentity:
    """Sprint 87: direct_response_node reads from PromptLoader instead of hardcoded."""

    @pytest.mark.asyncio
    async def test_direct_node_system_prompt_has_identity_content(self):
        """System prompt should contain identity-derived content."""
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
        # Should still be helpful (Sprint 99: multi-domain, not "MỌI câu hỏi")
        assert "đa lĩnh vực" in system_content
        # Should have identity-derived personality
        assert "Wiii" in system_content or settings_app_name_in(system_content)

    @pytest.mark.asyncio
    async def test_direct_node_still_allows_all_questions(self):
        """Sprint 80b behavior preserved: never refuses."""
        from app.engine.multi_agent.graph import direct_response_node

        state = {
            "query": "nấu cơm thế nào",
            "domain_id": "maritime",
            "domain_config": {"name_vi": "Hàng hải"},
            "context": {},
            "routing_metadata": {"intent": "off_topic", "confidence": 0.9},
        }

        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return MagicMock(content="Nấu cơm khá đơn giản...", tool_calls=[])

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = capture_ainvoke

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                    return_value=mock_llm), \
             patch("app.services.output_processor.extract_thinking_from_response",
                   return_value=("Nấu cơm khá đơn giản...", None)):
            result = await direct_response_node(state)

        system_content = captured_messages[0].content
        assert "đa lĩnh vực" in system_content
        assert "từ chối" not in system_content


def settings_app_name_in(text: str) -> bool:
    """Helper: check if settings.app_name appears in text."""
    try:
        from app.core.config import settings
        return settings.app_name in text
    except Exception:
        return "Wiii" in text
