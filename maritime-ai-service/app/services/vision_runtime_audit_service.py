"""Persisted live capability audit for vision runtime."""

from __future__ import annotations

import asyncio
import base64
import copy
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from PIL import Image, ImageDraw

from app.core.config import settings
from app.engine.llm_failover_runtime import classify_failover_reason_impl
from app.engine.vision_runtime import (
    VISION_RUNTIME_DEFAULT_TIMEOUT_SECONDS,
    VisionCapability,
    _provider_default_model,
    _provider_status,
    _run_google_vision_request,
    _run_openai_compatible_vision_request,
    _run_zhipu_layout_parsing_request,
)
from app.repositories.admin_runtime_settings_repository import (
    get_admin_runtime_settings_repository,
)
from app.services.vision_selectability_service import (
    VisionProviderSelectability,
    get_vision_selectability_snapshot,
)

logger = logging.getLogger(__name__)

VISION_RUNTIME_AUDIT_KEY = "vision_runtime_audit"
VISION_RUNTIME_AUDIT_DESCRIPTION = "Persisted vision runtime capability audit"
VISION_RUNTIME_AUDIT_SCHEMA_VERSION = 1
VISION_PROBE_TIMEOUT_SECONDS = 12.0
VISION_PROBE_OLLAMA_TIMEOUT_SECONDS = 30.0
VISION_PROBE_ZHIPU_OCR_TIMEOUT_SECONDS = 30.0

_SUPPORTED_CAPABILITIES: tuple[VisionCapability, ...] = (
    VisionCapability.VISUAL_DESCRIBE,
    VisionCapability.OCR_EXTRACT,
    VisionCapability.GROUNDED_VISUAL_ANSWER,
)
_SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "google",
    "openai",
    "openrouter",
    "ollama",
    "zhipu",
)


