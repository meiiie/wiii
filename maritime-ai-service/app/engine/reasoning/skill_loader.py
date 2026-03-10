"""Load reasoning skills from SKILL.md files."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_REASONING_SKILLS_DIR = Path(__file__).resolve().parent / "skills"
_TOOL_GOVERNANCE_SKILL = (
    Path(__file__).resolve().parent.parent / "skills" / "tool-governance" / "SKILL.md"
)


@dataclass(frozen=True)
class ReasoningSkill:
    """Runtime view of a reasoning skill."""

    id: str
    name: str
    skill_type: str
    description: str = ""
    node: Optional[str] = None
    applies_to: tuple[str, ...] = field(default_factory=tuple)
    phase_labels: dict[str, str] = field(default_factory=dict)
    phase_focus: dict[str, str] = field(default_factory=dict)
    delta_guidance: dict[str, str] = field(default_factory=dict)
    fallback_summaries: dict[str, str] = field(default_factory=dict)
    fallback_actions: dict[str, str] = field(default_factory=dict)
    action_style: str = ""
    avoid_phrases: tuple[str, ...] = field(default_factory=tuple)
    style_tags: tuple[str, ...] = field(default_factory=tuple)
    content: str = ""
    path: Optional[Path] = None


class ReasoningSkillLoader:
    """Load narrator-facing skills from SKILL.md files."""

    def __init__(self, skills_dir: Optional[Path] = None):
        self._skills_dir = skills_dir or _REASONING_SKILLS_DIR
        self._loaded = False
        self._skills: dict[str, ReasoningSkill] = {}
        self._node_index: dict[str, ReasoningSkill] = {}

    def _parse_skill(self, path: Path) -> Optional[ReasoningSkill]:
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("[REASONING_SKILL] Failed reading %s: %s", path, exc)
            return None

        if not raw.startswith("---"):
            return None
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except Exception as exc:
            logger.warning("[REASONING_SKILL] Failed parsing frontmatter %s: %s", path, exc)
            return None
        if not isinstance(frontmatter, dict):
            return None

        applies_to = frontmatter.get("applies_to", [])
        if isinstance(applies_to, str):
            applies_to = [applies_to]
        phase_labels = frontmatter.get("phase_labels", {}) or {}
        phase_focus = frontmatter.get("phase_focus", {}) or {}
        delta_guidance = frontmatter.get("delta_guidance", {}) or {}
        fallback_summaries = frontmatter.get("fallback_summaries", {}) or {}
        fallback_actions = frontmatter.get("fallback_actions", {}) or {}
        action_style = str(frontmatter.get("action_style", "") or "")
        avoid_phrases = frontmatter.get("avoid_phrases", []) or []
        if isinstance(avoid_phrases, str):
            avoid_phrases = [avoid_phrases]
        style_tags = frontmatter.get("style_tags", []) or []
        if isinstance(style_tags, str):
            style_tags = [style_tags]

        return ReasoningSkill(
            id=str(frontmatter.get("id", frontmatter.get("name", path.parent.name))),
            name=str(frontmatter.get("name", path.parent.name)),
            skill_type=str(frontmatter.get("skill_type", "subagent")),
            description=str(frontmatter.get("description", "")),
            node=str(frontmatter["node"]) if frontmatter.get("node") else None,
            applies_to=tuple(str(item) for item in applies_to),
            phase_labels={str(k): str(v) for k, v in phase_labels.items()},
            phase_focus={str(k): str(v) for k, v in phase_focus.items()},
            delta_guidance={str(k): str(v) for k, v in delta_guidance.items()},
            fallback_summaries={str(k): str(v) for k, v in fallback_summaries.items()},
            fallback_actions={str(k): str(v) for k, v in fallback_actions.items()},
            action_style=action_style,
            avoid_phrases=tuple(str(item) for item in avoid_phrases),
            style_tags=tuple(str(item) for item in style_tags),
            content=parts[2].strip(),
            path=path,
        )

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        for skill_path in sorted(self._skills_dir.rglob("SKILL.md")):
            skill = self._parse_skill(skill_path)
            if not skill:
                continue
            self._skills[skill.id] = skill
            if skill.node:
                self._node_index[skill.node] = skill

        tool_skill = self._parse_skill(_TOOL_GOVERNANCE_SKILL)
        if tool_skill:
            self._skills[tool_skill.id] = tool_skill

    def get(self, skill_id: str) -> Optional[ReasoningSkill]:
        self._ensure_loaded()
        return self._skills.get(skill_id)

    def get_node_skill(self, node: str) -> Optional[ReasoningSkill]:
        self._ensure_loaded()
        return self._node_index.get(node)

    def get_persona_skills(self) -> list[ReasoningSkill]:
        self._ensure_loaded()
        return sorted(
            [
            skill
            for skill in self._skills.values()
            if skill.skill_type == "persona"
            ],
            key=lambda skill: skill.id,
        )

    def get_tool_skill(self) -> Optional[ReasoningSkill]:
        self._ensure_loaded()
        return self._skills.get("tool-governance")


_LOADER: Optional[ReasoningSkillLoader] = None


def get_reasoning_skill_loader() -> ReasoningSkillLoader:
    """Return the shared reasoning skill loader."""
    global _LOADER
    if _LOADER is None:
        _LOADER = ReasoningSkillLoader()
    return _LOADER
