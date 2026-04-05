"""Thinking extraction helpers for output processing."""

from typing import Any, Optional


def extract_thinking_from_response(content: Any) -> tuple[str, Optional[str]]:
    """
    Extract visible text and model reasoning from a response payload.

    Kept as a standalone helper so the public output processor module can stay
    as a thin compatibility facade.
    """
    from app.services.thinking_post_processor import get_thinking_processor

    return get_thinking_processor().process(content)
