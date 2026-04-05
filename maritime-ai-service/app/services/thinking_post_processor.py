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
    VISIBLE_THINKING_BLOCK_PATTERN = re.compile(
        r"^\s*\*{1,2}\s*visible thinking\s*:\s*(?P<thinking>.*?)\s*\*{1,2}\s*(?P<answer>.+)$",
        re.DOTALL | re.IGNORECASE,
    )
    VISIBLE_THINKING_WRAPPED_LABEL_PATTERN = re.compile(
        r"^\s*\(\s*(?:visible thinking|suy nghĩ|suy nghi|suy nghĩ của wiii|suy nghi cua wiii"
        r"|suy nghĩ của wiii về [^:*]+|suy nghi cua wiii ve [^:*]+|nghĩ thầm|nghi tham)\s*:\s*(?P<body>.+?)\)\s*(?P<tail>.*)$",
        re.DOTALL | re.IGNORECASE,
    )
    VISIBLE_THINKING_LABEL_PREFIX_PATTERN = re.compile(
        r"^\s*\*{1,2}\s*(?:visible thinking|suy nghĩ|suy nghi|suy nghĩ của wiii|suy nghi cua wiii"
        r"|suy nghĩ của wiii về [^:*]+|suy nghi cua wiii ve [^:*]+"
        r"|nghĩ thầm|nghi tham)\s*:\s*\*{0,2}\s*",
        re.IGNORECASE,
    )

    @staticmethod
    def _should_surface_native_thinking(thinking: str) -> bool:
        clean = str(thinking or "").strip()
        if len(clean) <= 10:
            return False
        lowered = clean.lower()
        if any(token in lowered for token in ("mình", "người", "câu này", "bây giờ", "việt", "tiếng", "không", "để ")):
            return True
        vietnamese_chars = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
        return any(ch in vietnamese_chars for ch in lowered)

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

        text_result = self._extract_from_text(combined_text)
        if text_result.thinking:
            return text_result

        # PRIMARY for Gemini native blocks only when the thought itself is already
        # in a user-facing language we are willing to surface.
        if native_thinking_parts:
            native_thinking = '\n'.join(native_thinking_parts).strip()
            if self._should_surface_native_thinking(native_thinking):
                clean_text = self.THINKING_PATTERN.sub('', combined_text).strip()
                clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
                return ThinkingResult(
                    text=clean_text,
                    thinking=native_thinking,
                    source='gemini_native'
                )

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

        visible_match = self.VISIBLE_THINKING_BLOCK_PATTERN.match(text)
        if visible_match:
            thinking = visible_match.group("thinking").strip()
            clean_text = visible_match.group("answer").strip()
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
            if thinking and len(clean_text) > 20:
                return ThinkingResult(
                    text=clean_text,
                    thinking=thinking,
                    source='visible_thinking_block',
                )

        wrapped_label_match = self.VISIBLE_THINKING_WRAPPED_LABEL_PATTERN.match(text)
        if wrapped_label_match:
            body = wrapped_label_match.group("body").strip()
            tail = wrapped_label_match.group("tail").strip()
            clean_text = body if not tail else f"{body}\n\n{tail}"
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
            return ThinkingResult(
                text=clean_text,
                thinking=None,
                source='visible_thinking_wrapped_label',
            )

        preserve_emphasis = bool(
            re.match(
                r"^\s*\*{1,2}\s*(?:nghĩ thầm|nghi tham|suy nghĩ|suy nghi)\s*:\s*",
                text,
                re.IGNORECASE,
            )
        )
        label_removed = self.VISIBLE_THINKING_LABEL_PREFIX_PATTERN.sub("", text, count=1).strip()
        if label_removed != text.strip():
            if preserve_emphasis and label_removed and not label_removed.startswith("*"):
                label_removed = f"*{label_removed}"
            label_removed = re.sub(r"^\*+\s*", "", label_removed).strip()
            if preserve_emphasis:
                label_removed = "*" + label_removed.lstrip("*")
            else:
                label_removed = re.sub(r"\s+\*+$", "", label_removed).strip()
            label_removed = re.sub(r'\n{3,}', '\n\n', label_removed)
            return ThinkingResult(
                text=label_removed,
                thinking=None,
                source='visible_thinking_label',
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
