"""
Ollama Provider — Local, self-hosted, or Ollama Cloud backend for Wiii.

Supports both unauthenticated local hosts and direct authenticated access to
Ollama Cloud via https://ollama.com/api.

Sprint 59: Enhanced with thinking mode support for Qwen3/DeepSeek-R1.

Phase 1 (unified providers): Behind ``enable_unified_providers`` gate,
uses ``ChatOpenAI`` pointed at Ollama's ``/v1`` endpoint instead of
``ChatOllama``.
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


def _normalize_ollama_host(base_url: str | None) -> str | None:
    """Normalize Ollama host URLs for client libraries.

    The official HTTP examples use `https://ollama.com/api`, but the Python
    client used by langchain-ollama expects the host root and appends `/api`
    internally. Accept both forms here to keep runtime config forgiving.
    """
    if not isinstance(base_url, str):
        return base_url

    normalized = base_url.strip()
    if not normalized:
        return normalized

    if normalized.endswith("/api"):
        return normalized[:-4]
    return normalized


def _model_supports_thinking(model_name: str) -> bool:
    """Check if an Ollama model supports thinking mode (think=True).

    Models like Qwen3, DeepSeek-R1, and QwQ support structured
    thinking via the `think` parameter in Ollama's OpenAI-compat API.
    Qwen's newer instruct-specific tags should not be treated as
    thinking-capable by default.

    Args:
        model_name: Full model name (e.g., "qwen3:8b", "deepseek-r1:14b")

    Returns:
        True if the model supports thinking mode.
    """
    thinking_models: List[str] = getattr(
        settings, "ollama_thinking_models", DEFAULT_THINKING_MODELS
    )
    model_lower = model_name.lower()
    if model_lower.startswith("qwen3") and "-instruct" in model_lower:
        return False

    # Check if model_name starts with any thinking model prefix
    return any(model_lower.startswith(prefix) for prefix in thinking_models)


class OllamaProvider(LLMProvider):
    """
    Ollama provider.

    Two paths:
    - Legacy (default): ``ChatOllama`` from langchain-ollama
    - Unified (``enable_unified_providers=True``): ``ChatOpenAI`` via
      Ollama's ``/v1`` OpenAI-compatible endpoint
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
        if getattr(settings, "enable_unified_providers", False):
            return self._create_unified(tier, thinking_budget, include_thoughts, temperature)
        return self._create_legacy(tier, thinking_budget, include_thoughts, temperature)

    # --------------------------------------------------------------------- #
    # Legacy path: ChatOllama
    # --------------------------------------------------------------------- #
    def _create_legacy(
        self, tier: str, thinking_budget: int, include_thoughts: bool, temperature: float,
    ) -> BaseChatModel:
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "langchain-ollama is required for Ollama provider. "
                "Install with: pip install langchain-ollama"
            )

        model = getattr(settings, "ollama_model", "qwen3:4b-instruct-2507-q4_K_M")
        base_url = _normalize_ollama_host(
            getattr(settings, "ollama_base_url", "http://localhost:11434")
        )
        api_key = getattr(settings, "ollama_api_key", None)
        keep_alive = getattr(settings, "ollama_keep_alive", None)
        if not isinstance(api_key, str):
            api_key = None
        else:
            api_key = api_key.strip() or None
        if not isinstance(keep_alive, str):
            keep_alive = None
        elif not keep_alive.strip():
            keep_alive = None
        else:
            keep_alive = keep_alive.strip()

        # Build extra kwargs for thinking-capable models
        ollama_kwargs = {}
        if keep_alive:
            ollama_kwargs["keep_alive"] = keep_alive
        if api_key:
            ollama_kwargs["client_kwargs"] = {
                "headers": {"Authorization": f"Bearer {api_key}"}
            }
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
            "[OLLAMA] Created %s instance [legacy] (model=%s, base_url=%s, thinking=%s, keep_alive=%s, auth=%s)",
            tier.upper(),
            model,
            base_url,
            bool("extra_body" in ollama_kwargs),
            keep_alive,
            bool(api_key),
        )
        return llm

    # --------------------------------------------------------------------- #
    # Unified path: ChatOpenAI → Ollama /v1 endpoint
    # --------------------------------------------------------------------- #
    def _create_unified(
        self, tier: str, thinking_budget: int, include_thoughts: bool, temperature: float,
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        model = getattr(settings, "ollama_model", "qwen3:4b-instruct-2507-q4_K_M")
        raw_base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        api_key = getattr(settings, "ollama_api_key", None)
        if not isinstance(api_key, str) or not api_key.strip():
            api_key = "ollama"  # Ollama /v1 requires a non-empty key
        else:
            api_key = api_key.strip()

        # Ensure /v1 suffix for OpenAI-compat endpoint
        base_url_v1 = raw_base_url.rstrip("/")
        if not base_url_v1.endswith("/v1"):
            base_url_v1 = base_url_v1 + "/v1"

        llm_kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "base_url": base_url_v1,
            "temperature": temperature,
            "streaming": True,
        }

        # Ollama thinking for Qwen3/DeepSeek-R1
        thinks = thinking_budget > 0 or include_thoughts
        if _model_supports_thinking(model) and thinks:
            llm_kwargs["model_kwargs"] = {"extra_body": {"think": True}}
            logger.info("[OLLAMA] Thinking mode enabled for %s [unified]", model)

        llm = ChatOpenAI(**llm_kwargs)
        logger.info(
            "[OLLAMA] Created %s instance [unified/ChatOpenAI] (model=%s, base_url=%s)",
            tier.upper(), model, base_url_v1,
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
