"""
LLM Singleton Pool - Multi-Provider Failover (Sprint 11, SOTA 2026)

Evolved from single-provider (Gemini-only) to multi-provider failover
inspired by OpenClaw's model-agnostic architecture.

Key Features:
- Creates only 3 LLM instances (DEEP, MODERATE, LIGHT) per provider
- Automatic failover: Google → OpenAI → Ollama (configurable chain)
- Per-provider circuit breakers for fast failure detection
- Backward compatible: all 18+ consumer files use BaseChatModel methods

Reference: MEMORY_OVERFLOW_SOTA_ANALYSIS.md, OpenClaw architecture
"""

import logging
from typing import Dict, Optional

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_provider_registry import create_provider, is_supported_provider

try:
    from app.core.resilience import get_circuit_breaker
    _gemini_cb = get_circuit_breaker("gemini", failure_threshold=3, recovery_timeout=30)
except Exception:
    _gemini_cb = None

logger = logging.getLogger(__name__)


# Import ThinkingTier from canonical source (llm_factory.py)
from app.engine.llm_factory import ThinkingTier

# Thinking budget mapping (uses config values via get_thinking_budget)
THINKING_BUDGETS = {
    ThinkingTier.DEEP.value: 8192,
    ThinkingTier.MODERATE.value: 4096,
    ThinkingTier.LIGHT.value: 1024,
    ThinkingTier.MINIMAL.value: 512,
    ThinkingTier.OFF.value: 0,
}


