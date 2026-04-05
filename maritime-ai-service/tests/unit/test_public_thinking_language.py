from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch

import pytest

from app.engine.reasoning import (
    align_visible_thinking_language,
    should_align_visible_thinking_language,
)


def test_should_align_visible_thinking_language_detects_english_vendor_thought_for_vietnamese_turn():
    text = (
        "Okay, the user is asking about Rule 15. "
        "I need to anchor the trigger first before the explanation drifts."
    )

    assert should_align_visible_thinking_language(text, target_language="vi") is True


def test_should_align_visible_thinking_language_detects_mixed_english_answer_planning_for_vietnamese_turn():
    text = (
        "**My Approach to Explaining Rule 15 Again**\n\n"
        "Okay, the user's back asking about Rule 15. "
        "Let's see the plan: First, a friendly greeting. "
        "Drafting content: Greeting: Chao ban!"
    )

    assert should_align_visible_thinking_language(text, target_language="vi") is True


def test_should_align_visible_thinking_language_detects_selfhood_recollection_phrase_for_vietnamese_turn():
    text = (
        "**Recalling Personal History**\n\n"
        "I'm considering how to frame this user's question. "
        "I'll share a memory with a natural, warm tone. "
        "It's a casual recollection."
    )

    assert should_align_visible_thinking_language(text, target_language="vi") is True


@pytest.mark.asyncio
async def test_align_visible_thinking_language_keeps_text_when_language_already_matches():
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    text = "Nguoi dung dang hoi ve Rule 15. Minh can chot trigger truoc khi giai thich."

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            text,
            target_language="vi",
            llm=llm,
        )

    assert result == text
    llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_align_visible_thinking_language_translates_english_visible_thought():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content=(
                "Nguoi dung dang hoi ve Rule 15. "
                "Minh can khoa trigger truoc khi giai thich de khong troi sang mot doan doc lai dieu luat."
            )
        )
    )

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            (
                "Okay, the user is asking about Rule 15. "
                "I need to lock the trigger first so the explanation does not drift into a recital."
            ),
            target_language="vi",
            llm=llm,
        )

    assert result is not None
    assert "Nguoi dung dang hoi ve Rule 15" in result
    llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_align_visible_thinking_language_extracts_text_from_native_response_blocks():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content=[
                {
                    "type": "thinking",
                    "thinking": "Need to preserve the structure.",
                },
                {
                    "type": "text",
                    "text": (
                        "Nguoi dung dang hoi ve Rule 15. "
                        "Minh can chot trigger truoc khi giai thich."
                    ),
                },
            ]
        )
    )

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            "Okay, the user is asking about Rule 15. I need to anchor the trigger first.",
            target_language="vi",
            llm=llm,
        )

    assert result == (
        "Nguoi dung dang hoi ve Rule 15. Minh can chot trigger truoc khi giai thich."
    )
    llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_align_visible_thinking_language_strips_translator_native_thinking_tags():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content=(
                "<thinking>Okay, translate carefully.</thinking>\n\n"
                "Mình đang dựng hình minh họa cho Rule 15 để người học nhìn ra ngay tàu nào phải nhường đường."
            )
        )
    )

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            "Okay, the user is asking about Rule 15. I need to make the visual clearer.",
            target_language="vi",
            llm=llm,
        )

    assert result == (
        "Mình đang dựng hình minh họa cho Rule 15 để người học nhìn ra ngay tàu nào phải nhường đường."
    )
    llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_align_visible_thinking_language_retries_when_first_pass_stays_english():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[
            SimpleNamespace(
                content="Okay, the user is asking about Rule 15. I need to anchor the trigger first."
            ),
            SimpleNamespace(
                content="Nguoi dung dang hoi ve Rule 15. Minh can chot trigger truoc khi giai thich."
            ),
        ]
    )

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            "Okay, the user is asking about Rule 15. I need to anchor the trigger first.",
            target_language="vi",
            llm=llm,
        )

    assert result == (
        "Nguoi dung dang hoi ve Rule 15. Minh can chot trigger truoc khi giai thich."
    )
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_align_visible_thinking_language_selfhood_mode_uses_lighter_vietnamese_prompt():
    captured_messages = []

    async def _fake_invoke(messages):
        captured_messages.append(messages)
        return SimpleNamespace(
            content="Mình đang chạm vào câu hỏi về chính mình, nên muốn kể lại cho thật gần."
        )

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=_fake_invoke)

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            "**Exploring Origins** I'm delving into the heart of this question.",
            target_language="vi",
            alignment_mode="direct_selfhood",
            llm=llm,
        )

    assert result == "Mình đang chạm vào câu hỏi về chính mình, nên muốn kể lại cho thật gần."
    system_prompt = captured_messages[0][0].content
    assert 'Uu tien ngoi "minh"' in system_prompt
    assert "toi dang dao sau" in system_prompt


