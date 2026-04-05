"""
LLM Provider Status Endpoint — Per-Request Provider Selection.

Exposes available LLM providers and their health status for the
frontend model switcher UI.
"""

import logging

from fastapi import APIRouter

from app.services.llm_selectability_service import get_llm_selectability_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])

PROVIDER_DISPLAY_NAMES = {
    "google": "Gemini",
    "zhipu": "Zhipu GLM",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}


@router.get("/llm/status")
async def get_llm_status():
    """Return available LLM providers and their status."""
    providers = []
    for item in get_llm_selectability_snapshot():
        providers.append(
            {
                "id": item.provider,
                "display_name": item.display_name or PROVIDER_DISPLAY_NAMES.get(item.provider, item.provider),
                "available": item.available,
                "is_primary": item.is_primary,
                "is_fallback": item.is_fallback,
                "state": item.state,
                "reason_code": item.reason_code,
                "reason_label": item.reason_label,
                "selected_model": item.selected_model,
                "strict_pin": item.strict_pin,
                "verified_at": item.verified_at,
            }
        )
    return {"providers": providers}
