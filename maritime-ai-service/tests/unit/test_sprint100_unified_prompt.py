"""
Sprint 100: Unified Prompt Composition — direct_response_node uses PromptLoader

Tests:
1. direct.yaml loads correctly
2. direct_agent registered in PromptLoader personas
3. build_system_prompt with tools_context override
4. tools_context=None preserves existing behavior for tutor/rag/memory
5. direct_response_node uses PromptLoader.build_system_prompt
6. Backward compatibility: key strings present
7. Identity, anti-greeting, living state injected
8. _build_direct_tools_context helper
"""
import sys
import types
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Break circular import (same pattern as test_sprint97/99)
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs


from app.prompts.prompt_loader import PromptLoader, get_prompt_loader


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
# Phase 1: direct.yaml Loading
# =============================================================================

class TestDirectYamlLoads:
    """Test that direct.yaml is loaded by PromptLoader."""

    def test_direct_yaml_file_exists(self):
        """direct.yaml should exist in agents/ directory."""
        yaml_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "direct.yaml"
        assert yaml_path.exists(), f"direct.yaml not found at {yaml_path}"

    def test_direct_yaml_has_required_fields(self):
        """direct.yaml should have agent, style, directives, knowledge_limits."""
        import yaml
        yaml_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "direct.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config.get("agent", {}).get("id") == "direct_agent"
        assert config.get("agent", {}).get("name") == "Wiii"
        assert "knowledge_limits" in config
        assert config["knowledge_limits"]["training_cutoff"] == "đầu năm 2024"

    def test_direct_agent_in_personas(self):
        """get_persona('direct_agent') should return config."""
        loader = PromptLoader()
        persona = loader.get_persona("direct_agent")
        assert isinstance(persona, dict)
        assert persona.get("agent", {}).get("id") == "direct_agent"

    def test_direct_agent_has_goal_with_da_linh_vuc(self):
        """Direct agent goal should contain 'đa lĩnh vực'."""
        loader = PromptLoader()
        persona = loader.get_persona("direct_agent")
        goal = persona.get("agent", {}).get("goal", "")
        assert "đa lĩnh vực" in goal

    def test_direct_agent_has_tools_list(self):
        """Direct agent should list tools in YAML."""
        loader = PromptLoader()
        persona = loader.get_persona("direct_agent")
        tools = persona.get("agent", {}).get("tools", [])
        assert "tool_current_datetime" in tools
        assert "tool_web_search" in tools

    def test_knowledge_limits_in_yaml(self):
        """YAML should have knowledge_limits section with requires_tool_for."""
        import yaml
        yaml_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "direct.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        kl = config["knowledge_limits"]
        assert kl["no_direct_internet"] is True
        assert isinstance(kl["requires_tool_for"], list)
        assert len(kl["requires_tool_for"]) >= 2


# =============================================================================
# Phase 2: build_system_prompt with tools_context
# =============================================================================

class TestToolsContextParam:
    """Test tools_context parameter in build_system_prompt."""

    def test_tools_context_override(self):
        """When tools_context is provided, it replaces auto-generated tools section."""
        loader = PromptLoader()
        custom_tools = "## MY CUSTOM TOOLS\n- tool_foo: does foo"
        prompt = loader.build_system_prompt(
            role="direct_agent",
            tools_context=custom_tools,
        )
        assert "MY CUSTOM TOOLS" in prompt
        assert "tool_foo" in prompt
        # Auto-generated tools section should NOT be present
        assert "SỬ DỤNG CÔNG CỤ (TOOLS)" not in prompt

    def test_tools_context_none_default(self):
        """When tools_context is None, auto-generated tools section is used."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="tutor_agent",  # Tutor doesn't use tools_context
            tools_context=None,
        )
        # Should have auto-generated tools section
        assert "SỬ DỤNG CÔNG CỤ (TOOLS)" in prompt
        assert "tool_knowledge_search" in prompt

    def test_tools_context_for_rag_agent_none(self):
        """RAG agent with tools_context=None uses auto-generated section."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="rag_agent")
        assert "SỬ DỤNG CÔNG CỤ (TOOLS)" in prompt

    def test_tools_context_not_in_default_signature(self):
        """tools_context defaults to None — existing callers unaffected."""
        loader = PromptLoader()
        # Calling without tools_context should work (backward compat)
        prompt = loader.build_system_prompt(role="student")
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# =============================================================================
# Phase 3: build_system_prompt for direct_agent
# =============================================================================

