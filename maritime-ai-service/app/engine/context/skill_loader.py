"""Sprint 222b Phase 6: Dynamic YAML Skill Loading.

Loads context-aware skills from YAML files based on host_type + page_type.
Follows Claude Code's SKILL.md progressive disclosure pattern.

Fallback chain:
1. Exact: {host_type}/{page_type}.skill.yaml
2. Host default: {host_type}/default.skill.yaml
3. Global default: generic/default.skill.yaml
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_SKILLS_DIR = Path(__file__).parent / "skills"


@dataclass
class ContextSkill:
    """A context-aware skill loaded from YAML."""
    name: str
    host_type: str
    page_types: list[str]
    description: str
    priority: float = 0.5
    prompt_addition: str = ""
    tools: list[str] = field(default_factory=list)
    enrichment_triggers: list[dict] = field(default_factory=list)


class ContextSkillLoader:
    """Load YAML skills based on host_type + page_type."""

    def __init__(self, skills_dir: Optional[Path] = None):
        self._skills_dir = skills_dir or _DEFAULT_SKILLS_DIR
        self._cache: dict[str, list[ContextSkill]] = {}
        self._all_skills: list[ContextSkill] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._skills_dir.exists():
            return
        for yaml_file in self._skills_dir.rglob("*.skill.yaml"):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or "name" not in raw:
                    continue
                skill = ContextSkill(
                    name=raw["name"],
                    host_type=raw.get("host_type", "generic"),
                    page_types=raw.get("page_types", ["*"]),
                    description=raw.get("description", ""),
                    priority=float(raw.get("priority", 0.5)),
                    prompt_addition=raw.get("prompt_addition", ""),
                    tools=raw.get("tools", []),
                    enrichment_triggers=raw.get("enrichment_triggers", []),
                )
                self._all_skills.append(skill)
            except Exception as e:
                logger.warning("Failed to parse skill %s: %s", yaml_file, e)

    def load_skills(self, host_type: str, page_type: str) -> list[ContextSkill]:
        """Load skills matching host_type + page_type with fallback chain."""
        cache_key = f"{host_type}:{page_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._ensure_loaded()

        exact: list[ContextSkill] = []
        host_default: list[ContextSkill] = []
        generic_default: list[ContextSkill] = []

        for skill in self._all_skills:
            if skill.host_type == host_type:
                if page_type in skill.page_types:
                    exact.append(skill)
                elif "*" in skill.page_types:
                    host_default.append(skill)
            elif skill.host_type == "generic" and "*" in skill.page_types:
                generic_default.append(skill)

        if exact:
            result = exact + host_default
        elif host_default:
            result = host_default
        elif generic_default:
            result = generic_default
        else:
            result = []

        result.sort(key=lambda s: s.priority, reverse=True)
        self._cache[cache_key] = result
        return result

    @staticmethod
    def get_prompt_addition(skills: list[ContextSkill]) -> str:
        """Concatenate prompt additions from all matched skills."""
        parts = [s.prompt_addition for s in skills if s.prompt_addition]
        return "\n\n".join(parts)

    @staticmethod
    def get_tool_ids(skills: list[ContextSkill]) -> list[str]:
        """Collect deduplicated tool IDs from all matched skills."""
        seen: set[str] = set()
        result: list[str] = []
        for skill in skills:
            for tid in skill.tools:
                if tid not in seen:
                    seen.add(tid)
                    result.append(tid)
        return result


_loader_instance: Optional[ContextSkillLoader] = None


def get_skill_loader() -> ContextSkillLoader:
    """Get singleton ContextSkillLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ContextSkillLoader()
    return _loader_instance


def _reset_skill_loader() -> None:
    """Reset singleton (for testing)."""
    global _loader_instance
    _loader_instance = None
