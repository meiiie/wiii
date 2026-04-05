from app.engine.reasoning import sanitize_public_tutor_thinking


def test_sanitize_public_tutor_thinking_drops_tutor_self_pep_talk_and_answer_planning():
    reasoning = (
        "**Wiii Tutor - Ôn tập Quy tắc 15 COLREGs**\n\n"
        "Được rồi, người dùng lại quay lại với Quy tắc 15 rồi! Không vấn đề gì, mình đã sẵn sàng! "
        "Cơ sở dữ liệu của mình đã được nạp đầy đủ, và mình cần đảm bảo sẽ đưa ra một phản hồi thật tuyệt vời. "
        "Mục tiêu là phải hữu ích và nhất quán với hình tượng Wiii Tutor của mình.\n\n"
        "Mình cần nhanh chóng xác nhận lại là mình nhớ quy tắc này, rồi đưa ra một bản tóm tắt rõ ràng, súc tích.\n\n"
        "Được rồi, đến lúc tạo ra câu trả lời hoàn hảo thôi! Tất nhiên là phải thật thân thiện rồi!"
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is None or "câu trả lời hoàn hảo" not in sanitized.lower()
    assert sanitized is None or "hình tượng wiii tutor" not in sanitized.lower()
