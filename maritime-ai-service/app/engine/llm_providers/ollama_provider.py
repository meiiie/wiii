"""
Ollama Provider — Local/Self-Hosted LLM backend for Wiii.

Provides fallback to locally-running models via Ollama.
No API key required — just needs Ollama running at ollama_base_url.

Sprint 59: Enhanced with thinking mode support for Qwen3/DeepSeek-R1.
"""

import logging
from typing import Any, List

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Circuit breaker for Ollama
_ollama_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _ollama_cb = get_circuit_breaker("ollama", failure_threshold=3, recovery_timeout=60)
except Exception:
    pass

# Default models that support thinking mode via Ollama
DEFAULT_THINKING_MODELS = ["qwen3", "deepseek-r1", "qwq"]


def _model_supports_thinking(model_name: str) -> bool:
    """Check if an Ollama model supports thinking mode (think=True).

    Models like Qwen3, DeepSeek-R1, and QwQ support structured
    thinking via the `think` parameter in Ollama's OpenAI-compat API.

    Args:
        model_name: Full model name (e.g., "qwen3:8b", "deepseek-r1:14b")

    Returns:
        True if the model supports thinking mode.
    """
    thinking_models: List[str] = getattr(
        settings, "ollama_thinking_models", DEFAULT_THINKING_MODELS
    )
    # Check if model_name starts with any thinking model prefix
    model_lower = model_name.lower()
    return any(model_lower.startswith(prefix) for prefix in thinking_models)


class OllamaProvider(LLMProvider):
    """
    Ollama provider via langchain-ollama.

    Runs locally — no API key needed, just Ollama daemon at base_url.
    Sprint 59: Supports thinking mode for compatible models.
    """

    @property
    def name(self) -> str:
        return "ollama"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "ollama_base_url", None))

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _ollama_cb is not None:
            return _ollama_cb.is_available()
        return True

    def create_instance(
        self,
        tier: str,
        thinking_budget: int = 0,
        include_thoughts: bool = False,
        temperature: float = 0.5,
        **kwargs: Any,
    ) -> BaseChatModel:
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "langchain-ollama is required for Ollama provider. "
                "Install with: pip install langchain-ollama"
            )

        model = getattr(settings, "ollama_model", "qwen3:8b")
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")

        # Build extra kwargs for thinking-capable models
        ollama_kwargs = {}
        thinks = thinking_budget > 0 or include_thoughts
        if _model_supports_thinking(model) and thinks:
            # Pass think=True via extra_body for Qwen3/DeepSeek-R1
            ollama_kwargs["extra_body"] = {"think": True}
            logger.info("[OLLAMA] Thinking mode enabled for %s", model)

        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            **ollama_kwargs,
        )
        logger.info(
            "[OLLAMA] Created %s instance (model=%s, base_url=%s, thinking=%s)",
            tier.upper(), model, base_url, bool(ollama_kwargs)
        )
        return llm

    @staticmethod
    def get_circuit_breaker():
        return _ollama_cb

    @staticmethod
    async def record_success():
        if _ollama_cb is not None:
            await _ollama_cb.record_success()

    @staticmethod
    async def record_failure():
        if _ollama_cb is not None:
            await _ollama_cb.record_failure()
