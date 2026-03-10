"""
Tests for Sprint 49: ThinkingPostProcessor coverage.

Tests thinking extraction including:
- ThinkingResult dataclass
- process() main entry point (string, list, other)
- _extract_from_text (with tags, without, case insensitive, multiline, multiple newlines cleanup)
- _extract_from_list (native thinking, text tags priority, string items, empty, mixed)
- Non-string/non-list fallback
- Singleton get_thinking_processor
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# ThinkingResult
# ============================================================================


class TestThinkingResult:
    """Test ThinkingResult dataclass."""

    def test_defaults(self):
        from app.services.thinking_post_processor import ThinkingResult
        r = ThinkingResult(text="Hello", thinking=None, source="none")
        assert r.text == "Hello"
        assert r.thinking is None
        assert r.source == "none"

    def test_with_thinking(self):
        from app.services.thinking_post_processor import ThinkingResult
        r = ThinkingResult(text="Answer", thinking="I thought about it", source="text_tags")
        assert r.thinking == "I thought about it"
        assert r.source == "text_tags"


# ============================================================================
# process — string input
# ============================================================================


class TestProcessString:
    """Test processing string content."""

    def test_plain_text(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        text, thinking = p.process("Hello world")
        assert text == "Hello world"
        assert thinking is None

    def test_with_thinking_tags(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        content = "<thinking>Analyzing the question</thinking>Rule 15 states..."
        text, thinking = p.process(content)
        assert thinking == "Analyzing the question"
        assert "<thinking>" not in text
        assert "Rule 15 states" in text

    def test_case_insensitive(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        content = "<THINKING>Analysis here</THINKING>The answer is 42"
        text, thinking = p.process(content)
        assert thinking == "Analysis here"
        assert "The answer is 42" in text

    def test_multiline_thinking(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        content = "<thinking>\nStep 1: Read\nStep 2: Analyze\n</thinking>\nFinal answer"
        text, thinking = p.process(content)
        assert "Step 1: Read" in thinking
        assert "Step 2: Analyze" in thinking
        assert "Final answer" in text

    def test_cleans_extra_newlines(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        content = "Before\n\n\n\n<thinking>Think</thinking>\n\n\n\nAfter"
        text, thinking = p.process(content)
        assert thinking == "Think"
        # Extra newlines collapsed to max \n\n
        assert "\n\n\n" not in text

    def test_empty_string(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        text, thinking = p.process("")
        assert text == ""
        assert thinking is None


# ============================================================================
# process — list input (Gemini native format)
# ============================================================================


class TestProcessList:
    """Test processing Gemini native format lists."""

    def test_native_thinking_blocks(self):
        """Native thinking in English is suppressed (only Vietnamese surfaces to UX)."""
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "thinking", "thinking": "I need to consider Rule 15"},
            {"type": "text", "text": "Rule 15 describes crossing situations"},
        ]
        text, thinking = p.process(blocks)
        # English-only native thinking is suppressed by _should_surface_native_thinking
        assert thinking is None
        assert text == "Rule 15 describes crossing situations"

    def test_text_tags_take_priority_over_native(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "thinking", "thinking": "English thinking (native)"},
            {"type": "text", "text": "<thinking>Vietnamese thinking</thinking>The answer"},
        ]
        text, thinking = p.process(blocks)
        # Text tags should win over native
        assert thinking == "Vietnamese thinking"
        assert "The answer" in text

    def test_string_items_in_list(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = ["Hello", "World"]
        text, thinking = p.process(blocks)
        assert "Hello" in text
        assert "World" in text
        assert thinking is None

    def test_empty_list(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        text, thinking = p.process([])
        assert text == ""
        assert thinking is None

    def test_mixed_string_and_dict(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            "Intro text",
            {"type": "text", "text": "Main content"},
        ]
        text, thinking = p.process(blocks)
        assert "Intro text" in text
        assert "Main content" in text
        assert thinking is None

    def test_multiple_thinking_blocks(self):
        """Multiple native thinking blocks in English are suppressed (non-Vietnamese)."""
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "thinking", "thinking": "Step 1"},
            {"type": "thinking", "thinking": "Step 2"},
            {"type": "text", "text": "Final answer"},
        ]
        text, thinking = p.process(blocks)
        # English-only native thinking is suppressed by _should_surface_native_thinking
        assert thinking is None
        assert text == "Final answer"

    def test_empty_thinking_ignored(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "Answer only"},
        ]
        text, thinking = p.process(blocks)
        assert text == "Answer only"
        assert thinking is None

    def test_empty_text_ignored(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "text", "text": ""},
            {"type": "text", "text": "Real content"},
        ]
        text, thinking = p.process(blocks)
        assert text == "Real content"

    def test_unknown_block_type(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        blocks = [
            {"type": "unknown", "data": "something"},
            {"type": "text", "text": "Visible text"},
        ]
        text, thinking = p.process(blocks)
        assert text == "Visible text"
        assert thinking is None


# ============================================================================
# process — other input types
# ============================================================================


class TestProcessOther:
    """Test non-string/non-list inputs."""

    def test_number(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        text, thinking = p.process(42)
        assert text == "42"
        assert thinking is None

    def test_none(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()
        text, thinking = p.process(None)
        assert text == "None"
        assert thinking is None

    def test_object_with_thinking_tag_in_str(self):
        from app.services.thinking_post_processor import ThinkingPostProcessor
        p = ThinkingPostProcessor()

        class FakeContent:
            def __str__(self):
                return "<thinking>Hidden</thinking>Visible"

        text, thinking = p.process(FakeContent())
        assert thinking == "Hidden"
        assert "Visible" in text


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton factory."""

    def test_get_thinking_processor(self):
        from app.services.thinking_post_processor import get_thinking_processor
        p1 = get_thinking_processor()
        p2 = get_thinking_processor()
        assert p1 is p2
