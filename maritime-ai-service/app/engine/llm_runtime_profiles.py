"""Runtime presets for pluggable LLM providers."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RuntimeProviderPreset:
    provider: str
    failover_chain: tuple[str, ...]
    google_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    openai_model_advanced: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_keep_alive: Optional[str] = None


GOOGLE_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-oss-20b:free"
OPENROUTER_DEFAULT_MODEL_ADVANCED = "openai/gpt-oss-120b:free"
# Current local dev default: backend Docker container calls native host Ollama.
# If a team opts into the Docker Ollama profile, override this to http://ollama:11434.
OLLAMA_DEFAULT_BASE_URL = "http://host.docker.internal:11434"
OLLAMA_DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_DEFAULT_KEEP_ALIVE = "30m"

_PROVIDER_PRESETS: dict[str, RuntimeProviderPreset] = {
    "google": RuntimeProviderPreset(
        provider="google",
        failover_chain=("google", "ollama", "openrouter"),
        google_model=GOOGLE_DEFAULT_MODEL,
    ),
    "openai": RuntimeProviderPreset(
        provider="openai",
        failover_chain=("openai", "ollama", "google"),
    ),
    "openrouter": RuntimeProviderPreset(
        provider="openrouter",
        failover_chain=("openrouter", "ollama", "google"),
        openai_base_url=OPENROUTER_BASE_URL,
        openai_model=OPENROUTER_DEFAULT_MODEL,
        openai_model_advanced=OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ),
    "ollama": RuntimeProviderPreset(
        provider="ollama",
        failover_chain=("ollama", "google", "openrouter"),
        ollama_base_url=OLLAMA_DEFAULT_BASE_URL,
        ollama_model=OLLAMA_DEFAULT_MODEL,
        ollama_keep_alive=OLLAMA_DEFAULT_KEEP_ALIVE,
    ),
}

_LEGACY_PAID_OPENAI_MODELS = {
    "gpt-4o-mini",
    "gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
}

_KNOWN_DEFAULT_CHAINS = {
    tuple(preset.failover_chain) for preset in _PROVIDER_PRESETS.values()
}
_KNOWN_DEFAULT_CHAINS.add(("google", "openai", "ollama"))


def get_runtime_provider_preset(provider: str) -> RuntimeProviderPreset:
    return _PROVIDER_PRESETS[provider]


def should_apply_openrouter_defaults(model_name: Optional[str]) -> bool:
    if not model_name:
        return True
    return model_name.strip() in _LEGACY_PAID_OPENAI_MODELS


def is_known_default_provider_chain(chain: Optional[list[str] | tuple[str, ...]]) -> bool:
    if not chain:
        return False
    return tuple(chain) in _KNOWN_DEFAULT_CHAINS
