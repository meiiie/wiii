"""
Google Gemini Provider — Primary LLM backend for Wiii.

Extracted from llm_pool.py._create_instance() to support
multi-provider failover architecture.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Circuit breaker for Gemini API
_gemini_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _gemini_cb = get_circuit_breaker("gemini", failure_threshold=3, recovery_timeout=30)
except Exception:
    pass


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider via langchain-google-genai.

    Supports Gemini native thinking with tiered budgets.
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
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm_kwargs = {
            "model": settings.google_model,
            "google_api_key": settings.google_api_key,
            "temperature": temperature,
        }

        if settings.thinking_enabled and thinking_budget > 0:
            llm_kwargs["thinking_budget"] = thinking_budget
            if include_thoughts:
                llm_kwargs["include_thoughts"] = True

        llm = ChatGoogleGenerativeAI(**llm_kwargs)
        logger.info(
            f"[GEMINI] Created {tier.upper()} instance "
            f"(budget={thinking_budget}, thoughts={include_thoughts})"
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
