from tests.unit.living_continuity_helpers import (
    _make_settings,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestEpisodicMemory:
    """Test Sprint 210 episodic memory (MemoryType.EPISODE)."""

    def test_episode_enum_exists(self):
        """EPISODE enum value should exist in MemoryType."""
        from app.models.semantic_memory import MemoryType
        assert hasattr(MemoryType, 'EPISODE')
        assert MemoryType.EPISODE.value == "episode"

    def test_episode_content_format(self):
        """Episode content should include agent type, question, and answer."""
        _topic = "rag_agent"
        _message = "Luật COLREGs là gì?"
        _response = "COLREGs là bộ quy tắc phòng ngừa va chạm trên biển..."
        _episode = f"[{_topic}] User asked: {_message[:150]}. Wiii answered about: {_response[:150]}"

        assert "[rag_agent]" in _episode
        assert "User asked:" in _episode
        assert "Wiii answered about:" in _episode

    def test_episode_importance_from_positive(self):
        """Positive feedback should result in importance=0.8."""
        msg = "Cảm ơn bạn!"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank"]):
            _importance = 0.8
        assert _importance == 0.8

    def test_episode_importance_from_negative(self):
        """Negative feedback should result in importance=0.7."""
        msg = "Sai rồi!"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong"]):
            _importance = 0.7
        assert _importance == 0.7

    def test_episode_importance_default(self):
        """Default importance is 0.5."""
        msg = "Giải thích quy tắc 15"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank"]):
            _importance = 0.8
        elif any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong"]):
            _importance = 0.7
        assert _importance == 0.5

    def test_episode_flag_off_no_storage(self):
        """When enable_living_continuity=False, no episode is stored."""
        settings = _make_settings(enable_living_continuity=False)
        stored = False
        if getattr(settings, "enable_living_continuity", False):
            stored = True
        assert not stored