@dataclass(frozen=True)
class VisionRuntimeAuditRecord:
    payload: dict[str, Any]
    updated_at: Optional[datetime]
    persisted: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisionRuntimeAuditSummary:
    audit_updated_at: str | None
    last_live_probe_at: str | None
    audit_persisted: bool
    audit_warnings: tuple[str, ...]
    provider_state: dict[str, dict[str, Any]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _capability_recovered_since_probe(capability_state: Mapping[str, Any]) -> bool:
    probe_attempt_at = _parse_iso(capability_state.get("last_probe_attempt_at"))
    runtime_observation_at = _parse_iso(capability_state.get("last_runtime_observation_at"))
    runtime_success_at = _parse_iso(capability_state.get("last_runtime_success_at"))
    probe_success_at = _parse_iso(capability_state.get("last_probe_success_at"))
    probe_error = str(capability_state.get("last_probe_error") or "").strip()
    if runtime_success_at is None or runtime_observation_at is None or probe_attempt_at is None:
        return False
    if runtime_success_at < probe_attempt_at:
        return False
    if runtime_success_at < runtime_observation_at:
        return False
    if probe_success_at is not None and probe_success_at >= runtime_success_at:
        return False
    return bool(probe_error)


def _default_capability_state(capability: VisionCapability) -> dict[str, Any]:
    return {
        "capability": capability.value,
        "selected_model": None,
        "last_probe_attempt_at": None,
        "last_probe_success_at": None,
        "last_probe_error": None,
        "live_probe_note": None,
        "last_runtime_observation_at": None,
        "last_runtime_success_at": None,
        "last_runtime_error": None,
        "last_runtime_note": None,
        "last_runtime_source": None,
    }


def _default_provider_state(provider: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "last_probe_attempt_at": None,
        "last_probe_success_at": None,
        "last_probe_error": None,
        "last_runtime_observation_at": None,
        "last_runtime_success_at": None,
        "last_runtime_error": None,
        "last_runtime_note": None,
        "last_runtime_source": None,
        "degraded": False,
        "degraded_reasons": [],
        "capabilities": {
            capability.value: _default_capability_state(capability)
            for capability in _SUPPORTED_CAPABILITIES
        },
    }


def _default_payload() -> dict[str, Any]:
    return {
        "schema_version": VISION_RUNTIME_AUDIT_SCHEMA_VERSION,
        "audit_updated_at": None,
        "last_live_probe_at": None,
        "providers": {
            provider: _default_provider_state(provider)
            for provider in _SUPPORTED_PROVIDERS
        },
    }


def sanitize_vision_runtime_audit_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    clean = _default_payload()
    if not isinstance(payload, Mapping):
        return clean

    for field_name in ("audit_updated_at", "last_live_probe_at"):
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            clean[field_name] = value.strip()

    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, Mapping):
        return clean

    for provider in _SUPPORTED_PROVIDERS:
        raw_state = raw_providers.get(provider)
        if not isinstance(raw_state, Mapping):
            continue
        state = clean["providers"][provider]

        for field_name in (
            "last_probe_attempt_at",
            "last_probe_success_at",
            "last_probe_error",
            "last_runtime_observation_at",
            "last_runtime_success_at",
            "last_runtime_error",
            "last_runtime_note",
            "last_runtime_source",
        ):
            value = raw_state.get(field_name)
            if isinstance(value, str) and value.strip():
                state[field_name] = value.strip()
        degraded = raw_state.get("degraded")
        if isinstance(degraded, bool):
            state["degraded"] = degraded
        degraded_reasons = raw_state.get("degraded_reasons")
        if isinstance(degraded_reasons, list):
            state["degraded_reasons"] = [
                str(reason).strip() for reason in degraded_reasons if str(reason).strip()
            ]

        raw_capabilities = raw_state.get("capabilities")
        if not isinstance(raw_capabilities, Mapping):
            continue
        for capability in _SUPPORTED_CAPABILITIES:
            raw_capability = raw_capabilities.get(capability.value)
            if not isinstance(raw_capability, Mapping):
                continue
            capability_state = state["capabilities"][capability.value]
            model_name = raw_capability.get("selected_model")
            if isinstance(model_name, str) and model_name.strip():
                capability_state["selected_model"] = model_name.strip()
            for field_name in (
                "last_probe_attempt_at",
                "last_probe_success_at",
                "last_probe_error",
                "live_probe_note",
                "last_runtime_observation_at",
                "last_runtime_success_at",
                "last_runtime_error",
                "last_runtime_note",
                "last_runtime_source",
            ):
                value = raw_capability.get(field_name)
                if isinstance(value, str) and value.strip():
                    capability_state[field_name] = value.strip()

    return clean


def get_persisted_vision_runtime_audit() -> Optional[VisionRuntimeAuditRecord]:
    repo = get_admin_runtime_settings_repository()
    record = repo.get_settings(VISION_RUNTIME_AUDIT_KEY)
    if record is None:
        return None
    return VisionRuntimeAuditRecord(
        payload=sanitize_vision_runtime_audit_payload(record.settings),
        updated_at=record.updated_at,
        persisted=True,
    )


def persist_vision_runtime_audit_snapshot(snapshot: Mapping[str, Any]) -> Optional[VisionRuntimeAuditRecord]:
    repo = get_admin_runtime_settings_repository()
    clean = sanitize_vision_runtime_audit_payload(snapshot)
    record = repo.upsert_settings(
        VISION_RUNTIME_AUDIT_KEY,
        clean,
        description=VISION_RUNTIME_AUDIT_DESCRIPTION,
    )
    if record is None:
        return VisionRuntimeAuditRecord(
            payload=clean,
            updated_at=_utcnow(),
            persisted=False,
            warnings=(
                "Could not persist vision runtime audit to admin_runtime_settings.",
            ),
        )
    return VisionRuntimeAuditRecord(
        payload=sanitize_vision_runtime_audit_payload(record.settings),
        updated_at=record.updated_at,
        persisted=True,
    )


def _current_audit_payload() -> dict[str, Any]:
    existing = get_persisted_vision_runtime_audit()
    if existing and existing.payload:
        return copy.deepcopy(existing.payload)
    return _default_payload()


