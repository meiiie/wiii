"""
Vertex AI provider for Wiii — separate from Google AI Studio (Gemini) provider.

Uses WiiiChatModel (AsyncOpenAI SDK) via Vertex AI's OpenAI-compatible endpoint.
De-LangChaining Phase 1: Removed ChatGoogleGenerativeAI dependency.
"""

import logging
from typing import Any


from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel

logger = logging.getLogger(__name__)

try:
    from app.core.resilience import get_circuit_breaker

    _vertex_cb = get_circuit_breaker("vertex", failure_threshold=3, recovery_timeout=30)
except Exception:
    _vertex_cb = None


class VertexAIProvider(LLMProvider):
    """Vertex AI provider — uses Google's Vertex AI endpoint with separate quota."""

    @property
    def name(self) -> str:
        return "vertex"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "vertex_api_key", None))

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _vertex_cb is not None:
            return _vertex_cb.is_available()
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
        if not model_name:
            model_name = getattr(settings, "vertex_model", None) or settings.google_model

        # Vertex AI uses the same OpenAI-compatible endpoint structure
        base_url = getattr(settings, "vertex_base_url", "") or getattr(
            settings, "google_openai_compat_url", ""
        )

        model_kwargs: dict[str, Any] = {}
        if settings.thinking_enabled and thinking_budget > 0:
            # Gemini 2.5+ OpenAI-compat accepts `reasoning_effort`; legacy
            # `extra_body={"google": {"thinking_config": ...}}` is rejected.
            if thinking_budget <= 1024:
                effort = "low"
            elif thinking_budget <= 4096:
                effort = "medium"
            else:
                effort = "high"
            model_kwargs["reasoning_effort"] = effort

        llm = WiiiChatModel(
            model=model_name,
            api_key=settings.vertex_api_key,
            base_url=base_url,
            temperature=temperature,
            model_kwargs=model_kwargs,
        )
        logger.info(
            "[VERTEX] Created %s instance (model=%s, budget=%d, thoughts=%s)",
            tier.upper(), model_name, thinking_budget, include_thoughts,
        )
        return llm

    @staticmethod
    async def record_success() -> None:
        if _vertex_cb is not None:
            await _vertex_cb.record_success()

    @staticmethod
    async def record_failure() -> None:
        if _vertex_cb is not None:
            await _vertex_cb.record_failure()
