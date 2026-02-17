"""
Tests for app.channels — Channel Adapter base, ChannelMessage, registry.

Sprint 12: Multi-Channel Gateway.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.channels.base import ChannelMessage, ChannelAdapter, to_chat_request
from app.channels.registry import ChannelRegistry


# ============================================================================
# ChannelMessage Tests
# ============================================================================


class TestChannelMessage:
    """Test the normalized ChannelMessage dataclass."""

    def test_basic_creation(self):
        msg = ChannelMessage(
            text="Hello",
            sender_id="user-1",
            channel_id="ch-1",
            channel_type="test",
        )
        assert msg.text == "Hello"
        assert msg.sender_id == "user-1"
        assert msg.channel_id == "ch-1"
        assert msg.channel_type == "test"

    def test_auto_timestamp(self):
        """Timestamp is auto-set to UTC now if not provided."""
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t"
        )
        assert msg.timestamp is not None
        assert isinstance(msg.timestamp, datetime)

    def test_custom_timestamp(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            timestamp=ts,
        )
        assert msg.timestamp == ts

    def test_default_metadata_is_empty_dict(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t"
        )
        assert msg.metadata == {}

    def test_metadata_preserved(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"role": "admin", "extra": 42},
        )
        assert msg.metadata["role"] == "admin"
        assert msg.metadata["extra"] == 42


# ============================================================================
# ChannelAdapter ABC Tests
# ============================================================================


class TestChannelAdapterABC:
    """Test the abstract base class."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ChannelAdapter()

    def test_requires_channel_type(self):
        class Incomplete(ChannelAdapter):
            def parse_incoming(self, raw):
                return None

            def format_outgoing(self, response):
                return None

        with pytest.raises(TypeError):
            Incomplete()

    def test_requires_parse_incoming(self):
        class Incomplete(ChannelAdapter):
            @property
            def channel_type(self):
                return "test"

            def format_outgoing(self, response):
                return None

        with pytest.raises(TypeError):
            Incomplete()

    def test_requires_format_outgoing(self):
        class Incomplete(ChannelAdapter):
            @property
            def channel_type(self):
                return "test"

            def parse_incoming(self, raw):
                return None

        with pytest.raises(TypeError):
            Incomplete()

    def test_complete_implementation(self):
        class TestAdapter(ChannelAdapter):
            @property
            def channel_type(self):
                return "test"

            def parse_incoming(self, raw):
                return ChannelMessage(
                    text=raw, sender_id="u", channel_id="c", channel_type="test"
                )

            def format_outgoing(self, response):
                return str(response)

        adapter = TestAdapter()
        assert adapter.channel_type == "test"
        msg = adapter.parse_incoming("hello")
        assert msg.text == "hello"

    def test_repr(self):
        class TestAdapter(ChannelAdapter):
            @property
            def channel_type(self):
                return "mytest"

            def parse_incoming(self, raw):
                return None

            def format_outgoing(self, response):
                return None

        adapter = TestAdapter()
        r = repr(adapter)
        assert "TestAdapter" in r
        assert "mytest" in r


# ============================================================================
# to_chat_request Tests
# ============================================================================


class TestToChatRequest:
    """Test ChannelMessage → ChatRequest conversion."""

    def test_basic_conversion(self):
        msg = ChannelMessage(
            text="Xin chào",
            sender_id="user-123",
            channel_id="ws:session-1",
            channel_type="websocket",
        )
        req = to_chat_request(msg)
        assert req.user_id == "user-123"
        assert req.message == "Xin chào"
        assert req.session_id == "ws:session-1"

    def test_default_role_student(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t"
        )
        req = to_chat_request(msg)
        assert req.role.value == "student"

    def test_custom_role_from_metadata(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"role": "admin"},
        )
        req = to_chat_request(msg)
        assert req.role.value == "admin"

    def test_invalid_role_falls_back_to_student(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"role": "super_admin_xyz"},
        )
        req = to_chat_request(msg)
        assert req.role.value == "student"

    def test_session_id_from_metadata(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"session_id": "my-session"},
        )
        req = to_chat_request(msg)
        assert req.session_id == "my-session"

    def test_thread_id_from_metadata(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"thread_id": "thread-xyz"},
        )
        req = to_chat_request(msg)
        assert req.thread_id == "thread-xyz"

    def test_domain_id_from_metadata(self):
        msg = ChannelMessage(
            text="test", sender_id="u", channel_id="c", channel_type="t",
            metadata={"domain_id": "maritime"},
        )
        req = to_chat_request(msg)
        assert req.domain_id == "maritime"


# ============================================================================
# ChannelRegistry Tests
# ============================================================================


class TestChannelRegistry:
    """Test the singleton channel registry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        ChannelRegistry.reset()
        yield
        ChannelRegistry.reset()

    def _make_adapter(self, channel_type: str) -> ChannelAdapter:
        """Create a mock adapter."""
        adapter = MagicMock(spec=ChannelAdapter)
        adapter.channel_type = channel_type
        return adapter

    def test_singleton(self):
        r1 = ChannelRegistry()
        r2 = ChannelRegistry()
        assert r1 is r2

    def test_register_and_get(self):
        registry = ChannelRegistry()
        adapter = self._make_adapter("test")
        registry.register(adapter)
        assert registry.get("test") is adapter

    def test_get_nonexistent_returns_none(self):
        registry = ChannelRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        registry = ChannelRegistry()
        registry.register(self._make_adapter("ws"))
        registry.register(self._make_adapter("tg"))
        assert sorted(registry.list_all()) == ["tg", "ws"]

    def test_is_registered(self):
        registry = ChannelRegistry()
        registry.register(self._make_adapter("test"))
        assert registry.is_registered("test") is True
        assert registry.is_registered("other") is False

    def test_unregister(self):
        registry = ChannelRegistry()
        registry.register(self._make_adapter("test"))
        assert registry.unregister("test") is True
        assert registry.get("test") is None

    def test_unregister_nonexistent(self):
        registry = ChannelRegistry()
        assert registry.unregister("none") is False

    def test_clear(self):
        registry = ChannelRegistry()
        registry.register(self._make_adapter("a"))
        registry.register(self._make_adapter("b"))
        registry.clear()
        assert registry.list_all() == []

    def test_overwrite_warning(self):
        registry = ChannelRegistry()
        registry.register(self._make_adapter("test"))
        new_adapter = self._make_adapter("test")
        registry.register(new_adapter)
        assert registry.get("test") is new_adapter
