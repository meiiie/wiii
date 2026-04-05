import asyncio
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.test_tutor_agent_node import _make_tutor


@pytest.mark.asyncio
async def test_post_tool_continuation_prompt_includes_living_stream_cues(mock_llm):
    response_with_tool = MagicMock()
    response_with_tool.tool_calls = [
        {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
    ]
    response_with_tool.content = (
        "<thinking>Minh can chot dieu kien kich hoat cua Rule 15 truoc khi di vao cach nhuong duong.</thinking>"
    )

    continuation_response = MagicMock()
    continuation_response.tool_calls = []
    continuation_response.content = (
        "<thinking>Ket qua vua lo ra moc can neo that ro: tau thay doi phuong o man phai moi la tau phai nhuong.</thinking>"
    )

    response_final = MagicMock()
    response_final.tool_calls = []
    response_final.content = "Rule 15 answer"

    node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
    queue = asyncio.Queue()
    captured_system_prompts = []

    async def _dispatch_side_effect(**kwargs):
        await kwargs["push"](
            {
                "type": "tool_result",
                "content": {
                    "name": "tool_knowledge_search",
                    "result": "Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
                    "id": "call_1",
                },
                "node": "tutor_agent",
            }
        )
        return types.SimpleNamespace(
            phase_transition_count=0,
            last_tool_was_progress=False,
            should_break_loop=False,
            tool_result_text="Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
        )

    async def _collect_side_effect(*args, **kwargs):
        messages = []
        if len(args) >= 2:
            messages = args[1] or []
        elif "messages" in kwargs:
            messages = kwargs["messages"] or []
        if messages:
            first_content = getattr(messages[0], "content", "")
            if isinstance(first_content, str):
                captured_system_prompts.append(first_content)
        call_index = len(captured_system_prompts)
        if call_index == 1:
            return (response_with_tool, "", False)
        if call_index == 2:
            return (continuation_response, "", False)
        return (response_final, "", False)

    with patch(
        "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
        AsyncMock(side_effect=_collect_side_effect),
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
        return_value=[],
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
        return_value=None,
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
        return_value=(0.85, True),
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
        AsyncMock(side_effect=_dispatch_side_effect),
    ):
        await node._react_loop(
            "Giải thích Rule 15",
            {
                "user_id": "user-123",
                "mood_hint": "Nguoi dung dang hoc tiep sau mot luot hoi dap dai",
                "response_language": "vi",
                "living_context_block": {
                    "current_state": [
                        "Trang thai song: Wiii dang giu nhip on dinh va tap trung de go roi.",
                    ],
                    "relationship_memory": [
                        "User hien tai: Nam",
                        "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
                    ],
                    "narrative_state": [
                        "Nen noi tam hien tai: kha on, giu nhip vua phai.",
                    ],
                },
            },
            event_queue=queue,
        )

    assert len(captured_system_prompts) >= 2
    assert "## LIVING CONTINUITY CUES" in captured_system_prompts[1]
    assert "one_self: Day van la Wiii." in captured_system_prompts[1]
    assert "relationship: User hien tai: Nam" in captured_system_prompts[1]
    assert "narrative: Nen noi tam hien tai: kha on, giu nhip vua phai." in captured_system_prompts[1]
    assert (
        "current_state: Trang thai song: Wiii dang giu nhip on dinh va tap trung de go roi."
        in captured_system_prompts[1]
    )
