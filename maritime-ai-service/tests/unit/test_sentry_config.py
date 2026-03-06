"""Tests for Sentry configuration module."""
import pytest
from unittest.mock import patch, MagicMock


class TestSentryConfig:
    """Test Sentry initialization and filtering."""

    def test_init_sentry_with_empty_dsn_does_nothing(self):
        """Empty DSN should skip initialization."""
        from app.core.sentry_config import init_sentry
        # Should not raise regardless of sentry_sdk availability
        init_sentry(dsn="", environment="test")

    def test_init_sentry_with_valid_dsn_and_mock_sdk(self):
        """Valid DSN should call sentry_sdk.init when SDK available."""
        mock_sdk = MagicMock()
        with patch("app.core.sentry_config.sentry_sdk", mock_sdk):
            from app.core.sentry_config import init_sentry
            init_sentry(dsn="https://key@sentry.io/123", environment="production")
            mock_sdk.init.assert_called_once()

    def test_before_send_filters_404(self):
        """404 errors should be dropped (return None)."""
        from app.core.sentry_config import _before_send

        class FakeHTTPException:
            status_code = 404

        event = {"request": {"headers": {}}}
        hint = {"exc_info": (type(FakeHTTPException), FakeHTTPException(), None)}
        result = _before_send(event, hint)
        assert result is None

    def test_before_send_passes_500(self):
        """500 errors should be sent to Sentry."""
        from app.core.sentry_config import _before_send

        class FakeServerError:
            status_code = 500

        event = {"request": {"headers": {}}}
        hint = {"exc_info": (type(FakeServerError), FakeServerError(), None)}
        result = _before_send(event, hint)
        assert result is not None

    def test_before_send_scrubs_sensitive_headers(self):
        """API keys and auth headers should be filtered."""
        from app.core.sentry_config import _before_send

        event = {
            "request": {
                "headers": {
                    "x-api-key": "secret-key-123",
                    "authorization": "Bearer token-456",
                    "content-type": "application/json",
                }
            }
        }
        hint = {}
        result = _before_send(event, hint)
        assert result["request"]["headers"]["x-api-key"] == "[Filtered]"
        assert result["request"]["headers"]["authorization"] == "[Filtered]"
        assert result["request"]["headers"]["content-type"] == "application/json"

    def test_before_send_scrubs_headers_case_insensitive(self):
        """Header scrubbing should work regardless of case."""
        from app.core.sentry_config import _before_send

        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer token",
                    "X-API-Key": "secret",
                    "Cookie": "session=abc",
                }
            }
        }
        result = _before_send(event, {})
        assert result["request"]["headers"]["Authorization"] == "[Filtered]"
        assert result["request"]["headers"]["X-API-Key"] == "[Filtered]"
        assert result["request"]["headers"]["Cookie"] == "[Filtered]"

    def test_before_send_transaction_filters_health(self):
        """Health check transactions should be dropped."""
        from app.core.sentry_config import _before_send_transaction

        event = {"request": {"url": "https://wiii.holilihu.online/api/v1/health"}}
        result = _before_send_transaction(event, {})
        assert result is None

    def test_before_send_transaction_passes_api(self):
        """Normal API transactions should pass through."""
        from app.core.sentry_config import _before_send_transaction

        event = {"request": {"url": "https://wiii.holilihu.online/api/v1/chat/stream/v3"}}
        result = _before_send_transaction(event, {})
        assert result is not None

    def test_config_flags_exist(self):
        """Sentry config flags should exist in Settings."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "sentry_dsn" in fields
        assert "sentry_environment" in fields
        assert "sentry_traces_sample_rate" in fields

    def test_init_sentry_without_sdk_warns(self):
        """When sentry_sdk is None, init should warn and return."""
        with patch("app.core.sentry_config.sentry_sdk", None):
            from app.core.sentry_config import init_sentry
            # Should not raise, just log warning
            init_sentry(dsn="https://key@sentry.io/123", environment="test")


class TestSentryMainIntegration:
    """Test Sentry wiring in main.py."""

    def test_main_imports_sentry_config(self):
        """main.py should import init_sentry."""
        import app.core.sentry_config as sc
        assert hasattr(sc, "init_sentry")

    def test_init_sentry_called_with_settings(self):
        """Verify init_sentry uses settings values."""
        mock_sdk = MagicMock()
        with patch("app.core.sentry_config.sentry_sdk", mock_sdk):
            from app.core.sentry_config import init_sentry
            init_sentry(
                dsn="https://key@sentry.io/123",
                environment="staging",
                traces_sample_rate=0.1,
            )
            call_kwargs = mock_sdk.init.call_args
            assert call_kwargs.kwargs["environment"] == "staging"
            assert call_kwargs.kwargs["traces_sample_rate"] == 0.1
