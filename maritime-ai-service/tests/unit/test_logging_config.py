"""Tests for app.core.logging_config — structured logging setup."""

import logging

import pytest


class TestSetupLogging:
    """Verify setup_logging configures the root logger correctly."""

    def test_setup_logging_dev_mode(self):
        from app.core.logging_config import setup_logging

        setup_logging(json_output=False, log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) >= 1

    def test_setup_logging_production_mode(self):
        from app.core.logging_config import setup_logging

        setup_logging(json_output=True, log_level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_setup_logging_silences_noisy_loggers(self):
        from app.core.logging_config import setup_logging

        setup_logging(json_output=False, log_level="DEBUG")
        for name in ("httpcore", "httpx", "urllib3", "asyncio"):
            assert logging.getLogger(name).level >= logging.WARNING

    def test_setup_logging_idempotent(self):
        from app.core.logging_config import setup_logging

        setup_logging(json_output=False, log_level="INFO")
        handler_count = len(logging.getLogger().handlers)
        setup_logging(json_output=False, log_level="INFO")
        assert len(logging.getLogger().handlers) == handler_count
