"""
Maritime Domain Plugin - First domain for Wiii.

Sprint 26: Refactored to extend YamlDomainPlugin base class.
Only overrides domain-specific content methods.

Packages all maritime-specific content:
- Domain config (loaded from domain.yaml via base class)
- Prompt templates (persona YAML files)
- Skills (SKILL.md format for COLREGs, SOLAS, MARPOL)
- HyDE templates
- Routing config
"""

from pathlib import Path
from typing import Any, Dict

from app.domains.base import YamlDomainPlugin

_DOMAIN_DIR = Path(__file__).parent


class MaritimeDomain(YamlDomainPlugin):
    """Maritime Education domain plugin."""

    def __init__(self):
        super().__init__(domain_dir=_DOMAIN_DIR)

    def get_tool_instruction(self) -> str:
        return """
## QUY TẮC TOOL (CRITICAL - RAG-First Pattern):

1. **LUÔN LUÔN** sử dụng tool `tool_knowledge_search` để tìm kiếm kiến thức **TRƯỚC KHI** trả lời bất kỳ câu hỏi nào về:
   - Quy tắc hàng hải (COLREGs, SOLAS, MARPOL, ISM Code)
   - Thuật ngữ chuyên môn hàng hải
   - Quy trình, thủ tục an toàn
   - Bất kỳ kiến thức maritime nào

2. **KHÔNG BAO GIỜ** trả lời từ kiến thức riêng mà không tìm kiếm trước

3. Sau khi tìm kiếm, giảng dạy **DỰA TRÊN** kết quả tìm được

4. **TRÍCH DẪN nguồn** trong câu trả lời (ví dụ: "Theo Rule 15 COLREGs...")
"""

    def get_hyde_templates(self) -> Dict[str, str]:
        return {
            "vi": """Bạn là chuyên gia về luật hàng hải Việt Nam.

Hãy viết một đoạn văn ngắn (100-200 từ) trả lời câu hỏi sau.
Viết như thể đây là trích đoạn từ văn bản pháp luật hoặc tài liệu hàng hải chính thức.
Sử dụng thuật ngữ chuyên ngành và ngôn ngữ trang trọng.

Câu hỏi: {question}

Yêu cầu:
- Trả lời trực tiếp, không mở đầu bằng "Theo..."
- Sử dụng thuật ngữ chính xác (ví dụ: chủ tàu, thuyền viên, tàu biển)
- Nếu liên quan đến COLREG/SOLAS, đề cập các quy tắc cụ thể
- CHỈ trả về nội dung, không có giải thích thêm

Đoạn văn:""",
            "en": """You are an expert in maritime law and COLREG regulations.

Write a short paragraph (100-200 words) answering the following question.
Write as if this is an excerpt from official maritime documentation or COLREG rules.
Use precise technical terminology.

Question: {question}

Requirements:
- Answer directly, formal language
- Use exact terms (vessel, give-way, stand-on, crossing situation)
- Reference specific Rule numbers if applicable
- ONLY return the content, no explanations

Paragraph:""",
        }

    def get_routing_config(self) -> Dict[str, Any]:
        config = self.get_config()
        return {
            "routing_keywords": config.routing_keywords,
            "rag_description": config.rag_agent_description or "Tra cứu quy định hàng hải (COLREGs, SOLAS, MARPOL), luật, thủ tục",
            "tutor_description": config.tutor_agent_description or "Giải thích, dạy học, quiz về kiến thức hàng hải",
            "mandatory_search_triggers": config.mandatory_search_triggers,
        }

    def get_greetings(self) -> Dict[str, str]:
        return {
            "xin chào": "Xin chào! Tôi là Wiii. Tôi có thể giúp gì cho bạn?",
            "hello": "Hello! I'm Wiii. How can I help you?",
            "hi": "Chào bạn! Bạn muốn hỏi về vấn đề hàng hải nào?",
            "cảm ơn": "Không có gì! Nếu có thắc mắc gì khác, cứ hỏi nhé!",
            "thanks": "You're welcome! Let me know if you have more questions.",
        }
