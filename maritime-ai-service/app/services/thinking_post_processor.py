"""
Centralized Thinking Post-Processor (v9 — Gemini Native First)

SOTA Pattern: API-level thinking separation (Anthropic/OpenAI/Gemini 2026)

Priority:
1. Gemini native format {'type': 'thinking', 'thinking': '...'}  (PRIMARY)
2. Text-based <thinking>...</thinking> tags                       (FALLBACK)

Rationale: Native API-level separation is more robust than regex parsing.
Regex is kept as fallback for non-Gemini providers (Ollama, OpenAI).

Usage:
    from app.services.thinking_post_processor import get_thinking_processor

    processor = get_thinking_processor()
    text, thinking = processor.process(response.content)
"""

import re
import logging
from typing import Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ThinkingResult:
    """Standardized thinking extraction result."""
    text: str                     # Main response content (cleaned)
    thinking: Optional[str]       # Extracted thinking
    source: str                   # 'gemini_native' | 'text_tags' | 'none'


class ThinkingPostProcessor:
    """
    Centralized thinking extraction and normalization.

    Priority (v9 — Gemini Native First):
    1. Gemini native format blocks (API-level separation — PREFERRED)
    2. Text-based <thinking>...</thinking> tags (fallback for non-Gemini)
    3. Plain text responses (no thinking)

    The native format is preferred because:
    - API-level separation is 100% reliable (no regex, no tag parsing)
    - No risk of LLM forgetting to use tags
    - Works with Gemini's encrypted thought signatures for multi-turn
    """

    THINKING_PATTERN = re.compile(
        r'<thinking>(.*?)</thinking>',
        re.DOTALL | re.IGNORECASE
    )

    def process(self, content: Any) -> Tuple[str, Optional[str]]:
        """
        Process LLM response and extract thinking content.

        Args:
            content: Raw LLM response content (str, list, or other)

        Returns:
            Tuple of (cleaned_text, thinking_content)
        """
        result = self._extract(content)

        if result.thinking:
            logger.debug(
                "[THINKING] Source: %s, Length: %d chars",
                result.source, len(result.thinking),
            )

        return result.text, result.thinking

    def _extract(self, content: Any) -> ThinkingResult:
        """
        Internal extraction logic.

        Priority: native blocks → text tags → plain text
        """
        # Case 1: List (Gemini native format) — check FIRST
        if isinstance(content, list):
            return self._extract_from_list(content)

        # Case 2: String — check for <thinking> tags (fallback)
        if isinstance(content, str):
            return self._extract_from_text(content)

        # Case 3: Unknown format — convert to string
        text = str(content)
        return self._extract_from_text(text)

    def _extract_from_list(self, blocks: list) -> ThinkingResult:
        """
        Extract from Gemini native format (PRIMARY path).

        Gemini response format when include_thoughts=True:
        [
            {'type': 'thinking', 'thinking': '...'},  # Reasoning trace
            {'type': 'text', 'text': '...'}            # Final answer
        ]
        """
        text_parts = []
        native_thinking_parts = []

        for block in blocks:
            if isinstance(block, dict):
                block_type = block.get('type', '')

                if block_type == 'thinking':
                    native_thinking = block.get('thinking', '')
                    if native_thinking:
                        native_thinking_parts.append(native_thinking)

                elif block_type == 'text':
                    text_content = block.get('text', '')
                    if text_content:
                        text_parts.append(text_content)

            elif isinstance(block, str):
                text_parts.append(block)

        combined_text = '\n'.join(text_parts)

        # PRIMARY: Use Gemini native thinking blocks
        if native_thinking_parts:
            native_thinking = '\n'.join(native_thinking_parts)
            if native_thinking.strip() and len(native_thinking.strip()) > 10:
                # Clean any leftover <thinking> tags from the answer text
                clean_text = self.THINKING_PATTERN.sub('', combined_text).strip()
                clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
                return ThinkingResult(
                    text=clean_text,
                    thinking=native_thinking,
                    source='gemini_native'
                )

        # FALLBACK: Check for <thinking> tags in text
        text_result = self._extract_from_text(combined_text)
        if text_result.thinking:
            return text_result

        return ThinkingResult(text=combined_text, thinking=None, source='none')

    def _extract_from_text(self, text: str) -> ThinkingResult:
        """
        Extract <thinking> tags from text (FALLBACK for non-Gemini providers).
        """
        match = self.THINKING_PATTERN.search(text)

        if match:
            thinking = match.group(1).strip()
            clean_text = self.THINKING_PATTERN.sub('', text).strip()
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

            return ThinkingResult(
                text=clean_text,
                thinking=thinking,
                source='text_tags'
            )

        return ThinkingResult(text=text, thinking=None, source='none')


# =============================================================================
# Convenience function (backward compat)
# =============================================================================

def extract_thinking_from_response(content: Any) -> Tuple[str, Optional[str]]:
    """Extract thinking from LLM response. Returns (text, thinking)."""
    return get_thinking_processor().process(content)


# =============================================================================
# SINGLETON
# =============================================================================

from app.core.singleton import singleton_factory
get_thinking_processor = singleton_factory(ThinkingPostProcessor)
