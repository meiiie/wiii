"""Tests for agent handoff tools (Phase 3)."""

import pytest

from app.engine.multi_agent.handoff_tools import (
    _VALID_HANDOFF_TARGETS,
    extract_handoff_target,
    handoff_to_agent,
    is_handoff_tool_call,
)


class TestHandoffTool:
    @pytest.mark.asyncio
    async def test_valid_handoff_rag(self):
        result = await handoff_to_agent.ainvoke({"target_agent": "rag_agent", "reason": "Need knowledge"})
        assert "rag_agent" in result
        assert "acknowledged" in result.lower()

    @pytest.mark.asyncio
    async def test_valid_handoff_tutor(self):
        result = await handoff_to_agent.ainvoke({"target_agent": "tutor_agent"})
        assert "tutor_agent" in result

    @pytest.mark.asyncio
    async def test_valid_handoff_direct(self):
        result = await handoff_to_agent.ainvoke({"target_agent": "direct"})
        assert "direct" in result

    @pytest.mark.asyncio
    async def test_invalid_handoff(self):
        result = await handoff_to_agent.ainvoke({"target_agent": "nonexistent_agent"})
        assert "Invalid" in result
        assert "nonexistent_agent" in result

    @pytest.mark.asyncio
    async def test_empty_target(self):
        result = await handoff_to_agent.ainvoke({"target_agent": ""})
        assert "Invalid" in result


class TestHandoffHelpers:
    def test_is_handoff_tool_call_true(self):
        assert is_handoff_tool_call("handoff_to_agent") is True

    def test_is_handoff_tool_call_false(self):
        assert is_handoff_tool_call("tool_web_search") is False
        assert is_handoff_tool_call("") is False

    def test_extract_handoff_target_valid(self):
        assert extract_handoff_target({"target_agent": "rag_agent"}) == "rag_agent"
        assert extract_handoff_target({"target_agent": "tutor_agent"}) == "tutor_agent"
        assert extract_handoff_target({"target_agent": "direct"}) == "direct"

    def test_extract_handoff_target_invalid(self):
        assert extract_handoff_target({"target_agent": "bad_agent"}) is None
        assert extract_handoff_target({"target_agent": ""}) is None

    def test_extract_handoff_target_missing(self):
        assert extract_handoff_target({}) is None

    def test_valid_targets_set(self):
        assert "rag_agent" in _VALID_HANDOFF_TARGETS
        assert "tutor_agent" in _VALID_HANDOFF_TARGETS
        assert "direct" in _VALID_HANDOFF_TARGETS
        assert "code_studio_agent" in _VALID_HANDOFF_TARGETS
        assert "product_search_agent" in _VALID_HANDOFF_TARGETS
        assert "memory_agent" in _VALID_HANDOFF_TARGETS
        assert len(_VALID_HANDOFF_TARGETS) == 6
