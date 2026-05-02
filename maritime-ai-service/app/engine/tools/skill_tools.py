"""
Skill Management Tools — AI agent can create and manage skills.

Enables the self-extending agent pattern: the agent can create new
skills at runtime, expanding its own capabilities.

Sprint 13: Extended Tools & Self-Extending Skills.
"""

import logging
from typing import Optional

from app.engine.tools.native_tool import tool

logger = logging.getLogger(__name__)


@tool
def tool_create_skill(
    name: str,
    description: str,
    triggers: str,
    content: str,
    domain_id: str = "maritime",
) -> str:
    """
    Tạo skill mới cho hệ thống AI.

    Skill sẽ được lưu dưới dạng SKILL.md và có thể sử dụng ngay.

    Args:
        name: Tên skill (ví dụ: "colregs-rule-15")
        description: Mô tả ngắn gọn
        triggers: Các từ khóa trigger, cách nhau bằng dấu phẩy
        content: Nội dung skill (Markdown)
        domain_id: Domain ID (mặc định: maritime)

    Returns:
        Thông báo thành công hoặc lỗi
    """
    try:
        from app.domains.skill_manager import get_skill_manager

        manager = get_skill_manager()
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]

        result = manager.create_skill(
            domain_id=domain_id,
            name=name,
            description=description,
            triggers=trigger_list,
            content=content,
        )

        if result.success:
            return f"✅ {result.message} (path: {result.path})"
        else:
            return f"❌ {result.message}"

    except Exception as e:
        logger.error("[SKILL_TOOLS] create_skill error: %s", e)
        return f"❌ Lỗi tạo skill: {e}"


@tool
def tool_list_skills(domain_id: Optional[str] = None) -> str:
    """
    Liệt kê tất cả skills đã tạo.

    Args:
        domain_id: Lọc theo domain (None = tất cả)

    Returns:
        Danh sách skills
    """
    try:
        from app.domains.skill_manager import get_skill_manager

        manager = get_skill_manager()
        skills = manager.list_runtime_skills(domain_id)

        if not skills:
            return "📭 Chưa có runtime skill nào."

        lines = [f"📚 {len(skills)} runtime skills:"]
        for s in skills:
            lines.append(
                f"  • {s.get('name', 'N/A')} ({s.get('domain_id', '?')}) "
                f"— {s.get('description', 'No description')}"
            )
        return "\n".join(lines)

    except Exception as e:
        logger.error("[SKILL_TOOLS] list_skills error: %s", e)
        return f"❌ Lỗi liệt kê skills: {e}"


@tool
def tool_delete_skill(domain_id: str, skill_id: str) -> str:
    """
    Xóa một runtime skill.

    Args:
        domain_id: Domain ID chứa skill
        skill_id: ID của skill cần xóa

    Returns:
        Thông báo thành công hoặc lỗi
    """
    try:
        from app.domains.skill_manager import get_skill_manager

        manager = get_skill_manager()
        result = manager.delete_skill(domain_id, skill_id)

        if result.success:
            return f"✅ {result.message}"
        else:
            return f"❌ {result.message}"

    except Exception as e:
        logger.error("[SKILL_TOOLS] delete_skill error: %s", e)
        return f"❌ Lỗi xóa skill: {e}"


def get_skill_tools() -> list:
    """Get all skill management tools (for registration)."""
    return [tool_create_skill, tool_list_skills, tool_delete_skill]
