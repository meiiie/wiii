"""
Wiii LLM Provider Abstraction Layer — Multi-Provider Failover (SOTA 2026).

Inspired by OpenClaw's model-agnostic architecture.
Supports: Google Gemini (primary), OpenAI/OpenRouter, Ollama (local).
"""

from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.gemini_provider import GeminiProvider
from app.engine.llm_providers.openai_provider import OpenAIProvider
from app.engine.llm_providers.ollama_provider import OllamaProvider
from app.engine.llm_providers.zhipu_provider import ZhipuProvider
from app.engine.llm_providers.vertex_provider import VertexAIProvider
from app.engine.llm_providers.unified_client import UnifiedLLMClient, ProviderConfig

__all__ = [
    "LLMProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "ZhipuProvider",
    "VertexAIProvider",
    "UnifiedLLMClient",
    "ProviderConfig",
]
