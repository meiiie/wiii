"""
Unified LLM Client — AsyncOpenAI SDK for OpenAI-compatible endpoints.

Sprint 55: Phase 1 — Runs alongside existing LangChain providers.
All major LLM providers (Gemini, OpenAI, Ollama) now expose OpenAI-compatible
endpoints. This module provides direct AsyncOpenAI SDK access for use cases
where LangChain wrappers are not needed (e.g., agentic loop, MCP tools).

Feature-gated: enable_unified_client=False by default.
LangChain providers remain untouched for LangGraph nodes.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single OpenAI-compatible provider."""

    name: str
    api_key: str
    base_url: str
    default_model: str
    models: Dict[str, str] = field(default_factory=dict)
    supports_thinking: bool = False
    thinking_param: str = ""

    def __post_init__(self):
        if not self.models:
            self.models = {
                "deep": self.default_model,
                "moderate": self.default_model,
                "light": self.default_model,
            }


class UnifiedLLMClient:
    """
    Singleton providing AsyncOpenAI clients per provider.

    Uses OpenAI-compatible endpoints for all providers:
    - Google Gemini: generativelanguage.googleapis.com/v1beta/openai/
    - OpenAI: api.openai.com/v1
    - Ollama: localhost:11434/v1

    Thread-safe: clients are created once at startup and reused.
    """

    _clients: Dict[str, "AsyncOpenAI"] = {}  # noqa: F821
    _configs: Dict[str, ProviderConfig] = {}
    _initialized: bool = False
    _primary_provider: Optional[str] = None

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize AsyncOpenAI clients for all configured providers.

        Called after LLMPool.initialize() during app startup,
        gated by settings.enable_unified_client.
        """
        from app.core.config import settings

        if not settings.enable_unified_client:
            logger.info("Unified LLM Client disabled (enable_unified_client=False)")
            return

        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning(
                "openai package not installed — UnifiedLLMClient unavailable. "
                "Install with: pip install openai>=1.40.0"
            )
            return

        cls._clients.clear()
        cls._configs.clear()
        cls._primary_provider = None

        configs = cls._build_provider_configs(settings)

        for config in configs:
            try:
                client = AsyncOpenAI(
                    api_key=config.api_key,
                    base_url=config.base_url,
                )
                cls._clients[config.name] = client
                cls._configs[config.name] = config
                logger.info(
                    "Unified client registered: %s (base_url=%s, model=%s)",
                    config.name, config.base_url, config.default_model
                )

                if cls._primary_provider is None:
                    cls._primary_provider = config.name

            except Exception as e:
                logger.warning(
                    "Failed to create unified client for %s: %s",
                    config.name, e
                )

        cls._initialized = True
        logger.info(
            "UnifiedLLMClient initialized: %d provider(s) (primary=%s)",
            len(cls._clients), cls._primary_provider
        )

    @classmethod
    def _build_provider_configs(cls, settings) -> list:
        """Build ProviderConfig list from settings, respecting failover chain order."""
        configs = []
        seen = set()

        for provider_name in settings.llm_failover_chain:
            if provider_name in seen:
                continue
            seen.add(provider_name)

            config = cls._config_for_provider(provider_name, settings)
            if config is not None:
                configs.append(config)

        return configs

    @classmethod
    def _config_for_provider(
        cls, name: str, settings
    ) -> Optional[ProviderConfig]:
        """Create ProviderConfig for a named provider, or None if not configured."""
        if name == "google":
            if not settings.google_api_key:
                logger.debug("Skipping google unified client: no API key")
                return None
            return ProviderConfig(
                name="google",
                api_key=settings.google_api_key,
                base_url=settings.google_openai_compat_url,
                default_model=settings.google_model,
                models={
                    "deep": settings.google_model,
                    "moderate": settings.google_model,
                    "light": settings.google_model,
                },
                supports_thinking=True,
                thinking_param="thinking_budget",
            )

        elif name == "openai":
            if not settings.openai_api_key:
                logger.debug("Skipping openai unified client: no API key")
                return None
            base_url = settings.openai_base_url or "https://api.openai.com/v1"
            return ProviderConfig(
                name="openai",
                api_key=settings.openai_api_key,
                base_url=base_url,
                default_model=settings.openai_model,
                models={
                    "deep": settings.openai_model_advanced,
                    "moderate": settings.openai_model,
                    "light": settings.openai_model,
                },
                supports_thinking=False,
                thinking_param="reasoning_effort",
            )

        elif name == "ollama":
            if not settings.ollama_base_url:
                logger.debug("Skipping ollama unified client: no base URL")
                return None
            base_url = settings.ollama_base_url.rstrip("/") + "/v1"
            # Sprint 59: Detect thinking support for Qwen3/DeepSeek-R1
            default_think = ["qwen3", "deepseek-r1", "qwq"]
            thinking_models = getattr(
                settings, "ollama_thinking_models", default_think,
            )
            model_lower = settings.ollama_model.lower()
            has_thinking = any(model_lower.startswith(p) for p in thinking_models)
            return ProviderConfig(
                name="ollama",
                api_key="ollama",
                base_url=base_url,
                default_model=settings.ollama_model,
                models={
                    "deep": settings.ollama_model,
                    "moderate": settings.ollama_model,
                    "light": settings.ollama_model,
                },
                supports_thinking=has_thinking,
                thinking_param="think",
            )

        elif name == "zhipu":
            zhipu_key = getattr(settings, "zhipu_api_key", None)
            if not zhipu_key:
                logger.debug("Skipping zhipu unified client: no API key")
                return None
            base_url = getattr(
                settings, "zhipu_base_url",
                "https://open.bigmodel.cn/api/paas/v4",
            )
            model = getattr(settings, "zhipu_model", "glm-5")
            model_adv = getattr(settings, "zhipu_model_advanced", "glm-5")
            return ProviderConfig(
                name="zhipu",
                api_key=zhipu_key,
                base_url=base_url,
                default_model=model,
                models={
                    "deep": model_adv,
                    "moderate": model,
                    "light": model,
                },
                supports_thinking=False,
                thinking_param="",
            )

        else:
            logger.debug("Unknown provider for unified client: %s", name)
            return None

    @classmethod
    def get_client(cls, provider: Optional[str] = None) -> "AsyncOpenAI":  # noqa: F821
        """
        Get AsyncOpenAI client for a provider.

        Args:
            provider: Provider name ("google", "openai", "ollama").
                     If None, returns the primary provider client.

        Returns:
            AsyncOpenAI client instance.

        Raises:
            RuntimeError: If not initialized or provider not available.
        """
        if not cls._initialized:
            raise RuntimeError(
                "UnifiedLLMClient not initialized. "
                "Call UnifiedLLMClient.initialize() first or enable via "
                "enable_unified_client=True"
            )

        target = provider or cls._primary_provider
        if target is None or target not in cls._clients:
            available = list(cls._clients.keys())
            raise RuntimeError(
                f"Provider '{target}' not available. "
                f"Available providers: {available}"
            )

        return cls._clients[target]

    @classmethod
    def get_config(cls, provider: Optional[str] = None) -> ProviderConfig:
        """Get ProviderConfig for a provider."""
        if not cls._initialized:
            raise RuntimeError("UnifiedLLMClient not initialized.")

        target = provider or cls._primary_provider
        if target is None or target not in cls._configs:
            available = list(cls._configs.keys())
            raise RuntimeError(
                f"Provider '{target}' not configured. "
                f"Available: {available}"
            )

        return cls._configs[target]

    @classmethod
    def get_model(cls, provider: Optional[str] = None, tier: str = "moderate") -> str:
        """
        Get model name for a provider and tier.

        Args:
            provider: Provider name (None = primary)
            tier: "deep", "moderate", or "light"

        Returns:
            Model name string.
        """
        config = cls.get_config(provider)
        return config.models.get(tier, config.default_model)

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the unified client has been initialized."""
        return cls._initialized

    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available provider names."""
        return list(cls._clients.keys())

    @classmethod
    def reset(cls) -> None:
        """Reset all state. Used in tests."""
        cls._clients.clear()
        cls._configs.clear()
        cls._initialized = False
        cls._primary_provider = None
