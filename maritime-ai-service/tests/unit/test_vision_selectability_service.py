from types import SimpleNamespace
from unittest.mock import patch


def _status(
    *,
    available: bool,
    model_name: str | None,
    lane_fit: str | None = None,
    lane_fit_label: str | None = None,
    reason_code: str | None = None,
    reason_label: str | None = None,
    resolved_base_url: str | None = None,
):
    return SimpleNamespace(
        available=available,
        model_name=model_name,
        lane_fit=lane_fit,
        lane_fit_label=lane_fit_label,
        reason_code=reason_code,
        reason_label=reason_label,
        resolved_base_url=resolved_base_url,
    )


def test_vision_selectability_snapshot_marks_active_provider_from_auto_chain():
    from app.engine.vision_runtime import VisionCapability
    from app.services import vision_selectability_service as mod

    patched_settings = SimpleNamespace(
        vision_provider="auto",
        vision_failover_chain=["google", "openai", "ollama"],
        google_api_key="google-key",
        google_model="gemini-3.1-flash-lite-preview",
        openai_api_key="openai-key",
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-4.1-mini",
        ollama_base_url="http://localhost:11434",
        ollama_model="llava:latest",
        zhipu_model="glm-5v",
        zhipu_api_key=None,
    )

    def provider_status(provider: str, capability: VisionCapability):
        if provider == "google":
            return _status(
                available=False,
                model_name="gemini-3.1-flash-lite-preview",
                reason_code="rate_limit",
                reason_label="Google vision dang bi gioi han.",
            )
        if provider == "openai":
            return _status(
                available=True,
                model_name="gpt-4.1-mini",
                lane_fit="general",
                lane_fit_label="General vision",
                resolved_base_url="https://api.openai.com/v1",
            )
        return _status(
            available=False,
            model_name="llava:latest",
            reason_code="model_missing",
            reason_label="Model vision local chua duoc cai tren Ollama.",
        )

    with patch.object(mod, "settings", patched_settings), patch(
        "app.engine.vision_runtime.settings",
        patched_settings,
    ), patch.object(
        mod, "_resolve_provider_order", return_value=["google", "openai", "ollama"]
    ), patch.object(mod, "_provider_status", side_effect=provider_status):
        mod.invalidate_vision_selectability_cache()
        snapshot = mod.get_vision_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    openai = next(item for item in snapshot if item.provider == "openai")

    assert google.available is False
    assert google.is_default is True
    assert google.reason_code == "rate_limit"
    assert openai.available is True
    assert openai.is_active is True
    assert openai.is_default is False
    assert any(cap.available for cap in openai.capabilities)


def test_vision_selectability_snapshot_reports_capability_specific_reason():
    from app.engine.vision_runtime import VisionCapability
    from app.services import vision_selectability_service as mod

    patched_settings = SimpleNamespace(
        vision_provider="ollama",
        vision_failover_chain=["ollama"],
        google_api_key=None,
        google_model="gemini-3.1-flash-lite-preview",
        openai_api_key=None,
        openai_base_url=None,
        openai_model="gpt-4.1-mini",
        ollama_base_url="http://localhost:11434",
        ollama_model="llava:latest",
        zhipu_model="glm-5v",
        zhipu_api_key=None,
    )

    def provider_status(provider: str, capability: VisionCapability):
        if provider != "ollama":
            return _status(
                available=False,
                model_name=None,
                reason_code="missing_api_key",
                reason_label="Thieu key.",
            )
        if capability == VisionCapability.OCR_EXTRACT:
            return _status(
                available=False,
                model_name="llava:latest",
                reason_code="model_missing",
                reason_label="Model vision local chua duoc cai tren Ollama.",
            )
        return _status(
            available=True,
            model_name="llava:latest",
            lane_fit="general" if capability != VisionCapability.OCR_EXTRACT else "fallback",
            lane_fit_label="General vision" if capability != VisionCapability.OCR_EXTRACT else "OCR fallback",
            resolved_base_url="http://localhost:11434",
        )

    with patch.object(mod, "settings", patched_settings), patch(
        "app.engine.vision_runtime.settings",
        patched_settings,
    ), patch.object(mod, "_resolve_provider_order", return_value=["ollama"]), patch.object(
        mod, "_provider_status", side_effect=provider_status
    ):
        mod.invalidate_vision_selectability_cache()
        snapshot = mod.get_vision_selectability_snapshot(force_refresh=True)

    ollama = next(item for item in snapshot if item.provider == "ollama")
    ocr = next(item for item in ollama.capabilities if item.capability == "ocr_extract")

    assert ollama.available is True
    assert ollama.is_default is True
    assert ollama.is_active is True
    assert ocr.available is False
    assert next(item for item in ollama.capabilities if item.capability == "visual_describe").lane_fit == "general"
    assert ocr.reason_code == "model_missing"