class TestBuildSystemPromptDirect:
    """Test build_system_prompt output for direct_agent role."""

    def test_prompt_contains_identity(self):
        """Prompt should have identity section from character card."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        # The identity section is now "CỐT LÕI NHÂN VẬT" or "WIII LIVING CORE CARD"
        assert "CỐT LÕI NHÂN VẬT" in prompt or "WIII LIVING CORE CARD" in prompt

    def test_prompt_contains_wiii_name(self):
        """Prompt should mention Wiii."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        assert "Wiii" in prompt

    def test_prompt_contains_da_linh_vuc(self):
        """Prompt should contain 'đa lĩnh vực' from goal."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        assert "đa lĩnh vực" in prompt

    def test_prompt_contains_emoji_usage(self):
        """Prompt should include identity traits from character card."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        # Emoji section was consolidated into character card traits (CỐT LÕI NHÂN VẬT)
        assert "CỐT LÕI NHÂN VẬT" in prompt or "WIII LIVING CORE CARD" in prompt

    def test_prompt_contains_avoid_rules(self):
        """Prompt should include avoid rules from identity."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        # "QUY TẮC PHONG CÁCH:" was replaced by "TRÁNH:" in the character card
        assert "TRÁNH:" in prompt or "QUY TẮC PHONG CÁCH:" in prompt

    def test_prompt_contains_personality_summary(self):
        """Prompt should include personality summary."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="direct_agent")
        # From wiii_identity.yaml personality.summary
        assert "Đáng yêu" in prompt or "đáng yêu" in prompt

    def test_prompt_with_tools_context_has_training_cutoff(self):
        """With tools_context containing '2024', prompt has training cutoff."""
        loader = PromptLoader()
        tools_ctx = (
            "## GIỚI HẠN KIẾN THỨC\n"
            "- Kiến thức CŨ — ngắt vào đầu năm 2024.\n"
            "- tool_web_search: tìm kiếm web\n"
            "- tool_current_datetime: ngày giờ"
        )
        prompt = loader.build_system_prompt(
            role="direct_agent",
            tools_context=tools_ctx,
        )
        assert "2024" in prompt
        assert "tool_web_search" in prompt
        assert "tool_current_datetime" in prompt

    def test_anti_greeting_on_follow_up(self):
        """Follow-up messages should have anti-greeting instruction."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="direct_agent",
            is_follow_up=True,
        )
        # Sprint 203/204: "FOLLOW-UP" label removed; anti-greeting is now expressed via
        # positive framing: "Đi thẳng vào nội dung" or "không qua lời chào lặp".
        # Legacy path uses "TUYỆT ĐỐI KHÔNG". Either is valid depending on config.
        assert (
            "Đi thẳng vào nội dung" in prompt
            or "lời chào lặp" in prompt
            or "TUYỆT ĐỐI KHÔNG" in prompt
            or "FOLLOW-UP" in prompt
        )

    def test_no_anti_greeting_on_first_message(self):
        """First messages should NOT have follow-up anti-greeting."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="direct_agent",
            is_follow_up=False,
        )
        # First message should have greeting tone anchor instead
        assert "ĐÂY LÀ TIN NHẮN FOLLOW-UP" not in prompt

    def test_identity_anchor_at_threshold_turns(self):
        """At N+ turns (Sprint 115: default=6), identity anchor should be injected."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="direct_agent",
            total_responses=8,
        )
        assert "PERSONA REMINDER" in prompt

    def test_maritime_tool_hint_in_tools_context(self):
        """Tools context should expose maritime search without injecting domain labels."""
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = True
        mock_settings.enable_code_execution = False

        tools_ctx = _build_direct_tools_context(mock_settings, "Hàng hải")
        assert "tool_search_maritime" in tools_ctx
        assert "Chuyên môn sâu" not in tools_ctx


# =============================================================================
# Phase 4: _build_direct_tools_context helper
# =============================================================================

class TestBuildDirectToolsContext:
    """Test _build_direct_tools_context helper function."""

    def test_basic_output_has_tool_hints(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "Hàng hải")
        assert "tool_current_datetime" in result
        assert "tool_web_search" in result
        assert ("GIỚI HẠN KIẾN THỨC" in result) or ("GIOI HAN KIEN THUC" in result)
        assert "2024" in result

    def test_character_tools_hint_when_enabled(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = True
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "")
        assert "tool_character_note" in result

    def test_no_character_tools_hint_when_disabled(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "")
        assert "tool_character_note" not in result

    def test_code_execution_hint_when_enabled(self):
        # tool_execute_python moved from direct node to code_studio_agent (WAVE-001).
        # Verify it appears in the code studio tools context with admin role.
        from app.engine.multi_agent.graph import _build_code_studio_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_code_execution = True
        mock_settings.enable_browser_agent = False
        mock_settings.enable_privileged_sandbox = False

        result = _build_code_studio_tools_context(mock_settings, user_role="admin")
        assert "tool_execute_python" in result

    def test_no_code_execution_hint_when_disabled(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "")
        assert "tool_execute_python" not in result

    def test_domain_name_not_injected(self):
        """Sprint 121: Domain name removed from tools context to prevent topic redirection."""
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "Luật Giao thông")
        # Sprint 121: Domain name no longer injected — it caused LLM
        # to redirect off-topic queries back to domain topics
        assert "Chuyên môn sâu" not in result

    def test_empty_domain_name_no_crash(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "")
        assert ("GIỚI HẠN KIẾN THỨC" in result) or ("GIOI HAN KIEN THUC" in result)
        # No domain specialization line
        assert "Chuyên môn sâu:" not in result

    def test_tool_rules_present(self):
        from app.engine.multi_agent.graph import _build_direct_tools_context
        mock_settings = MagicMock()
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False

        result = _build_direct_tools_context(mock_settings, "Hàng hải")
        assert ("QUY TẮC BẮT BUỘC VỀ TOOL" in result) or ("QUY TAC BAT BUOC VE TOOL" in result)
        assert ("GỌI TOOL TRƯỚC" in result) or ("GOI TOOL TRUOC" in result)
        assert ("KHÔNG BAO GIỜ tự bịa" in result) or ("KHONG BAO GIO tu bia" in result)


# =============================================================================
# Phase 5: direct_response_node integration
# =============================================================================

class TestDirectNodeUsesPromptLoader:
    """Test that direct_response_node calls build_system_prompt."""

    @pytest.mark.asyncio
    async def test_direct_node_calls_build_system_prompt(self):
        """direct_response_node should call loader.build_system_prompt with direct_agent."""
        from app.engine.multi_agent.graph import direct_response_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "test response"
        mock_response.tool_calls = []
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = {
            "query": "hôm nay thời tiết đẹp",
            "domain_id": "maritime",
            "domain_config": {"name_vi": "Hàng hải"},
            "context": {"is_follow_up": False, "user_name": "Minh"},
            "routing_metadata": {"intent": "general"},
        }

        mock_loader = MagicMock()
        mock_loader.build_system_prompt.return_value = "Bạn là Wiii, trợ lý đa lĩnh vực."

        async def fake_execute_direct_tool_rounds(*args, **kwargs):
            messages = args[2]
            return mock_response, messages, []

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                    return_value=mock_llm), \
             patch("app.prompts.prompt_loader.get_prompt_loader",
                    return_value=mock_loader), \
             patch("app.engine.multi_agent.graph._execute_direct_tool_rounds",
                    side_effect=fake_execute_direct_tool_rounds), \
             patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("test response", None)):
            await direct_response_node(state)

        # Verify build_system_prompt was called with correct role
        mock_loader.build_system_prompt.assert_called_once()
        call_kwargs = mock_loader.build_system_prompt.call_args
        assert call_kwargs.kwargs.get("role") == "direct_agent"
        assert call_kwargs.kwargs.get("user_name") == "Minh"
        assert call_kwargs.kwargs.get("is_follow_up") is False
        assert "tools_context" in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_direct_node_real_prompt_has_key_strings(self):
        """Using real PromptLoader, system prompt has backward-compat key strings."""
        from app.engine.multi_agent.graph import direct_response_node

        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return MagicMock(content="Response here", tool_calls=[])

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = capture_ainvoke

        async def fake_execute_direct_tool_rounds(*args, **kwargs):
            messages = args[2]
            captured_messages.extend(messages)
            return MagicMock(content="Response here", tool_calls=[]), messages, []

        state = {
            "query": "xin chào bạn",
            "domain_id": "maritime",
            "domain_config": {"name_vi": "Hàng hải"},
            "context": {"is_follow_up": False},
            "routing_metadata": {},
        }

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                    return_value=mock_llm), \
             patch("app.engine.multi_agent.graph._execute_direct_tool_rounds",
                    side_effect=fake_execute_direct_tool_rounds), \
             patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Response here", None)):
            await direct_response_node(state)

        # Find the SystemMessage
        system_content = captured_messages[0].content
        assert "đa lĩnh vực" in system_content
        assert "Wiii" in system_content
        assert "2024" in system_content
        # Sprint 203/204: "GIỚI HẠN KIẾN THỨC" renamed in natural mode;
        # now appears as "VỀ KIẾN THỨC CỦA WIII" (positive framing) or legacy variants.
        assert (
            "VỀ KIẾN THỨC CỦA WIII" in system_content
            or "Ranh giới" in system_content
            or "GIỚI HẠN KIẾN THỨC" in system_content
            or "kiến thức" in system_content.lower()
        )
        assert "tool_web_search" in system_content
        assert "tool_current_datetime" in system_content
        # Must NOT have old "trả lời MỌI câu hỏi" contradiction
        assert "trả lời MỌI câu hỏi" not in system_content

    @pytest.mark.asyncio
    async def test_direct_node_core_memory_appended(self):
        """Core memory should enter through PromptLoader's memory contract."""
        from app.engine.multi_agent.graph import direct_response_node

        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return MagicMock(content="Response", tool_calls=[])

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = capture_ainvoke

        async def fake_execute_direct_tool_rounds(*args, **kwargs):
            messages = args[2]
            captured_messages.extend(messages)
            return MagicMock(content="Response", tool_calls=[]), messages, []

        state = {
            "query": "tell me about cooking techniques",
            "domain_id": "maritime",
            "domain_config": {"name_vi": "Hàng hải"},
            "context": {
                "is_follow_up": False,
                "core_memory_block": "User prefers visual learning.",
            },
            "routing_metadata": {},
        }

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                    return_value=mock_llm), \
             patch("app.engine.multi_agent.graph._execute_direct_tool_rounds",
                    side_effect=fake_execute_direct_tool_rounds), \
             patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Response", None)):
            await direct_response_node(state)

        system_content = captured_messages[0].content
        # The direct node must not append memory by hand; PromptLoader owns the
        # single authoritative memory injection path.
        assert "WIII MEMORY CONTRACT" in system_content
        assert "CORE MEMORY BLOCK" in system_content
        assert "User prefers visual learning." in system_content


