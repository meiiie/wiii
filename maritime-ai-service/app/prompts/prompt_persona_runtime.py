"""Prompt persona loading and template helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.prompts.prompt_overlay_guard import merge_with_base, sanitize_domain_overlay


logger = logging.getLogger(__name__)


def _get_default_persona_impl() -> Dict[str, Any]:
    return {
        "role": "AI Assistant",
        "tone": ["Thân thiện", "Chuyên nghiệp"],
        "instructions": {},
        "few_shot_examples": [],
    }


def _load_identity_impl(prompts_dir: Path) -> Dict[str, Any]:
    """Load Wiii character identity (single source of truth)."""
    identity_path = prompts_dir / "wiii_identity.yaml"
    if identity_path.exists():
        try:
            with open(identity_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
            logger.info("[OK] Loaded Wiii identity from wiii_identity.yaml")
            return config
        except Exception as exc:
            logger.warning("[WARN] Failed to load wiii_identity.yaml: %s", exc)
    return {}


def _load_shared_config_impl(prompts_dir: Path) -> Dict[str, Any]:
    """Load shared base configuration for inheritance."""
    shared_path = prompts_dir / "base" / "_shared.yaml"
    if shared_path.exists():
        try:
            with open(shared_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle)
            logger.info("[OK] Loaded shared base config from base/_shared.yaml")
            return config
        except Exception as exc:
            logger.error("[FAIL] Failed to load shared config: %s", exc)
    return {}


def _load_domain_shared_config_impl(domain_prompts_dir: Optional[Path]) -> Dict[str, Any]:
    """Load domain-specific shared base config (Layer 2 overlay)."""
    if not domain_prompts_dir:
        return {}
    shared_path = domain_prompts_dir / "base" / "_shared.yaml"
    if shared_path.exists():
        try:
            with open(shared_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle)
            logger.debug("Loaded domain shared config overlay")
            return config
        except Exception as exc:
            logger.warning("Failed to load domain shared config: %s", exc)
    return {}


def get_persona_impl(personas: Dict[str, Dict[str, Any]], role: str) -> Dict[str, Any]:
    """Get persona configuration for a role."""
    return personas.get(role, personas.get("student", {}))


def _replace_template_variables_impl(text: str, user_name: Optional[str] = None, **kwargs) -> str:
    """Replace template variables in text with actual values."""
    if not text:
        return text

    if user_name:
        text = text.replace("{{user_name}}", user_name)
    else:
        text = text.replace("{{user_name}}", "bạn")

    return text


def _load_personas_impl(
    prompts_dir: Path,
    domain_prompts_dir: Optional[Path],
) -> Dict[str, Dict[str, Any]]:
    """Load all persona YAML files with inheritance support."""
    from app.core.config import settings as app_settings

    legacy_files = {
        "student": "agents/tutor.yaml",
        "teacher": "agents/assistant.yaml",
        "admin": "agents/assistant.yaml",
    }
    new_agent_files = {
        "tutor_agent": "agents/tutor.yaml",
        "assistant_agent": "agents/assistant.yaml",
        "rag_agent": "agents/rag.yaml",
        "memory_agent": "agents/memory.yaml",
        "direct_agent": "agents/direct.yaml",
        "direct_chatter_agent": "agents/direct_chatter.yaml",
        "code_studio_agent": "agents/code_studio.yaml",
    }

    personas: Dict[str, Dict[str, Any]] = {}
    detailed_startup_logs = app_settings.environment != "development"

    if detailed_startup_logs:
        logger.debug("PromptLoader: Looking for YAML files in %s", prompts_dir)
        logger.debug("PromptLoader: Directory exists: %s", prompts_dir.exists())

    if prompts_dir.exists():
        try:
            files_in_dir = list(prompts_dir.glob("**/*.yaml"))
            if detailed_startup_logs:
                logger.debug(
                    "PromptLoader: Found YAML files: %s",
                    [str(f.relative_to(prompts_dir)) for f in files_in_dir],
                )
        except Exception as exc:
            logger.warning("PromptLoader: Could not list directory: %s", exc)

    shared_config = _load_shared_config_impl(prompts_dir)
    loaded_count = 0

    for role, filename in legacy_files.items():
        filepath = prompts_dir / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as handle:
                    personas[role] = yaml.safe_load(handle)
                if detailed_startup_logs:
                    logger.debug("Loaded persona for role '%s' from %s", role, filename)
                loaded_count += 1
            except Exception as exc:
                logger.error("[FAIL] Failed to load %s: %s", filename, exc)
                personas[role] = _get_default_persona_impl()
        else:
            logger.warning("[WARN] Persona file not found: %s - using default", filepath)
            personas[role] = _get_default_persona_impl()

    for agent_id, filename in new_agent_files.items():
        filepath = prompts_dir / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as handle:
                    agent_config = yaml.safe_load(handle)
                if agent_config.get("extends"):
                    agent_config = merge_with_base(agent_config, shared_config)
                personas[agent_id] = agent_config
                if detailed_startup_logs:
                    logger.debug("Loaded agent persona '%s' from %s", agent_id, filename)
                loaded_count += 1
            except Exception as exc:
                logger.error("[FAIL] Failed to load %s: %s", filename, exc)

    if domain_prompts_dir and domain_prompts_dir.exists():
        domain_agent_dir = domain_prompts_dir / "agents"
        if domain_agent_dir.exists():
            for yaml_file in domain_agent_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as handle:
                        domain_config = yaml.safe_load(handle)

                    domain_shared = _load_domain_shared_config_impl(domain_prompts_dir)
                    if domain_config.get("extends") and domain_shared:
                        domain_config = merge_with_base(domain_config, domain_shared)

                    agent_id = domain_config.get("agent", {}).get("id", "")
                    role_key = yaml_file.stem

                    if agent_id:
                        if agent_id in personas:
                            personas[agent_id] = merge_with_base(
                                domain_config,
                                personas[agent_id],
                                preserve_identity=True,
                            )
                        else:
                            personas[agent_id] = sanitize_domain_overlay(domain_config)

                    stem_to_legacy = {
                        "tutor": ["student"],
                        "assistant": ["teacher", "admin"],
                    }
                    legacy_roles = stem_to_legacy.get(role_key, [])
                    for legacy_role in legacy_roles:
                        if legacy_role in personas:
                            personas[legacy_role] = merge_with_base(
                                domain_config,
                                personas[legacy_role],
                                preserve_identity=True,
                            )
                        else:
                            personas[legacy_role] = sanitize_domain_overlay(domain_config)

                    loaded_count += 1
                    if detailed_startup_logs:
                        logger.info("  Domain overlay loaded: %s", yaml_file.name)
                except Exception as exc:
                    logger.warning("  Failed to load domain overlay %s: %s", yaml_file, exc)

    logger.info("PromptLoader loaded %d persona files", loaded_count)
    return personas
