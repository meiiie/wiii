"""
LLM Factory - Centralized LLM Creation with Tiered Thinking

Provides create_llm() core factory and ThinkingTier enum.

Note: For new code, prefer the singleton pool:
    from app.engine.llm_pool import get_llm_deep, get_llm_moderate, get_llm_light

create_llm() is used internally by llm_pool and is not deprecated,
but direct usage from application code should use the pool interfaces.

4-Tier Thinking Strategy (Chain of Draft pattern):
- DEEP (8192): Teaching agents - requires full explanation
- MODERATE (4096): RAG synthesis - requires summarization
- LIGHT (1024): Quick check - basic self-check
- MINIMAL (512): Structured tasks - minimal buffer

Sprint 11: Returns BaseChatModel for multi-provider compatibility.
"""

from enum import Enum
from typing import Optional
import logging

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.engine.llm_provider_registry import create_provider, get_supported_provider_names
from app.engine.model_catalog import GOOGLE_DEEP_MODEL

logger = logging.getLogger(__name__)


# =============================================================================
# THINKING TIER ENUM
# =============================================================================

class ThinkingTier(Enum):
    """
    4-Tier Thinking Strategy.

    Values correspond to thinking_budget tokens.
    """
    DEEP = "deep"         # Teaching agents (tutor)
    MODERATE = "moderate" # RAG synthesis (rag_agent, grader)
    LIGHT = "light"       # Quick check (analyzer, verifier)
    MINIMAL = "minimal"   # Structured tasks (extraction, memory)
    DYNAMIC = "dynamic"   # Let Gemini auto-decide (-1)
    OFF = "off"           # Disabled (0) - use sparingly!


def get_thinking_budget(tier: ThinkingTier) -> int:
    """
    Get thinking budget for a tier from config.

    Args:
        tier: ThinkingTier enum value

    Returns:
        Token budget for thinking (0-24576, or -1 for dynamic)
    """
    if not settings.thinking_enabled:
        return 0

    budget_map = {
        ThinkingTier.DEEP: settings.thinking_budget_deep,
        ThinkingTier.MODERATE: settings.thinking_budget_moderate,
        ThinkingTier.LIGHT: settings.thinking_budget_light,
        ThinkingTier.MINIMAL: settings.thinking_budget_minimal,
        ThinkingTier.DYNAMIC: -1,
        ThinkingTier.OFF: 0,
    }

    return budget_map.get(tier, settings.thinking_budget_moderate)


# =============================================================================
# LLM FACTORY
# =============================================================================

def create_llm(
    tier: ThinkingTier = ThinkingTier.MODERATE,
    temperature: float = 0.7,
    include_thoughts: Optional[bool] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> BaseChatModel:
    """
    Factory function for creating LLM instances with proper thinking config.

    SOTA Pattern: Centralized LLM creation with configurable thinking.
    Supports explicit provider selection for multi-provider setups.

    Args:
        tier: Thinking tier (DEEP, MODERATE, LIGHT, MINIMAL, DYNAMIC, OFF)
        temperature: LLM temperature (0.0-2.0)
        include_thoughts: Include thought summaries in response (default from config)
        model: Override model name (default from config)
        provider: Explicit provider name ('google', 'openai', 'openrouter', 'ollama').
            Defaults to the configured runtime provider.

    Returns:
        BaseChatModel instance (Gemini, OpenAI, or Ollama)

    Note:
        Response format when include_thoughts=True (Gemini only):
        response.content = [
            {'type': 'thinking', 'thinking': '...'},  # Reasoning
            {'type': 'text', 'text': '...'}           # Answer
        ]

    Example:
        >>> llm = create_llm(tier=ThinkingTier.DEEP)
        >>> response = await llm.ainvoke(messages)
        >>> # Explicit provider
        >>> llm = create_llm(tier=ThinkingTier.MODERATE, provider="openai")
    """
    thinking_budget = get_thinking_budget(tier)

    # Default include_thoughts from config
    if include_thoughts is None:
        include_thoughts = settings.include_thought_summaries

    configured_provider = provider or getattr(settings, "llm_provider", "google")
    if not isinstance(configured_provider, str) or not configured_provider.strip():
        effective_provider = "google"
    else:
        effective_provider = configured_provider.strip().lower()

    # --- Explicit/configured provider selection (Sprint 11) ---
    if effective_provider != "google":
        try:
            p = create_provider(effective_provider)
            logger.info(
                "[LLM_FACTORY] Creating LLM via %s: tier=%s, budget=%d, include_thoughts=%s",
                effective_provider, tier.value, thinking_budget, include_thoughts
            )
            return p.create_instance(
                tier=tier.value,
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts,
                temperature=temperature,
            )
        except ValueError:
            raise ValueError(
                f"Unknown provider: {effective_provider}. Must be one of {list(get_supported_provider_names())}"
            ) from None
        except ImportError:
            logger.warning(
                "[LLM_FACTORY] Provider %s not available, falling back to Gemini",
                effective_provider,
            )

    # --- Default: Google Gemini via GeminiProvider (WiiiChatModel) ---
    p = create_provider("google")
    logger.info(
        "[LLM_FACTORY] Creating LLM via GeminiProvider: tier=%s, budget=%d",
        tier.value, thinking_budget,
    )
    return p.create_instance(
        tier=tier.value,
        thinking_budget=thinking_budget,
        include_thoughts=include_thoughts,
        temperature=temperature,
        model=model,
    )
