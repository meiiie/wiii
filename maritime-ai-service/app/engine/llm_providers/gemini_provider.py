"""
Google Gemini Provider — Primary LLM backend for Wiii.

Extracted from llm_pool.py._create_instance() to support
multi-provider failover architecture.

Phase 1 (unified providers): Behind ``enable_unified_providers`` gate,
uses ``ChatOpenAI`` pointed at Gemini's OpenAI-compatible endpoint
instead of ``ChatGoogleGenerativeAI``.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.model_catalog import GOOGLE_DEEP_MODEL

logger = logging.getLogger(__name__)

# Circuit breaker for Gemini API
_gemini_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _gemini_cb = get_circuit_breaker("gemini", failure_threshold=3, recovery_timeout=30)
except Exception:
    pass


def _resolve_gemini_model_for_tier(tier: str, explicit_model: str | None = None) -> str:
    if explicit_model:
        return explicit_model
    if str(tier or "").strip().lower() == "deep":
        return getattr(settings, "google_model_advanced", GOOGLE_DEEP_MODEL)
    return settings.google_model


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider.

    Two paths:
    - Legacy (default): ``ChatGoogleGenerativeAI`` from langchain-google-genai
    - Unified (``enable_unified_providers=True``): ``ChatOpenAI`` via
      Gemini's OpenAI-compatible endpoint
    """

    @property
    def name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        return bool(settings.google_api_key)

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _gemini_cb is not None:
            return _gemini_cb.is_available()
        return True

    def create_instance(
        self,
        tier: str,
        thinking_budget: int = 0,
        include_thoughts: bool = False,
        temperature: float = 0.5,
        **kwargs: Any,
    ) -> BaseChatModel:
        model_name = kwargs.get("model_name") or kwargs.get("model")
        if getattr(settings, "enable_unified_providers", False):
            return self._create_unified(tier, thinking_budget, include_thoughts, temperature, model_name=model_name)
        return self._create_legacy(tier, thinking_budget, include_thoughts, temperature, model_name=model_name)

    # --------------------------------------------------------------------- #
    # Legacy path: ChatGoogleGenerativeAI
    # --------------------------------------------------------------------- #
    def _create_legacy(
        self, tier: str, thinking_budget: int, include_thoughts: bool, temperature: float, *, model_name: str | None = None,
    ) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm_kwargs: dict[str, Any] = {
            "model": _resolve_gemini_model_for_tier(tier, model_name),
            "google_api_key": settings.google_api_key,
            "temperature": temperature,
        }

        if settings.thinking_enabled and thinking_budget > 0:
            llm_kwargs["thinking_budget"] = thinking_budget
            if include_thoughts:
                llm_kwargs["include_thoughts"] = True

        llm = ChatGoogleGenerativeAI(**llm_kwargs)
        logger.info(
            "[GEMINI] Created %s instance [legacy] (budget=%d, thoughts=%s)",
            tier.upper(), thinking_budget, include_thoughts,
        )
        return llm

    # --------------------------------------------------------------------- #
    # Unified path: ChatOpenAI → Gemini OpenAI-compat endpoint
    # --------------------------------------------------------------------- #
    def _create_unified(
        self, tier: str, thinking_budget: int, include_thoughts: bool, temperature: float, *, model_name: str | None = None,
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        llm_kwargs: dict[str, Any] = {
            "model": _resolve_gemini_model_for_tier(tier, model_name),
            "api_key": settings.google_api_key,
            "base_url": settings.google_openai_compat_url,
            "temperature": temperature,
            "streaming": True,
        }

        # Gemini thinking via model_kwargs passthrough
        if settings.thinking_enabled and thinking_budget > 0:
            llm_kwargs["model_kwargs"] = {
                "extra_body": {
                    "google": {
                        "thinking_config": {
                            "thinking_budget": thinking_budget,
                            "include_thoughts": include_thoughts,
                        }
                    }
                }
            }

        llm = ChatOpenAI(**llm_kwargs)
        logger.info(
            "[GEMINI] Created %s instance [unified/ChatOpenAI] (budget=%d, thoughts=%s)",
            tier.upper(), thinking_budget, include_thoughts,
        )
        return llm

    @staticmethod
    def get_circuit_breaker():
        """Access the underlying Gemini circuit breaker."""
        return _gemini_cb

    @staticmethod
    async def record_success():
        if _gemini_cb is not None:
            await _gemini_cb.record_success()

    @staticmethod
    async def record_failure():
        if _gemini_cb is not None:
            await _gemini_cb.record_failure()
