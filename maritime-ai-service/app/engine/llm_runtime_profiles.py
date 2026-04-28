"""Runtime presets for pluggable LLM providers."""

from dataclasses import dataclass
from typing import Optional

from app.engine.model_catalog import (
    GOOGLE_DEEP_MODEL,
    GOOGLE_DEFAULT_MODEL,
    NVIDIA_DEFAULT_BASE_URL,
    NVIDIA_DEFAULT_MODEL,
    NVIDIA_DEFAULT_MODEL_ADVANCED,
    OPENAI_DEFAULT_MODEL,
    OPENAI_DEFAULT_MODEL_ADVANCED,
    OPENROUTER_DEFAULT_BASE_URL,
    OPENROUTER_DEFAULT_MODEL,
    OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ZHIPU_DEFAULT_MODEL,
    ZHIPU_DEFAULT_MODEL_ADVANCED,
)


@dataclass(frozen=True)
class RuntimeProviderPreset:
    provider: str
    failover_chain: tuple[str, ...]
    google_model: Optional[str] = None
    google_model_advanced: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    openai_model_advanced: Optional[str] = None
    openrouter_base_url: Optional[str] = None
    openrouter_model: Optional[str] = None
    openrouter_model_advanced: Optional[str] = None
    nvidia_base_url: Optional[str] = None
    nvidia_model: Optional[str] = None
    nvidia_model_advanced: Optional[str] = None
    zhipu_base_url: Optional[str] = None
    zhipu_model: Optional[str] = None
    zhipu_model_advanced: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_keep_alive: Optional[str] = None
ZHIPU_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
# Current local dev default: backend Docker container calls native host Ollama.
# If a team opts into the Docker Ollama profile, override this to http://ollama:11434.
OLLAMA_DEFAULT_BASE_URL = "http://host.docker.internal:11434"
OLLAMA_DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_DEFAULT_KEEP_ALIVE = "30m"

_PROVIDER_PRESETS: dict[str, RuntimeProviderPreset] = {
    "google": RuntimeProviderPreset(
        provider="google",
        failover_chain=("google", "zhipu", "ollama", "openrouter"),
        google_model=GOOGLE_DEFAULT_MODEL,
        google_model_advanced=GOOGLE_DEEP_MODEL,
    ),
    "openai": RuntimeProviderPreset(
        provider="openai",
        failover_chain=("openai", "google", "zhipu", "ollama"),
        openai_model=OPENAI_DEFAULT_MODEL,
        openai_model_advanced=OPENAI_DEFAULT_MODEL_ADVANCED,
    ),
    "openrouter": RuntimeProviderPreset(
        provider="openrouter",
        failover_chain=("openrouter", "google", "zhipu", "ollama"),
        openrouter_base_url=OPENROUTER_DEFAULT_BASE_URL,
        openrouter_model=OPENROUTER_DEFAULT_MODEL,
        openrouter_model_advanced=OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ),
    "nvidia": RuntimeProviderPreset(
        provider="nvidia",
        failover_chain=("nvidia",),
        nvidia_base_url=NVIDIA_DEFAULT_BASE_URL,
        nvidia_model=NVIDIA_DEFAULT_MODEL,
        nvidia_model_advanced=NVIDIA_DEFAULT_MODEL_ADVANCED,
    ),
    "zhipu": RuntimeProviderPreset(
        provider="zhipu",
        failover_chain=("zhipu", "google", "openrouter", "ollama"),
        zhipu_base_url=ZHIPU_DEFAULT_BASE_URL,
        zhipu_model=ZHIPU_DEFAULT_MODEL,
        zhipu_model_advanced=ZHIPU_DEFAULT_MODEL_ADVANCED,
    ),
    "ollama": RuntimeProviderPreset(
        provider="ollama",
        failover_chain=("ollama", "google", "zhipu", "openrouter"),
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
_KNOWN_DEFAULT_CHAINS.add(("google", "ollama", "openrouter"))
_KNOWN_DEFAULT_CHAINS.add(("openrouter", "ollama", "google"))
_KNOWN_DEFAULT_CHAINS.add(("ollama", "google", "openrouter"))
_KNOWN_DEFAULT_CHAINS.add(("ollama", "google", "zhipu", "openrouter"))


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
