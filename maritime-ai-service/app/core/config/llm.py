"""LLMConfig — LLM provider settings (Gemini, OpenAI, Ollama)."""
from typing import Optional

from pydantic import BaseModel

from app.engine.llm_runtime_profiles import GOOGLE_DEFAULT_MODEL


class LLMConfig(BaseModel):
    """LLM provider settings — Gemini, OpenAI, Ollama."""
    provider: str = "ollama"
    failover_chain: list[str] = ["ollama", "google", "openrouter"]
    enable_failover: bool = True
    google_api_key: Optional[str] = None
    google_model: str = GOOGLE_DEFAULT_MODEL
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_model_advanced: str = "gpt-4o"
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
