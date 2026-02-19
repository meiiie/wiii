"""
OpenAI / OpenRouter Provider — Secondary LLM backend for Wiii.

Supports both OpenAI direct and OpenRouter via `openai_base_url`.
Config fields already exist in config.py (previously unused).
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Circuit breaker for OpenAI API
_openai_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _openai_cb = get_circuit_breaker("openai", failure_threshold=3, recovery_timeout=30)
except Exception:
    pass

# Map tiers to OpenAI models
_TIER_MODEL_MAP = {
    "deep": None,      # Use openai_model_advanced from config
    "moderate": None,   # Use openai_model from config
    "light": None,      # Use openai_model from config
}

# o-series models that support reasoning_effort parameter
_O_SERIES_PREFIXES = ("o1", "o3-mini", "o3", "o4-mini")

# Map tier → reasoning_effort for o-series models
_TIER_REASONING_EFFORT = {
    "deep": "high",
    "moderate": "medium",
    "light": "low",
}


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider via langchain-openai.

    Also supports OpenRouter and any OpenAI-compatible API
    through the `openai_base_url` config field.
    """

    @property
    def name(self) -> str:
        return "openai"

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _openai_cb is not None:
            return _openai_cb.is_available()
        return True

    def create_instance(
        self,
        tier: str,
        thinking_budget: int = 0,
        include_thoughts: bool = False,
        temperature: float = 0.5,
        **kwargs: Any,
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        # Select model based on tier
        if tier == "deep":
            model = settings.openai_model_advanced
        else:
            model = settings.openai_model

        # Detect o-series reasoning models
        is_o_series = any(model.startswith(prefix) for prefix in _O_SERIES_PREFIXES)

        llm_kwargs = {
            "model": model,
            "api_key": settings.openai_api_key,
        }

        if is_o_series:
            # o-series models don't support temperature; use reasoning_effort instead
            reasoning_effort = _TIER_REASONING_EFFORT.get(tier, "medium")
            llm_kwargs["model_kwargs"] = {"reasoning_effort": reasoning_effort}
            logger.info(
                f"[OPENAI] o-series model detected: reasoning_effort={reasoning_effort}"
            )
        else:
            llm_kwargs["temperature"] = temperature

        # Support OpenRouter or custom base URL
        if settings.openai_base_url:
            llm_kwargs["base_url"] = settings.openai_base_url

        llm = ChatOpenAI(**llm_kwargs)
        logger.info(
            f"[OPENAI] Created {tier.upper()} instance "
            f"(model={model}, o_series={is_o_series}, "
            f"base_url={settings.openai_base_url or 'default'})"
        )
        return llm

    @staticmethod
    def get_circuit_breaker():
        return _openai_cb

    @staticmethod
    async def record_success():
        if _openai_cb is not None:
            await _openai_cb.record_success()

    @staticmethod
    async def record_failure():
        if _openai_cb is not None:
            await _openai_cb.record_failure()
