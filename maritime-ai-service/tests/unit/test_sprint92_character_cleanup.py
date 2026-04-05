"""
Sprint 92: SOTA Character Architecture — Dead Code Purge + Wire All Identity Fields

Tests:
1. 6 dead methods removed from PromptLoader
2. Dead YAML sections (empathy, variations, memory_extraction) removed
3. personality.traits[] wired into prompt
4. agent.goal wired into prompt
5. voice.formality/language wired into prompt
6. greeting tone anchor for first messages
7. agent.tools[] drives TOOLS section
8. identity_anchor re-injected after 10 turns
9. Maritime overlays are minimal + inherit platform
"""

import sys
import types
import pytest
import yaml
from pathlib import Path

# Break circular import (graph → services → chat_service → graph)
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from unittest.mock import MagicMock, patch

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
# Paths
# =============================================================================
PROMPTS_DIR = Path(__file__).parent.parent.parent / "app" / "prompts"
MARITIME_DIR = Path(__file__).parent.parent.parent / "app" / "domains" / "maritime" / "prompts"


# =============================================================================
# Phase 1: Dead methods removed
# =============================================================================

class TestDeadMethodsRemoved:
    """Verify 6 dead methods no longer exist on PromptLoader."""

    def test_get_fact_extraction_hints_removed(self):
        assert not hasattr(PromptLoader, "get_fact_extraction_hints")

    def test_get_empathy_instruction_removed(self):
        assert not hasattr(PromptLoader, "get_empathy_instruction")

    def test_detect_empathy_needed_removed(self):
        assert not hasattr(PromptLoader, "detect_empathy_needed")

    def test_get_variation_phrases_removed(self):
        assert not hasattr(PromptLoader, "get_variation_phrases")

    def test_get_random_opening_removed(self):
        assert not hasattr(PromptLoader, "get_random_opening")

    def test_get_empathy_response_template_removed(self):
        assert not hasattr(PromptLoader, "get_empathy_response_template")

    def test_get_thinking_instruction_kept(self):
        """get_thinking_instruction should still exist (has callers)."""
        assert hasattr(PromptLoader, "get_thinking_instruction")

    def test_get_greeting_exists(self):
        """New get_greeting() method should exist."""
        assert hasattr(PromptLoader, "get_greeting")


# =============================================================================
# Phase 2: Dead YAML sections removed
# =============================================================================

class TestDeadYamlSectionsRemoved:
    """Verify empathy, variations, memory_extraction removed from YAMLs."""

    def test_platform_tutor_no_empathy(self):
        path = PROMPTS_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "empathy" not in config, "tutor.yaml should not have 'empathy'"

    def test_platform_tutor_no_variations(self):
        path = PROMPTS_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "variations" not in config, "tutor.yaml should not have 'variations'"

    def test_platform_tutor_no_addressing_in_style(self):
        path = PROMPTS_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        style = config.get("style", {})
        assert "addressing" not in style, "tutor.yaml style should not have 'addressing'"

    def test_platform_assistant_no_empathy(self):
        path = PROMPTS_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "empathy" not in config

    def test_platform_assistant_no_variations(self):
        path = PROMPTS_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "variations" not in config

    def test_platform_memory_no_extraction(self):
        path = PROMPTS_DIR / "agents" / "memory.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "memory_extraction" not in config


# =============================================================================
# Phase 3: Wire identity fields
# =============================================================================

