"""
Sprint 91: VTuber Character Card Standard — Fix Dead YAML + Enhance Identity

Tests:
1. wiii_identity.yaml has all VTuber-standard fields (backstory, greeting, example_dialogues, emotional_range)
2. prompt_loader.py key mappings fixed (agent→profile, must→dos, examples→few_shot_examples, etc.)
3. build_system_prompt() output contains all injected sections
4. No contradictory "Thuyền phó 1 đã về hưu" backstory
5. All agent YAMLs use 'avoid' not 'must_not'
6. Tone rendered as single string (not character-by-character)
7. thought_process.steps rendered correctly
"""

import sys
import types
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Break circular import (graph → services → chat_service → graph)
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.prompts.prompt_loader import PromptLoader


# =============================================================================
# Paths
# =============================================================================
PROMPTS_DIR = Path(__file__).parent.parent.parent / "app" / "prompts"
MARITIME_DIR = Path(__file__).parent.parent.parent / "app" / "domains" / "maritime" / "prompts"


# =============================================================================
# Phase 1: VTuber Character Card fields in wiii_identity.yaml
# =============================================================================

class TestIdentityCharacterCard:
    """Verify wiii_identity.yaml has all VTuber-standard fields."""

    @pytest.fixture
    def identity(self):
        path = PROMPTS_DIR / "wiii_identity.yaml"
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)["identity"]

    def test_has_backstory(self, identity):
        """VTuber standard: backstory is the unified origin story."""
        backstory = identity.get("backstory", "")
        assert backstory.strip(), "backstory should not be empty"
        assert "The Wiii Lab" in backstory
        assert "AI" in backstory

    def test_backstory_no_contradiction(self, identity):
        """Backstory should NOT claim to be a retired human officer."""
        backstory = identity.get("backstory", "")
        assert "Thuyền phó" not in backstory
        assert "về hưu" not in backstory

    def test_has_greeting(self, identity):
        """VTuber standard: greeting is the canonical first message."""
        greeting = identity.get("greeting", "")
        assert greeting.strip(), "greeting should not be empty"
        assert "Wiii" in greeting

    def test_has_example_dialogues(self, identity):
        """VTuber standard: example_dialogues with Ali:Chat format."""
        examples = identity.get("example_dialogues", [])
        assert len(examples) >= 3, f"Need at least 3 examples, got {len(examples)}"
        for ex in examples:
            assert "context" in ex, "Each example needs 'context'"
            assert "user" in ex, "Each example needs 'user'"
            assert "wiii" in ex, "Each example needs 'wiii'"

    def test_example_dialogues_emotional_range(self, identity):
        """Examples should cover different emotional situations."""
        examples = identity.get("example_dialogues", [])
        contexts = [ex.get("context", "") for ex in examples]
        contexts_str = " ".join(contexts).lower()
        # Should cover at least tired/knowledge/greeting
        assert "mệt" in contexts_str or "buồn" in contexts_str
        assert "kiến thức" in contexts_str or "hỏi" in contexts_str

    def test_has_emotional_range(self, identity):
        """VTuber standard: emotional_range describes reactions."""
        emotional_range = identity.get("emotional_range", {})
        assert len(emotional_range) >= 3, f"Need at least 3 emotions, got {len(emotional_range)}"
        assert "happy" in emotional_range
        assert "empathetic" in emotional_range
        assert "teaching" in emotional_range

    def test_emotional_range_values_are_strings(self, identity):
        """Each emotional_range value is a descriptive string."""
        for mood, behavior in identity.get("emotional_range", {}).items():
            assert isinstance(behavior, str), f"{mood} should be string"
            assert len(behavior) > 5, f"{mood} description too short"

    def test_existing_fields_preserved(self, identity):
        """Original fields (name, personality, voice, response_style) still present."""
        assert identity["name"] == "Wiii"
        assert "personality" in identity
        assert "voice" in identity
        assert "response_style" in identity
        assert "identity_anchor" in identity