@pytest.mark.asyncio
async def test_align_visible_thinking_language_ignores_meta_failure_reply_and_falls_back_to_clean_source():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[
            SimpleNamespace(
                content=(
                    "Rất xin lỗi, hiện tại tôi chưa thấy khối nội dung visible thinking mà bạn muốn chuyển ngữ. "
                    "Bạn vui lòng cung cấp đoạn văn bản đó."
                )
            ),
            SimpleNamespace(
                content=(
                    "Rất xin lỗi, hiện tại tôi chưa thấy khối nội dung visible thinking mà bạn muốn chuyển ngữ. "
                    "Bạn vui lòng cung cấp đoạn văn bản đó."
                )
            ),
        ]
    )
    source = "Okay, the user is asking about Rule 15. I need to anchor the trigger first."

    with patch(
        "app.engine.llm_pool.get_llm_light",
        return_value=None,
    ):
        result = await align_visible_thinking_language(
            source,
            target_language="vi",
            llm=llm,
        )

    assert result == source
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_align_visible_thinking_language_falls_back_to_light_llm_when_primary_stays_english():
    source = (
        "**Visualizing Rule 15**\n\n"
        "I'm working on a visual representation of COLREGs Rule 15 (Crossing Situation), as requested. "
        "I'm focusing on creating an HTML-based illustration to clearly depict the \"Give-way\" and "
        "\"Stand-on\" vessel roles within the crossing scenario. The `tool_generate_visual` tool and "
        "`code_html` are being utilized to make a clear comparison.\n\n"
        "**Refining the Visual**\n\n"
        "I'm now refining the visual, focusing on a clear side-by-side comparison for Rule 15. "
        "I've added Vietnamese titles and descriptions, with `Give-way` on the left and `Stand-on` "
        "on the right."
    )
    assert should_align_visible_thinking_language(source, target_language="vi") is True
    primary_llm = MagicMock()
    primary_llm.ainvoke = AsyncMock(
        side_effect=[
            SimpleNamespace(
                content=source
            ),
            SimpleNamespace(
                content=source
            ),
        ]
    )
    fallback_llm = MagicMock()
    fallback_llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content=(
                "Mình đang tinh chỉnh hình minh họa, tập trung vào cách đặt hai bên đối chiếu thật rõ cho Rule 15. "
                "Mình đã thêm tiêu đề và mô tả tiếng Việt, với `Give-way` ở bên trái và `Stand-on` ở bên phải."
            )
        )
    )

    with patch(
        "app.engine.llm_pool.get_llm_light",
        return_value=fallback_llm,
        ):
            result = await align_visible_thinking_language(
            source,
            target_language="vi",
            llm=primary_llm,
        )

    assert result == (
        "Mình đang tinh chỉnh hình minh họa, tập trung vào cách đặt hai bên đối chiếu thật rõ cho Rule 15. "
        "Mình đã thêm tiêu đề và mô tả tiếng Việt, với `Give-way` ở bên trái và `Stand-on` ở bên phải."
    )
    assert primary_llm.ainvoke.await_count == 2
    fallback_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_align_visible_thinking_language_realigns_remaining_english_paragraphs_after_full_translation():
    source = (
        "Đây là đoạn mở đầu bằng tiếng Việt.\n\n"
        "Okay, first I need to consider the evolution equation and use Stone's theorem.\n\n"
        "Cuối cùng là đoạn kết cũng bằng tiếng Việt."
    )
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[
            SimpleNamespace(content=source),
            SimpleNamespace(content=source),
            SimpleNamespace(content="Bây giờ, xét phương trình tiến hóa và dùng định lý Stone."),
        ]
    )

    with patch("app.engine.llm_pool.get_llm_light", return_value=None):
        result = await align_visible_thinking_language(
            source,
            target_language="vi",
            llm=llm,
        )

    assert result == (
        "Đây là đoạn mở đầu bằng tiếng Việt.\n\n"
        "Bây giờ, xét phương trình tiến hóa và dùng định lý Stone.\n\n"
        "Cuối cùng là đoạn kết cũng bằng tiếng Việt."
    )
    assert llm.ainvoke.await_count == 3
