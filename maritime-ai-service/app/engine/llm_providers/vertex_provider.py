"""Vertex AI provider for Wiii — separate from Google AI Studio (Gemini) provider.

Uses the same ChatGoogleGenerativeAI from langchain-google-genai but with
Vertex AI API key and endpoint. Allows independent failover and quota management.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

try:
    from app.core.resilience import get_circuit_breaker

    _vertex_cb = get_circuit_breaker(
        "vertex",
        failure_threshold=3,
        recovery_timeout=30,
    )
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
    ) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = kwargs.get("model_name") or kwargs.get("model")
        if not model_name:
            model_name = getattr(settings, "vertex_model", None) or settings.google_model

        llm_kwargs: dict[str, Any] = {
            "model": model_name,
            "google_api_key": settings.vertex_api_key,
            "temperature": temperature,
        }

        if settings.thinking_enabled and thinking_budget > 0:
            llm_kwargs["thinking_budget"] = thinking_budget
            if include_thoughts:
                llm_kwargs["include_thoughts"] = True

        llm = ChatGoogleGenerativeAI(**llm_kwargs)

        logger.info(
            "[VERTEX] Created %s instance (model=%s, budget=%d, thoughts=%s)",
            tier.upper(),
            model_name,
            thinking_budget,
            include_thoughts,
        )
        return llm

    @staticmethod
    def record_success() -> None:
        if _vertex_cb is not None:
            _vertex_cb.record_success()

    @staticmethod
    def record_failure() -> None:
        if _vertex_cb is not None:
            _vertex_cb.record_failure()
