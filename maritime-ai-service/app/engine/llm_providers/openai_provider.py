"""
OpenAI / OpenRouter / NVIDIA NIM Provider — Secondary LLM backend for Wiii.

Uses WiiiChatModel (AsyncOpenAI SDK).
De-LangChaining Phase 1: Removed ChatOpenAI dependency.
Issue #110: NVIDIA NIM added as alias-based OpenAI-compatible target.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel
from app.engine.openai_compatible_credentials import (
    resolve_nvidia_api_key,
    resolve_nvidia_base_url,
    resolve_nvidia_model,
    resolve_nvidia_model_advanced,
    resolve_openai_api_key,
    resolve_openai_base_url,
    resolve_openai_model,
    resolve_openai_model_advanced,
    resolve_openrouter_api_key,
    resolve_openrouter_base_url,
    resolve_openrouter_model,
    resolve_openrouter_model_advanced,
)
from app.engine.openrouter_routing import (
    build_openrouter_extra_body,
    is_openrouter_base_url,
)

logger = logging.getLogger(__name__)

# Circuit breaker for OpenAI API
_openai_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _openai_cb = get_circuit_breaker("openai", failure_threshold=3, recovery_timeout=30)
except Exception:
    pass

# o-series models that support reasoning_effort parameter
_O_SERIES_PREFIXES = ("o1", "o3-mini", "o3", "o4-mini")

# Map tier → reasoning_effort for o-series models
_TIER_REASONING_EFFORT = {
    "deep": "high",
    "moderate": "medium",
    "light": "low",
}


class OpenAIProvider(LLMProvider):
    """OpenAI / OpenRouter provider via WiiiChatModel."""

    def __init__(self, provider_alias: str = "openai"):
        self._provider_alias = str(provider_alias or "openai").strip().lower()

    @property
    def name(self) -> str:
        return self._provider_alias

    def is_configured(self) -> bool:
        if self._provider_alias == "openrouter":
            return bool(resolve_openrouter_api_key(settings))
        if self._provider_alias == "nvidia":
            return bool(resolve_nvidia_api_key(settings))
        return bool(resolve_openai_api_key(settings))

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
        # Select model based on tier
        model_name = kwargs.get("model_name") or kwargs.get("model")
        if model_name:
            model = model_name
        elif self._provider_alias == "openrouter" and tier == "deep":
            model = resolve_openrouter_model_advanced(settings)
        elif self._provider_alias == "openrouter":
            model = resolve_openrouter_model(settings)
        elif self._provider_alias == "nvidia" and tier == "deep":
            model = resolve_nvidia_model_advanced(settings)
        elif self._provider_alias == "nvidia":
            model = resolve_nvidia_model(settings)
        elif tier == "deep":
            model = resolve_openai_model_advanced(settings)
        else:
            model = resolve_openai_model(settings)

        # Detect o-series reasoning models
        is_o_series = any(model.startswith(prefix) for prefix in _O_SERIES_PREFIXES)

        if self._provider_alias == "openrouter":
            api_key = resolve_openrouter_api_key(settings)
        elif self._provider_alias == "nvidia":
            api_key = resolve_nvidia_api_key(settings)
        else:
            api_key = resolve_openai_api_key(settings)

        model_kwargs: dict[str, Any] = {}

        if is_o_series:
            reasoning_effort = _TIER_REASONING_EFFORT.get(tier, "medium")
            model_kwargs["extra_body"] = {"reasoning_effort": reasoning_effort}
            logger.info(
                f"[OPENAI] o-series model detected: reasoning_effort={reasoning_effort}"
            )
        else:
            model_kwargs["temperature"] = temperature

        # Support OpenRouter / NVIDIA NIM / custom base URL
        base_url = ""
        use_openrouter_request = False
        if self._provider_alias == "openrouter":
            base_url = resolve_openrouter_base_url(settings)
            use_openrouter_request = True
        elif self._provider_alias == "nvidia":
            base_url = resolve_nvidia_base_url(settings)
        else:
            explicit_openai_base = getattr(settings, "openai_base_url", None)
            if isinstance(explicit_openai_base, str) and explicit_openai_base.strip():
                base_url = explicit_openai_base.strip()
                use_openrouter_request = is_openrouter_base_url(base_url)

        openrouter_extra_body = (
            build_openrouter_extra_body(settings, primary_model=model)
            if use_openrouter_request
            else {}
        )
        if openrouter_extra_body:
            existing = model_kwargs.get("extra_body", {})
            existing.update(openrouter_extra_body)
            model_kwargs["extra_body"] = existing

        llm = WiiiChatModel(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature if not is_o_series else 0.5,
            model_kwargs=model_kwargs,
        )
        logger.info(
            f"[OPENAI] Created {tier.upper()} instance "
            f"(model={model}, o_series={is_o_series}, "
            f"provider={self._provider_alias}, base_url={base_url or 'default'})"
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
