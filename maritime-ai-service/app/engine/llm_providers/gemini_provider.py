"""
Google Gemini Provider — Primary LLM backend for Wiii.

Uses WiiiChatModel (AsyncOpenAI SDK) via Gemini's OpenAI-compatible endpoint.
De-LangChaining Phase 1: Removed ChatGoogleGenerativeAI dependency.
"""

import logging
from typing import Any


from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel
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
    """Google Gemini provider via OpenAI-compatible endpoint."""

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
    ) -> Any:
        model_name = kwargs.get("model_name") or kwargs.get("model")
        model = _resolve_gemini_model_for_tier(tier, model_name)

        model_kwargs: dict[str, Any] = {}
        if settings.thinking_enabled and thinking_budget > 0:
            # Gemini 2.5+ OpenAI-compat accepts `reasoning_effort` and rejects the
            # legacy `extra_body={"google": {"thinking_config": {...}}}` format
            # (returns `Unknown name "google": Cannot find field`). Map budget → effort.
            if thinking_budget <= 1024:
                effort = "low"
            elif thinking_budget <= 4096:
                effort = "medium"
            else:
                effort = "high"
            model_kwargs["reasoning_effort"] = effort

        llm = WiiiChatModel(
            model=model,
            api_key=settings.google_api_key,
            base_url=settings.google_openai_compat_url,
            temperature=temperature,
            model_kwargs=model_kwargs,
        )
        logger.info(
            "[GEMINI] Created %s instance (model=%s, budget=%d, thoughts=%s)",
            tier.upper(), model, thinking_budget, include_thoughts,
        )
        return llm

    @staticmethod
    def get_circuit_breaker():
        return _gemini_cb

    @staticmethod
    async def record_success():
        if _gemini_cb is not None:
            await _gemini_cb.record_success()

    @staticmethod
    async def record_failure():
        if _gemini_cb is not None:
            await _gemini_cb.record_failure()
