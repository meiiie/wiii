"""
Zhipu AI (GLM-5) Provider — Fallback LLM backend for Wiii.

Uses WiiiChatModel (AsyncOpenAI SDK).
De-LangChaining Phase 1: Removed ChatOpenAI dependency.
"""

import logging
from typing import Any


from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel

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


class ZhipuProvider(LLMProvider):
    """Zhipu AI provider (GLM-5) via WiiiChatModel."""

    @property
    def name(self) -> str:
        return "zhipu"

    def is_configured(self) -> bool:
        api_key = getattr(settings, "zhipu_api_key", None)
        return bool(api_key) and isinstance(api_key, str)

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
    ) -> Any:
        model_name = kwargs.get("model_name") or kwargs.get("model")
        if model_name:
            model = model_name
        elif tier == "deep":
            model = getattr(settings, "zhipu_model_advanced", "glm-5")
        else:
            model = getattr(settings, "zhipu_model", "glm-5")

        base_url = getattr(settings, "zhipu_base_url", ZHIPU_DEFAULT_BASE_URL)

        llm = WiiiChatModel(
            model=model,
            api_key=settings.zhipu_api_key,
            base_url=base_url,
            temperature=temperature,
        )
        logger.info(
            "[ZHIPU] Created %s instance (model=%s, base_url=%s)",
            tier.upper(), model, base_url,
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
