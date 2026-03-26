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
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.engine.llm_provider_registry import create_provider, is_supported_provider
from app.engine.llm_timeout_policy import (
    TIMEOUT_PROFILE_BY_NAME,
    TIMEOUT_PROFILE_SETTINGS,
    loads_timeout_provider_overrides,
)

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

FAILOVER_MODE_AUTO = "auto"
FAILOVER_MODE_PINNED = "pinned"


@dataclass
class ResolvedLLMRoute:
    """Resolved primary/fallback runtime objects for one request."""

    provider: Optional[str]
    llm: BaseChatModel
    circuit_breaker: Any = None
    fallback_provider: Optional[str] = None
    fallback_llm: Optional[BaseChatModel] = None


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
    _provider_pools: Dict[str, Dict[str, BaseChatModel]] = {}
    _initialized: bool = False
    _active_provider: Optional[str] = None
    _fallback_provider: Optional[str] = None
    _providers: Dict[str, "LLMProvider"] = {}

    @classmethod
    def _get_provider_chain(cls) -> list[str]:
        """Return the effective provider order with the selected provider first."""
        configured = list(
            getattr(settings, "llm_failover_chain", ["google", "zhipu", "ollama", "openrouter"])
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
    def _normalize_provider(cls, provider: Optional[str]) -> Optional[str]:
        """Normalize request provider names and collapse ``auto`` to None."""
        if not provider:
            return None
        normalized = str(provider).strip().lower()
        if not normalized or normalized == "auto":
            return None
        return normalized

    @classmethod
    def _normalize_failover_mode(cls, failover_mode: Optional[str]) -> str:
        normalized = str(failover_mode or FAILOVER_MODE_AUTO).strip().lower()
        if normalized == FAILOVER_MODE_PINNED:
            return FAILOVER_MODE_PINNED
        return FAILOVER_MODE_AUTO

    @classmethod
    def _normalize_tier_key(cls, tier) -> str:
        """Map helper tiers to the shared pool keys."""
        tier_key = cls._resolve_tier(tier)
        if tier_key in [ThinkingTier.MINIMAL.value, ThinkingTier.OFF.value]:
            return ThinkingTier.LIGHT.value
        return tier_key

    @classmethod
    def _resolve_auto_primary_provider(cls) -> Optional[str]:
        """Prefer a provider that is currently selectable for auto mode.

        This lets auto-routing skip providers already known to be degraded
        (for example Google quota exhaustion) instead of spending multiple
        node hops timing out before failover finally engages.
        """
        try:
            from app.services.llm_selectability_service import (
                choose_best_runtime_provider,
            )

            best = choose_best_runtime_provider(
                preferred_provider=getattr(settings, "llm_provider", None) or cls._active_provider,
                provider_order=cls._get_request_provider_chain(),
                allow_degraded_fallback=False,
            )
            provider = cls._normalize_provider(best.provider if best else None)
            if provider:
                return provider
        except Exception as exc:
            logger.debug("[LLM_POOL] Auto provider preselection skipped: %s", exc)

        selectable_names = cls._get_selectable_provider_names()
        chain = cls._get_request_provider_chain()
        for provider_name in chain:
            normalized_name = cls._normalize_provider(provider_name)
            if selectable_names is not None and normalized_name not in selectable_names:
                continue
            provider = cls._ensure_provider(provider_name)
            if provider is None or not provider.is_configured() or not provider.is_available():
                continue
            return provider_name
        return None

    @classmethod
    def _get_selectable_provider_names(cls) -> Optional[set[str]]:
        """Return the current selectable providers from user-facing runtime truth."""
        try:
            from app.services.llm_selectability_service import (
                get_llm_selectability_snapshot,
            )

            return {
                provider
                for item in get_llm_selectability_snapshot()
                if item.state == "selectable"
                for provider in [cls._normalize_provider(item.provider)]
                if provider
            }
        except Exception as exc:
            logger.debug("[LLM_POOL] Selectable provider lookup skipped: %s", exc)
            return None

    @classmethod
    def _tag_runtime_metadata(
        cls,
        llm: BaseChatModel,
        *,
        provider_name: str,
        tier_key: str,
        requested_provider: Optional[str] = None,
    ) -> BaseChatModel:
        """Attach lightweight runtime metadata for downstream failover helpers."""
        try:
            setattr(llm, "_wiii_provider_name", provider_name)
            setattr(llm, "_wiii_tier_key", tier_key)
            setattr(llm, "_wiii_requested_provider", requested_provider)
        except Exception:
            logger.debug("[LLM_POOL] Could not tag runtime metadata for provider=%s", provider_name)
        return llm

    @classmethod
    def _ensure_provider(cls, provider_name: Optional[str]):
        """Ensure a provider instance exists in the registry."""
        normalized = cls._normalize_provider(provider_name)
        if not normalized:
            return None
        if normalized in cls._providers:
            return cls._providers[normalized]
        if not is_supported_provider(normalized):
            return None
        try:
            provider = create_provider(normalized)
            cls._providers[normalized] = provider
            logger.debug("[LLM_POOL] Lazily registered provider: %s", normalized)
            return provider
        except Exception as exc:
            logger.warning("[LLM_POOL] Failed to lazily register provider %s: %s", normalized, exc)
            return None

    @classmethod
    def _get_request_provider_chain(cls, provider: Optional[str] = None) -> list[str]:
        """Build request-scoped provider order with the requested provider first."""
        configured: list[str] = []
        for name in cls._get_provider_chain():
            if cls._ensure_provider(name) is not None and name not in configured:
                configured.append(name)

        requested = cls._normalize_provider(provider)
        primary = requested or cls._active_provider

        chain: list[str] = []
        if primary and cls._ensure_provider(primary) is not None:
            chain.append(primary)

        for name in configured:
            if name not in chain:
                chain.append(name)

        return chain

    @classmethod
    def _thinking_budget_for_tier(cls, tier_key: str) -> tuple[int, bool]:
        """Return thinking budget + thought flag for one tier."""
        thinking_budget = THINKING_BUDGETS.get(tier_key, 1024)
        include_thoughts = thinking_budget > 0
        return thinking_budget, include_thoughts

    @classmethod
    def _create_provider_instance(
        cls,
        provider_name: str,
        tier_key: str,
        *,
        requested_provider: Optional[str] = None,
    ) -> BaseChatModel | None:
        """Create and cache a provider-specific LLM instance on demand."""
        provider = cls._ensure_provider(provider_name)
        if provider is None or not provider.is_configured():
            return None

        provider_cache = cls._provider_pools.setdefault(provider_name, {})
        if tier_key in provider_cache:
            return provider_cache[tier_key]

        thinking_budget, include_thoughts = cls._thinking_budget_for_tier(tier_key)
        llm = provider.create_instance(
            tier=tier_key,
            thinking_budget=thinking_budget,
            include_thoughts=include_thoughts,
            temperature=0.5,
        )
        cls._attach_tracking_callback(llm, f"{provider_name}_{tier_key}")
        llm = cls._tag_runtime_metadata(
            llm,
            provider_name=provider_name,
            tier_key=tier_key,
            requested_provider=requested_provider,
        )
        provider_cache[tier_key] = llm
        return llm

    @classmethod
    def get_provider_instance(
        cls,
        provider_name: Optional[str],
        tier=None,
        *,
        allow_unavailable: bool = False,
        requested_provider: Optional[str] = None,
    ) -> BaseChatModel | None:
        """Return a provider-specific instance, creating one lazily when needed."""
        normalized_provider = cls._normalize_provider(provider_name)
        if not normalized_provider:
            return None

        tier_key = cls._normalize_tier_key(tier or ThinkingTier.MODERATE)
        provider = cls._ensure_provider(normalized_provider)
        if provider is None:
            return None
        if not allow_unavailable and not provider.is_available():
            return None

        if normalized_provider == cls._active_provider and tier_key in cls._pool:
            llm = cls._pool[tier_key]
            cls._provider_pools.setdefault(normalized_provider, {})[tier_key] = llm
            return cls._tag_runtime_metadata(
                llm,
                provider_name=normalized_provider,
                tier_key=tier_key,
                requested_provider=requested_provider,
            )

        if normalized_provider == cls._fallback_provider and tier_key in cls._fallback_pool:
            llm = cls._fallback_pool[tier_key]
            cls._provider_pools.setdefault(normalized_provider, {})[tier_key] = llm
            return cls._tag_runtime_metadata(
                llm,
                provider_name=normalized_provider,
                tier_key=tier_key,
                requested_provider=requested_provider,
            )

        try:
            return cls._create_provider_instance(
                normalized_provider,
                tier_key,
                requested_provider=requested_provider,
            )
        except Exception as exc:
            logger.warning(
                "[LLM_POOL] Provider-specific instance failed (%s/%s): %s",
                normalized_provider,
                tier_key,
                exc,
            )
            return None

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
        logger.info("[LLM_POOL] Initializing provider chain: %s (preferred=%s, failover=%s)",
                     chain, getattr(settings, 'llm_provider', '?'), getattr(settings, 'llm_failover_chain', '?'))
        for name in chain:
            if not is_supported_provider(name):
                logger.warning("[LLM_POOL] Skipping unsupported provider in chain: %s", name)
                continue
            try:
                cls._providers[name] = create_provider(name)
                logger.info("[LLM_POOL] Registered provider: %s", name)
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
                    llm = cls._tag_runtime_metadata(
                        llm,
                        provider_name=provider_name,
                        tier_key=tier_key,
                    )
                    cls._pool[tier_key] = llm
                    cls._provider_pools.setdefault(provider_name, {})[tier_key] = llm
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
                    llm = cls._tag_runtime_metadata(
                        llm,
                        provider_name=name,
                        tier_key=tier_key,
                    )
                    cls._fallback_pool[tier_key] = llm
                    cls._provider_pools.setdefault(name, {})[tier_key] = llm
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
                llm = cls._tag_runtime_metadata(
                    llm,
                    provider_name="google",
                    tier_key=tier_key,
                )
                cls._pool[tier_key] = llm
                cls._provider_pools.setdefault("google", {})[tier_key] = llm
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
            llm = cls._tag_runtime_metadata(
                llm,
                provider_name="google",
                tier_key=tier_key,
            )
            cls._pool[tier_key] = llm
            cls._provider_pools.setdefault("google", {})[tier_key] = llm
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
    def get_request_selectable_providers(cls) -> list[str]:
        """Return providers that should be exposed in request-level switchers."""
        if not cls._providers:
            cls._init_providers()

        providers: list[str] = []
        openrouter_mode = "openrouter.ai" in str(getattr(settings, "openai_base_url", "") or "").lower()

        for name in cls._get_request_provider_chain():
            provider = cls._ensure_provider(name)
            if provider is None or not provider.is_configured():
                continue

            # OpenAI and OpenRouter currently share the OpenAI-compatible config
            # surface, so expose only the truthy runtime mode.
            if name == "openrouter" and not openrouter_mode:
                continue
            if name == "openai" and openrouter_mode:
                continue
            if name not in providers:
                providers.append(name)

        return providers

    @classmethod
    def get_fallback_for_provider(
        cls,
        provider_name: Optional[str],
        tier=None,
        *,
        failover_mode: str = FAILOVER_MODE_AUTO,
        prefer_selectable_only: bool = False,
    ) -> tuple[Optional[str], Optional[BaseChatModel]]:
        """Return the next available provider/LLM for one request route."""
        if cls._normalize_failover_mode(failover_mode) == FAILOVER_MODE_PINNED:
            return None, None
        tier_key = cls._normalize_tier_key(tier or ThinkingTier.MODERATE)
        primary = cls._normalize_provider(provider_name) or cls._active_provider
        chain = cls._get_request_provider_chain(primary)
        selectable_now = cls._get_selectable_provider_names() if prefer_selectable_only else None

        seen_primary = primary is None
        for candidate in chain:
            if not seen_primary:
                if candidate == primary:
                    seen_primary = True
                continue
            if candidate == primary:
                continue
            if selectable_now is not None and candidate not in selectable_now:
                continue
            fallback_llm = cls.get_provider_instance(candidate, tier_key, allow_unavailable=False)
            if fallback_llm is not None:
                return candidate, fallback_llm

        if (
            provider_name is None
            and cls._fallback_provider
            and (selectable_now is None or cls._fallback_provider in selectable_now)
        ):
            fallback_llm = cls.get_provider_instance(cls._fallback_provider, tier_key, allow_unavailable=False)
            if fallback_llm is not None:
                return cls._fallback_provider, fallback_llm

        return None, None

    @classmethod
    def resolve_runtime_route(
        cls,
        provider_name: Optional[str],
        tier=None,
        *,
        failover_mode: str = FAILOVER_MODE_AUTO,
        prefer_selectable_fallback: bool = False,
    ) -> ResolvedLLMRoute:
        """Resolve a request-scoped primary/fallback route for failover helpers."""
        tier_key = cls._normalize_tier_key(tier or ThinkingTier.MODERATE)
        primary = cls._normalize_provider(provider_name)
        normalized_mode = cls._normalize_failover_mode(failover_mode)

        if primary:
            primary_llm = cls.get_provider_instance(
                primary,
                tier_key,
                allow_unavailable=True,
                requested_provider=primary,
            )
            if primary_llm is None:
                if normalized_mode == FAILOVER_MODE_PINNED:
                    raise ProviderUnavailableError(
                        provider=primary,
                        reason_code="busy",
                        message="Provider duoc chon hien khong san sang de xu ly yeu cau nay.",
                    )
                logger.warning(
                    "[LLM_POOL] Requested provider %s unavailable, falling back to auto route",
                    primary,
                )
                return cls.resolve_runtime_route(
                    None,
                    tier_key,
                    failover_mode=FAILOVER_MODE_AUTO,
                    prefer_selectable_fallback=prefer_selectable_fallback,
                )
            fallback_provider, fallback_llm = cls.get_fallback_for_provider(
                primary,
                tier_key,
                failover_mode=normalized_mode,
                prefer_selectable_only=prefer_selectable_fallback,
            )
            return ResolvedLLMRoute(
                provider=primary,
                llm=primary_llm,
                circuit_breaker=cls.get_circuit_breaker_for_provider(primary),
                fallback_provider=fallback_provider,
                fallback_llm=fallback_llm,
            )

        auto_primary = cls._resolve_auto_primary_provider()
        if auto_primary:
            auto_llm = cls.get_provider_instance(
                auto_primary,
                tier_key,
                allow_unavailable=False,
            )
            if auto_llm is not None:
                fallback_provider, fallback_llm = cls.get_fallback_for_provider(
                    auto_primary,
                    tier_key,
                    failover_mode=normalized_mode,
                    prefer_selectable_only=True,
                )
                return ResolvedLLMRoute(
                    provider=auto_primary,
                    llm=auto_llm,
                    circuit_breaker=cls.get_circuit_breaker_for_provider(auto_primary),
                    fallback_provider=fallback_provider,
                    fallback_llm=fallback_llm,
                )

        selectable_names = cls._get_selectable_provider_names()
        if selectable_names is not None:
            raise ProviderUnavailableError(
                provider="auto",
                reason_code="busy",
                message="Hien khong co provider nao dang san sang cho che do Tu dong.",
            )

        llm = cls.get(tier_key)
        active_provider = getattr(llm, "_wiii_provider_name", None) or cls._active_provider
        fallback_provider, fallback_llm = cls.get_fallback_for_provider(
            active_provider,
            tier_key,
            failover_mode=normalized_mode,
        )
        return ResolvedLLMRoute(
            provider=active_provider,
            llm=llm,
            circuit_breaker=cls.get_circuit_breaker_for_provider(active_provider),
            fallback_provider=fallback_provider,
            fallback_llm=fallback_llm,
        )

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
            "request_selectable_providers": (
                cls.get_request_selectable_providers() if cls._providers else []
            ),
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
    async def record_success_for_provider(cls, provider_name: Optional[str]) -> None:
        """Record a successful call for a specific runtime provider."""
        normalized = cls._normalize_provider(provider_name) or cls._active_provider
        if normalized and normalized in cls._providers:
            provider = cls._providers[normalized]
            if hasattr(provider, "record_success"):
                await provider.record_success()
                return
        if normalized in (None, "google") and _gemini_cb is not None:
            await _gemini_cb.record_success()

    @classmethod
    async def record_success(cls) -> None:
        """Record a successful API call for the active provider."""
        await cls.record_success_for_provider(cls._active_provider)

    @classmethod
    async def record_failure_for_provider(cls, provider_name: Optional[str]) -> None:
        """Record a failed call for a specific runtime provider."""
        normalized = cls._normalize_provider(provider_name) or cls._active_provider
        if normalized and normalized in cls._providers:
            provider = cls._providers[normalized]
            if hasattr(provider, "record_failure"):
                await provider.record_failure()
                return
        if normalized in (None, "google") and _gemini_cb is not None:
            await _gemini_cb.record_failure()

    @classmethod
    async def record_failure(cls) -> None:
        """Record a failed API call for the active provider."""
        await cls.record_failure_for_provider(cls._active_provider)

    @classmethod
    def get_circuit_breaker_for_provider(cls, provider_name: Optional[str]):
        """Get the circuit breaker associated with a specific provider."""
        normalized = cls._normalize_provider(provider_name) or cls._active_provider
        if normalized:
            provider = cls._ensure_provider(normalized)
            if provider is not None and hasattr(provider, "get_circuit_breaker"):
                return provider.get_circuit_breaker()
        if normalized in (None, "google"):
            return _gemini_cb
        return None

    @classmethod
    def get_circuit_breaker(cls):
        """
        Get the circuit breaker for the active provider.

        Returns:
            CircuitBreaker instance or None
        """
        return cls.get_circuit_breaker_for_provider(cls._active_provider)

    @classmethod
    def create_llm_with_model_for_provider(
        cls,
        provider_name: str,
        model_name: str,
        tier: ThinkingTier,
    ) -> BaseChatModel | None:
        """Create a dedicated provider-scoped LLM instance for a specific model name.

        Used for grouped admin profiles and per-agent model overrides.
        Caches by provider + model + tier to avoid re-creation.
        """
        normalized_provider = cls._normalize_provider(provider_name)
        if not normalized_provider:
            return None

        cache_key = f"_custom_{normalized_provider}_{model_name}_{tier.value}"
        if cache_key in cls._pool:
            return cls._pool[cache_key]

        thinking_budget = THINKING_BUDGETS.get(tier.value, 4096)
        include_thoughts = tier in (ThinkingTier.DEEP, ThinkingTier.MODERATE)

        try:
            provider = cls._ensure_provider(normalized_provider)
            if provider is None or not provider.is_configured():
                return None

            llm = provider.create_instance(
                tier=tier.value,
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts,
                temperature=0.5,
                model_name=model_name,
            )
            cls._attach_tracking_callback(llm, cache_key)
            llm = cls._tag_runtime_metadata(
                llm,
                provider_name=normalized_provider,
                tier_key=tier.value,
                requested_provider=normalized_provider,
            )
            cls._pool[cache_key] = llm
            logger.info(
                "[LLM_POOL] Created custom model LLM: provider=%s model=%s tier=%s budget=%d",
                normalized_provider,
                model_name,
                tier.value,
                thinking_budget,
            )
            return llm
        except Exception as exc:
            logger.warning(
                "[LLM_POOL] Custom model %s/%s failed: %s",
                normalized_provider,
                model_name,
                exc,
            )
            return None

    @classmethod
    def create_llm_with_model(cls, model_name: str, tier: ThinkingTier) -> BaseChatModel | None:
        """Backward-compatible helper for Google-only custom model overrides."""
        return cls.create_llm_with_model_for_provider("google", model_name, tier)

    @classmethod
    def reset(cls) -> None:
        """
        Reset the pool state (for testing purposes).

        Clears all instances, providers, and resets initialization flag.
        """
        cls._pool.clear()
        cls._fallback_pool.clear()
        cls._provider_pools.clear()
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

    tier = _EFFORT_TO_TIER.get(effort, default_tier)
    return LLMPool.get(tier)


def get_llm_for_provider(
    provider: Optional[str],
    effort: Optional[str] = None,
    default_tier: ThinkingTier = ThinkingTier.MODERATE,
    *,
    strict_pin: bool = False,
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
        tier = _EFFORT_TO_TIER.get(effort, default_tier)
    else:
        tier = default_tier

    normalized_provider = LLMPool._normalize_provider(provider)
    if normalized_provider and not strict_pin:
        provider_llm = LLMPool.get_provider_instance(
            normalized_provider,
            tier,
            allow_unavailable=True,
            requested_provider=None,
        )
        if provider_llm is not None:
            return provider_llm

    route = LLMPool.resolve_runtime_route(
        provider,
        tier,
        failover_mode=FAILOVER_MODE_PINNED if strict_pin else FAILOVER_MODE_AUTO,
    )
    return route.llm


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


_PRIMARY_TIMEOUT: float = 12.0  # legacy LIGHT-tier first-response timeout

_EFFORT_TO_TIER: dict[str, "ThinkingTier"] = {
    "low": ThinkingTier.LIGHT,
    "medium": ThinkingTier.MODERATE,
    "high": ThinkingTier.DEEP,
    "max": ThinkingTier.DEEP,
}

TIMEOUT_PROFILE_STRUCTURED = "structured"
TIMEOUT_PROFILE_BACKGROUND = "background"


def resolve_primary_timeout_seconds(
    *,
    tier: str = "moderate",
    timeout_profile: Optional[str] = None,
    provider: Optional[str] = None,
) -> float | None:
    """Resolve the first-response timeout for one invocation.

    This timeout only protects the initial LLM response path. It is not meant
    to cap the total workflow duration for streaming/background tasks.
    """
    normalized_profile = str(timeout_profile or "").strip().lower()
    if normalized_profile == TIMEOUT_PROFILE_BACKGROUND:
        profile_key = TIMEOUT_PROFILE_BY_NAME["background"]
    elif normalized_profile == TIMEOUT_PROFILE_STRUCTURED:
        profile_key = TIMEOUT_PROFILE_BY_NAME["structured"]
    else:
        normalized_tier = LLMPool._normalize_tier_key(tier)
        profile_key = TIMEOUT_PROFILE_BY_NAME.get(normalized_tier, "moderate_seconds")

    attr_name = TIMEOUT_PROFILE_SETTINGS[profile_key]
    normalized_provider = LLMPool._normalize_provider(provider)
    if normalized_provider:
        overrides = loads_timeout_provider_overrides(
            getattr(settings, "llm_timeout_provider_overrides", "{}")
        )
        override_value = overrides.get(normalized_provider, {}).get(profile_key)
        if override_value is not None:
            return override_value if override_value > 0 else None

    fallback_default = {
        "llm_primary_timeout_light_seconds": _PRIMARY_TIMEOUT,
        "llm_primary_timeout_moderate_seconds": 25.0,
        "llm_primary_timeout_deep_seconds": 45.0,
        "llm_primary_timeout_structured_seconds": 60.0,
        "llm_primary_timeout_background_seconds": 0.0,
    }[attr_name]
    timeout = float(getattr(settings, attr_name, fallback_default) or 0.0)
    return timeout if timeout > 0 else None


async def ainvoke_with_failover(
    llm,
    messages,
    *,
    tier: str = "moderate",
    provider: Optional[str] = None,
    failover_mode: str = FAILOVER_MODE_AUTO,
    prefer_selectable_fallback: bool = False,
    on_primary: Optional[Callable[[BaseChatModel], BaseChatModel]] = None,
    on_fallback: Optional[Callable[[BaseChatModel], BaseChatModel]] = None,
    on_switch: Optional[Callable[[str, str, str], Any]] = None,
    primary_timeout: Optional[float] = None,
    timeout_profile: Optional[str] = None,
):
    """Invoke LLM with automatic runtime failover on rate-limit errors.

    Three-layer defense (Google SRE / Netflix Hystrix pattern):

    1. **Circuit breaker fast-path** — if primary is already known to be
       down (CB open after 3 failures), skip directly to fallback (0ms).
    2. **Primary timeout** — caps the time to first response to
       ``primary_timeout`` seconds (resolved by tier/profile when omitted).
       Prevents the 31s+
       worst-case from Gemini SDK exponential backoff (1+2+4+8+16s).
    3. **Catch-and-switch** — if primary raises 429 or times out, record
       failure (updating CB for future requests) then retry on fallback.

    Args:
        llm: Primary LLM (may be wrapped, e.g. via with_structured_output).
        messages: Messages to send.
        tier: Tier key for fallback selection ("deep" | "moderate" | "light").
        provider: Requested runtime provider for this call. ``None`` /
                  ``"auto"`` uses the active route.
        on_primary: Optional callback to prepare the resolved primary LLM
                    before invocation. Needed when the resolved runtime route
                    swaps providers under auto mode and the caller needs to
                    re-apply wrappers such as ``with_structured_output``.
        on_fallback: Optional callback to prepare the raw fallback LLM
                     before retry.  Receives BaseChatModel, returns a
                     ready-to-invoke LLM.
                     Example: ``lambda fb: fb.with_structured_output(MySchema)``
        on_switch: Optional callback called when failover occurs.
                   Signature: ``(from_provider, to_provider, reason)``.
        primary_timeout: Explicit first-response timeout override in seconds.
                         Set 0 to disable.
        timeout_profile: Optional timeout profile ("structured" | "background").
                         Used only when ``primary_timeout`` is omitted.

    Returns:
        LLM response (same type as ``llm.ainvoke``).

    Raises:
        Original exception when the error is not rate-limit related
        or no fallback provider is available.
    """
    import asyncio

    normalized_failover_mode = LLMPool._normalize_failover_mode(failover_mode)
    route = LLMPool.resolve_runtime_route(
        provider,
        tier,
        failover_mode=normalized_failover_mode,
        prefer_selectable_fallback=prefer_selectable_fallback,
    )
    primary_llm = route.llm
    if on_primary is not None:
        primary_llm = on_primary(primary_llm)
    elif (
        getattr(llm, "_wiii_provider_name", None) == route.provider
        or route.provider is None
    ):
        primary_llm = llm

    timeout = (
        primary_timeout
        if primary_timeout is not None
        else resolve_primary_timeout_seconds(
            tier=tier,
            timeout_profile=timeout_profile,
            provider=route.provider,
        )
    )

    def _prepare_fallback():
        fallback_llm = route.fallback_llm
        if fallback_llm is None:
            return None
        if on_fallback is not None:
            fallback_llm = on_fallback(fallback_llm)
        return fallback_llm

    async def _emit_switch(reason: str) -> None:
        primary = route.provider or "unknown"
        fallback_name = route.fallback_provider or "unknown"
        logger.warning(
            "[LLM_FAILOVER] %s → %s (%s, tier=%s)",
            primary, fallback_name, reason, tier,
        )
        if on_switch is not None and route.fallback_provider:
            await on_switch(primary, fallback_name, reason)

    # ── Layer 1: Circuit breaker fast-path ──
    cb = route.circuit_breaker
    if cb is not None and not cb.is_available():
        fb = _prepare_fallback()
        if fb is not None:
            await _emit_switch("circuit_breaker_open")
            return await fb.ainvoke(messages)
        if normalized_failover_mode == FAILOVER_MODE_PINNED:
            raise ProviderUnavailableError(
                provider=route.provider or (provider or "unknown"),
                reason_code="busy",
                message="Provider duoc chon tam thoi ban hoac da cham gioi han.",
            )

    # ── Layer 2+3: Primary with timeout → catch-and-switch ──
    try:
        if timeout and timeout > 0:
            result = await asyncio.wait_for(primary_llm.ainvoke(messages), timeout=timeout)
        else:
            result = await primary_llm.ainvoke(messages)
        await asyncio.shield(LLMPool.record_success_for_provider(route.provider))
        return result
    except (asyncio.TimeoutError, Exception) as exc:
        is_timeout = isinstance(exc, asyncio.TimeoutError)
        if not is_timeout and not is_rate_limit_error(exc):
            raise

        # Record failure → trips CB after threshold
        await asyncio.shield(LLMPool.record_failure_for_provider(route.provider))

        fb = _prepare_fallback()
        if fb is None:
            if is_timeout:
                raise TimeoutError(
                    f"Primary LLM timed out after {timeout}s, no fallback available"
                )
            raise

        reason = f"timeout_{timeout}s" if is_timeout else type(exc).__name__
        await _emit_switch(reason)
        # Fallback also gets a timeout (2x primary) to prevent indefinite blocking
        fallback_timeout = timeout * 2 if (timeout and timeout > 0) else None
        if fallback_timeout:
            return await asyncio.wait_for(fb.ainvoke(messages), timeout=fallback_timeout)
        return await fb.ainvoke(messages)


# Re-export get_thinking_budget from llm_factory for convenience
# (already imported at top of file)
