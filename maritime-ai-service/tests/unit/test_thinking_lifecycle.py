"""
Sprint 64: Thinking Lifecycle Events — Backend Tests

Tests:
1. create_thinking_start_event produces correct type/content/node
2. create_thinking_end_event includes duration_ms in details
3. create_thinking_end_event with block_id
4. StreamEventType has THINKING_START and THINKING_END
5. graph_streaming emits thinking_start before thinking content
6. graph_streaming emits thinking_end after node processing
7. RAG partial answer emitted between rag_agent and synthesizer
8. Synthesizer skips re-emission when output matches RAG
9. Guardian emits only start/end (no thinking content)
10. _NODE_LABELS mapping exists and has expected keys

NOTE: graph_streaming has a deep circular import chain via multi_agent.graph -> agents ->
services -> chat_service -> multi_agent.graph. We break it by pre-mocking app.services
in sys.modules before importing.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Break circular import chain before importing graph_streaming
# ============================================================================

_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_graph_key = "app.engine.multi_agent.graph"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_had_graph = _graph_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
_orig_graph = sys.modules.get(_graph_key)

if not _had_cs:
    _mock_chat_svc = types.ModuleType(_cs_key)
    _mock_chat_svc.ChatService = type("ChatService", (), {})
    _mock_chat_svc.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_chat_svc

# Break graph_streaming ↔ graph mutual import
# Note: get_multi_agent_graph_async is async, so use AsyncMock
from unittest.mock import AsyncMock as _AsyncMock
if not _had_graph:
    _mock_graph = types.ModuleType(_graph_key)
    _mock_graph.get_multi_agent_graph_async = _AsyncMock()
    _mock_graph._build_domain_config = MagicMock(return_value={})
    _mock_graph._build_turn_local_state_defaults = MagicMock(return_value={})
    _mock_graph.open_multi_agent_graph = _AsyncMock()
    _mock_graph._inject_host_context = MagicMock(return_value=None)
    _mock_graph._TRACERS = {}
    _mock_graph._cleanup_tracer = MagicMock()
    sys.modules[_graph_key] = _mock_graph

from app.engine.multi_agent.stream_utils import (
    StreamEventType,
    create_thinking_start_event,
    create_thinking_end_event,
)
from app.engine.multi_agent.graph_streaming import (
    _NODE_LABELS,
    process_with_multi_agent_streaming,
)

# Restore sys.modules
if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs

# Restore graph module to avoid polluting later test files
if not _had_graph:
    sys.modules.pop(_graph_key, None)
elif _orig_graph is not None:
    sys.modules[_graph_key] = _orig_graph


# =============================================================================
# Tests: StreamEventType — new types
# =============================================================================

class TestThinkingLifecycleEventTypes:
    def test_thinking_start_type(self):
        assert StreamEventType.THINKING_START == "thinking_start"

    def test_thinking_end_type(self):
        assert StreamEventType.THINKING_END == "thinking_end"


# =============================================================================
# Tests: create_thinking_start_event
# =============================================================================

class TestCreateThinkingStartEvent:
    @pytest.mark.asyncio
    async def test_basic(self):
        event = await create_thinking_start_event("Phan tich cau hoi", "supervisor")
        assert event.type == "thinking_start"
        assert event.content == "Phan tich cau hoi"
        assert event.node == "supervisor"
        assert event.details is None

    @pytest.mark.asyncio
    async def test_with_block_id(self):
        event = await create_thinking_start_event("Tra cuu", "rag_agent", block_id="block-1")
        assert event.type == "thinking_start"
        assert event.node == "rag_agent"
        assert event.details == {"block_id": "block-1"}

    @pytest.mark.asyncio
    async def test_to_dict(self):
        event = await create_thinking_start_event("Giang day", "tutor_agent")
        d = event.to_dict()
        assert d["type"] == "thinking_start"
        assert d["content"] == "Giang day"
        assert d["node"] == "tutor_agent"


# =============================================================================
# Tests: create_thinking_end_event
# =============================================================================

class TestCreateThinkingEndEvent:
    @pytest.mark.asyncio
    async def test_basic(self):
        event = await create_thinking_end_event("supervisor")
        assert event.type == "thinking_end"
        assert event.content == ""
        assert event.node == "supervisor"
        assert event.details is None

    @pytest.mark.asyncio
    async def test_with_duration(self):
        event = await create_thinking_end_event("rag_agent", duration_ms=5000)
        assert event.type == "thinking_end"
        assert event.node == "rag_agent"
        assert event.details["duration_ms"] == 5000

    @pytest.mark.asyncio
    async def test_with_block_id(self):
        event = await create_thinking_end_event("grader", block_id="block-2")
        assert event.details["block_id"] == "block-2"

    @pytest.mark.asyncio
    async def test_with_both(self):
        event = await create_thinking_end_event("rag_agent", duration_ms=8000, block_id="b1")
        assert event.details["duration_ms"] == 8000
        assert event.details["block_id"] == "b1"

    @pytest.mark.asyncio
    async def test_to_dict_with_duration(self):
        event = await create_thinking_end_event("grader", duration_ms=3000)
        d = event.to_dict()
        assert d["type"] == "thinking_end"
        assert d["node"] == "grader"
        assert d["details"]["duration_ms"] == 3000


# =============================================================================
# Tests: _NODE_LABELS mapping
# =============================================================================

class TestNodeLabels:
    def test_node_labels_exist(self):
        assert isinstance(_NODE_LABELS, dict)
        assert len(_NODE_LABELS) >= 8

    def test_expected_keys(self):
        expected = ["guardian", "supervisor", "rag_agent", "tutor_agent",
                    "synthesizer", "memory_agent", "direct"]
        for key in expected:
            assert key in _NODE_LABELS, f"Missing key: {key}"

    def test_values_are_strings(self):
        for key, val in _NODE_LABELS.items():
            assert isinstance(val, str), f"{key} has non-string value"


# =============================================================================
# Tests: graph_streaming emits lifecycle events
# =============================================================================

def _make_mock_graph(node_updates):
    """Create a mock graph that yields the given node state updates."""
    async def _astream(*args, **kwargs):
        for update in node_updates:
            yield update
    mock_graph = MagicMock()
    mock_graph.astream = _astream
    return mock_graph


class _MockGraphCM:
    """Async context manager that returns a mock graph."""
    def __init__(self, graph):
        self._graph = graph

    async def __aenter__(self):
        return self._graph

    async def __aexit__(self, *args):
        pass


def _make_narrator_result(node: str):
    """Create a mock ReasoningRenderResult with predictable labels per node."""
    labels = {
        "supervisor": "Phân tích câu hỏi",
        "rag_agent": "Tra cứu tri thức",
        "tutor_agent": "Soạn bài giảng",
        "memory_agent": "Truy xuất bộ nhớ",
        "direct": "Suy nghĩ câu trả lời",
        "synthesizer": "Tổng hợp câu trả lời",
        "product_search_agent": "Tìm kiếm sản phẩm",
        "code_studio_agent": "Code Studio",
    }
    result = MagicMock()
    result.label = labels.get(node, node)
    result.summary = f"Mock summary for {node}"
    result.action_text = ""
    result.delta_chunks = [f"Thinking about {node}..."]
    result.phase = "route"
    result.style_tags = []
    return result


async def _collect_events(node_updates):
    """Helper to collect all stream events from a graph run."""
    mock_graph = _make_mock_graph(node_updates)
    mock_registry = MagicMock()
    mock_registry.start_request_trace.return_value = "trace-1"
    mock_registry.end_request_trace.return_value = {"span_count": 0}

    # Mock reasoning narrator to return predictable labels
    mock_narrator = MagicMock()

    async def _mock_render(req):
        return _make_narrator_result(req.node)

    mock_narrator.render = _mock_render
    mock_narrator.render_fast = lambda req: _make_narrator_result(req.node)

    async def _mock_forward_graph_events(*, initial_state, merged_queue):
        for update in node_updates:
            await merged_queue.put(("graph", update))
        await merged_queue.put(("graph_done", None))

    with patch("app.engine.multi_agent.graph_streaming.forward_graph_events_impl",
               new=_mock_forward_graph_events), \
         patch("app.engine.multi_agent.graph_streaming.get_agent_registry",
               return_value=mock_registry), \
         patch("app.engine.multi_agent.graph_streaming._build_domain_config",
               return_value={}), \
         patch("app.engine.multi_agent.graph_streaming._build_turn_local_state_defaults",
               return_value={}), \
         patch("app.engine.multi_agent.graph._inject_host_context",
               return_value=None), \
         patch("app.engine.multi_agent.graph_streaming.get_reasoning_narrator",
               return_value=mock_narrator), \
         patch("app.engine.multi_agent.graph_streaming.settings"):

        events = []
        async for e in process_with_multi_agent_streaming("test", "user1"):
            events.append(e)
        return events


class TestGraphStreamingLifecycle:
    """Test that process_with_multi_agent_streaming emits lifecycle events."""

    @pytest.mark.asyncio
    async def test_supervisor_emits_status_only(self):
        """Supervisor no longer surfaces its own thinking lifecycle in the live stream."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent", "thinking": "Routing to RAG agent"}},
        ])

        event_types = [e.type for e in events]
        assert "status" in event_types
        assert "thinking_start" not in event_types
        assert "thinking_end" not in event_types

    @pytest.mark.asyncio
    async def test_rag_emits_partial_answer(self):
        """RAG agent should emit partial answer before synthesizer."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {
                "final_response": "This is the RAG answer text for the user.",
                "sources": [{"title": "src1"}],
                "thinking_content": "Analyzing the question and searching for relevant documents...",
            }},
            {"synthesizer": {
                "final_response": "This is the RAG answer text for the user.",
                "sources": [{"title": "src1"}],
            }},
        ])

        # Should have answer events after rag_agent thinking_end
        rag_end_idx = next(i for i, e in enumerate(events)
                           if e.type == "thinking_end" and e.node == "rag_agent")
        answer_indices = [i for i, e in enumerate(events) if e.type == "answer"]
        assert len(answer_indices) > 0, "Should have answer events"
        # At least one answer event should come after rag_agent thinking_end
        assert any(idx > rag_end_idx for idx in answer_indices)

    @pytest.mark.asyncio
    async def test_synthesizer_skips_duplicate_answer(self):
        """When synthesizer output matches RAG, no extra answer events."""
        # Use Vietnamese text to avoid _ensure_vietnamese translation
        rag_text = "Câu trả lời giống hệt nhau từ RAG và bộ tổng hợp"
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {"final_response": rag_text}},
            {"synthesizer": {"final_response": rag_text}},
        ])

        # Count answer chunks — they should come from RAG partial only
        answer_events = [e for e in events if e.type == "answer"]
        total_answer_text = "".join(e.content for e in answer_events)
        assert total_answer_text == rag_text

    @pytest.mark.asyncio
    async def test_guardian_emits_status_only(self):
        """Sprint 145: Guardian demoted to status-only (no thinking lifecycle)."""
        events = await _collect_events([
            {"guardian": {"guardian_passed": True}},
            {"supervisor": {"next_agent": "direct"}},
            {"direct": {"final_response": "Hello!"}},
        ])

        guardian_status = [e for e in events
                          if e.type == "status" and e.node == "guardian"]
        guardian_starts = [e for e in events
                           if e.type == "thinking_start" and e.node == "guardian"]
        guardian_ends = [e for e in events
                        if e.type == "thinking_end" and e.node == "guardian"]

        assert len(guardian_status) == 1
        # Sprint 145: Guardian no longer emits thinking lifecycle
        assert len(guardian_starts) == 0
        assert len(guardian_ends) == 0

    @pytest.mark.asyncio
    async def test_legacy_grader_updates_are_ignored(self):
        """Sprint 233: legacy grader updates are ignored by the live pipeline."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {"final_response": "answer"}},
            {"grader": {"grader_score": 8}},
            {"synthesizer": {"final_response": "answer"}},
        ])

        grader_events = [e for e in events if e.node == "grader"]
        assert grader_events == []

    @pytest.mark.asyncio
    async def test_rag_thinking_start_has_label(self):
        """RAG thinking_start content should be the Vietnamese node label with diacritics."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {
                "thinking_content": "Đang dò các nguồn liên quan...",
                "final_response": "Đây là câu trả lời từ RAG.",
            }},
        ])

        rag_start = next(e for e in events if e.type == "thinking_start" and e.node == "rag_agent")
        assert rag_start.content == "Tra cứu tri thức"

    @pytest.mark.asyncio
    async def test_thinking_end_has_duration_ms(self):
        """thinking_end should include duration_ms in details."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {
                "thinking_content": "Dang kiem tra nguon lien quan...",
                "final_response": "Answer",
            }},
        ])

        end_events = [e for e in events if e.type == "thinking_end"]
        assert len(end_events) >= 1
        for end_event in end_events:
            assert end_event.details is not None
            assert "duration_ms" in end_event.details
            assert isinstance(end_event.details["duration_ms"], int)
            assert end_event.details["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_rag_with_different_synthesizer_output(self):
        """When synthesizer has different output, it should be emitted."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {"final_response": "RAG partial"}},
            {"synthesizer": {"final_response": "Synthesized final answer"}},
        ])

        answer_events = [e for e in events if e.type == "answer"]
        total_text = "".join(e.content for e in answer_events)
        # Should contain both RAG partial and synthesizer output
        assert "RAG partial" in total_text
        assert "Synthesized final answer" in total_text

    @pytest.mark.asyncio
    async def test_tutor_agent_lifecycle(self):
        """Tutor agent should emit thinking_start + thinking_end when thinking content exists."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {"thinking_content": "Phân tích khái niệm từng bước..." * 3}},
            {"synthesizer": {"final_response": "Lesson content"}},
        ])

        tutor_starts = [e for e in events
                        if e.type == "thinking_start" and e.node == "tutor_agent"]
        tutor_ends = [e for e in events
                      if e.type == "thinking_end" and e.node == "tutor_agent"]
        assert len(tutor_starts) == 1
        assert len(tutor_ends) == 1
        # Sprint 141: _NODE_LABELS updated to "Soạn bài giảng"
        assert tutor_starts[0].content == "Soạn bài giảng"

    @pytest.mark.asyncio
    async def test_tutor_agent_no_thinking_still_emits_lifecycle(self):
        """Tutor agent emits thinking lifecycle even without thinking content (narrative layer)."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {}},
            {"synthesizer": {"final_response": "Lesson"}},
        ])

        tutor_starts = [e for e in events
                        if e.type == "thinking_start" and e.node == "tutor_agent"]
        tutor_ends = [e for e in events
                      if e.type == "thinking_end" and e.node == "tutor_agent"]
        # Post-narrative-reasoning: tutor always emits thinking lifecycle
        assert len(tutor_starts) == 1
        assert len(tutor_ends) == 1

    @pytest.mark.asyncio
    async def test_rag_tool_calls_outside_thinking_block(self):
        """Tool calls should be emitted BEFORE thinking block, not inside it."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {
                "thinking_content": "Đang phân tích kết quả tìm kiếm...",
                "tool_call_events": [
                    {"id": "tc1", "name": "search_kb", "args": {"query": "test"},
                     "result": "Found 3 docs"},
                ],
            }},
            {"synthesizer": {"final_response": "Answer"}},
        ])

        # Find indices
        tool_call_idx = next(i for i, e in enumerate(events) if e.type == "tool_call")
        rag_start_idx = next(i for i, e in enumerate(events)
                             if e.type == "thinking_start" and e.node == "rag_agent")
        # Tool call should come BEFORE thinking_start
        assert tool_call_idx < rag_start_idx, "Tool calls must be outside (before) thinking block"

    @pytest.mark.asyncio
    async def test_extract_thinking_prefers_native(self):
        """Sprint 140b: _extract_thinking_content prefers native thinking over thinking_content.

        Native thinking is genuine model reasoning (even if English);
        thinking_content may be a pipeline dump from ReasoningTracer.
        """
        events = await _collect_events([
            {"supervisor": {"next_agent": "rag_agent"}},
            {"rag_agent": {
                "thinking": "English native thinking from Gemini extended mode...",
                "thinking_content": "Phân tích câu hỏi và tìm kiếm tài liệu liên quan...",
                "final_response": "Answer text here.",
            }},
            {"synthesizer": {"final_response": "Answer text here."}},
        ])

        # Sprint 141b: Bulk thinking now emitted as thinking_delta (not thinking)
        # Sprint 144: Filter by rag_agent node (supervisor also emits thinking_delta now)
        rag_thinking = [e for e in events if e.type == "thinking_delta" and e.node == "rag_agent"]
        assert len(rag_thinking) >= 1
        # Native model reasoning preferred over thinking_content
        thinking_text = rag_thinking[0].content
        assert "English native thinking" in thinking_text

    @pytest.mark.asyncio
    async def test_memory_agent_lifecycle(self):
        """Memory agent should emit thinking_start + thinking_end."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "memory_agent"}},
            {"memory_agent": {}},
            {"synthesizer": {"final_response": "Memory result"}},
        ])

        mem_starts = [e for e in events
                      if e.type == "thinking_start" and e.node == "memory_agent"]
        mem_ends = [e for e in events
                    if e.type == "thinking_end" and e.node == "memory_agent"]
        assert len(mem_starts) == 1
        assert len(mem_ends) == 1

    @pytest.mark.asyncio
    async def test_tutor_recovered_answer_can_flow_through_safety_net(self):
        """When tutor recovers from thinking, synthesizer/safety-net should still be able to surface it."""
        # Vietnamese text to avoid translation, >50 chars to trigger recovery
        thinking_text = "Đây là giải thích chi tiết về Quy tắc 15 tình huống mạn vượt trong hàng hải quốc tế."
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {
                "tutor_output": "",  # Empty response (Gemini quirk)
                "agent_outputs": {"tutor": ""},  # Also empty
                "thinking": thinking_text,
            }},
            {"synthesizer": {"final_response": "", "agent_outputs": {"tutor": thinking_text}}},
        ])

        answer_events = [e for e in events if e.type == "answer"]
        assert len(answer_events) > 0, "Should recover answer through synthesizer/safety-net"
        total_text = "".join(e.content for e in answer_events)
        assert "Quy tắc 15" in total_text

    @pytest.mark.asyncio
    async def test_safety_net_fallback_when_no_answer_emitted(self):
        """If no node emits an answer, safety net should extract from final_state."""
        # Vietnamese text to avoid _ensure_vietnamese translation
        synth_text = "Phản hồi dự phòng của bộ tổng hợp được tạo từ ngữ cảnh."
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {
                "agent_outputs": {},
            }},
            {"synthesizer": {
                "final_response": synth_text,
            }},
        ])

        answer_events = [e for e in events if e.type == "answer"]
        total_text = "".join(e.content for e in answer_events)
        assert "Phản hồi dự phòng" in total_text

    @pytest.mark.asyncio
    async def test_safety_net_from_agent_outputs_when_all_empty(self):
        """Safety net should try agent_outputs when final_response is empty."""
        # Vietnamese text to avoid _ensure_vietnamese translation
        recovered_text = "Đã khôi phục câu trả lời từ từ điển đầu ra của agent thành công."
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {
                "tutor_output": "",
                "agent_outputs": {"tutor": ""},
                "thinking": "",
            }},
            {"synthesizer": {
                "final_response": "",
                "agent_outputs": {"tutor": recovered_text},
            }},
        ])

        answer_events = [e for e in events if e.type == "answer"]
        total_text = "".join(e.content for e in answer_events)
        assert "khôi phục câu trả lời" in total_text

    @pytest.mark.asyncio
    async def test_tutor_partial_answer_survives_legacy_grader_updates(self):
        """Tutor partial answer should still stream even if a stale grader update appears."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {
                "tutor_output": "Here is the tutor explanation.",
                "thinking_content": "Phân tích khái niệm này từng bước một...",
            }},
            {"grader": {"grader_score": 8}},
            {"synthesizer": {"final_response": "Here is the tutor explanation."}},
        ])

        answer_indices = [i for i, e in enumerate(events) if e.type == "answer"]
        assert len(answer_indices) > 0
        assert all(e.node != "grader" for e in events)

    @pytest.mark.asyncio
    async def test_tutor_stream_uses_synthesizer_authority_for_final_answer(self):
        """Tutor stream should hold raw tutor_output and surface the synthesizer final_response instead."""
        events = await _collect_events([
            {"supervisor": {"next_agent": "tutor_agent"}},
            {"tutor_agent": {
                "tutor_output": "Bản nháp thô từ tutor.",
                "thinking_content": "Mình đang đối chiếu Rule 15 với ngữ cảnh hiện tại...",
            }},
            {"synthesizer": {"final_response": "Bản chốt cuối giàu chất Wiii hơn từ synthesizer."}},
        ])

        answer_events = [e for e in events if e.type == "answer"]
        total_text = "".join(e.content for e in answer_events)

        assert "Bản chốt cuối giàu chất Wiii hơn từ synthesizer." in total_text
        assert "Bản nháp thô từ tutor." not in total_text
