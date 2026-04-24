"""Sprint 135: Soul Emotion streaming integration tests.

Uses sys.modules pre-population to avoid circular import through
app.engine.multi_agent.__init__ → graph → services → chat_service → graph.
"""
import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# Pre-populate to break circular import chain
if "app.services.chat_service" not in sys.modules:
    _stub = types.ModuleType("app.services.chat_service")
    _stub.ChatService = MagicMock  # type: ignore
    _stub.get_chat_service = MagicMock  # type: ignore
    sys.modules["app.services.chat_service"] = _stub

# Now safe to import stream_utils directly (bypassing __init__.py still)
from app.engine.multi_agent.stream_utils import (
    StreamEventType,
    create_emotion_event,
)


class TestStreamEventTypeEmotion:
    """Tests for EMOTION event type."""

    def test_emotion_type_exists(self):
        assert hasattr(StreamEventType, "EMOTION")
        assert StreamEventType.EMOTION == "emotion"


class TestCreateEmotionEvent:
    """Tests for create_emotion_event factory."""

    @pytest.mark.asyncio
    async def test_basic_emotion_event(self):
        event = await create_emotion_event(
            mood="warm",
            face={"blush": 0.3, "mouthCurve": 0.5},
            intensity=0.8,
        )
        assert event.type == "emotion"
        assert event.content["mood"] == "warm"
        assert event.content["face"]["blush"] == 0.3
        assert event.content["intensity"] == 0.8

    @pytest.mark.asyncio
    async def test_emotion_event_empty_face(self):
        event = await create_emotion_event(mood="neutral", face={}, intensity=0.5)
        assert event.type == "emotion"
        assert event.content["face"] == {}

    @pytest.mark.asyncio
    async def test_emotion_event_to_dict(self):
        event = await create_emotion_event(
            mood="excited",
            face={"eyeShape": 0.3},
            intensity=0.9,
        )
        d = event.to_dict()
        assert d["type"] == "emotion"
        assert d["content"]["mood"] == "excited"


class TestGraphStreamingEmotionIntegration:
    """Tests for soul emotion in graph_streaming."""

    @pytest.mark.asyncio
    async def test_no_tag_passthrough(self):
        """When text has no tag, _extract_and_stream_emotion_then_answer passes through."""
        with patch("app.engine.multi_agent.graph_stream_surface.settings") as mock_settings:
            mock_settings.enable_soul_emotion = False
            # Lazy import to avoid circular at collection time
            from app.engine.multi_agent.graph_streaming import _extract_and_stream_emotion_then_answer

            events = []
            async for event in _extract_and_stream_emotion_then_answer("Hello world", False):
                events.append(event)
            # Should have answer events, no emotion event
            assert all(e.type == "answer" for e in events)

    @pytest.mark.asyncio
    async def test_emotion_extracted_from_full_text(self):
        """When text has a soul tag, emotion event is yielded first."""
        with patch("app.engine.multi_agent.graph_stream_surface.settings") as mock_settings:
            mock_settings.enable_soul_emotion = True
            from app.engine.multi_agent.graph_streaming import _extract_and_stream_emotion_then_answer

            text = '<!--WIII_SOUL:{"mood":"warm","face":{"blush":0.3},"intensity":0.8}-->Hello'
            events = []
            async for event in _extract_and_stream_emotion_then_answer(text, False):
                events.append(event)

            # First event should be emotion
            assert events[0].type == "emotion"
            assert events[0].content["mood"] == "warm"
            # Remaining should be answer events (clean text)
            answer_events = [e for e in events if e.type == "answer"]
            answer_text = "".join(e.content for e in answer_events)
            assert "Hello" in answer_text
            assert "WIII_SOUL" not in answer_text
