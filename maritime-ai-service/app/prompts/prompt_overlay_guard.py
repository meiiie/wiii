"""Overlay sanitization and merge helpers for prompt loading."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict

logger = logging.getLogger(__name__)

DOMAIN_PROTECTED_TOP_LEVEL_KEYS = {
    "identity",
    "role",
    "tone",
    "character",
    "backstory",
    "name",
    "display_name",
    "greeting",
}

DOMAIN_PROTECTED_AGENT_KEYS = {
    "name",
    "role",
    "backstory",
    "identity",
    "persona",
    "character",
}

DOMAIN_PROTECTED_STYLE_KEYS = {
    "tone",
    "voice",
    "personality",
    "persona",
}

IDENTITY_OVERRIDE_LINE_PATTERNS = [
    re.compile(r"\b(?:ban|bạn|you)\s+(?:duoc goi la|được gọi là|are now|your name is)\b", re.IGNORECASE),
    re.compile(r"\b(?:doi ten|đổi tên|rename)\b", re.IGNORECASE),
    re.compile(r"\b(?:hay dong vai|hãy đóng vai|act as)\b", re.IGNORECASE),
    re.compile(r"\b(?:ban|bạn|you)\s+la\s+(?:tro ly|trợ lý|chatbot|assistant)\b", re.IGNORECASE),
]

IDENTITY_OVERRIDE_NORMALIZED_PATTERNS = [
    re.compile(r"\b(?:ban|you)\s+(?:duoc goi la|are now|your name is)\b", re.IGNORECASE),
    re.compile(r"\b(?:doi ten|rename)\b", re.IGNORECASE),
    re.compile(r"\b(?:hay dong vai|act as)\b", re.IGNORECASE),
    re.compile(r"\b(?:ban|you)\s+la\s+(?:tro ly|chatbot|assistant)\b", re.IGNORECASE),
]


def normalize_overlay_line(text: str) -> str:
    """Normalize overlay text for robust identity-override detection."""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def sanitize_domain_overlay(overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Prevent domain overlays from redefining Wiii's core identity."""
    sanitized: Dict[str, Any] = {}
    stripped_keys: list[str] = []

    for key, value in overlay.items():
        if key in DOMAIN_PROTECTED_TOP_LEVEL_KEYS:
            stripped_keys.append(key)
            continue
        if key == "agent" and isinstance(value, dict):
            safe_agent = {
                nested_key: nested_value
                for nested_key, nested_value in value.items()
                if nested_key not in DOMAIN_PROTECTED_AGENT_KEYS
            }
            stripped_keys.extend(
                f"agent.{nested_key}"
                for nested_key in value.keys()
                if nested_key in DOMAIN_PROTECTED_AGENT_KEYS
            )
            sanitized[key] = safe_agent
            continue
        if key == "style" and isinstance(value, dict):
            safe_style = {
                nested_key: nested_value
                for nested_key, nested_value in value.items()
                if nested_key not in DOMAIN_PROTECTED_STYLE_KEYS
            }
            stripped_keys.extend(
                f"style.{nested_key}"
                for nested_key in value.keys()
                if nested_key in DOMAIN_PROTECTED_STYLE_KEYS
            )
            sanitized[key] = safe_style
            continue
        sanitized[key] = value

    if stripped_keys:
        logger.info(
            "PromptLoader: stripped identity-sensitive keys from domain overlay: %s",
            ", ".join(stripped_keys),
        )
    return sanitized


def sanitize_contextual_overlay_text(text: str) -> str:
    """Strip obvious attempts to rename or redefine Wiii in contextual overlays."""
    kept_lines: list[str] = []
    stripped = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            kept_lines.append(raw_line)
            continue
        normalized_line = normalize_overlay_line(line)
        if any(pattern.search(line) for pattern in IDENTITY_OVERRIDE_LINE_PATTERNS) or any(
            pattern.search(normalized_line) for pattern in IDENTITY_OVERRIDE_NORMALIZED_PATTERNS
        ):
            stripped += 1
            continue
        kept_lines.append(raw_line)

    cleaned = "\n".join(kept_lines).strip()
    if stripped:
        logger.info(
            "PromptLoader: stripped %d identity-override line(s) from contextual overlay",
            stripped,
        )
    return cleaned


def merge_with_base(
    agent_config: Dict[str, Any],
    base_config: Dict[str, Any],
    *,
    preserve_identity: bool = False,
) -> Dict[str, Any]:
    """Merge agent config with base config using overlay inheritance."""
    source_config = (
        sanitize_domain_overlay(agent_config)
        if preserve_identity
        else agent_config
    )
    merged = base_config.copy()

    for key, value in source_config.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return merged
