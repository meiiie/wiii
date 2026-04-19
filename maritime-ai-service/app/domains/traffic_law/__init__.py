"""
Traffic Law Domain Plugin - Second domain for multi-domain PoC.

Sprint 26: Refactored to extend YamlDomainPlugin base class.
Only overrides domain-specific content methods.

Vietnamese traffic law education: road signs, driving regulations,
penalties, license exam preparation.
"""

from pathlib import Path
from typing import Any, Dict

from app.domains.base import YamlDomainPlugin

_DOMAIN_DIR = Path(__file__).parent


class TrafficLawDomain(YamlDomainPlugin):
    """Vietnamese Traffic Law education domain plugin."""

    def __init__(self):
        super().__init__(domain_dir=_DOMAIN_DIR)

    def get_tool_instruction(self) -> str:
        return """
## QUY TẮC TOOL (CRITICAL - RAG-First Pattern):

1. **LUÔN LUÔN** sử dụng tool `tool_knowledge_search` để tìm kiếm kiến thức **TRƯỚC KHI** trả lời câu hỏi về:
   - Luật giao thông đường bộ Việt Nam
   - Mức phạt vi phạm (Nghị định 168, 100)
   - Biển báo giao thông
   - Quy định về bằng lái xe

2. **KHÔNG BAO GIỜ** trả lời từ kiến thức riêng mà không tìm kiếm trước

3. Sau khi tìm kiếm, giảng dạy **DỰA TRÊN** kết quả tìm được

4. **TRÍCH DẪN nguồn** trong câu trả lời (ví dụ: "Theo Điều 5 Luật GTĐB 2008...")
"""

    def get_hyde_templates(self) -> Dict[str, str]:
        return {
            "vi": """Bạn là chuyên gia về luật giao thông đường bộ Việt Nam.

Hãy viết một đoạn văn ngắn (100-200 từ) trả lời câu hỏi sau.
Viết như thể đây là trích đoạn từ văn bản pháp luật giao thông chính thức.

Câu hỏi: {question}

Đoạn văn:""",
            "en": """You are an expert in Vietnamese traffic law and road regulations.

Write a short paragraph (100-200 words) answering the following question.

Question: {question}

Paragraph:""",
        }

    def get_routing_config(self) -> Dict[str, Any]:
        config = self.get_config()
        return {
            "routing_keywords": config.routing_keywords,
            "rag_description": config.rag_agent_description,
            "tutor_description": config.tutor_agent_description,
            "mandatory_search_triggers": config.mandatory_search_triggers,
            "scope_description": config.scope_description or "",
        }

    def get_greetings(self) -> Dict[str, str]:
        return {
            "xin chào": "Xin chào! Tôi là Wiii Traffic Law Tutor. Bạn muốn hỏi về luật giao thông gì?",
            "hello": "Hello! I'm Wiii Traffic Law Tutor. How can I help you with traffic regulations?",
            "hi": "Chào bạn! Bạn cần tìm hiểu về luật giao thông nào?",
        }
