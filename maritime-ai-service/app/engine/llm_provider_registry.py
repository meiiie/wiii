"""Lightweight registry for supported LLM runtime providers."""

from __future__ import annotations

SUPPORTED_PROVIDER_NAMES: tuple[str, ...] = (
    "google",
    "openai",
    "openrouter",
    "ollama",
)
SUPPORTED_PROVIDER_NAME_SET = frozenset(SUPPORTED_PROVIDER_NAMES)


def get_supported_provider_names() -> tuple[str, ...]:
    """Return provider names in the canonical runtime order."""
    return SUPPORTED_PROVIDER_NAMES


def is_supported_provider(name: str) -> bool:
    """Return True when the provider name is known by the runtime."""
    return name in SUPPORTED_PROVIDER_NAME_SET


def get_provider_class(name: str):
    """Resolve a provider class lazily to avoid config import cycles."""
    if not is_supported_provider(name):
        raise ValueError(
            f"Unknown provider: {name}. Must be one of {list(SUPPORTED_PROVIDER_NAMES)}"
        )

    from app.engine.llm_providers import GeminiProvider, OllamaProvider, OpenAIProvider

    provider_map = {
        "google": GeminiProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenAIProvider,
        "ollama": OllamaProvider,
    }
    return provider_map[name]


def create_provider(name: str):
    """Instantiate a provider by canonical provider name."""
    provider_cls = get_provider_class(name)
    return provider_cls()