class LLMPool:
    """
    SOTA Pattern: Singleton LLM Pool with Multi-Provider Failover.

    Pre-creates 3 LLM instances (DEEP, MODERATE, LIGHT) at startup.
    All components share these instances via BaseChatModel interface.

    Failover chain (configurable via settings.llm_failover_chain):
        Google Gemini → Zhipu GLM-5 → OpenAI/OpenRouter → Ollama (local)

    Runtime failover: When primary provider hits rate limits (429),
    get_fallback(tier) returns a pre-created fallback instance from
    the next available provider. No 60s SDK retry wait.

    Memory Impact:
    - Before: 15+ LLM instances = ~600MB
    - After: 3+3 LLM instances = ~240MB (primary + fallback)

    Usage:
        from app.engine.llm_pool import LLMPool, get_llm_moderate

        # Initialize at startup
        LLMPool.initialize()

        # Get shared instance in components
        llm = get_llm_moderate()

        # Runtime failover (in graph nodes)
        fallback = LLMPool.get_fallback("moderate")
    """

    _pool: Dict[str, BaseChatModel] = {}
    _fallback_pool: Dict[str, BaseChatModel] = {}
    _initialized: bool = False
    _active_provider: Optional[str] = None
    _fallback_provider: Optional[str] = None
    _providers: Dict[str, "LLMProvider"] = {}

    @classmethod
    def _get_provider_chain(cls) -> list[str]:
        """Return the effective provider order with the selected provider first."""
        configured = list(
            getattr(settings, "llm_failover_chain", ["google", "openai", "ollama"])
        )
        preferred = getattr(settings, "llm_provider", "google")

        chain: list[str] = []
        if preferred:
            chain.append(preferred)

        for provider_name in configured:
            if provider_name not in chain:
                chain.append(provider_name)

        return chain

    @classmethod
    def _resolve_tier(cls, tier) -> str:
        """Resolve ThinkingTier enum or string to string value."""
        if isinstance(tier, ThinkingTier):
            return tier.value
        return tier

    @classmethod
    def _init_providers(cls) -> None:
        """
        Initialize provider instances from the failover chain config.

        Loads providers lazily — only instantiates providers that are
        in the configured failover chain.
        """
        if cls._providers:
            return

        chain = cls._get_provider_chain()
        for name in chain:
            if not is_supported_provider(name):
                logger.debug("[LLM_POOL] Skipping unsupported provider in chain: %s", name)
                continue
            try:
                cls._providers[name] = create_provider(name)
                logger.debug("[LLM_POOL] Registered provider: %s", name)
            except Exception as e:
                logger.warning("[LLM_POOL] Failed to register provider %s: %s", name, e)

        logger.info(
            "[LLM_POOL] Provider chain: %s (failover=%s)",
            list(cls._providers.keys()),
            'enabled' if settings.enable_llm_failover else 'disabled',
        )

    @classmethod
    def initialize(cls) -> None:
        """
        Pre-warm all LLM tiers at application startup.

        Called once in main.py lifespan.
        Creates 3 shared instances: DEEP, MODERATE, LIGHT.
        """
        if cls._initialized:
            logger.info("[LLM_POOL] Already initialized, skipping")
            return

        cls._init_providers()

        for tier in [ThinkingTier.DEEP, ThinkingTier.MODERATE, ThinkingTier.LIGHT]:
            cls._create_instance(tier)

        # Pre-create fallback instances for runtime failover
        cls._create_fallback_instances()

        cls._initialized = True
        fallback_info = f", fallback={cls._fallback_provider}" if cls._fallback_provider else ""
        logger.info(
            "[LLM_POOL] Initialized with %d primary + %d fallback instances "
            "(DEEP, MODERATE, LIGHT) -- provider=%s%s",
            len(cls._pool), len(cls._fallback_pool),
            cls._active_provider, fallback_info,
        )

    @classmethod
    def _create_instance(cls, tier) -> BaseChatModel:
        """
        Create a single LLM instance for the specified tier.

        Uses failover chain: tries each provider in order until one succeeds.
        Falls back to direct Gemini creation if no providers work.

        Args:
            tier: ThinkingTier enum or string value

        Returns:
            BaseChatModel instance
        """
        tier_key = cls._resolve_tier(tier)

        if tier_key in cls._pool:
            return cls._pool[tier_key]

        thinking_budget = THINKING_BUDGETS.get(tier_key, 1024)
        # v10: include_thoughts for ALL tiers — Gemini native thinking is primary path
        include_thoughts = thinking_budget > 0

        # --- Multi-Provider Failover ---
        should_use_provider_chain = cls._providers and (
            settings.enable_llm_failover or settings.llm_provider != "google"
        )

        if should_use_provider_chain:
            chain = cls._get_provider_chain()
            errors = []

            for provider_name in chain:
                provider = cls._providers.get(provider_name)
                if provider is None:
                    continue
                if not provider.is_available():
                    logger.debug("[LLM_POOL] Provider %s not available, skipping", provider_name)
                    continue

                try:
                    llm = provider.create_instance(
                        tier=tier_key,
                        thinking_budget=thinking_budget,
                        include_thoughts=include_thoughts,
                        temperature=0.5,
                    )
                    # Sprint 27: Attach token tracking callback
                    cls._attach_tracking_callback(llm, tier_key)
                    cls._pool[tier_key] = llm
                    cls._active_provider = provider_name
                    logger.info(
                        "[LLM_POOL] Created %s via %s (budget=%d, thoughts=%s)",
                        tier_key.upper(), provider_name, thinking_budget, include_thoughts,
                    )
                    return llm
                except Exception as e:
                    errors.append(f"{provider_name}: {e}")
                    logger.warning(
                        "[LLM_POOL] Provider %s failed for %s: %s",
                        provider_name, tier_key, e,
                    )
                    continue

            # All providers failed — raise with details
            error_detail = "; ".join(errors) if errors else "no providers available"
            raise RuntimeError(
                f"[LLM_POOL] All providers failed for tier {tier_key}: {error_detail}"
            )

        # --- Legacy single-provider path (failover disabled) ---
        return cls._create_instance_legacy(tier_key, thinking_budget, include_thoughts)

    @classmethod
    def _create_fallback_instances(cls) -> None:
        """
        Pre-create fallback LLM instances from the next available provider.

        Called during initialization. Creates 3 fallback instances (DEEP,
        MODERATE, LIGHT) from the first provider after the active one.
        These are used for runtime failover when the primary hits 429.
        """
        if not settings.enable_llm_failover or not cls._providers:
            return

        chain = cls._get_provider_chain()

        for name in chain:
            if name == cls._active_provider:
                continue
            provider = cls._providers.get(name)
            if provider is None or not provider.is_available():
                continue

            created = 0
            for tier in [ThinkingTier.DEEP, ThinkingTier.MODERATE, ThinkingTier.LIGHT]:
                tier_key = tier.value
                thinking_budget = THINKING_BUDGETS.get(tier_key, 1024)
                include_thoughts = thinking_budget > 0
                try:
                    llm = provider.create_instance(
                        tier=tier_key,
                        thinking_budget=thinking_budget,
                        include_thoughts=include_thoughts,
                        temperature=0.5,
                    )
                    cls._attach_tracking_callback(llm, f"fallback_{tier_key}")
                    cls._fallback_pool[tier_key] = llm
                    created += 1
                except Exception as e:
                    logger.warning(
                        "[LLM_POOL] Fallback %s/%s failed: %s", name, tier_key, e,
                    )

            if created > 0:
                cls._fallback_provider = name
                logger.info(
                    "[LLM_POOL] Pre-created %d fallback instances via %s",
                    created, name,
                )
                return  # Only need one fallback provider

    @classmethod
    def get_fallback(cls, tier=None) -> Optional[BaseChatModel]:
        """
        Get pre-created fallback LLM for runtime failover.

        Use when primary provider returns 429/rate-limit errors.
        Returns None if no fallback is available.

        Args:
            tier: ThinkingTier enum or string (default: MODERATE)

        Usage in graph nodes:
            try:
                result = await llm.ainvoke(messages)
            except Exception as e:
                if is_rate_limit_error(e):
                    fallback = LLMPool.get_fallback("moderate")
                    if fallback:
                        result = await fallback.ainvoke(messages)
        """
        if not cls._fallback_pool:
            return None

        if tier is None:
            tier = ThinkingTier.MODERATE

        tier_key = cls._resolve_tier(tier)
        if tier_key in [ThinkingTier.MINIMAL.value, ThinkingTier.OFF.value]:
            tier_key = ThinkingTier.LIGHT.value

        return cls._fallback_pool.get(tier_key)

    @classmethod
    def _create_instance_legacy(
        cls, tier_key: str, thinking_budget: int, include_thoughts: bool
    ) -> BaseChatModel:
        """
        Legacy single-provider creation (Gemini-only).

        Used when enable_llm_failover=False or as ultimate fallback.

        Behind ``enable_unified_providers`` gate, delegates to
        GeminiProvider (which picks ChatOpenAI or ChatGoogleGenerativeAI).
        """
        # Unified path: delegate to provider registry
        if getattr(settings, "enable_unified_providers", False):
            provider = create_provider("google")
            try:
                llm = provider.create_instance(
                    tier=tier_key,
                    thinking_budget=thinking_budget,
                    include_thoughts=include_thoughts,
                    temperature=0.5,
                )
                cls._attach_tracking_callback(llm, tier_key)
                cls._pool[tier_key] = llm
                cls._active_provider = "google"
                logger.info(
                    "[LLM_POOL] Created %s instance [unified] (budget=%d, thoughts=%s)",
                    tier_key.upper(), thinking_budget, include_thoughts,
                )
                return llm
            except Exception as e:
                logger.error("[LLM_POOL] Failed to create %s instance [unified]: %s", tier_key, e)
                raise

        # Legacy direct ChatGoogleGenerativeAI path
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm_kwargs = {
            "model": settings.google_model,
            "google_api_key": settings.google_api_key,
            "temperature": 0.5,
        }

        if settings.thinking_enabled and thinking_budget > 0:
            llm_kwargs["thinking_budget"] = thinking_budget
            if include_thoughts:
                llm_kwargs["include_thoughts"] = True

        try:
            llm = ChatGoogleGenerativeAI(**llm_kwargs)
            # Sprint 27: Attach token tracking callback
            cls._attach_tracking_callback(llm, tier_key)
            cls._pool[tier_key] = llm
            cls._active_provider = "google"
            logger.info(
                "[LLM_POOL] Created %s instance [legacy] (budget=%d, thoughts=%s)",
                tier_key.upper(), thinking_budget, include_thoughts,
            )
            return llm
        except Exception as e:
            logger.error("[LLM_POOL] Failed to create %s instance: %s", tier_key, e)
            raise

    @classmethod
    def _attach_tracking_callback(cls, llm: BaseChatModel, tier_key: str) -> None:
        """
        Attach token tracking callback to an LLM instance.

        Sprint 27: Enables automatic per-request token usage accounting
        via the ContextVar-based TokenTracker system.
        """
        try:
            from app.core.token_tracker import TokenTrackingCallback
            callback = TokenTrackingCallback(tier=tier_key)
            if hasattr(llm, "callbacks") and llm.callbacks is not None:
                llm.callbacks.append(callback)
            else:
                llm.callbacks = [callback]
        except Exception as e:
            logger.debug("[LLM_POOL] Token tracking callback not attached: %s", e)

    @classmethod
    def get_provider_info(cls, name: str):
        """Public API: get a registered provider by name."""
        if not cls._providers:
            cls._init_providers()
        return cls._providers.get(name)

    @classmethod
    def get(cls, tier=None) -> BaseChatModel:
        """
        Get a shared LLM instance for the specified tier.

        Args:
            tier: ThinkingTier enum or string value (default: MODERATE)

        Returns:
            Shared BaseChatModel instance (backward compatible with all consumers)
        """
        if tier is None:
            tier = ThinkingTier.MODERATE

        if not cls._initialized:
            cls.initialize()

        tier_key = cls._resolve_tier(tier)

        # Map MINIMAL/OFF to LIGHT for memory efficiency
        if tier_key in [ThinkingTier.MINIMAL.value, ThinkingTier.OFF.value]:
            tier_key = ThinkingTier.LIGHT.value

        if tier_key not in cls._pool:
            logger.warning("[LLM_POOL] Tier %s not in pool, creating on-demand", tier_key)
            cls._create_instance(tier_key)

        return cls._pool[tier_key]

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the pool has been initialized."""
        return cls._initialized

    @classmethod
    def get_active_provider(cls) -> Optional[str]:
        """Get the name of the currently active provider."""
        return cls._active_provider

    @classmethod
    def get_stats(cls) -> dict:
        """Get pool statistics for monitoring."""
        if not cls._providers:
            try:
                cls._init_providers()
            except Exception as e:
                logger.debug("[LLM_POOL] get_stats() could not init providers: %s", e)

        stats = {
            "initialized": cls._initialized,
            "instance_count": len(cls._pool),
            "fallback_count": len(cls._fallback_pool),
            "tiers": list(cls._pool.keys()),
            "active_provider": cls._active_provider,
            "fallback_provider": cls._fallback_provider,
            "failover_enabled": settings.enable_llm_failover,
            "provider_chain": cls._get_provider_chain(),
            "providers_registered": list(cls._providers.keys()),
        }
        # Include per-provider circuit breaker stats
        cb_stats = {}
        for name, provider in cls._providers.items():
            cb = provider.get_circuit_breaker() if hasattr(provider, "get_circuit_breaker") else None
            if cb is not None:
                cb_stats[name] = cb.get_stats()
        if cb_stats:
            stats["circuit_breakers"] = cb_stats
        # Legacy gemini CB
        if _gemini_cb is not None and "circuit_breakers" not in stats:
            stats["circuit_breaker"] = _gemini_cb.get_stats()
        return stats

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if any LLM provider is likely available.

        With failover enabled, returns True if ANY provider in the chain
        has a non-open circuit breaker. Without failover, checks Gemini only.

        Returns:
            True if at least one provider is available
        """
        if settings.enable_llm_failover and cls._providers:
            return any(p.is_available() for p in cls._providers.values())
        # Legacy: check Gemini circuit breaker
        if _gemini_cb is None:
            return True
        return _gemini_cb.is_available()

    @classmethod
    async def record_success(cls) -> None:
        """Record a successful API call for the active provider."""
        if cls._active_provider and cls._active_provider in cls._providers:
            provider = cls._providers[cls._active_provider]
            if hasattr(provider, "record_success"):
                await provider.record_success()
                return
        # Legacy fallback
        if _gemini_cb is not None:
            await _gemini_cb.record_success()

    @classmethod
    async def record_failure(cls) -> None:
        """Record a failed API call for the active provider."""
        if cls._active_provider and cls._active_provider in cls._providers:
            provider = cls._providers[cls._active_provider]
            if hasattr(provider, "record_failure"):
                await provider.record_failure()
                return
        # Legacy fallback
        if _gemini_cb is not None:
            await _gemini_cb.record_failure()

    @classmethod
    def get_circuit_breaker(cls):
        """
        Get the circuit breaker for the active provider.

        Returns:
            CircuitBreaker instance or None
        """
        if cls._active_provider and cls._active_provider in cls._providers:
            provider = cls._providers[cls._active_provider]
            if hasattr(provider, "get_circuit_breaker"):
                return provider.get_circuit_breaker()
        return _gemini_cb

    @classmethod
    def create_llm_with_model(cls, model_name: str, tier: ThinkingTier) -> BaseChatModel | None:
        """Create a dedicated LLM instance with a specific model name.

        Used for per-agent model overrides (e.g., code_studio_agent -> gemini-3.1-pro).
        Caches by model_name + tier to avoid re-creation.
        """
        cache_key = f"_custom_{model_name}_{tier.value}"
        if cache_key in cls._pool:
            return cls._pool[cache_key]

        thinking_budget = THINKING_BUDGETS.get(tier.value, 4096)
        include_thoughts = tier in (ThinkingTier.DEEP, ThinkingTier.MODERATE)

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm_kwargs = {
                "model": model_name,
                "google_api_key": settings.google_api_key,
                "temperature": 0.5,
            }
            if settings.thinking_enabled and thinking_budget > 0:
                llm_kwargs["thinking_budget"] = thinking_budget
                if include_thoughts:
                    llm_kwargs["include_thoughts"] = True

            llm = ChatGoogleGenerativeAI(**llm_kwargs)
            cls._attach_tracking_callback(llm, cache_key)
            cls._pool[cache_key] = llm
            logger.info(
                "[LLM_POOL] Created custom model LLM: %s tier=%s budget=%d",
                model_name, tier.value, thinking_budget,
            )
            return llm
        except Exception as exc:
            logger.warning("[LLM_POOL] Custom model %s failed: %s", model_name, exc)
            return None

    @classmethod
    def reset(cls) -> None:
        """
        Reset the pool state (for testing purposes).

        Clears all instances, providers, and resets initialization flag.
        """
        cls._pool.clear()
        cls._fallback_pool.clear()
        cls._providers.clear()
        cls._initialized = False
        cls._active_provider = None
        cls._fallback_provider = None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
