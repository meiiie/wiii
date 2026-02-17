"""
Tests for SSE reconnection support — Sprint 68.

Tests format_sse() backward compat, SSEEventBuffer, V3 event IDs, retry field.
"""

import json
import pytest

from app.api.v1.chat_stream import format_sse


# =============================================================================
# format_sse backward compatibility
# =============================================================================


class TestFormatSSE:
    """Test format_sse() with and without event_id."""

    def test_without_event_id(self):
        """Backward compat: no event_id produces same format as before."""
        result = format_sse("answer", {"content": "hello"})
        assert result.startswith("event: answer\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        # Should NOT contain id: line
        assert "id:" not in result

    def test_with_event_id(self):
        """event_id adds id: line before event."""
        result = format_sse("answer", {"content": "hello"}, event_id=42)
        assert result.startswith("id: 42\n")
        assert "event: answer\n" in result
        assert result.endswith("\n\n")

    def test_json_content_preserved(self):
        """JSON data is properly serialized."""
        data = {"content": "xin chào", "step": "routing"}
        result = format_sse("status", data, event_id=1)
        # Extract data line
        for line in result.split("\n"):
            if line.startswith("data: "):
                parsed = json.loads(line[6:])
                assert parsed["content"] == "xin chào"
                assert parsed["step"] == "routing"

    def test_ensure_ascii_false(self):
        """Vietnamese characters are not escaped."""
        result = format_sse("answer", {"content": "Đây là câu trả lời"})
        assert "Đây là câu trả lời" in result
        assert "\\u" not in result

    def test_event_id_zero(self):
        """event_id=0 is valid (included in output)."""
        result = format_sse("done", {"status": "complete"}, event_id=0)
        assert "id: 0\n" in result
