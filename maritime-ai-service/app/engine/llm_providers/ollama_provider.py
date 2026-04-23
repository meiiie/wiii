"""
Ollama Provider — Local, self-hosted, or Ollama Cloud backend for Wiii.

Uses WiiiChatModel (AsyncOpenAI SDK) via Ollama's /v1 endpoint.
De-LangChaining Phase 1: Removed ChatOllama dependency.
"""

import logging
import time
from typing import Any, List

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel

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
_OLLAMA_AVAILABILITY_CACHE_TTL_SECONDS = 15.0
_ollama_availability_cache: dict[str, tuple[float, bool]] = {}


def _normalize_ollama_host(base_url: str | None) -> str | None:
    if not isinstance(base_url, str):
        return base_url
    normalized = base_url.strip()
    if not normalized:
        return normalized
    if normalized.endswith("/api"):
        return normalized[:-4]
    return normalized


def _model_supports_thinking(model_name: str) -> bool:
    thinking_models: List[str] = getattr(
        settings, "ollama_thinking_models", DEFAULT_THINKING_MODELS
    )
    model_lower = model_name.lower()
    if model_lower.startswith("qwen3") and "-instruct" in model_lower:
        return False
    return any(model_lower.startswith(prefix) for prefix in thinking_models)


def _ollama_connectivity_headers(api_key: str | None) -> dict[str, str]:
    if isinstance(api_key, str) and api_key.strip():
        return {"Authorization": f"Bearer {api_key.strip()}"}
    return {}


def reset_ollama_availability_cache() -> None:
    _ollama_availability_cache.clear()


def check_ollama_host_reachable(
    base_url: str | None = None,
    *,
    api_key: str | None = None,
    force_refresh: bool = False,
) -> bool:
    normalized = _normalize_ollama_host(
        base_url if base_url is not None else getattr(settings, "ollama_base_url", None)
    )
    if not isinstance(normalized, str) or not normalized.strip():
        return False

    cache_key = normalized
    now = time.monotonic()
    cached = _ollama_availability_cache.get(cache_key)
    if (
        not force_refresh
        and cached is not None
        and now - cached[0] < _OLLAMA_AVAILABILITY_CACHE_TTL_SECONDS
    ):
        return cached[1]

    headers = _ollama_connectivity_headers(
        api_key if api_key is not None else getattr(settings, "ollama_api_key", None)
    )

    import httpx

    reachable = False
    try:
        with httpx.Client(timeout=2.5) as client:
            for path in ("/api/version", "/api/tags"):
                response = client.get(f"{normalized}{path}", headers=headers)
                if response.status_code < 400:
                    reachable = True
                    break
                if response.status_code in {401, 403}:
                    reachable = True
                    break
    except Exception:
        reachable = False

    _ollama_availability_cache[cache_key] = (now, reachable)
    return reachable


class OllamaProvider(LLMProvider):
    """Ollama provider via WiiiChatModel at /v1 endpoint."""

    @property
    def name(self) -> str:
        return "ollama"

    def is_configured(self) -> bool:
        return bool(getattr(settings, "ollama_base_url", None))

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        if _ollama_cb is not None:
            if not _ollama_cb.is_available():
                return False
        return check_ollama_host_reachable()

    def create_instance(
        self,
        tier: str,
        thinking_budget: int = 0,
        include_thoughts: bool = False,
        temperature: float = 0.5,
        **kwargs: Any,
    ) -> BaseChatModel:
        model_name = kwargs.get("model_name") or kwargs.get("model")
        model = model_name or getattr(settings, "ollama_model", "qwen3:4b-instruct-2507-q4_K_M")

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

        model_kwargs: dict[str, Any] = {}

        # Ollama thinking for Qwen3/DeepSeek-R1
        thinks = thinking_budget > 0 or include_thoughts
        if _model_supports_thinking(model) and thinks:
            model_kwargs["extra_body"] = {"think": True}
            logger.info("[OLLAMA] Thinking mode enabled for %s", model)

        llm = WiiiChatModel(
            model=model,
            api_key=api_key,
            base_url=base_url_v1,
            temperature=temperature,
            model_kwargs=model_kwargs,
        )
        logger.info(
            "[OLLAMA] Created %s instance (model=%s, base_url=%s, thinking=%s)",
            tier.upper(), model, base_url_v1, bool(model_kwargs.get("extra_body")),
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