# These are the primary interface for components to get LLM instances.
# Use these instead of create_llm() to ensure singleton pattern.
# Return type: BaseChatModel (backward compat — all consumers use .ainvoke/.astream)

def get_llm_deep() -> BaseChatModel:
    """
    Get shared DEEP tier LLM (8192 tokens thinking).

    Use for:
    - TutorAgent (teaching, explanations)
    - Student-facing responses requiring full explanation
    """
    return LLMPool.get(ThinkingTier.DEEP)


def get_llm_moderate() -> BaseChatModel:
    """
    Get shared MODERATE tier LLM (4096 tokens thinking).

    Use for:
    - RAGAgent (synthesis)
    - RetrievalGrader (document grading)
    - AnswerVerifier (verification)
    - GraderAgent (quality assessment)
    - KGBuilderAgent (entity extraction)
    """
    return LLMPool.get(ThinkingTier.MODERATE)


def get_llm_light() -> BaseChatModel:
    """
    Get shared LIGHT tier LLM (1024 tokens thinking).

    Use for:
    - QueryAnalyzer (query classification)
    - QueryRewriter (rewrite queries)
    - SupervisorAgent (routing)
    - GuardianAgent (safety check)
    - MemorySummarizer (summarization)
    - InsightExtractor (insight extraction)
    - MemoryConsolidator (consolidation)
    - MemoryManager (fact extraction)
    - FactExtractor (structured extraction)
    """
    return LLMPool.get(ThinkingTier.LIGHT)


