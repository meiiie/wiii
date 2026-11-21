from unittest.mock import patch

from tests.unit.tutor_agent_node_helpers import (
    _make_tutor,
    mock_llm as mock_llm,
)


class TestTutorPostToolContextDistillation:
    def test_distill_post_tool_context_keeps_signals_and_drops_answer_shell(self):
        from app.engine.multi_agent.agents.tutor_node import distill_post_tool_context

        raw_tool_result = (
            "<answer>Chao ban, de minh giai thich cho ban nhe! "
            "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va. "
            "Tau nao thay tau kia o man phai thi phai nhuong duong. "
            "Tau nhuong duong can tranh cat ngang phia truoc mui tau kia. "
            "Neu can minh co the so sanh them voi Rule 17 cho ban.</answer>"
        )

        distilled = distill_post_tool_context(raw_tool_result)

        assert "Tin hieu vua lo ra:" in distilled
        assert "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va." in distilled
        assert "Tau nao thay tau kia o man phai thi phai nhuong duong." in distilled
        assert "Tau nhuong duong can tranh cat ngang phia truoc mui tau kia." in distilled
        assert "Chao ban" not in distilled
        assert "de minh giai thich" not in distilled.lower()
        assert "Neu can minh co the so sanh them" not in distilled

    def test_distill_post_tool_context_drops_social_and_followup_bait(self):
        from app.engine.multi_agent.agents.tutor_node import distill_post_tool_context

        raw_tool_result = (
            "Dung chuan luon ne! Wiii rat an tuong voi cach ban tom tat Quy tac 15 day. "
            "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va. "
            "Tau nao thay tau kia o man phai thi phai nhuong duong. "
            "Tau nhuong duong can tranh cat ngang phia truoc mui tau kia. "
            "Hay la chung ta di sau hon sang Quy tac 17 nhe? Wiii da san sang!"
        )

        distilled = distill_post_tool_context(raw_tool_result)

        assert "Wiii rat an tuong" not in distilled
        assert "Hay la chung ta" not in distilled
        assert "Wiii da san sang" not in distilled
        assert "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va." in distilled
        assert "Tau nao thay tau kia o man phai thi phai nhuong duong." in distilled


class TestExtractContent:
    def test_extract_content_with_thinking_returns_tuple(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Answer", "Thinking process"),
        ):
            text, thinking = node._extract_content_with_thinking("raw content")

        assert text == "Answer"
        assert thinking == "Thinking process"

    def test_extract_content_with_thinking_shapes_learning_answer_thesis_first(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        raw_answer = (
            "Chào Nam, mình hiểu là bạn muốn phân biệt rõ hai quy tắc này. "
            "Để Wiii tóm tắt lại cốt lõi cho bạn nhé:\n\n"
            "1. Rule 13 (Overtaking - Vượt): Tàu vượt từ phía sau phải nhường đường."
        )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=(raw_answer, "Thinking process"),
        ):
            text, thinking = node._extract_content_with_thinking(
                "raw content",
                query="Giải thích Rule 15 khác gì Rule 13",
            )

        assert thinking == "Thinking process"
        assert not text.startswith("Chào bạn")
        assert "Để Wiii" not in text
        assert text.startswith("Khác biệt cốt lõi")
        assert "Rule 13" in text

    def test_extract_content_with_thinking_strips_name_callout_retrieval_opener(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        raw_answer = (
            "Nam ơi, mình vừa tra cứu lại kỹ để chắc thông tin cho bạn đây!\n\n"
            "Để phân biệt Rule 13 và Rule 15 cho gọn, bạn hãy nhớ Rule 13 là tình huống vượt từ phía sau."
        )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=(raw_answer, None),
        ):
            text, thinking = node._extract_content_with_thinking(
                "raw content",
                query="Giải thích Rule 15 khác gì Rule 13",
            )

        assert thinking is None
        assert not text.startswith("Nam ơi")
        assert "mình vừa tra cứu lại kỹ" not in text
        assert text.startswith("Để phân biệt Rule 13")
