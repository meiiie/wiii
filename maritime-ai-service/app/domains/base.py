"""
Domain Plugin Base Classes.

Defines the ABC for domain plugins and data structures.

Sprint 26: Added YamlDomainPlugin intermediate class to eliminate
~95% code duplication between domain implementations.

Inspired by:
- OpenClaw SKILL.md manifest format
- Google ADK code-first agents
- Cloudflare RFC 8615 discovery
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class DomainConfig:
    """Configuration for a domain plugin."""
    id: str                           # "maritime"
    name: str                         # "Maritime Education"
    name_vi: str                      # "Giao duc Hang hai"
    version: str                      # "1.0.0"
    description: str = ""
    routing_keywords: List[str] = field(default_factory=list)
    mandatory_search_triggers: List[str] = field(default_factory=list)
    rag_agent_description: str = ""
    tutor_agent_description: str = ""
    scope_description: str = ""


@dataclass
class SkillManifest:
    """
    Manifest for a domain skill (OpenClaw-inspired SKILL.md format).

    Progressive disclosure:
      Level 1: name + description (always loaded)
      Level 2: triggers (loaded on domain activation)
      Level 3: full content body (loaded on skill activation)
    """
    id: str                           # "colregs"
    name: str                         # "COLREGs Navigation Rules"
    description: str                  # Brief description
    triggers: List[str] = field(default_factory=list)
    domain_id: str = ""
    content_path: Optional[Path] = None  # Path to full SKILL.md body
    version: str = "1.0.0"


class DomainPlugin(ABC):
    """
    Abstract base class for domain plugins.

    Each domain implements this to provide:
    - Configuration (routing keywords, descriptions)
    - Prompt templates (persona YAML files)
    - Skills (SKILL.md format)
    - HyDE templates
    - Custom tools (optional)
    """

    @abstractmethod
    def get_config(self) -> DomainConfig:
        """Return domain configuration."""
        ...

    @abstractmethod
    def get_prompts_dir(self) -> Path:
        """Return path to domain prompt YAML files."""
        ...

    def get_tools(self) -> List[Callable]:
        """Return domain-specific tools. Override to add custom tools."""
        return []

    def get_tool_instruction(self) -> str:
        """Return tool usage instruction for agent system prompt."""
        return """
## QUY TAC TOOL (CRITICAL - RAG-First Pattern):

