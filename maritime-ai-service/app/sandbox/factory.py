"""Factory for the privileged sandbox executor."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.sandbox.base import SandboxExecutor
from app.sandbox.models import SandboxProvider
from app.sandbox.opensandbox_executor import OpenSandboxExecutor


@lru_cache
def get_sandbox_executor() -> Optional[SandboxExecutor]:
    """Return the configured privileged sandbox executor, if any."""
    settings = get_settings()

    if not settings.enable_privileged_sandbox:
        return None

    provider = SandboxProvider(settings.sandbox_provider)
    if provider == SandboxProvider.OPENSANDBOX:
        return OpenSandboxExecutor.from_settings(settings)

    # local_subprocess remains handled by the legacy code path until Phase 2
    return None


def reset_sandbox_executor() -> None:
    """Clear cached executor instance. Used in tests."""
    get_sandbox_executor.cache_clear()
