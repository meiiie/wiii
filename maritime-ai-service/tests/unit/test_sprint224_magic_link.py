"""Sprint 224: Magic Link Email Auth — Unit Tests."""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConfigDefaults:
    """Config flag defaults."""

    def test_enable_magic_link_auth_default_false(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_magic_link_auth"].default
        assert default is False

    def test_magic_link_expires_default_600(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_expires_seconds"].default
        assert default == 600

    def test_magic_link_max_per_hour_default_5(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_max_per_hour"].default
        assert default == 5

    def test_magic_link_ws_timeout_default_900(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_ws_timeout_seconds"].default
        assert default == 900

    def test_magic_link_resend_cooldown_default_45(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_resend_cooldown_seconds"].default
        assert default == 45