1. **LUON LUON** su dung tool `tool_knowledge_search` de tim kiem kien thuc **TRUOC KHI** tra loi.
2. **KHONG BAO GIO** tra loi tu kien thuc rieng ma khong tim kiem truoc.
3. Sau khi tim kiem, giang day **DUA TREN** ket qua tim duoc.
4. **TRICH DAN nguon** trong cau tra loi.
"""

    def get_skills(self) -> List[SkillManifest]:
        """Return list of skill manifests (progressive disclosure level 1-2)."""
        return []

    def get_hyde_templates(self) -> Dict[str, str]:
        """Return HyDE prompt templates keyed by language code ('vi', 'en')."""
        return {}

    def get_routing_config(self) -> Dict[str, Any]:
        """Return routing configuration (keywords, prompt fragments)."""
        config = self.get_config()
        return {
            "routing_keywords": config.routing_keywords,
            "rag_description": config.rag_agent_description,
            "tutor_description": config.tutor_agent_description,
            "scope_description": config.scope_description,
        }

    def get_greetings(self) -> Dict[str, str]:
        """Return greeting responses keyed by trigger phrase."""
        config = self.get_config()
        return {
            "xin chao": f"Xin chao! Toi la {config.name} Tutor. Toi co the giup gi cho ban?",
            "hello": f"Hello! I'm {config.name} Tutor. How can I help you?",
            "hi": f"Chao ban! Ban muon hoi ve van de {config.name_vi} nao?",
            "cam on": "Khong co gi! Neu co thac mac gi khac, cu hoi nhe!",
            "thanks": "You're welcome! Let me know if you have more questions.",
        }

    def activate_skill(self, skill_id: str) -> Optional[str]:
        """
        Lazy-load full skill content (progressive disclosure level 3).

        Args:
            skill_id: Skill identifier

        Returns:
            Full SKILL.md body text, or None if not found
        """
        for skill in self.get_skills():
            if skill.id == skill_id and skill.content_path:
                try:
                    return skill.content_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("Failed to load skill %s: %s", skill_id, e)
                    return None
        return None

    def match_skills(self, query: str) -> List[SkillManifest]:
        """
        Match query against skill triggers.

        Args:
            query: User query text

        Returns:
            List of matching skills, sorted by trigger specificity
        """
        query_lower = query.lower()
        matched = []
        for skill in self.get_skills():
            for trigger in skill.triggers:
                # Each trigger can be comma-separated alternatives
                alternatives = [t.strip().lower() for t in trigger.split(",")]
                for alt in alternatives:
                    if alt in query_lower:
                        matched.append(skill)
                        break
                else:
                    continue
                break  # Only match a skill once
        return matched


class YamlDomainPlugin(DomainPlugin):
    """
    Base class for YAML-configured domain plugins.

    Sprint 26: Extracted common logic from MaritimeDomain/TrafficLawDomain
    to eliminate ~95% code duplication. Subclasses only need to override
    domain-specific content methods (get_tool_instruction, get_hyde_templates,
    get_routing_config, get_greetings).

    Handles:
    - domain.yaml manifest loading and caching
    - DomainConfig construction from YAML
    - Skill loading from skills/ directory
    - SKILL.md frontmatter parsing with dynamic domain_id
    - Prompts directory resolution
    """

    def __init__(self, domain_dir: Path):
        """
        Initialize from a domain directory containing domain.yaml.

        Args:
            domain_dir: Path to the domain's root directory
        """
        self._domain_dir = domain_dir
        self._config: Optional[DomainConfig] = None
        self._skills: Optional[List[SkillManifest]] = None
        self._manifest: Optional[Dict[str, Any]] = None
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load domain.yaml manifest from domain directory."""
        manifest_path = self._domain_dir / "domain.yaml"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                self._manifest = yaml.safe_load(f)
            logger.info("%s domain manifest loaded", self.__class__.__name__)
        except Exception as e:
            logger.error(
                "Failed to load %s domain manifest: %s",
                self.__class__.__name__, e,
            )
            self._manifest = {}

    def get_config(self) -> DomainConfig:
        if self._config is None:
            m = self._manifest or {}
            self._config = DomainConfig(
                id=m.get("id", self._domain_dir.name),
                name=m.get("name", self._domain_dir.name.replace("_", " ").title()),
                name_vi=m.get("name_vi", ""),
                version=m.get("version", "1.0.0"),
                description=m.get("description", ""),
                routing_keywords=m.get("routing_keywords", []),
                mandatory_search_triggers=m.get("mandatory_search_triggers", []),
                rag_agent_description=m.get("rag_agent_description", ""),
                tutor_agent_description=m.get("tutor_agent_description", ""),
                scope_description=m.get("scope_description", ""),
            )
        return self._config

    def get_prompts_dir(self) -> Path:
        return self._domain_dir / "prompts"

    def get_skills(self) -> List[SkillManifest]:
        if self._skills is None:
            self._skills = self._load_skills()
        return self._skills

    def refresh_skills(self) -> None:
        """Invalidate skills cache, forcing reload on next access."""
        self._skills = None

    def _load_skills(self) -> List[SkillManifest]:
        """Load SKILL.md files from plugin dir AND runtime workspace."""
        skills = []

        # 1. Static skills from plugin directory
        static_dir = self._domain_dir / "skills"
        if static_dir.exists():
            skills.extend(self._scan_skills_dir(static_dir))

        # 2. Runtime skills from workspace directory (Sprint 29)
        runtime_dir = self._get_runtime_skills_dir()
        if runtime_dir and runtime_dir.exists() and runtime_dir != static_dir:
            seen_ids = {s.id for s in skills}
            for skill in self._scan_skills_dir(runtime_dir):
                if skill.id not in seen_ids:
                    skills.append(skill)

        config = self.get_config()
        logger.info("%s domain loaded %d skills", config.id, len(skills))
        return skills

    def _get_runtime_skills_dir(self) -> Optional[Path]:
        """Get the runtime skills directory for this domain."""
        try:
            from app.core.config import settings
            root = getattr(settings, "workspace_root", "~/.wiii/workspace")
            workspace = Path(root).expanduser().resolve()
            config = self.get_config()
            return workspace / "skills" / config.id
        except Exception as e:
            logger.debug("Failed to resolve runtime skills dir: %s", e)
            return None

    def _scan_skills_dir(self, skills_dir: Path) -> List[SkillManifest]:
        """Scan a directory for SKILL.md files."""
        skills = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                manifest = self._parse_skill_frontmatter(skill_md)
                if manifest:
                    skills.append(manifest)
            except Exception as e:
                logger.warning("Failed to parse skill %s: %s", skill_dir.name, e)
        return skills

    def _parse_skill_frontmatter(self, skill_path: Path) -> Optional[SkillManifest]:
        """Parse YAML frontmatter from SKILL.md file."""
        content = skill_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])
        if not frontmatter:
            return None

        triggers = frontmatter.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [triggers]

        return SkillManifest(
            id=frontmatter.get("id", frontmatter.get("name", skill_path.parent.name)),
            name=frontmatter.get("display_name", frontmatter.get("name", "")),
            description=frontmatter.get("description", ""),
            triggers=triggers,
            domain_id=self.get_config().id,
            content_path=skill_path,
            version=frontmatter.get("version", "1.0.0"),
        )