def build_vision_runtime_audit_summary() -> VisionRuntimeAuditSummary:
    record = get_persisted_vision_runtime_audit()
    if record is None:
        payload = _default_payload()
        return VisionRuntimeAuditSummary(
            audit_updated_at=payload["audit_updated_at"],
            last_live_probe_at=payload["last_live_probe_at"],
            audit_persisted=False,
            audit_warnings=(),
            provider_state=payload["providers"],
        )
    return VisionRuntimeAuditSummary(
        audit_updated_at=record.payload.get("audit_updated_at"),
        last_live_probe_at=record.payload.get("last_live_probe_at"),
        audit_persisted=record.persisted,
        audit_warnings=record.warnings,
        provider_state=record.payload.get("providers", {}),
    )


def build_vision_runtime_provider_statuses(
    snapshot: list[VisionProviderSelectability] | None = None,
) -> list[dict[str, Any]]:
    base_snapshot = snapshot if snapshot is not None else get_vision_selectability_snapshot()
    audit = build_vision_runtime_audit_summary()
    provider_state = audit.provider_state

    enriched: list[dict[str, Any]] = []
    for provider in base_snapshot:
        payload = provider.to_dict()
        audit_state = provider_state.get(provider.provider, {})
        payload["last_probe_attempt_at"] = audit_state.get("last_probe_attempt_at")
        payload["last_probe_success_at"] = audit_state.get("last_probe_success_at")
        payload["last_probe_error"] = audit_state.get("last_probe_error")
        payload["last_runtime_observation_at"] = audit_state.get("last_runtime_observation_at")
        payload["last_runtime_success_at"] = audit_state.get("last_runtime_success_at")
        payload["last_runtime_error"] = audit_state.get("last_runtime_error")
        payload["last_runtime_note"] = audit_state.get("last_runtime_note")
        payload["last_runtime_source"] = audit_state.get("last_runtime_source")
        payload["degraded"] = bool(audit_state.get("degraded", False))
        payload["degraded_reasons"] = list(audit_state.get("degraded_reasons", []))
        payload["recovered"] = False
        payload["recovered_reasons"] = []

        capability_state = audit_state.get("capabilities", {})
        payload["capabilities"] = []
        recovered_labels: list[str] = []
        for capability in provider.capabilities:
            if hasattr(capability, "to_dict"):
                capability_payload = capability.to_dict()
                capability_key = getattr(capability, "capability", capability_payload.get("capability"))
            elif isinstance(capability, Mapping):
                capability_payload = dict(capability)
                capability_key = capability_payload.get("capability")
            else:
                continue
            capability_audit = capability_state.get(capability_key, {})
            capability_payload["last_probe_attempt_at"] = capability_audit.get("last_probe_attempt_at")
            capability_payload["last_probe_success_at"] = capability_audit.get("last_probe_success_at")
            capability_payload["last_probe_error"] = capability_audit.get("last_probe_error")
            capability_payload["live_probe_note"] = capability_audit.get("live_probe_note")
            capability_payload["last_runtime_observation_at"] = capability_audit.get("last_runtime_observation_at")
            capability_payload["last_runtime_success_at"] = capability_audit.get("last_runtime_success_at")
            capability_payload["last_runtime_error"] = capability_audit.get("last_runtime_error")
            capability_payload["last_runtime_note"] = capability_audit.get("last_runtime_note")
            capability_payload["last_runtime_source"] = capability_audit.get("last_runtime_source")
            recovered = _capability_recovered_since_probe(capability_audit)
            capability_payload["recovered"] = recovered
            capability_payload["recovered_label"] = (
                "Runtime da hoi phuc sau probe" if recovered else None
            )
            if recovered:
                recovered_labels.append(str(capability_payload.get("display_name") or capability_key))
            payload["capabilities"].append(capability_payload)
        payload["recovered"] = bool(recovered_labels)
        payload["recovered_reasons"] = recovered_labels
        enriched.append(payload)
    return enriched


def _truncate_runtime_note(value: str | None, *, limit: int = 200) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    compact = " ".join(text.split())
    return compact[:limit]