# =============================================================================
# Phase 6: Backward Compatibility with Existing Agents
# =============================================================================

class TestBackwardCompatibility:
    """Ensure existing agent roles still work after adding tools_context."""

    def test_tutor_agent_unchanged(self):
        """Tutor agent prompt should be unchanged (no tools_context)."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="tutor_agent")
        assert "SỬ DỤNG CÔNG CỤ (TOOLS)" in prompt
        assert "tool_knowledge_search" in prompt

    def test_student_role_unchanged(self):
        """Legacy 'student' role should still work."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_rag_agent_unchanged(self):
        """RAG agent should still have auto-generated tools."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="rag_agent")
        assert "tool_knowledge_search" in prompt

    def test_memory_agent_unchanged(self):
        """Memory agent should still work."""
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="memory_agent")
        assert isinstance(prompt, str)
        assert "Wiii" in prompt

    def test_all_agents_have_identity_section(self):
        """All agent roles should have an identity section from the character card."""
        loader = PromptLoader()
        for role in ["student", "tutor_agent", "rag_agent", "memory_agent", "direct_agent"]:
            prompt = loader.build_system_prompt(role=role)
            # "TÍNH CÁCH WIII" was replaced by "CỐT LÕI NHÂN VẬT" / "WIII LIVING CORE CARD"
            assert (
                "CỐT LÕI NHÂN VẬT" in prompt
                or "WIII LIVING CORE CARD" in prompt
                or "TÍNH CÁCH WIII" in prompt
            ), f"Missing identity for role={role}"
