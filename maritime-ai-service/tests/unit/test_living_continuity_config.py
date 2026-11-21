from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestConfigFlag:
    """Test enable_living_continuity config."""

    def test_flag_exists_as_bool(self):
        """Flag exists and is a boolean (default False, but env can override)."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert isinstance(s.enable_living_continuity, bool)

    def test_flag_can_be_enabled(self):
        """Flag can be set to True."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_living_continuity=True,
        )
        assert s.enable_living_continuity is True

    def test_flag_requires_living_agent_conceptually(self):
        """enable_living_continuity is meaningless without enable_living_agent,
        but should not error — it's just a no-op."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_living_continuity=True,
            enable_living_agent=False,
        )
        assert s.enable_living_continuity is True
        assert s.enable_living_agent is False