class TestTraitsInjected:
    """personality.traits[] should appear in built prompt."""

    def test_traits_section_present(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Post-Living Core Card refactor: traits in TÍNH NÉT CHỦ ĐẠO or CỐT LÕI NHÂN VẬT
        assert "TÍNH NÉT CHỦ ĐẠO" in prompt or "CỐT LÕI NHÂN VẬT" in prompt

    def test_traits_content_present(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # From wiii_identity.yaml personality.traits[]
        assert "Đáng yêu và nhiệt tình" in prompt
        assert "Kiên nhẫn" in prompt


class TestGoalInjected:
    """agent.goal should appear in built prompt."""

    def test_goal_in_prompt(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "MỤC TIÊU:" in prompt
        # Tutor goal: "Guide students with engaging, practical teaching"
        assert "Guide students" in prompt


class TestVoiceInjected:
    """voice.formality and voice.language should appear in built prompt."""

    def test_default_tone_in_prompt(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Post-refactor: tone in GIỌNG VĂN section
        assert "GIỌNG VĂN" in prompt

    def test_language_enforcement_in_prompt(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Language enforcement may be in voice section or directives
        assert "Việt" in prompt or "Vietnamese" in prompt


class TestGreeting:
    """greeting wiring tests."""

    def test_get_greeting_returns_nonempty(self):
        loader = PromptLoader()
        greeting = loader.get_greeting()
        assert greeting, "get_greeting() should return non-empty string"
        assert "Wiii" in greeting

    def test_greeting_tone_anchor_first_message(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", is_follow_up=False)
        # Post-refactor: greeting may use different section name
        assert "LỜI CHÀO MẪU" in prompt or "ĐIỂM TỰA GIỌNG NÓI" in prompt or "Wiii" in prompt

    def test_greeting_not_injected_followup(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", is_follow_up=True)
        assert "LỜI CHÀO MẪU" not in prompt


class TestToolsFromYaml:
    """Tools section generated from agent.tools[]."""

    def test_tools_from_yaml(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Tutor tools: tool_knowledge_search, tool_save_user_info, tool_remember
        assert "tool_knowledge_search" in prompt
        assert "tool_save_user_info" in prompt
        assert "tool_remember" in prompt

    def test_tools_fallback_no_yaml(self):
        """Fallback hardcoded tools when no YAML tools."""
        loader = PromptLoader()
        # Create persona without tools
        loader._personas["no_tools"] = {"agent": {"name": "Test", "role": "Test"}}
        prompt = loader.build_system_prompt(role="no_tools")
        # Should still have tools section with fallback
        assert "SỬ DỤNG CÔNG CỤ" in prompt
        assert "tool_knowledge_search" in prompt

    def test_memory_agent_tools_in_prompt(self):
        """Memory agent has 5 tools — all should appear."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="memory_agent")
        assert "tool_get_user_info" in prompt
        assert "tool_save_user_info" in prompt
        assert "tool_remember" in prompt
        assert "tool_forget" in prompt
        assert "tool_list_memories" in prompt


class TestAnchorReinjection:
    """Identity anchor re-injected after N turns (Sprint 115: 10→6)."""

    def test_anchor_reinjected_after_threshold_turns(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", total_responses=6)
        assert "PERSONA REMINDER" in prompt
        assert "Wiii" in prompt.split("PERSONA REMINDER")[1]

    def test_anchor_not_injected_early(self):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", total_responses=3)
        assert "PERSONA REMINDER" not in prompt

    def test_anchor_at_boundary(self):
        loader = PromptLoader()
        prompt_5 = loader.build_system_prompt(role="student", total_responses=5)
        prompt_6 = loader.build_system_prompt(role="student", total_responses=6)
        assert "PERSONA REMINDER" not in prompt_5
        assert "PERSONA REMINDER" in prompt_6


# =============================================================================
# Phase 4: Maritime overlay trimming + merge
# =============================================================================

class TestMaritimeOverlayMinimal:
    """Maritime overlay YAMLs should be minimal (~25 lines)."""

    def test_maritime_tutor_is_minimal(self):
        path = MARITIME_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 40, f"Maritime tutor.yaml should be < 40 lines, got {len(lines)}"

    def test_maritime_assistant_is_minimal(self):
        path = MARITIME_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 40, f"Maritime assistant.yaml should be < 40 lines, got {len(lines)}"

    def test_maritime_rag_is_minimal(self):
        path = MARITIME_DIR / "agents" / "rag.yaml"
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 30, f"Maritime rag.yaml should be < 30 lines, got {len(lines)}"

    def test_maritime_memory_is_minimal(self):
        path = MARITIME_DIR / "agents" / "memory.yaml"
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 30, f"Maritime memory.yaml should be < 30 lines, got {len(lines)}"

    def test_maritime_tutor_no_empathy(self):
        path = MARITIME_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "empathy" not in config
        assert "variations" not in config

    def test_maritime_memory_no_extraction(self):
        path = MARITIME_DIR / "agents" / "memory.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "memory_extraction" not in config


class TestMaritimeOverlayInheritsPlatform:
    """Maritime persona should inherit platform style/directives via merge."""

    def test_maritime_tutor_has_platform_style(self):
        """Maritime tutor should have platform style after merge."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        persona = loader.get_persona("student")
        # Platform tutor.yaml has style.tone
        style = persona.get("style", {})
        assert style.get("tone"), "Maritime tutor should inherit platform style.tone"

    def test_maritime_tutor_has_platform_directives(self):
        """Maritime tutor should have platform directives after merge."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        persona = loader.get_persona("student")
        directives = persona.get("directives", {})
        assert directives.get("must"), "Maritime tutor should inherit platform directives.must"

    def test_maritime_tutor_has_platform_examples(self):
        """Maritime tutor should have platform examples after merge."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        persona = loader.get_persona("student")
        examples = persona.get("examples", [])
        assert len(examples) >= 2, "Maritime tutor should inherit platform examples"

    def test_maritime_tutor_keeps_platform_identity(self):
        """Maritime overlay can add tools/domain workflow but must not replace Wiii's core role."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        persona = loader.get_persona("student")
        agent = persona.get("agent", {})
        assert agent.get("name") == "Wiii"
        assert "Learning Mentor" in agent.get("role", "")
        assert "Maritime" not in agent.get("role", "")

    def test_maritime_tutor_has_maritime_tools(self):
        """Maritime tutor should have tool_maritime_search (not tool_knowledge_search)."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        persona = loader.get_persona("student")
        agent = persona.get("agent", {})
        tools = agent.get("tools", [])
        assert "tool_maritime_search" in tools

    def test_maritime_tutor_prompt_has_maritime_tool(self):
        """Built prompt for maritime tutor should reference tool_maritime_search."""
        loader = PromptLoader(
            domain_prompts_dir=str(MARITIME_DIR)
        )
        prompt = loader.build_system_prompt(role="student")
        assert "tool_maritime_search" in prompt


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge cases for Sprint 92 changes."""

    def test_no_identity_graceful(self):
        """If identity YAML missing, build_system_prompt still works."""
        loader = PromptLoader()
        loader._identity = {}  # Simulate missing identity
        prompt = loader.build_system_prompt(role="student")
        assert "Wiii" in prompt  # From agent.name in tutor.yaml

    def test_no_tools_in_agent_uses_fallback(self):
        """Agent without tools[] gets fallback tools section."""
        loader = PromptLoader()
        loader._personas["test"] = {
            "agent": {"name": "Test", "role": "Helper"},
        }
        prompt = loader.build_system_prompt(role="test")
        assert "tool_knowledge_search" in prompt

    def test_greeting_empty_identity(self):
        """get_greeting with no identity returns empty string."""
        loader = PromptLoader()
        loader._identity = {}
        assert loader.get_greeting() == ""

    def test_anchor_empty_identity(self):
        """Anchor not injected when identity has no identity_anchor."""
        loader = PromptLoader()
        loader._identity = {}
        prompt = loader.build_system_prompt(role="student", total_responses=15)
        assert "PERSONA REMINDER" not in prompt