def record_vision_runtime_observation(
    *,
    provider: str,
    capability: VisionCapability,
    success: bool,
    model_name: str | None = None,
    note: str | None = None,
    error: str | None = None,
    source: str = "runtime_call",
) -> VisionRuntimeAuditRecord | None:
    if provider not in _SUPPORTED_PROVIDERS:
        return get_persisted_vision_runtime_audit()

    payload = _current_audit_payload()
    now = _utcnow()
    now_iso = _iso(now)
    provider_payload = payload["providers"].setdefault(provider, _default_provider_state(provider))
    capability_payload = provider_payload["capabilities"].setdefault(
        capability.value,
        _default_capability_state(capability),
    )

    normalized_note = _truncate_runtime_note(note)
    normalized_error = _truncate_runtime_note(error)
    selected_model = model_name or _provider_default_model(provider, capability)

    provider_payload["last_runtime_observation_at"] = now_iso
    provider_payload["last_runtime_source"] = source
    capability_payload["selected_model"] = selected_model
    capability_payload["last_runtime_observation_at"] = now_iso
    capability_payload["last_runtime_source"] = source

    if success:
        provider_payload["last_runtime_success_at"] = now_iso
        provider_payload["last_runtime_error"] = None
        provider_payload["last_runtime_note"] = normalized_note
        capability_payload["last_runtime_success_at"] = now_iso
        capability_payload["last_runtime_error"] = None
        capability_payload["last_runtime_note"] = normalized_note
    else:
        provider_payload["last_runtime_error"] = normalized_error or "Vision runtime call failed."
        provider_payload["last_runtime_note"] = normalized_note
        capability_payload["last_runtime_error"] = normalized_error or "Vision runtime call failed."
        capability_payload["last_runtime_note"] = normalized_note

    payload["audit_updated_at"] = now_iso
    return persist_vision_runtime_audit_snapshot(payload)


