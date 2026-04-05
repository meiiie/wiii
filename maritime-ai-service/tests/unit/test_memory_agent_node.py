"""
Tests for MemoryAgentNode — Sprint 72: Retrieve-Extract-Respond.

Tests memory retrieval, fact extraction, response generation,
template fallbacks, and state management.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_semantic_memory():
    mem = MagicMock()
    mem.get_user_facts = AsyncMock(return_value={
        "name": "Minh",
        "role": "student",
        "preferences": ["visual learning"],
        "interests": ["COLREGs", "SOLAS"],
    })
    mem._fact_extractor = MagicMock()
    mem._fact_extractor.extract_and_store_facts = AsyncMock(return_value=[])
    return mem


@pytest.fixture
def base_state():
    return {
        "user_id": "user-123",
        "query": "test query",
        "agent_outputs": {},
    }


def _make_node(semantic_memory=None):
    """Create MemoryAgentNode with mocked dependencies (avoids singleton)."""
    from app.engine.multi_agent.agents.memory_agent import MemoryAgentNode
    return MemoryAgentNode(semantic_memory=semantic_memory)


# ---------------------------------------------------------------------------
# process() tests
# ---------------------------------------------------------------------------

class TestMemoryAgentProcess:
    @pytest.mark.asyncio
    async def test_process_happy_path(self, mock_semantic_memory, base_state):
        node = _make_node(mock_semantic_memory)
        result = await node.process(base_state)

        assert result["current_agent"] == "memory_agent"
        assert result["memory_output"]  # non-empty string
        assert result["agent_outputs"]["memory"] == result["memory_output"]

    @pytest.mark.asyncio
    async def test_process_semantic_memory_only(self, mock_semantic_memory, base_state):
        node = _make_node(semantic_memory=mock_semantic_memory)
        result = await node.process(base_state)

        assert result["current_agent"] == "memory_agent"
        assert result["memory_output"]

    @pytest.mark.asyncio
    async def test_process_no_services(self, base_state):
        """Without semantic memory, returns friendly fallback."""
        node = _make_node()
        result = await node.process(base_state)

        assert result["current_agent"] == "memory_agent"
        assert result["memory_output"]
        # Should NOT contain old hardcoded error
        assert "Không có thông tin về user" not in result["memory_output"]

    @pytest.mark.asyncio
    async def test_process_semantic_memory_exception(self, base_state):
        bad_mem = MagicMock()
        bad_mem.get_user_facts = AsyncMock(side_effect=Exception("DB down"))
        bad_mem._fact_extractor = MagicMock()
        bad_mem._fact_extractor.extract_and_store_facts = AsyncMock(
            side_effect=Exception("LLM down"),
        )
        node = _make_node(semantic_memory=bad_mem)
        result = await node.process(base_state)

        # Should still have a response (graceful fallback)
        assert result["current_agent"] == "memory_agent"
        assert result["memory_output"]

    @pytest.mark.asyncio
    async def test_process_with_llm(self, mock_semantic_memory, base_state):
        """process() accepts and uses llm parameter."""
        node = _make_node(mock_semantic_memory)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
            content="Chào Minh!"
        ))

        from unittest.mock import patch
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Chào Minh!", "")):
            result = await node.process(base_state, llm=mock_llm)

        assert result["memory_output"] == "Chào Minh!"


# ---------------------------------------------------------------------------
# _retrieve_facts() tests
# ---------------------------------------------------------------------------

class TestRetrieveFacts:
    @pytest.mark.asyncio
    async def test_returns_facts_list(self, mock_semantic_memory):
        node = _make_node(mock_semantic_memory)
        facts = await node._retrieve_facts("user-123")
        # Should contain name and role at minimum
        types_found = {f["type"] for f in facts}
        assert "name" in types_found
        assert "role" in types_found

    @pytest.mark.asyncio
    async def test_no_service_returns_empty(self):
        node = _make_node()
        facts = await node._retrieve_facts("user-1")
        assert facts == []


# ---------------------------------------------------------------------------
# _template_response() tests
# ---------------------------------------------------------------------------

class TestTemplateResponse:
    def test_with_new_facts(self):
        node = _make_node()
        text = node._template_response("test", [], ["Tên: Minh"], "")
        assert "ghi nhớ" in text
        assert "Minh" in text

    def test_with_existing_facts(self):
        node = _make_node()
        text = node._template_response(
            "bạn nhớ gì?",
            [{"type": "name", "content": "Minh"}],
            [],
            "",
        )
        assert "Minh" in text

    def test_empty_returns_friendly(self):
        node = _make_node()
        text = node._template_response("test", [], [], "")
        assert "chưa có thông tin" in text.lower() or "chia sẻ" in text.lower()
        # Never returns old hardcoded error
        assert text != "Không có thông tin về user"


# ---------------------------------------------------------------------------
# is_available() tests
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_available_with_semantic_memory(self, mock_semantic_memory):
        node = _make_node(semantic_memory=mock_semantic_memory)
        assert node.is_available() is True

    def test_not_available_without_services(self):
        node = _make_node()
        assert node.is_available() is False


# ---------------------------------------------------------------------------
# Singleton test
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_memory_agent_node_returns_instance(self):
        import app.engine.multi_agent.agents.memory_agent as mod
        mod._memory_node = None  # reset singleton
        try:
            node = mod.get_memory_agent_node()
            assert isinstance(node, mod.MemoryAgentNode)
            # Second call returns same instance
            node2 = mod.get_memory_agent_node()
            assert node is node2
        finally:
            mod._memory_node = None


class TestMemoryPublicThinking:
    @pytest.mark.asyncio
    async def test_process_with_llm_does_not_propagate_private_thinking(self, mock_semantic_memory, base_state):
        node = _make_node(mock_semantic_memory)
        base_state["query"] = "Minh ten Nam, nho giup minh nhe"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Chao Nam!"))
        mock_semantic_memory._fact_extractor.extract_and_store_facts = AsyncMock(
            return_value=[MagicMock(to_content=MagicMock(return_value="name: Nam"))]
        )

        narrator_results = [
            MagicMock(label="Ra lai", summary="Minh nhin lai mach cu de xem diem nao con dinh voi luot nay.", phase="retrieve"),
            MagicMock(label="Neo lai", summary="Minh da co vai moc cu, nhung ten rieng moi nay van la diem noi bat nhat.", phase="verify"),
            MagicMock(label="Tach y", summary="Minh dang tach phan dang nho lau khoi phan chi thuoc ve khoanh khac nay.", phase="verify"),
            MagicMock(label="Giu lai", summary="Ten Nam du ro de giu lai nhu mot diem neo xung ho.", phase="verify"),
            MagicMock(label="Dap lai", summary="Minh se dap gon de Nam thay minh nho ma khong bien cau tra loi thanh log he thong.", phase="synthesize"),
        ]

        with patch(
            "app.engine.multi_agent.agents.memory_agent.get_reasoning_narrator",
        ) as mock_narrator_fn, patch(
            "app.services.output_processor.extract_thinking_from_response",
            return_value=(
                "Chao Nam!",
                "Nam's Name: Confirmed! No \"Chao\", no thinking process, just pure cuteness.",
            ),
        ):
            mock_narrator = MagicMock()
            mock_narrator.render = AsyncMock(side_effect=narrator_results)
            mock_narrator_fn.return_value = mock_narrator
            result = await node.process(base_state, llm=mock_llm)

        assert result["memory_output"] == "Chao Nam!"
        assert "thinking" not in result
        assert "thinking_content" in result
        assert "Nam vua" not in result["thinking_content"]
        assert "Chao Nam" not in result["thinking_content"]
        assert "pure cuteness" not in result["thinking_content"]
        assert "Khoan" not in result["thinking_content"]
        assert "truong du lieu" not in result["thinking_content"].lower()
        assert "Ten Nam du ro de giu lai nhu mot diem neo xung ho." in result["thinking_content"]
        assert "Minh se dap gon de Nam thay minh nho ma khong bien cau tra loi thanh log he thong." in result["thinking_content"]

    @pytest.mark.asyncio
    async def test_process_builds_public_thinking_content_from_narrator_fragments(self, mock_semantic_memory, base_state):
        node = _make_node(mock_semantic_memory)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Minh nho roi nhe!"))

        narrator_results = [
            MagicMock(label="Luc lai", summary="Minh luc lai chut ngu canh rieng dang dinh voi dieu ban vua noi.", phase="retrieve"),
            MagicMock(label="Xem lai", summary="Minh nhin lai vai manh ky uc cu de xem cai nao dang lien quan den nhip nay.", phase="verify"),
            MagicMock(label="Doi chieu", summary="Minh soi xem trong nhip nay co chi tiet nao can giu lai that khong.", phase="verify"),
            MagicMock(label="Khoa lai", summary="Minh khoa lai manh thong tin vua lo ra de luc dap khong bi lenh.", phase="verify"),
            MagicMock(label="Khau lai", summary="Minh khau lai dieu cu va dieu moi cho that gon.", phase="synthesize"),
        ]

        mock_semantic_memory._fact_extractor.extract_and_store_facts = AsyncMock(
            return_value=[MagicMock(to_content=MagicMock(return_value="name: Nam"))]
        )

        with patch(
            "app.engine.multi_agent.agents.memory_agent.get_reasoning_narrator",
        ) as mock_narrator_fn, patch(
            "app.services.output_processor.extract_thinking_from_response",
            return_value=("Minh nho roi nhe!", "private hidden thought"),
        ):
            mock_narrator = MagicMock()
            mock_narrator.render = AsyncMock(side_effect=narrator_results)
            mock_narrator_fn.return_value = mock_narrator

            result = await node.process(base_state, llm=mock_llm)

        assert "thinking" not in result
        assert "thinking_content" in result
        assert "private hidden thought" not in result["thinking_content"]
        assert "Minh luc lai chut ngu canh rieng dang dinh voi dieu ban vua noi." in result["thinking_content"]
        assert "Minh khoa lai manh thong tin vua lo ra de luc dap khong bi lenh." in result["thinking_content"]
        assert "tach bach giua chi tiet du ben de luu lau" not in result["thinking_content"].lower()
        assert "doc to toan bo viec vua luu lai" not in result["thinking_content"].lower()
