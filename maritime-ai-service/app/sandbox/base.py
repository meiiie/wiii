"""Provider interface for privileged sandbox execution."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.sandbox.models import (
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxProvider,
)


class SandboxExecutor(ABC):
    """Abstract interface for remote privileged execution backends."""

    @property
    @abstractmethod
    def provider(self) -> SandboxProvider:
        """Provider identifier."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the executor has enough config to be used."""

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Lightweight availability probe."""

    @abstractmethod
    async def execute(
        self,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        """Run a privileged workload inside the sandbox backend."""
