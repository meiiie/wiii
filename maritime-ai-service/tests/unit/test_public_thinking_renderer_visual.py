from app.engine.reasoning import sanitize_public_tutor_thinking


def test_sanitize_public_tutor_thinking_keeps_visual_planning_body_under_headings():
    reasoning = (
        "**Hình ảnh hóa Quy tắc 15**\n\n"
        "Hiện tại mình đang tập trung tạo ra một hình ảnh trực quan rõ ràng cho Quy tắc 15 của COLREGs, "
        "tình huống cắt hướng. Mục tiêu là làm rõ trách nhiệm của tàu phải nhường đường.\n\n"
        "**Xây dựng các yếu tố hình ảnh**\n\n"
        "Bây giờ mình đang thiết kế khung chứa cho sơ đồ, gồm hình dáng tàu, nhãn vai trò và chỉ báo mạn phải rõ ràng."
    )

    sanitized = sanitize_public_tutor_thinking(reasoning)

    assert sanitized is not None
    assert "Hiện tại mình đang tập trung tạo ra một hình ảnh trực quan rõ ràng" in sanitized
    assert "Bây giờ mình đang thiết kế khung chứa cho sơ đồ" in sanitized
