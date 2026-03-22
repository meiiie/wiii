"""
LLM Provider Status Endpoint — Per-Request Provider Selection.

Exposes available LLM providers and their health status for the
frontend model switcher UI.
"""

import logging

from fastapi import APIRouter

from app.engine.llm_pool import LLMPool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])

PROVIDER_DISPLAY_NAMES = {
    "google": "Gemini",
    "zhipu": "GLM-5",
    "openai": "OpenAI",
    "ollama": "Ollama",
}


@router.get("/llm/status")
async def get_llm_status():
    """Return available LLM providers and their status."""
    stats = LLMPool.get_stats()
    providers = []
    for name in stats.get("providers_registered", []):
        provider = LLMPool.get_provider_info(name)
        providers.append({
            "id": name,
            "display_name": PROVIDER_DISPLAY_NAMES.get(name, name),
            "available": provider.is_available() if provider else False,
            "is_primary": name == stats.get("active_provider"),
            "is_fallback": name == stats.get("fallback_provider"),
        })
    return {"providers": providers}
