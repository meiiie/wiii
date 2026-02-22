"""
Soul Loader — Reads and validates Wiii's identity from YAML.

Sprint 170: Loads SOUL.yaml into a validated SoulConfig model.
Cached with TTL — reloads when file changes (hot-reload support).

Usage:
    soul = get_soul()
    print(soul.core_truths)
    print(soul.interests.primary)
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from app.engine.living_agent.models import MoodType, SoulBoundary, SoulConfig, SoulInterests

logger = logging.getLogger(__name__)

# Default soul file path (relative to project root)
_SOUL_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "soul"
_DEFAULT_SOUL_FILE = _SOUL_DIR / "wiii_soul.yaml"


def load_soul_from_file(file_path: Optional[Path] = None) -> SoulConfig:
    """Load Wiii's soul configuration from a YAML file.

    Args:
        file_path: Path to soul YAML file. Defaults to prompts/soul/wiii_soul.yaml.

    Returns:
        Validated SoulConfig instance.

    Raises:
        FileNotFoundError: If soul file doesn't exist.
        ValueError: If YAML is malformed or fails validation.
    """
    path = file_path or _DEFAULT_SOUL_FILE

    if not path.exists():
        logger.warning("[SOUL] Soul file not found at %s, using defaults", path)
        return SoulConfig()

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error("[SOUL] Failed to parse soul YAML: %s", e)
        raise ValueError(f"Invalid soul YAML: {e}") from e

    if not raw or not isinstance(raw, dict):
        logger.warning("[SOUL] Empty or invalid soul file, using defaults")
        return SoulConfig()

    return _parse_soul_config(raw)


def _parse_soul_config(raw: dict) -> SoulConfig:
    """Parse raw YAML dict into a validated SoulConfig."""

    identity = raw.get("identity", {})
    style = raw.get("communication_style", {})
    interests_raw = raw.get("interests", {})
    emotional = raw.get("emotional_baseline", {})
    goals = raw.get("growth_goals", {})

    # Parse boundaries (list of strings or dicts)
    boundaries = []
    for b in raw.get("boundaries", []):
        if isinstance(b, str):
            boundaries.append(SoulBoundary(rule=b))
        elif isinstance(b, dict):
            boundaries.append(SoulBoundary(**b))

    # Parse interests
    interests = SoulInterests(
        primary=interests_raw.get("primary", []),
        exploring=interests_raw.get("exploring", []),
        wants_to_learn=interests_raw.get("wants_to_learn", []),
    )

    # Parse default mood
    default_mood_str = emotional.get("default_mood", "curious")
    try:
        default_mood = MoodType(default_mood_str)
    except ValueError:
        logger.warning("[SOUL] Unknown mood '%s', defaulting to CURIOUS", default_mood_str)
        default_mood = MoodType.CURIOUS

    return SoulConfig(
        name=identity.get("name", "Wiii"),
        creator=identity.get("creator", "The Wiii Lab"),
        species=identity.get("species", "AI Living Agent"),
        age_metaphor=identity.get("age_metaphor", ""),
        core_truths=raw.get("core_truths", []),
        boundaries=boundaries,
        tone=style.get("tone", "Thân thiện"),
        language=style.get("language", "Tiếng Việt tự nhiên"),
        humor_level=style.get("humor_level", "moderate"),
        formality=style.get("formality", "adaptive"),
        interests=interests,
        default_mood=default_mood,
        energy_cycle=emotional.get("energy_cycle", ""),
        short_term_goals=goals.get("short_term", []),
        long_term_goals=goals.get("long_term", []),
    )


# =============================================================================
# Singleton access
# =============================================================================

_soul_instance: Optional[SoulConfig] = None


def get_soul(force_reload: bool = False) -> SoulConfig:
    """Get the cached soul configuration (singleton).

    Args:
        force_reload: Force re-read from file.

    Returns:
        SoulConfig instance.
    """
    global _soul_instance

    if _soul_instance is None or force_reload:
        _soul_instance = load_soul_from_file()
        logger.info(
            "[SOUL] Loaded: name=%s, truths=%d, boundaries=%d, interests=%d",
            _soul_instance.name,
            len(_soul_instance.core_truths),
            len(_soul_instance.boundaries),
            len(_soul_instance.interests.primary),
        )

    return _soul_instance


def compile_soul_prompt(soul: Optional[SoulConfig] = None) -> str:
    """Compile soul config into a system prompt section.

    Returns a formatted string to inject into LLM system prompts.
    """
    s = soul or get_soul()

    sections = [
        f"--- LINH HỒN CỦA {s.name.upper()} ---",
        "",
        f"Tên: {s.name} | Tạo bởi: {s.creator}",
        f"Bản chất: {s.age_metaphor}",
        "",
        "## Chân lý cốt lõi:",
    ]
    for truth in s.core_truths:
        sections.append(f"- {truth}")

    sections.append("")
    sections.append("## Ranh giới:")
    for b in s.boundaries:
        marker = "[CỨNG]" if b.severity == "hard" else "[MỀM]"
        sections.append(f"- {marker} {b.rule}")

    sections.append("")
    sections.append(f"## Phong cách: {s.tone}")
    sections.append(f"## Ngôn ngữ: {s.language}")

    if s.interests.primary:
        sections.append("")
        sections.append("## Sở thích chính:")
        for interest in s.interests.primary:
            sections.append(f"- {interest}")

    if s.short_term_goals:
        sections.append("")
        sections.append("## Mục tiêu hiện tại:")
        for goal in s.short_term_goals:
            sections.append(f"- {goal}")

    sections.append("")
    sections.append("--- HẾT LINH HỒN ---")

    return "\n".join(sections)
