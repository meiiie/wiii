"""
LLM Provider ABC — Interface for all LLM backends.

All providers return `Any` instances, ensuring that
consumer code (18+ files) can use `.ainvoke()` and `.astream()`
without knowing which provider is active.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any


logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Each provider wraps a specific LLM backend (Gemini, OpenAI, Ollama)
    and exposes a uniform interface for the LLMPool failover chain.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'google', 'openai', 'ollama')."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if this provider has the required credentials/config.

        Returns True if API keys or endpoints are set, False otherwise.
        This is a quick check — does NOT make network calls.
        """
        ...

    @abstractmethod
    def create_instance(
        self,
        tier: str,
        thinking_budget: int = 0,
        include_thoughts: bool = False,
        temperature: float = 0.5,
        **kwargs: Any,
    ) -> Any:
        """
        Create an LLM instance for the specified tier.

        Args:
            tier: Thinking tier string ('deep', 'moderate', 'light')
            thinking_budget: Token budget for thinking (provider-specific)
            include_thoughts: Whether to include thought process in response
            temperature: LLM temperature (0.0-2.0)
            **kwargs: Provider-specific extra arguments

        Returns:
            Any instance ready for `.ainvoke()` / `.astream()`

        Raises:
            Exception: If instance creation fails (missing key, bad config, etc.)
        """
        ...

    def is_available(self) -> bool:
        """
        Check if the provider is likely available (circuit breaker not open).

        Default implementation returns is_configured().
        Providers with circuit breakers should override this.
        """
        return self.is_configured()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} configured={self.is_configured()}>"