def _make_probe_image() -> str:
    image = Image.new("RGB", (220, 96), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 210, 86), outline="black", width=2)
    draw.text((82, 34), "OK", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _probe_prompt(capability: VisionCapability) -> str:
    if capability == VisionCapability.OCR_EXTRACT:
        return "Doc ky van ban trong anh nay va tra ve dung 1 dong ngan."
    if capability == VisionCapability.GROUNDED_VISUAL_ANSWER:
        return "Trong anh co chu gi? Tra loi rat ngan gon bang tieng Viet."
    return "Mo ta ngan gon anh nay bang 1 cau tieng Viet."


def _probe_timeout_seconds(provider: str, capability: VisionCapability) -> float:
    configured = float(
        getattr(settings, "vision_timeout_seconds", VISION_RUNTIME_DEFAULT_TIMEOUT_SECONDS)
        or VISION_RUNTIME_DEFAULT_TIMEOUT_SECONDS
    )
    if provider == "ollama":
        return min(configured, VISION_PROBE_OLLAMA_TIMEOUT_SECONDS)
    if provider == "zhipu" and capability == VisionCapability.OCR_EXTRACT:
        return min(configured, VISION_PROBE_ZHIPU_OCR_TIMEOUT_SECONDS)
    return min(configured, VISION_PROBE_TIMEOUT_SECONDS)


async def _probe_capability(provider: str, capability: VisionCapability) -> tuple[bool, str | None]:
    status = _provider_status(provider, capability)
    if not status.available or not status.model_name:
        return False, status.reason_label or status.reason_code or "Provider currently unavailable."

    image_base64 = _make_probe_image()
    timeout_value = _probe_timeout_seconds(provider, capability)
    try:
        async with asyncio.timeout(timeout_value):
            if provider == "google":
                text = await _run_google_vision_request(
                    model_name=status.model_name,
                    prompt=_probe_prompt(capability),
                    image_base64=image_base64,
                    media_type="image/png",
                    temperature=0.0,
                    max_output_tokens=128,
                )
            elif provider == "zhipu" and capability == VisionCapability.OCR_EXTRACT:
                text = await _run_zhipu_layout_parsing_request(
                    model_name=status.model_name,
                    image_base64=image_base64,
                    media_type="image/png",
                    timeout_seconds=timeout_value,
                )
            elif provider in {"openai", "openrouter", "ollama", "zhipu"}:
                text = await _run_openai_compatible_vision_request(
                    provider=provider,
                    model_name=status.model_name,
                    prompt=_probe_prompt(capability),
                    image_base64=image_base64,
                    media_type="image/png",
                    temperature=0.0,
                    max_output_tokens=128,
                    resolved_base_url=status.resolved_base_url,
                )
            else:
                return False, "Provider vision chua ho tro live probe."
    except Exception as exc:
        timeout_context = timeout_value if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else None
        classified = classify_failover_reason_impl(error=exc, timeout_seconds=timeout_context)
        detail = classified.get("reason_label") or classified.get("detail") or str(exc)
        logger.warning("[VisionAudit] provider=%s capability=%s probe failed: %s", provider, capability.value, detail)
        return False, detail

    normalized = str(text or "").strip()
    if not normalized:
        return False, "Provider tra ve output rong cho probe vision."
    return True, normalized[:160]


async def run_live_vision_capability_probes(
    *,
    providers: list[str] | None = None,
) -> VisionRuntimeAuditRecord | None:
    payload = _current_audit_payload()
    target_providers = [
        provider
        for provider in (providers or list(_SUPPORTED_PROVIDERS))
        if provider in _SUPPORTED_PROVIDERS
    ]
    if not target_providers:
        return get_persisted_vision_runtime_audit()

    now = _utcnow()
    now_iso = _iso(now)
    for provider in target_providers:
        provider_payload = payload["providers"].setdefault(provider, _default_provider_state(provider))
        provider_payload["last_probe_attempt_at"] = now_iso
        provider_payload["last_probe_success_at"] = None
        provider_payload["last_probe_error"] = None
        provider_payload["degraded"] = False
        provider_payload["degraded_reasons"] = []

        provider_errors: list[str] = []
        provider_success = False

        for capability in _SUPPORTED_CAPABILITIES:
            capability_payload = provider_payload["capabilities"].setdefault(
                capability.value,
                _default_capability_state(capability),
            )
            status = _provider_status(provider, capability)
            capability_payload["selected_model"] = status.model_name or _provider_default_model(provider, capability)
            capability_payload["last_probe_attempt_at"] = now_iso
            capability_payload["last_probe_success_at"] = None
            capability_payload["last_probe_error"] = None
            capability_payload["live_probe_note"] = None

            if not status.available or not capability_payload["selected_model"]:
                detail = status.reason_label or status.reason_code or "Provider unavailable for this capability."
                capability_payload["last_probe_error"] = detail
                provider_errors.append(f"{capability.value}: {detail}")
                continue

            success, note = await _probe_capability(provider, capability)
            if success:
                capability_payload["last_probe_success_at"] = now_iso
                capability_payload["live_probe_note"] = note
                provider_success = True
            else:
                capability_payload["last_probe_error"] = note
                provider_errors.append(f"{capability.value}: {note}")

        if provider_success:
            provider_payload["last_probe_success_at"] = now_iso
        if provider_errors:
            provider_payload["last_probe_error"] = provider_errors[-1]
            provider_payload["degraded"] = True
            provider_payload["degraded_reasons"] = provider_errors

    payload["audit_updated_at"] = now_iso
    payload["last_live_probe_at"] = now_iso
    return persist_vision_runtime_audit_snapshot(payload)


__all__ = [
    "VISION_RUNTIME_AUDIT_KEY",
    "VISION_RUNTIME_AUDIT_DESCRIPTION",
    "VISION_RUNTIME_AUDIT_SCHEMA_VERSION",
    "VisionRuntimeAuditRecord",
    "VisionRuntimeAuditSummary",
    "build_vision_runtime_audit_summary",
    "build_vision_runtime_provider_statuses",
    "get_persisted_vision_runtime_audit",
    "persist_vision_runtime_audit_snapshot",
    "record_vision_runtime_observation",
    "run_live_vision_capability_probes",
    "sanitize_vision_runtime_audit_payload",
]
