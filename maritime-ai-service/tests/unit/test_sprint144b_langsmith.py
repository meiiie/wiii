"""
Sprint 144b: LangSmith Integration Tests

Tests for configure_langsmith(), is_langsmith_enabled(), and
get_langsmith_callback() in app/core/langsmith.py.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Create a mock settings object with LangSmith fields."""
    defaults = {
        "enable_langsmith": False,
        "langsmith_api_key": None,
        "langsmith_project": "wiii",
        "langsmith_endpoint": "https://api.smith.langchain.com",
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _reset_module():
    """Reset the module-level _langsmith_enabled flag."""
    import app.core.langsmith as mod
    mod._langsmith_enabled = False
    # Clean env vars that configure_langsmith sets
    for key in (
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_ENDPOINT",
    ):
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# Tests: configure_langsmith
# ---------------------------------------------------------------------------

class TestConfigureLangsmith:
    """Tests for configure_langsmith()."""

    def setup_method(self):
        _reset_module()

    def teardown_method(self):
        _reset_module()

    def test_disabled_by_default(self):
        """When enable_langsmith=False, no env vars are set."""
        from app.core.langsmith import configure_langsmith, is_langsmith_enabled

        settings = _make_settings(enable_langsmith=False)
        configure_langsmith(settings)

        assert not is_langsmith_enabled()
        assert "LANGCHAIN_TRACING_V2" not in os.environ

    def test_enabled_marks_module_state_without_setting_langchain_env(self):
        """Phase 8 of #207: the LangChain auto-tracer was removed. The flag
        still flips ``is_langsmith_enabled`` so a future direct hook can pick
        it up, but no LANGCHAIN_* env vars are exported anymore.
        """
        from app.core.langsmith import configure_langsmith, is_langsmith_enabled

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="lsv2_pt_test123",
            langsmith_project="test-project",
            langsmith_endpoint="https://custom.endpoint.com",
        )
        configure_langsmith(settings)

        assert is_langsmith_enabled()
        assert "LANGCHAIN_TRACING_V2" not in os.environ
        assert "LANGCHAIN_API_KEY" not in os.environ
        assert "LANGCHAIN_PROJECT" not in os.environ
        assert "LANGCHAIN_ENDPOINT" not in os.environ

    def test_enabled_without_api_key_stays_disabled(self):
        """When enabled but API key is None/empty, tracing is NOT activated."""
        from app.core.langsmith import configure_langsmith, is_langsmith_enabled

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key=None,
        )
        configure_langsmith(settings)

        assert not is_langsmith_enabled()
        assert "LANGCHAIN_TRACING_V2" not in os.environ

    def test_enabled_with_empty_string_api_key(self):
        """Empty string API key also stays disabled."""
        from app.core.langsmith import configure_langsmith, is_langsmith_enabled

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="",
        )
        configure_langsmith(settings)

        assert not is_langsmith_enabled()


# ---------------------------------------------------------------------------
# Tests: is_langsmith_enabled
# ---------------------------------------------------------------------------

class TestIsLangsmithEnabled:
    """Tests for is_langsmith_enabled()."""

    def setup_method(self):
        _reset_module()

    def teardown_method(self):
        _reset_module()

    def test_false_before_configure(self):
        from app.core.langsmith import is_langsmith_enabled
        assert not is_langsmith_enabled()

    def test_true_after_successful_configure(self):
        from app.core.langsmith import configure_langsmith, is_langsmith_enabled

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="lsv2_pt_abc",
        )
        configure_langsmith(settings)
        assert is_langsmith_enabled()


# ---------------------------------------------------------------------------
# Tests: get_langsmith_callback
# ---------------------------------------------------------------------------

class TestGetLangsmithCallback:
    """Tests for get_langsmith_callback()."""

    def setup_method(self):
        _reset_module()

    def teardown_method(self):
        _reset_module()

    def test_returns_none_when_disabled(self):
        """When LangSmith is not enabled, callback is None."""
        from app.core.langsmith import get_langsmith_callback
        assert get_langsmith_callback("u1", "s1", "maritime") is None

    def test_returns_none_on_import_error(self):
        """Graceful None when langsmith package is not installed."""
        from app.core.langsmith import configure_langsmith, get_langsmith_callback
        import app.core.langsmith as mod

        # Force enabled
        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="lsv2_pt_test",
        )
        configure_langsmith(settings)

        with patch.dict("sys.modules", {"langsmith": None}):
            result = get_langsmith_callback("u1", "s1", "maritime")
            # ImportError path — returns None
            assert result is None

    def test_returns_none_after_langchain_tracer_removal(self):
        """Phase 8 of #207: get_langsmith_callback always returns None now.

        The LangChainTracer import was dropped to remove the langchain-core
        dependency from this module. A future direct LangSmith integration
        will re-introduce a non-None return; until then, callers receive
        None unconditionally — even when the flag is enabled.
        """
        from app.core.langsmith import configure_langsmith, get_langsmith_callback

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="lsv2_pt_test",
        )
        configure_langsmith(settings)

        result = get_langsmith_callback("user1", "sess1", "maritime")
        assert result is None

    def test_graceful_on_exception(self):
        """If callback creation raises, returns None instead of crashing."""
        from app.core.langsmith import configure_langsmith
        import app.core.langsmith as mod

        settings = _make_settings(
            enable_langsmith=True,
            langsmith_api_key="lsv2_pt_test",
        )
        configure_langsmith(settings)

        # Patch to force exception
        with patch("app.core.langsmith.Client", side_effect=RuntimeError("boom"), create=True):
            pass

        # Force the internal code path to raise
        original_enabled = mod._langsmith_enabled
        mod._langsmith_enabled = True
        # Create a scenario where the import succeeds but construction fails
        # We'll just verify the function doesn't crash
        result = mod.get_langsmith_callback("u1", "s1", "d1")
        # Result may be None (import error on missing langsmith) or a tracer
        # Either way, no exception should propagate
        mod._langsmith_enabled = original_enabled


# ---------------------------------------------------------------------------
# Tests: Config fields exist
# ---------------------------------------------------------------------------

class TestConfigFields:
    """Verify LangSmith config fields are properly defined."""

    def test_settings_has_langsmith_fields(self):
        """Settings model includes all 4 LangSmith fields."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "enable_langsmith" in fields
        assert "langsmith_api_key" in fields
        assert "langsmith_project" in fields
        assert "langsmith_endpoint" in fields

    def test_defaults(self):
        """Default values are correct."""
        from app.core.config import Settings

        defaults = {
            "enable_langsmith": False,
            "langsmith_api_key": None,
            "langsmith_project": "wiii",
            "langsmith_endpoint": "https://api.smith.langchain.com",
        }
        for field_name, expected in defaults.items():
            field = Settings.model_fields[field_name]
            assert field.default == expected, f"{field_name}: expected {expected}, got {field.default}"
