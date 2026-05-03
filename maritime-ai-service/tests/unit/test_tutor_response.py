import pytest
from unittest.mock import AsyncMock, MagicMock

from app.engine.messages import Message

from app.engine.multi_agent.agents.tutor_response import (
    collect_tutor_model_message,
    looks_like_tutor_placeholder_answer,
    normalize_tutor_answer_shape,
    recover_tutor_answer_from_messages,
)


def test_normalize_tutor_answer_shape_strips_repeat_question_opener():
    raw = (
        "(\u2299_\u2299)? H\u00ecnh nh\u01b0 b\u1ea1n v\u1eeba h\u1ecfi l\u1ea1i c\u00e2u n\u00e0y \u0111\u00fang kh\u00f4ng n\u00e8? "
        "Kh\u00f4ng sao c\u1ea3, ki\u1ebfn th\u1ee9c quan tr\u1ecdng th\u00ec nh\u1eafc l\u1ea1i c\u00e0ng nh\u1edb l\u00e2u th\u00f4i~\n\n"
        "\u0110\u1ec3 m\u00ecnh ch\u1ed1t l\u1ea1i l\u1ea7n n\u1eefa cho th\u1eadt th\u1ea5m nh\u00e9: "
        "**Rule 13 (V\u01b0\u1ee3t)** lu\u00f4n \u0111\u01b0\u1ee3c \u01b0u ti\u00ean h\u01a1n **Rule 15 (C\u1eaft h\u01b0\u1edbng)**."
    )

    normalized = normalize_tutor_answer_shape(
        raw,
        query="Gi\u1ea3i th\u00edch Rule 15 kh\u00e1c g\u00ec Rule 13",
    )

    assert not normalized.startswith("(\u2299_\u2299)?")
    assert "H\u00ecnh nh\u01b0 b\u1ea1n v\u1eeba h\u1ecfi l\u1ea1i" not in normalized
    assert "Kh\u00f4ng sao c\u1ea3" not in normalized
    assert "\u0110\u1ec3 m\u00ecnh ch\u1ed1t l\u1ea1i" not in normalized
    assert normalized.startswith("Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i")


def test_normalize_tutor_answer_shape_keeps_warmth_but_removes_greeting_lead():
    raw = (
        "Ch\u00e0o b\u1ea1n! R\u1ea5t vui \u0111\u01b0\u1ee3c g\u1eb7p l\u1ea1i b\u1ea1n.\n\n"
        "M\u00ecnh c\u00f9ng nh\u00ecn nh\u1eadn s\u1ef1 kh\u00e1c bi\u1ec7t n\u00e0y nh\u00e9:\n\n"
        "**Rule 13 (Overtaking - V\u01b0\u1ee3t):** T\u00e0u v\u01b0\u1ee3t t\u1eeb ph\u00eda sau ph\u1ea3i nh\u01b0\u1eddng \u0111\u01b0\u1eddng."
    )

    normalized = normalize_tutor_answer_shape(
        raw,
        query="Gi\u1ea3i th\u00edch Rule 15 kh\u00e1c g\u00ec Rule 13",
    )

    assert "Ch\u00e0o b\u1ea1n" not in normalized
    assert "M\u00ecnh c\u00f9ng nh\u00ecn nh\u1eadn" not in normalized
    assert normalized.startswith("Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i")


def test_recover_tutor_answer_from_messages_uses_last_substantive_tool_result():
    messages = [
        Message(role="tool", content="Error: timed out", tool_call_id="call_0"),
        Message(role="tool", content=(
                "**Rule 13 (V\u01b0\u1ee3t)** \u00e1p d\u1ee5ng khi m\u1ed9t t\u00e0u ti\u1ebfn \u0111\u1ebfn t\u1eeb ph\u00eda sau v\u01b0\u1ee3t qu\u00e1 22.5 \u0111\u1ed9 sau ngang m\u1ea1n.\n\n"
                "**Rule 15 (C\u1eaft h\u01b0\u1edbng)** \u00e1p d\u1ee5ng khi hai t\u00e0u m\u00e1y c\u1eaft nhau v\u00e0 m\u1ed9t t\u00e0u th\u1ea5y t\u00e0u kia \u1edf m\u1ea1n ph\u1ea3i.\n\n"
                "<!-- CONFIDENCE: 0.95 | IS_COMPLETE: True -->"
            ),
            tool_call_id="call_1",
        ),
    ]

    recovered = recover_tutor_answer_from_messages(
        messages,
        query="Gi\u1ea3i th\u00edch Rule 15 kh\u00e1c g\u00ec Rule 13",
    )

    assert recovered.startswith("Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i")
    assert "CONFIDENCE" not in recovered


def test_normalize_tutor_answer_shape_strips_inline_decorative_kaomoji():
    raw = (
        "Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i n\u1eb1m \u1edf ti\u00eau ch\u00ed nh\u1eadn di\u1ec7n v\u00e0 \u0111i\u1ec1u ki\u1ec7n \u00e1p d\u1ee5ng c\u1ee7a t\u1eebng v\u1ebf. "
        "(\u02f6\u02c3 \u1d55 \u02c2\u02f6) **Rule 13 (V\u01b0\u1ee3t)** \u00e1p d\u1ee5ng khi t\u00e0u v\u01b0\u1ee3t t\u1eeb ph\u00eda sau; "
        "**Rule 15 (C\u1eaft h\u01b0\u1edbng)** \u00e1p d\u1ee5ng khi hai t\u00e0u c\u1eaft nhau."
    )

    normalized = normalize_tutor_answer_shape(
        raw,
        query="Gi\u1ea3i th\u00edch Rule 15 kh\u00e1c g\u00ec Rule 13",
    )

    assert "(\u02f6\u02c3 \u1d55 \u02c2\u02f6)" not in normalized
    assert normalized.startswith("Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i")


def test_placeholder_answer_flags_tool_markup_payload():
    raw = (
        'tool_generate_visual <arg_key>figure_group_id</arg_key> '
        '<arg_value>colregs_rule15_visual</arg_value> <svg viewBox="0 0 800 500">'
    )

    assert looks_like_tutor_placeholder_answer(raw) is True


def test_recover_tutor_answer_skips_visual_payload_json():
    messages = [
        Message(role="tool", content='{"id":"visual-1","type":"chart","renderer_kind":"inline_html","visual_session_id":"vs-1"}',
            tool_call_id="call_visual",
        ),
        Message(role="tool", content=(
                "**Rule 15** ap dung khi hai tau cat ngang va tau thay doi phuong o man phai "
                "phai nhuong duong."
            ),
            tool_call_id="call_search",
        ),
    ]

    recovered = recover_tutor_answer_from_messages(
        messages,
        query="Giai thich Quy tac 15 COLREGs",
    )

    assert "visual_session_id" not in recovered
    assert "Rule 15" in recovered


@pytest.mark.asyncio
async def test_collect_tutor_model_message_copies_runtime_metadata_from_llm():
    llm = MagicMock()
    llm._wiii_provider_name = "zhipu"
    llm._wiii_model_name = "glm-5"
    response = MagicMock()
    response.content = "Answer"
    llm.ainvoke = AsyncMock(return_value=response)

    final_msg, streamed_text, used_streaming = await collect_tutor_model_message(
        llm,
        [],
        logger=MagicMock(),
    )

    assert streamed_text == ""
    assert used_streaming is False
    assert getattr(final_msg, "_wiii_provider_name", None) == "zhipu"
    assert getattr(final_msg, "_wiii_model_name", None) == "glm-5"