# =============================================================================
# Phase 2: Prompt Loader Key Mappings Fixed
# =============================================================================

class TestPromptLoaderKeyMappings:
    """Verify fixed key mappings: agent→profile, must→dos, examples→few_shot_examples."""

    @pytest.fixture
    def loader(self):
        return PromptLoader()

    def test_agent_name_appears_in_prompt(self, loader):
        """agent.name from YAML should appear in built prompt."""
        prompt = loader.build_system_prompt(role="student")
        assert "Wiii" in prompt

    def test_agent_backstory_appears_in_prompt(self, loader):
        """agent.backstory from YAML should appear in built prompt."""
        prompt = loader.build_system_prompt(role="student")
        # Tutor backstory now says "Mentor hướng dẫn"
        assert "Mentor" in prompt or "hướng dẫn" in prompt

    def test_directives_must_appears_in_prompt(self, loader):
        """directives.must from YAML should appear in NÊN LÀM section."""
        prompt = loader.build_system_prompt(role="student")
        assert "NÊN LÀM" in prompt
        # Tutor must: "Socratic"
        assert "Socratic" in prompt

    def test_directives_avoid_appears_in_prompt(self, loader):
        """directives.avoid from YAML should appear in TRÁNH section."""
        prompt = loader.build_system_prompt(role="student")
        assert "TRÁNH" in prompt

    def test_examples_appear_in_prompt(self, loader):
        """examples[] with input/output sub-keys should appear in VÍ DỤ section."""
        prompt = loader.build_system_prompt(role="student")
        assert "VÍ DỤ CÁCH TRẢ LỜI" in prompt
        # Tutor example: "COLREGs" or "Rule 15"
        assert "COLREGs" in prompt or "Quy tắc 15" in prompt

    def test_tone_rendered_as_string_not_chars(self, loader):
        """Tone string should appear as one item, not character-by-character."""
        prompt = loader.build_system_prompt(role="student")
        assert "GIỌNG VĂN" in prompt
        # Tone is "Ấm áp, tin cậy, đôi chút hài hước nghề biển"
        # If iterated char-by-char, we'd see "- Ấ" and "- m" separately
        # But correct rendering should have the full string
        assert "Ấm áp" in prompt

    def test_thought_process_steps_rendered(self, loader):
        """thought_process.steps should be numbered and rendered correctly."""
        prompt = loader.build_system_prompt(role="student")
        assert "QUY TRÌNH SUY NGHĨ" in prompt
        # Steps: "User đang hỏi kiến thức hay đang chia sẻ cảm xúc?"
        assert "kiến thức" in prompt.lower() or "cảm xúc" in prompt.lower()

    def test_thought_process_not_renders_steps_key(self, loader):
        """Should NOT render 'steps' as a step instruction."""
        prompt = loader.build_system_prompt(role="student")
        lines = prompt.split("\n")
        # The old code would iterate dict items of thought_process, including 'steps' key
        for line in lines:
            if line.startswith("1.") and "QUY TRÌNH" not in line:
                assert "steps" != line.strip().split(". ", 1)[-1] if ". " in line else True


# =============================================================================
# Phase 2b: Identity sections injected into prompt
# =============================================================================

