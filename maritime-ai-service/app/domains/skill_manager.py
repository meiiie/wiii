"""
Runtime Skill Manager — Dynamic skill creation for Wiii AI agent.

Creates, validates, and registers SKILL.md files at runtime,
enabling the agent to extend its own capabilities.

Sprint 13: Extended Tools & Self-Extending Skills.
"""

import logging
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RuntimeSkillResult:
    """Result of a skill creation/deletion operation."""
    success: bool
    message: str
    skill_id: Optional[str] = None
    path: Optional[str] = None


class SkillManager:
    """
    Manages runtime-created skills (SKILL.md files).

    Skills are stored as SKILL.md files in the workspace,
    with YAML frontmatter for metadata and Markdown body for content.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        root = workspace_root or getattr(settings, "workspace_root", "~/.wiii/workspace")
        self._root = Path(root).expanduser().resolve()
        self._skills_dir = self._root / "skills"

    def _ensure_dirs(self, domain_id: str, skill_name: str) -> Path:
        """Create skill directory structure."""
        skill_dir = self._skills_dir / domain_id / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        return skill_dir

    def _validate_skill(
        self,
        name: str,
        description: str,
        triggers: List[str],
        content: str,
    ) -> Optional[str]:
        """
        Validate skill parameters.

        Returns:
            None if valid, error message if invalid
        """
        if not name or len(name) < 2:
            return "Tên skill phải có ít nhất 2 ký tự"
        if not description:
            return "Mô tả skill không được để trống"
        if not triggers:
            return "Skill cần ít nhất 1 trigger keyword"
        if not content:
            return "Nội dung skill không được để trống"

        # Validate name (safe for filesystem)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return "Tên skill chỉ được chứa chữ cái, số, _ và -"

        return None

    def create_skill(
        self,
        domain_id: str,
        name: str,
        description: str,
        triggers: List[str],
        content: str,
        version: str = "1.0.0",
    ) -> RuntimeSkillResult:
        """
        Create a new runtime skill as a SKILL.md file.

        Args:
            domain_id: Domain this skill belongs to
            name: Skill name (used as folder name)
            description: Brief description
            triggers: List of trigger keywords
            content: Full skill content (Markdown)
            version: Version string

        Returns:
            RuntimeSkillResult with success/failure info
        """
        # Validate
        error = self._validate_skill(name, description, triggers, content)
        if error:
            return RuntimeSkillResult(success=False, message=error)

        try:
            skill_dir = self._ensure_dirs(domain_id, name)
            skill_path = skill_dir / "SKILL.md"

            # Build YAML frontmatter
            frontmatter = {
                "id": name,
                "name": name.replace("-", " ").replace("_", " ").title(),
                "description": description,
                "triggers": triggers,
                "domain_id": domain_id,
                "version": version,
                "runtime": True,  # Mark as runtime-created
            }

            # Write SKILL.md with YAML frontmatter + Markdown body
            yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
            skill_content = f"---\n{yaml_str}---\n\n{content}\n"

            skill_path.write_text(skill_content, encoding="utf-8")

            logger.info("[SKILL_MANAGER] Created skill: %s/%s", domain_id, name)
            self._refresh_domain_cache(domain_id)

            return RuntimeSkillResult(
                success=True,
                message=f"Đã tạo skill '{name}' cho domain '{domain_id}'",
                skill_id=name,
                path=str(skill_path),
            )

        except Exception as e:
            logger.error("[SKILL_MANAGER] Error creating skill %s: %s", name, e)
            return RuntimeSkillResult(
                success=False,
                message=f"Lỗi tạo skill: {e}",
            )

    def list_runtime_skills(self, domain_id: Optional[str] = None) -> List[Dict]:
        """
        List all runtime-created skills.

        Args:
            domain_id: Filter by domain (None for all)

        Returns:
            List of skill metadata dicts
        """
        skills = []

        if not self._skills_dir.exists():
            return skills

        search_dirs = []
        if domain_id:
            domain_dir = self._skills_dir / domain_id
            if domain_dir.exists():
                search_dirs = [domain_dir]
        else:
            search_dirs = [d for d in self._skills_dir.iterdir() if d.is_dir()]

        for domain_dir in search_dirs:
            for skill_dir in domain_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                try:
                    content = skill_md.read_text(encoding="utf-8")
                    # Parse YAML frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            metadata = yaml.safe_load(parts[1])
                            if metadata:
                                metadata["_path"] = str(skill_md)
                                skills.append(metadata)
                except Exception as e:
                    logger.warning("[SKILL_MANAGER] Error reading %s: %s", skill_md, e)

        return skills

    def delete_skill(self, domain_id: str, skill_id: str) -> RuntimeSkillResult:
        """
        Delete a runtime-created skill.

        Args:
            domain_id: Domain the skill belongs to
            skill_id: Skill identifier

        Returns:
            RuntimeSkillResult with success/failure info
        """
        skill_dir = self._skills_dir / domain_id / skill_id

        if not skill_dir.exists():
            return RuntimeSkillResult(
                success=False,
                message=f"Skill '{skill_id}' không tồn tại trong domain '{domain_id}'",
            )

        try:
            # Remove skill files and directory
            import shutil
            shutil.rmtree(skill_dir)
            logger.info("[SKILL_MANAGER] Deleted skill: %s/%s", domain_id, skill_id)
            self._refresh_domain_cache(domain_id)
            return RuntimeSkillResult(
                success=True,
                message=f"Đã xóa skill '{skill_id}' khỏi domain '{domain_id}'",
                skill_id=skill_id,
            )
        except Exception as e:
            logger.error("[SKILL_MANAGER] Error deleting skill %s: %s", skill_id, e)
            return RuntimeSkillResult(
                success=False,
                message=f"Lỗi xóa skill: {e}",
            )

    def _refresh_domain_cache(self, domain_id: str) -> None:
        """Refresh the domain plugin's skills cache after create/delete."""
        try:
            from app.domains.registry import get_domain_registry
            registry = get_domain_registry()
            plugin = registry.get(domain_id)
            if plugin and hasattr(plugin, "refresh_skills"):
                plugin.refresh_skills()
                logger.debug("[SKILL_MANAGER] Refreshed skills cache for domain %s", domain_id)
        except Exception as e:
            logger.debug("[SKILL_MANAGER] Could not refresh domain cache: %s", e)

    def get_skill_content(self, domain_id: str, skill_id: str) -> Optional[str]:
        """Get the full content body of a skill."""
        skill_md = self._skills_dir / domain_id / skill_id / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content


# Singleton factory
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get the singleton SkillManager instance."""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
