"""Singleton access helpers for PromptLoader."""

from __future__ import annotations

def get_prompt_loader():
    """Get or create the shared PromptLoader instance."""
    from app.prompts.prompt_loader import get_prompt_loader as _get_prompt_loader

    return _get_prompt_loader()
