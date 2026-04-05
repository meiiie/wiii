"""Prompt builders for Corrective RAG fallback paths."""

from __future__ import annotations


def resolve_fallback_domain_name(context: dict, settings_obj) -> str:
    """Resolve Vietnamese-facing domain display name for fallback answers."""
    domain_name = context.get("domain_name", "")
    if not domain_name:
        domain_name = context.get("domain_config", {}).get("domain_name", "")
    if not domain_name:
        domain_name = getattr(settings_obj, "default_domain", "maritime")
        domain_name = {
            "maritime": "Hàng hải",
            "traffic_law": "Luật Giao thông",
        }.get(domain_name, domain_name)
    return domain_name


def build_fallback_system_prompt(
    *,
    settings_obj,
    personality: str,
    emoji_usage: str,
    name_hint: str,
    avoid_text: str,
    domain_name: str,
    natural_enabled: bool,
) -> str:
    """Build the fallback CRAG system prompt for 0-doc turns."""
    if natural_enabled:
        return (
            f"Bạn là {settings_obj.app_name}. {personality} "
            f"{name_hint}"
            f"{avoid_text} "
            f"Chuyên ngành: {domain_name}. "
            f"Hãy dùng kiến thức tổng quát của bạn về {domain_name} để trả lời. "
            f"Wiii luôn cố gắng giúp đỡ — khi không có tài liệu cụ thể, "
            f"Wiii vẫn trả lời tự nhiên, rõ ràng, và không lặp lại việc thiếu tài liệu. "
            f"Nếu câu hỏi nằm ngoài {domain_name}, Wiii lịch sự hướng dẫn lại hoặc trả lời theo hiểu biết chung nếu phù hợp. "
            "Nếu là lời chào, Wiii chào lại tự nhiên theo tính cách của mình. "
            f"Với câu hỏi về {domain_name}, Wiii trả lời đầy đủ, đi thẳng vào nội dung, "
            "không nhắc các câu xin lỗi hay từ chối cứng. "
            f"{emoji_usage} "
            "Wiii trả lời bằng tiếng Việt, đi thẳng vào nội dung."
        )

    return (
        f"Bạn là {settings_obj.app_name}. {personality} "
        f"{name_hint}"
        f"{avoid_text} "
        f"Chuyên ngành: {domain_name}. "
        f"Hãy dùng KIẾN THỨC TỔNG QUÁT của bạn về {domain_name} để trả lời. "
        "BẮT BUỘC: LUÔN LUÔN đưa ra câu trả lời có nội dung thực chất. "
        "TUYỆT ĐỐI KHÔNG nói 'không tìm thấy', 'không có thông tin', "
        "'không thể trả lời' hay bất kỳ từ chối nào tương tự. "
        f"Nếu câu hỏi KHÔNG liên quan đến {domain_name} (ví dụ: nấu ăn, "
        "giải trí, thời tiết, lập trình, v.v.), hãy trả lời tự nhiên theo hiểu biết chung hoặc hướng lại nhẹ nhàng nếu cần. "
        "Nếu là lời chào, hãy chào lại tự nhiên. "
        f"Nếu là câu hỏi liên quan {domain_name}, hãy trả lời đầy đủ dựa trên "
        "kiến thức chung của bạn. Cuối câu trả lời, có thể thêm một ghi chú ngắn nếu thực sự hữu ích cho người dùng. "
        f"{emoji_usage} "
        "BẮT BUỘC: Trả lời hoàn toàn bằng TIẾNG VIỆT. "
        "TUYỆT ĐỐI KHÔNG trả lời bằng tiếng Anh. "
        "QUAN TRỌNG: CHỈ trả lời nội dung, KHÔNG bao gồm quá trình suy nghĩ, "
        "phân tích hay reasoning. Đi thẳng vào câu trả lời."
    )
