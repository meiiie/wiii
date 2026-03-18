"""Incremental parser for tool_call_chunks args — extracts code_html content in real-time.

Used during astream() to forward code_html tokens to the frontend as they arrive
from the LLM, enabling real-time code streaming (like Claude Artifacts).

The parser is a character-level state machine that scans for the "code_html" key
in the JSON args string and forwards its value character-by-character, handling
JSON escape sequences.
"""

from __future__ import annotations


class ToolCallCodeHtmlStreamer:
    """Parse incremental tool_call_chunks args and yield code_html content."""

    def __init__(self) -> None:
        self._raw_args = ""
        self._code_html = ""
        self._pending_delta = ""
        self._in_code_html_value = False
        self._code_html_complete = False
        self._escape_next = False
        self._found_key = False
        self._key_search_buffer = ""

    def feed(self, args_fragment: str) -> str:
        """Feed a raw args JSON fragment. Return new code_html content (delta).

        Call this for each tool_call_chunk.args string. Returns only the NEW
        characters of the code_html value since the last call.
        """
        if not args_fragment or self._code_html_complete:
            return ""

        self._raw_args += args_fragment
        delta = ""

        for ch in args_fragment:
            if self._code_html_complete:
                break

            if self._in_code_html_value:
                if self._escape_next:
                    decoded = _unescape_char(ch)
                    self._code_html += decoded
                    delta += decoded
                    self._escape_next = False
                elif ch == "\\":
                    self._escape_next = True
                elif ch == '"':
                    self._code_html_complete = True
                else:
                    self._code_html += ch
                    delta += ch
            elif not self._found_key:
                self._key_search_buffer += ch
                if self._key_search_buffer.endswith('"code_html"'):
                    self._found_key = True
                    self._key_search_buffer = ""
                elif len(self._key_search_buffer) > 200:
                    self._key_search_buffer = self._key_search_buffer[-20:]
            else:
                if ch == '"' and not self._in_code_html_value:
                    self._in_code_html_value = True

        self._pending_delta += delta
        result = self._pending_delta
        self._pending_delta = ""
        return result

    @property
    def is_code_html_started(self) -> bool:
        return self._in_code_html_value or self._code_html_complete

    @property
    def is_code_html_complete(self) -> bool:
        return self._code_html_complete

    @property
    def full_code_html(self) -> str:
        return self._code_html

    @property
    def full_args_json(self) -> str:
        return self._raw_args


def _unescape_char(ch: str) -> str:
    """Decode a JSON escape character after backslash."""
    return {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "b": "\b",
        "f": "\f",
    }.get(ch, ch)
