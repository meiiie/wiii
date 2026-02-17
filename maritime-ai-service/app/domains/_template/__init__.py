"""
Template Domain Plugin - Copy and customize for your domain.

Sprint 26: Updated to extend YamlDomainPlugin for zero-boilerplate setup.

Instructions:
1. Copy this entire _template folder to app/domains/your_domain/
2. Rename this class to YourDomainName
3. Edit domain.yaml with your domain config
4. Write prompts in prompts/agents/*.yaml
5. Add SKILL.md files in skills/ (optional)
6. Override get_tool_instruction(), get_hyde_templates(), get_greetings() etc.
"""

from pathlib import Path
from typing import Dict

from app.domains.base import YamlDomainPlugin

_DOMAIN_DIR = Path(__file__).parent


class TemplateDomain(YamlDomainPlugin):
    """Template domain - DO NOT register this directly. Copy and customize."""

    def __init__(self):
        super().__init__(domain_dir=_DOMAIN_DIR)

    def get_hyde_templates(self) -> Dict[str, str]:
        # Override with domain-specific HyDE templates
        return {
            "vi": "Bạn là chuyên gia. Trả lời câu hỏi: {question}",
            "en": "You are an expert. Answer: {question}",
        }
