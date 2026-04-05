"""Regression tests for public reasoning helpers that still matter."""

import unicodedata

from app.engine.reasoning import (
    ThinkingSoulIntensity,
    ThinkingToneMode,
    build_living_thinking_context,
    classify_memory_name_turn,
    looks_like_name_introduction,
    resolve_public_thinking_mode,
    sanitize_public_tutor_thinking,
)


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def test_resolve_public_thinking_mode_routes_memory_and_rag_lanes():
    assert resolve_public_thinking_mode(lane="memory") == ThinkingToneMode.RELATIONAL_COMPANION
    assert resolve_public_thinking_mode(lane="rag") == ThinkingToneMode.TECHNICAL_RESTRAINED


def test_looks_like_name_introduction_accepts_ascii_vietnamese_pattern():
    assert looks_like_name_introduction("minh ten Nam, nho giup minh nhe") is True


def test_classify_memory_name_turn_treats_recall_as_non_introduction():
    query = "Mình tên gì nhỉ?"

    assert classify_memory_name_turn(query) == "recall"
    assert looks_like_name_introduction(query) is False


def test_build_living_thinking_context_distills_wiii_card_for_memory_lane():
    context = build_living_thinking_context(
        user_id="user-123",
        lane="memory",
        intent="personal",
    )

    assert context.lane == "memory"
    assert context.soul_intensity == ThinkingSoulIntensity.LIVING
    assert context.identity_anchor
    assert context.relationship_style
    assert context.reasoning_style


def test_sanitize_public_tutor_thinking_keeps_reasoning_and_drops_answerish_text():
    reasoning = (
        "Voi Rule 15, cho de lech nhat la nham giua tinh huong cat mat va vuot. "
        "Minh can chot tung moc truoc khi giai thich."
    )
    answerish = "Rule 15 quy dinh ve tinh huong cat mat giua hai tau."

    assert sanitize_public_tutor_thinking(reasoning) == reasoning
    assert sanitize_public_tutor_thinking(answerish) is None


def test_sanitize_public_tutor_thinking_keeps_new_post_tool_reasoning_markers():
    reasoning = (
        "Nguon vua tra ve da neo kha ro Rule 13 va Rule 15. "
        "Minh nen bam vao vi tri tiep can va quy tac uu tien, khoan da roi moi mo rong."
    )

    assert sanitize_public_tutor_thinking(reasoning) == reasoning


def test_sanitize_public_tutor_thinking_keeps_model_owned_english_reasoning():
    reasoning = (
        "Okay, the user is asking about Rule 15. I need to anchor the trigger first, "
        "otherwise the explanation will drift into a dry recital of the rule text."
    )

    assert sanitize_public_tutor_thinking(reasoning) == reasoning


def test_sanitize_public_tutor_thinking_strips_raw_thinking_tags():
    reasoning = (
        "<thinking> Được rồi, mình cần chốt trước điều kiện áp dụng "
        "rồi mới kéo sang quyền ưu tiên. </thinking>"
    )

    assert sanitize_public_tutor_thinking(reasoning) == (
        "Được rồi, mình cần chốt trước điều kiện áp dụng rồi mới kéo sang quyền ưu tiên."
    )


def test_sanitize_public_tutor_thinking_drops_answer_planning_paragraphs():
    reasoning = (
        "Người dùng đang cần nắm được điểm neo của Quy tắc 15 trước khi nghe điều luật.\n\n"
        "Với tư cách là Wiii Tutor, tôi rất vui được giúp bạn củng cố kiến thức. "
        "Mục tiêu của tôi là trả lời tự nhiên và giờ thì đến phần câu trả lời!"
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized == "Người dùng đang cần nắm được điểm neo của Quy tắc 15 trước khi nghe điều luật."


def test_sanitize_public_tutor_thinking_promotes_user_need_paragraph_and_strips_decorative_aside():
    reasoning = (
        "Điểm mấu chốt ở đây là vị trí mạn phải. (˶˃ ᵕ ˂˶)\n\n"
        "Người dùng đang cần nắm bắt Quy tắc 15 theo cách dùng được ngoài thực tế, chứ không phải chỉ nghe đọc lại điều luật.\n\n"
        "Mình sẽ khóa trigger áp dụng trước rồi mới nói đến cách nhường đường."
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is not None
    paragraphs = [part for part in sanitized.split("\n\n") if part.strip()]
    assert paragraphs[0].startswith("Người dùng đang cần nắm bắt")
    assert "(˶˃ ᵕ ˂˶)" not in sanitized


def test_sanitize_public_tutor_thinking_dedupes_near_repeat_paragraphs():
    reasoning = (
        "Người dùng muốn hiểu Quy tắc 15 theo cách dùng được ngoài thực tế, không phải chỉ nghe đọc lại điều luật.\n\n"
        "Mình nên khóa trigger áp dụng trước rồi mới nói đến cách nhường đường.\n\n"
        "Người dùng đang hỏi về Quy tắc 15, nhưng nếu chỉ trích dẫn điều luật thì họ sẽ khó hình dung được tình huống cắt mặt ngoài thực tế."
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is not None
    paragraphs = [part for part in sanitized.split("\n\n") if part.strip()]
    assert len(paragraphs) == 2


def test_sanitize_public_tutor_thinking_keeps_single_user_opening_when_later_one_repeats():
    reasoning = (
        "Người dùng đang hỏi về Quy tắc 15, nên điểm quan trọng nhất là nhận ra lúc nào tàu thấy đối phương ở mạn phải.\n\n"
        "Mình nên dựng lại tình huống cắt hướng bằng một hình ảnh dễ hình dung trước khi đưa điều luật.\n\n"
        "Người dùng đang hỏi về Quy tắc 15, nhưng nếu chỉ đọc điều khoản thì vẫn khó thấy vì sao tàu kia lại phải nhường đường.\n\n"
        "Cuối cùng mình mới nhấn vào việc tránh cắt mũi để nối luật với trực giác an toàn."
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is not None
    paragraphs = [part for part in sanitized.split("\n\n") if part.strip()]
    assert len([part for part in paragraphs if _fold_text(part).startswith("nguoi dung")]) == 1


def test_sanitize_public_tutor_thinking_dedupes_same_prefix_strategy_paragraphs():
    reasoning = (
        "Người dùng đang hỏi về Quy tắc 15 nên cần một điểm bấu víu rõ trước.\n\n"
        "Thay vì liệt kê khô khan, mình sẽ dựng một tình huống cắt hướng để người học hình dung ngay.\n\n"
        "Cuối cùng mình mới nhắc đến việc tránh cắt mũi để nối luật với phản xạ an toàn.\n\n"
        "Thay vì liệt kê điều khoản, mình sẽ mô phỏng một tình huống giao thông tương tự để người học thấy vì sao tàu kia phải nhường."
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is not None
    paragraphs = [part for part in sanitized.split("\n\n") if part.strip()]
    assert len([part for part in paragraphs if _fold_text(part).startswith("thay vi")]) == 1