class TestIdentityInjection:
    """Verify new VTuber sections injected into build_system_prompt."""

    @pytest.fixture
    def prompt(self):
        loader = PromptLoader()
        return loader.build_system_prompt(role="student")

    def test_emotional_range_injected(self, prompt):
        """Emotional range from identity should appear in prompt."""
        assert "CẢM XÚC:" in prompt
        assert "happy" in prompt.lower() or "empathetic" in prompt.lower()

    def test_example_dialogues_injected(self, prompt):
        """Example dialogues from identity should appear in prompt."""
        assert "VÍ DỤ CÁCH WIII NÓI CHUYỆN" in prompt
        # Check that at least one example context appears
        assert "User:" in prompt and "Wiii:" in prompt

    def test_example_dialogues_have_context(self, prompt):
        """Each example should have its [context] bracket."""
        # Count occurrences of "[User" pattern in the identity examples section
        # The identity examples use [context] format
        assert "[User mệt mỏi]" in prompt or "[User hỏi kiến thức]" in prompt

    def test_example_dialogues_limited_to_8(self):
        """Sprint 115: Should inject at most 8 examples from identity (was 5)."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Count "Wiii:" occurrences in identity example section
        idx = prompt.find("VÍ DỤ CÁCH WIII NÓI CHUYỆN")
        if idx >= 0:
            identity_section = prompt[idx:prompt.find("---", idx + 1)] if "---" in prompt[idx + 1:] else prompt[idx:]
            wiii_count = identity_section.count("Wiii:")
            assert wiii_count <= 8


# =============================================================================
# Phase 3: No character contradiction in built prompt
# =============================================================================

class TestNoCharacterContradiction:
    """No retired human officer backstory should appear in built prompts."""

    @pytest.fixture
    def loader(self):
        return PromptLoader()

    def test_student_prompt_no_retired_officer(self, loader):
        """Student prompt should not mention retired Chief Officer."""
        prompt = loader.build_system_prompt(role="student")
        assert "Thuyền phó 1" not in prompt
        assert "đã về hưu" not in prompt
        assert "Chief Officer" not in prompt

    def test_teacher_prompt_no_retired_officer(self, loader):
        """Teacher prompt should not mention retired Chief Officer."""
        prompt = loader.build_system_prompt(role="teacher")
        assert "Thuyền phó 1" not in prompt
        assert "đã về hưu" not in prompt

    def test_admin_prompt_no_retired_officer(self, loader):
        """Admin prompt should not mention retired Chief Officer."""
        prompt = loader.build_system_prompt(role="admin")
        assert "Thuyền phó 1" not in prompt
        assert "đã về hưu" not in prompt

    def test_tutor_yaml_backstory_is_functional(self):
        """Tutor YAML backstory should describe function, not character."""
        path = PROMPTS_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        backstory = config["agent"]["backstory"]
        assert "Mentor" in backstory or "hướng dẫn" in backstory
        assert "Thuyền phó" not in backstory

    def test_maritime_tutor_yaml_backstory_is_functional(self):
        """Maritime domain tutor YAML backstory should be functional too."""
        path = MARITIME_DIR / "agents" / "tutor.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        backstory = config["agent"]["backstory"]
        assert "Mentor" in backstory or "hướng dẫn" in backstory
        assert "Thuyền phó" not in backstory


# =============================================================================
# Phase 3b: All agent YAMLs use 'avoid' not 'must_not'
# =============================================================================

class TestAllYamlsUseAvoid:
    """Sprint 91: Remaining must_not → avoid conversions."""

    def test_platform_assistant_uses_avoid(self):
        """assistant.yaml should use 'avoid' not 'must_not'."""
        path = PROMPTS_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "avoid" in directives, "assistant.yaml needs 'avoid'"
        assert "must_not" not in directives, "assistant.yaml should NOT have 'must_not'"

    def test_platform_rag_uses_avoid(self):
        """rag.yaml should use 'avoid' not 'must_not'."""
        path = PROMPTS_DIR / "agents" / "rag.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "avoid" in directives, "rag.yaml needs 'avoid'"
        assert "must_not" not in directives, "rag.yaml should NOT have 'must_not'"

    def test_platform_memory_uses_avoid(self):
        """memory.yaml should use 'avoid' not 'must_not'."""
        path = PROMPTS_DIR / "agents" / "memory.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "avoid" in directives, "memory.yaml needs 'avoid'"
        assert "must_not" not in directives, "memory.yaml should NOT have 'must_not'"

    def test_maritime_assistant_no_must_not(self):
        """Maritime assistant.yaml (minimal overlay) should NOT have 'must_not'.
        Sprint 92: Maritime overlays are minimal — directives inherited from platform."""
        path = MARITIME_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "must_not" not in directives

    def test_maritime_rag_no_must_not(self):
        """Maritime rag.yaml (minimal overlay) should NOT have 'must_not'.
        Sprint 92: Directives inherited from platform via merge."""
        path = MARITIME_DIR / "agents" / "rag.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "must_not" not in directives

    def test_maritime_memory_no_must_not(self):
        """Maritime memory.yaml (minimal overlay) should NOT have 'must_not'.
        Sprint 92: Directives inherited from platform via merge."""
        path = MARITIME_DIR / "agents" / "memory.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        directives = config.get("directives", {})
        assert "must_not" not in directives


# =============================================================================
# Phase 4: Assistant backstory functional
# =============================================================================

class TestAssistantBackstoryFunctional:
    """Assistant YAML backstory should be functional, not character."""

    def test_platform_assistant_backstory(self):
        """Platform assistant.yaml backstory is role-based."""
        path = PROMPTS_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        backstory = config["agent"]["backstory"]
        assert "Vai trò" in backstory or "Hỗ trợ" in backstory

    def test_assistant_avoid_content(self):
        """Assistant avoid rules should be present and reasonable."""
        path = PROMPTS_DIR / "agents" / "assistant.yaml"
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        avoid = config["directives"]["avoid"]
        assert len(avoid) >= 2
        # Check content is about professionalism
        avoid_text = " ".join(avoid).lower()
        assert "giới tính" in avoid_text or "trống" in avoid_text


# =============================================================================
# Phase 5: Full integration — build_system_prompt comprehensive check
# =============================================================================

class TestBuildSystemPromptIntegration:
    """Comprehensive check that build_system_prompt produces correct output."""

    @pytest.fixture
    def student_prompt(self):
        loader = PromptLoader()
        return loader.build_system_prompt(
            role="student",
            user_name="Minh",
            is_follow_up=True,
            total_responses=5,
        )

    def test_has_profile_section(self, student_prompt):
        """Prompt starts with agent identity."""
        assert "Wiii" in student_prompt

    def test_has_identity_personality(self, student_prompt):
        """TÍNH CÁCH WIII section present."""
        assert "TÍNH CÁCH WIII" in student_prompt

    def test_has_response_style(self, student_prompt):
        """PHONG CÁCH TRẢ LỜI section present."""
        assert "PHONG CÁCH TRẢ LỜI" in student_prompt

    def test_has_avoid_rules(self, student_prompt):
        """QUY TẮC PHONG CÁCH section present."""
        assert "QUY TẮC PHONG CÁCH" in student_prompt

    def test_has_emotional_range(self, student_prompt):
        """CẢM XÚC section present."""
        assert "CẢM XÚC:" in student_prompt

    def test_has_identity_examples(self, student_prompt):
        """VÍ DỤ CÁCH WIII NÓI CHUYỆN section present."""
        assert "VÍ DỤ CÁCH WIII NÓI CHUYỆN" in student_prompt

    def test_has_tone_section(self, student_prompt):
        """GIỌNG VĂN section present with full string."""
        assert "GIỌNG VĂN" in student_prompt

    def test_has_thought_process(self, student_prompt):
        """QUY TRÌNH SUY NGHĨ section present."""
        assert "QUY TRÌNH SUY NGHĨ" in student_prompt

    def test_has_directives(self, student_prompt):
        """NÊN LÀM and TRÁNH sections present."""
        assert "NÊN LÀM" in student_prompt
        assert "TRÁNH" in student_prompt

    def test_has_agent_examples(self, student_prompt):
        """VÍ DỤ CÁCH TRẢ LỜI section from agent YAML present."""
        assert "VÍ DỤ CÁCH TRẢ LỜI" in student_prompt

    def test_has_tools_section(self, student_prompt):
        """SỬ DỤNG CÔNG CỤ section present."""
        assert "SỬ DỤNG CÔNG CỤ" in student_prompt

    def test_has_user_context(self, student_prompt):
        """THÔNG TIN NGƯỜI DÙNG section with name."""
        assert "Minh" in student_prompt

    def test_has_variation_section(self, student_prompt):
        """HƯỚNG DẪN ĐA DẠNG HÓA section for follow-up."""
        assert "HƯỚNG DẪN ĐA DẠNG HÓA" in student_prompt
        assert "FOLLOW-UP" in student_prompt

    def test_user_name_template_replaced_in_directives(self, student_prompt):
        """{{user_name}} should be replaced with 'Minh' in directives."""
        assert "{{user_name}}" not in student_prompt
        # Check that Minh appears in the directives section
        assert "Minh" in student_prompt


# =============================================================================
# Phase 6: Edge cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases in key mapping fixes."""

    def test_old_format_persona_still_works(self):
        """Default persona (no YAML) should still render."""
        loader = PromptLoader()
        # Force a persona without 'agent' or 'profile' key
        loader._personas["test_role"] = {
            "role": "Test Role",
            "description": "A test description",
            "tone": ["Friendly"],
        }
        prompt = loader.build_system_prompt(role="test_role")
        assert "Test Role" in prompt

    def test_tone_as_list_works(self):
        """Tone as list should render each item."""
        loader = PromptLoader()
        loader._personas["test_list_tone"] = {
            "style": {"tone": ["Friendly", "Professional"]},
        }
        prompt = loader.build_system_prompt(role="test_list_tone")
        assert "Friendly" in prompt
        assert "Professional" in prompt

    def test_tone_as_string_works(self):
        """Tone as string should render as one item."""
        loader = PromptLoader()
        loader._personas["test_str_tone"] = {
            "style": {"tone": "Warm and casual"},
        }
        prompt = loader.build_system_prompt(role="test_str_tone")
        assert "Warm and casual" in prompt
        # Should NOT have individual characters
        assert "- W\n" not in prompt

    def test_thought_process_with_steps_list(self):
        """Steps list of dicts should render correctly."""
        loader = PromptLoader()
        loader._personas["test_steps"] = {
            "thought_process": {
                "steps": [
                    {"analyze": "Check the question"},
                    {"respond": "Draft answer"},
                ]
            },
        }
        prompt = loader.build_system_prompt(role="test_steps")
        assert "1. Check the question" in prompt
        assert "2. Draft answer" in prompt

    def test_thought_process_empty_gracefully(self):
        """Empty thought_process should not crash."""
        loader = PromptLoader()
        loader._personas["test_empty_tp"] = {
            "thought_process": {},
        }
        prompt = loader.build_system_prompt(role="test_empty_tp")
        assert "QUY TRÌNH SUY NGHĨ" not in prompt

    def test_directives_must_fallback_to_dos(self):
        """If YAML uses 'dos' key, it should still work."""
        loader = PromptLoader()
        loader._personas["test_dos"] = {
            "directives": {
                "dos": ["Rule 1", "Rule 2"],
                "donts": ["Bad thing"],
            },
        }
        prompt = loader.build_system_prompt(role="test_dos")
        assert "Rule 1" in prompt
        assert "Bad thing" in prompt

    def test_examples_fallback_to_few_shot(self):
        """If YAML uses 'few_shot_examples' key, it should still work."""
        loader = PromptLoader()
        loader._personas["test_fewshot"] = {
            "few_shot_examples": [
                {"context": "test", "user": "Hello", "ai": "Hi there!"},
            ],
        }
        prompt = loader.build_system_prompt(role="test_fewshot")
        assert "Hello" in prompt
        assert "Hi there!" in prompt

    def test_examples_input_output_keys(self):
        """Examples with input/output sub-keys should work."""
        loader = PromptLoader()
        loader._personas["test_io"] = {
            "examples": [
                {"context": "Q&A", "input": "What is X?", "output": "X is..."},
            ],
        }
        prompt = loader.build_system_prompt(role="test_io")
        assert "What is X?" in prompt
        assert "X is..." in prompt