def get_llm_for_effort(effort: Optional[str], default_tier: ThinkingTier = ThinkingTier.MODERATE) -> BaseChatModel:
    """
    Get LLM instance based on per-request thinking effort.

    Maps user-facing effort levels to internal ThinkingTier:
      - "low"    → LIGHT  (1024 tokens, fast/cheap)
      - "medium" → MODERATE (4096 tokens, balanced)
      - "high"   → DEEP (8192 tokens, thorough)
      - "max"    → DEEP (8192 tokens, deepest reasoning)
      - None     → default_tier (no override)

    Args:
        effort: Per-request thinking effort from ChatRequest.
        default_tier: Fallback tier when effort is None.

    Returns:
        BaseChatModel at the appropriate tier.

    Sprint 66: Adaptive Thinking Effort
    """
    if not effort:
        return LLMPool.get(default_tier)

    effort_to_tier = {
        "low": ThinkingTier.LIGHT,
        "medium": ThinkingTier.MODERATE,
        "high": ThinkingTier.DEEP,
        "max": ThinkingTier.DEEP,
    }
    tier = effort_to_tier.get(effort, default_tier)
    return LLMPool.get(tier)


def get_llm_for_provider(
    provider: Optional[str],
    effort: Optional[str] = None,
    default_tier: ThinkingTier = ThinkingTier.MODERATE,
) -> BaseChatModel:
    """
    Get LLM instance routed to a specific provider.

    Used for per-request provider selection (model switcher UI).
    Reuses existing pool/fallback instances — no new LLM creation.

    Args:
        provider: "auto" | "google" | "zhipu" | None (= auto)
        effort: Per-request thinking effort override.
        default_tier: Fallback tier when effort is None.
    """
    # Resolve tier from effort
    if effort:
        effort_to_tier = {
            "low": ThinkingTier.LIGHT,
            "medium": ThinkingTier.MODERATE,
            "high": ThinkingTier.DEEP,
            "max": ThinkingTier.DEEP,
        }
        tier = effort_to_tier.get(effort, default_tier)
    else:
        tier = default_tier

    if not provider or provider == "auto":
        return LLMPool.get(tier)

    # Requested provider is the active primary → use primary pool
    if provider == LLMPool._active_provider:
        return LLMPool.get(tier)

    # Requested provider is the fallback → use fallback pool
    if provider == LLMPool._fallback_provider:
        tier_key = LLMPool._resolve_tier(tier)
        fallback = LLMPool.get_fallback(tier_key)
        if fallback:
            return fallback

    # Unknown provider or unavailable — graceful fallback to primary
    return LLMPool.get(tier)


def get_llm_fallback(tier: Optional[str] = "moderate") -> Optional[BaseChatModel]:
    """
    Get pre-created fallback LLM for runtime failover.

    Returns None if no fallback is configured. Use in graph nodes:

        try:
            result = await llm.ainvoke(messages)
        except Exception as e:
            if is_rate_limit_error(e):
                fb = get_llm_fallback("moderate")
                if fb:
                    result = await fb.ainvoke(messages)
    """
    return LLMPool.get_fallback(tier)


def is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception is a rate-limit (429) error from any provider."""
    err_str = str(error).lower()
    return any(marker in err_str for marker in [
        "429",
        "resource_exhausted",
        "rate_limit",
        "rate limit",
        "quota",
        "too many requests",
    ])


# Re-export get_thinking_budget from llm_factory for convenience
# (already imported at top of file)
