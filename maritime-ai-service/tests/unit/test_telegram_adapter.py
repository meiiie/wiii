"""
Tests for Telegram Channel Adapter.

Sprint 12: Multi-Channel Gateway.
Tests Telegram Update parsing, response formatting, edge cases.
"""

import pytest
from unittest.mock import MagicMock

from app.channels.telegram_adapter import TelegramAdapter
from app.channels.base import ChannelMessage


class TestTelegramAdapter:
    """Test the Telegram channel adapter."""

    def setup_method(self):
        self.adapter = TelegramAdapter()

    def test_channel_type(self):
        assert self.adapter.channel_type == "telegram"

    # --- parse_incoming ---

    def test_parse_basic_message(self):
        update = {
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 42,
                    "first_name": "Minh",
                    "last_name": "Nguyen",
                    "username": "minh_ng",
                },
                "chat": {
                    "id": 42,
                    "type": "private",
                },
                "text": "Giải thích COLREGs Rule 15",
            }
        }
        msg = self.adapter.parse_incoming(update)
        assert msg.text == "Giải thích COLREGs Rule 15"
        assert msg.sender_id == "42"
        assert msg.channel_type == "telegram"
        assert msg.channel_id == "tg:42"
        assert msg.metadata["sender_name"] == "Minh Nguyen"
        assert msg.metadata["sender_username"] == "minh_ng"
        assert msg.metadata["chat_type"] == "private"

    def test_parse_first_name_only(self):
        update = {
            "message": {
                "message_id": 2,
                "from": {"id": 100, "first_name": "Anh"},
                "chat": {"id": 100, "type": "private"},
                "text": "Hello",
            }
        }
        msg = self.adapter.parse_incoming(update)
        assert msg.metadata["sender_name"] == "Anh"

    def test_parse_edited_message(self):
        """Should also handle edited_message updates."""
        update = {
            "update_id": 789,
            "edited_message": {
                "message_id": 5,
                "from": {"id": 42, "first_name": "Test"},
                "chat": {"id": 42, "type": "private"},
                "text": "Edited question",
            }
        }
        msg = self.adapter.parse_incoming(update)
        assert msg.text == "Edited question"

    def test_parse_no_message_raises(self):
        with pytest.raises(ValueError, match="No message"):
            self.adapter.parse_incoming({"update_id": 1})

    def test_parse_no_text_raises(self):
        update = {
            "message": {
                "message_id": 3,
                "from": {"id": 42, "first_name": "Test"},
                "chat": {"id": 42, "type": "private"},
                # No text field
            }
        }
        with pytest.raises(ValueError, match="No text"):
            self.adapter.parse_incoming(update)

    def test_parse_non_dict_raises(self):
        with pytest.raises(ValueError, match="Expected dict"):
            self.adapter.parse_incoming("not a dict")

    def test_parse_group_message(self):
        update = {
            "message": {
                "message_id": 10,
                "from": {"id": 42, "first_name": "User"},
                "chat": {"id": -100123, "type": "group"},
                "text": "Group question",
            }
        }
        msg = self.adapter.parse_incoming(update)
        assert msg.metadata["chat_type"] == "group"
        assert msg.channel_id == "tg:-100123"

    def test_parse_update_id_in_metadata(self):
        update = {
            "update_id": 999,
            "message": {
                "message_id": 1,
                "from": {"id": 1},
                "chat": {"id": 1, "type": "private"},
                "text": "hi",
            }
        }
        msg = self.adapter.parse_incoming(update)
        assert msg.metadata["update_id"] == 999
        assert msg.metadata["message_id"] == 1

    # --- format_outgoing ---

    def test_format_outgoing_basic(self):
        response = {
            "answer": "Đây là câu trả lời",
            "chat_id": "42",
        }
        result = self.adapter.format_outgoing(response)
        assert result["chat_id"] == "42"
        assert result["text"] == "Đây là câu trả lời"
        assert result["parse_mode"] == "Markdown"

    def test_format_outgoing_with_sources(self):
        response = {
            "answer": "Answer",
            "chat_id": "42",
            "sources": [
                {"title": "COLREGs Rule 15"},
                {"title": "SOLAS Chapter V"},
            ],
        }
        result = self.adapter.format_outgoing(response)
        assert "COLREGs Rule 15" in result["text"]
        assert "SOLAS Chapter V" in result["text"]

    def test_format_outgoing_with_string_sources(self):
        response = {
            "answer": "Answer",
            "chat_id": "42",
            "sources": ["Source 1", "Source 2"],
        }
        result = self.adapter.format_outgoing(response)
        assert "Source 1" in result["text"]

    def test_format_outgoing_no_sources(self):
        response = {"answer": "Just answer", "chat_id": "42"}
        result = self.adapter.format_outgoing(response)
        assert "Nguồn tham khảo" not in result["text"]

    def test_format_typing_action(self):
        result = self.adapter.format_typing_action("42")
        assert result["chat_id"] == "42"
        assert result["action"] == "typing"
