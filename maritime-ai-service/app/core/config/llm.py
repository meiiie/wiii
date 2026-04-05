"""LLMConfig — LLM provider settings (Gemini, OpenAI, Ollama)."""
from typing import Optional

from pydantic import BaseModel

from app.engine.model_catalog import (
    GOOGLE_DEEP_MODEL,
    GOOGLE_DEFAULT_MODEL,
    OPENAI_DEFAULT_MODEL,
    OPENAI_DEFAULT_MODEL_ADVANCED,
    OPENROUTER_DEFAULT_BASE_URL,
    OPENROUTER_DEFAULT_MODEL,
    OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ZHIPU_DEFAULT_MODEL,
    ZHIPU_DEFAULT_MODEL_ADVANCED,
)


class LLMConfig(BaseModel):
    """LLM provider settings — Gemini, OpenAI, Ollama."""
    provider: str = "google"
    failover_chain: list[str] = ["google", "zhipu", "ollama", "openrouter"]
    enable_failover: bool = True
    primary_timeout_light_seconds: float = 12.0
    primary_timeout_moderate_seconds: float = 25.0
    primary_timeout_deep_seconds: float = 45.0
    primary_timeout_structured_seconds: float = 60.0
    primary_timeout_background_seconds: float = 0.0
    stream_keepalive_interval_seconds: float = 15.0
    stream_idle_timeout_seconds: float = 0.0
    timeout_provider_overrides: dict[str, dict[str, float]] = {}
    google_api_key: Optional[str] = None
    google_model: str = GOOGLE_DEFAULT_MODEL
    google_model_advanced: str = GOOGLE_DEEP_MODEL
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: Optional[str] = OPENROUTER_DEFAULT_BASE_URL
    openai_model: str = OPENAI_DEFAULT_MODEL
    openai_model_advanced: str = OPENAI_DEFAULT_MODEL_ADVANCED
    openrouter_model: str = OPENROUTER_DEFAULT_MODEL
    openrouter_model_advanced: str = OPENROUTER_DEFAULT_MODEL_ADVANCED
    openrouter_model_fallbacks: list[str] = []
    openrouter_provider_order: list[str] = []
    openrouter_allowed_providers: list[str] = []
    openrouter_ignored_providers: list[str] = []
    openrouter_allow_fallbacks: Optional[bool] = None
    openrouter_require_parameters: Optional[bool] = None
    openrouter_data_collection: Optional[str] = None
    openrouter_zdr: Optional[bool] = None
    openrouter_provider_sort: Optional[str] = None
    ollama_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = "http://localhost:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_keep_alive: Optional[str] = "30m"
    ollama_thinking_models: list[str] = ["qwen3", "deepseek-r1", "qwq"]
    zhipu_api_key: Optional[str] = None
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = ZHIPU_DEFAULT_MODEL
    zhipu_model_advanced: str = ZHIPU_DEFAULT_MODEL_ADVANCED
