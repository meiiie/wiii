"""
Zhipu AI (GLM-5) Provider — Fallback LLM backend for Wiii.

GLM-5 is OpenAI-compatible, so we use ChatOpenAI with base_url override.
API docs: https://docs.z.ai/guides/llm/glm-5

Sprint V5-Visual: Added as fallback for Gemini 429 rate limiting.
$400 credit available for this provider.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Circuit breaker for Zhipu API
_zhipu_cb = None
try:
    from app.core.resilience import get_circuit_breaker
    _zhipu_cb = get_circuit_breaker("zhipu", failure_threshold=3, recovery_timeout=30)
except Exception:
    pass

# Default base URL (international endpoint)
ZHIPU_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# Map tiers to GLM models
_TIER_MODEL_MAP = {
    "deep": None,      # Use zhipu_model_advanced from config (glm-5)
    "moderate": None,   # Use zhipu_model from config (glm-5)
    "light": None,      # Use zhipu_model from config (glm-5)
}


class ZhipuProvider(LLMProvider):
    """
    Zhipu AI provider (GLM-5) via langchain-openai ChatOpenAI.

    GLM-5 exposes a fully OpenAI-compatible API, so we reuse
    ChatOpenAI with base_url pointed to Zhipu's endpoint.

    Features:
    - Tool calling / function calling (up to 128 functions)
    - Streaming support
    - 200K context window, 128K max output
    - MoE architecture (745B total, 44B active)
    """

    @property
    def name(self) -> str:
        return "zhipu"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "zhipu_api_key", None))

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _zhipu_cb is not None:
            return _zhipu_cb.is_available()
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
            model = getattr(settings, "zhipu_model_advanced", "glm-5")
        else:
            model = getattr(settings, "zhipu_model", "glm-5")

        base_url = getattr(
            settings, "zhipu_base_url", ZHIPU_DEFAULT_BASE_URL
        )

        llm_kwargs = {
            "model": model,
            "api_key": settings.zhipu_api_key,
            "base_url": base_url,
            "temperature": temperature,
            "streaming": True,
        }

        llm = ChatOpenAI(**llm_kwargs)
        logger.info(
            f"[ZHIPU] Created {tier.upper()} instance "
            f"(model={model}, base_url={base_url})"
        )
        return llm

    @staticmethod
    def get_circuit_breaker():
        return _zhipu_cb

    @staticmethod
    async def record_success():
        if _zhipu_cb is not None:
            await _zhipu_cb.record_success()

    @staticmethod
    async def record_failure():
        if _zhipu_cb is not None:
            await _zhipu_cb.record_failure()
