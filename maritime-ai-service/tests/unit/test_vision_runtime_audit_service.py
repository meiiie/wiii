from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def test_build_vision_runtime_provider_statuses_merges_persisted_probe_state():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import (
        VisionRuntimeAuditSummary,
        build_vision_runtime_provider_statuses,
    )
    from app.services.vision_selectability_service import (
        VisionCapabilitySelectability,
        VisionProviderSelectability,
    )

    snapshot = [
        VisionProviderSelectability(
            provider="google",
            display_name="Gemini Vision",
            state="selectable",
            configured=True,
            available=True,
            in_failover_chain=True,
            is_default=True,
            is_active=True,
            selected_model="gemini-3.1-flash-lite-preview",
            reason_code=None,
            reason_label=None,
            capabilities=[
                VisionCapabilitySelectability(
                    capability=VisionCapability.VISUAL_DESCRIBE.value,
                    display_name="Mo ta anh",
                    available=True,
                    selected_model="gemini-3.1-flash-lite-preview",
                    lane_fit="general",
                    lane_fit_label="General vision",
                    reason_code=None,
                    reason_label=None,
                    resolved_base_url=None,
                )
            ],
        )
    ]

    summary = VisionRuntimeAuditSummary(
        audit_updated_at="2026-04-03T01:00:00+00:00",
        last_live_probe_at="2026-04-03T01:01:00+00:00",
        audit_persisted=True,
        audit_warnings=(),
        provider_state={
            "google": {
                "last_probe_attempt_at": "2026-04-03T01:00:00+00:00",
                "last_probe_success_at": "2026-04-03T01:01:00+00:00",
                "last_probe_error": None,
                "degraded": False,
                "degraded_reasons": [],
                "capabilities": {
                    "visual_describe": {
                        "last_probe_attempt_at": "2026-04-03T01:00:00+00:00",
                        "last_probe_success_at": "2026-04-03T01:01:00+00:00",
                        "last_probe_error": None,
                        "live_probe_note": "Mo ta hop le.",
                        "last_runtime_observation_at": "2026-04-03T01:02:00+00:00",
                        "last_runtime_success_at": "2026-04-03T01:02:00+00:00",
                        "last_runtime_error": None,
                        "last_runtime_note": "Runtime call thanh cong.",
                        "last_runtime_source": "runtime_call",
                    }
                },
            }
        },
    )

    with patch(
        "app.services.vision_runtime_audit_service.build_vision_runtime_audit_summary",
        return_value=summary,
    ):
        statuses = build_vision_runtime_provider_statuses(snapshot)

    assert statuses[0]["last_probe_success_at"] == "2026-04-03T01:01:00+00:00"
    assert statuses[0]["degraded"] is False
    assert statuses[0]["recovered"] is False
    assert statuses[0]["capabilities"][0]["live_probe_note"] == "Mo ta hop le."
    assert statuses[0]["capabilities"][0]["last_runtime_success_at"] == "2026-04-03T01:02:00+00:00"
    assert statuses[0]["capabilities"][0]["last_runtime_note"] == "Runtime call thanh cong."


def test_build_vision_runtime_provider_statuses_marks_recovered_when_runtime_beats_failed_probe():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import (
        VisionRuntimeAuditSummary,
        build_vision_runtime_provider_statuses,
    )
    from app.services.vision_selectability_service import (
        VisionCapabilitySelectability,
        VisionProviderSelectability,
    )

    snapshot = [
        VisionProviderSelectability(
            provider="zhipu",
            display_name="Zhipu Vision",
            state="selectable",
            configured=True,
            available=True,
            in_failover_chain=True,
            is_default=False,
            is_active=False,
            selected_model="glm-ocr",
            reason_code=None,
            reason_label=None,
            capabilities=[
                VisionCapabilitySelectability(
                    capability=VisionCapability.OCR_EXTRACT.value,
                    display_name="OCR / trich xuat",
                    available=True,
                    selected_model="glm-ocr",
                    lane_fit="specialist",
                    lane_fit_label="OCR specialist",
                    reason_code=None,
                    reason_label=None,
                    resolved_base_url="https://open.bigmodel.cn/api/paas/v4",
                )
            ],
        )
    ]

    summary = VisionRuntimeAuditSummary(
        audit_updated_at="2026-04-04T02:00:00+00:00",
        last_live_probe_at="2026-04-04T02:00:00+00:00",
        audit_persisted=True,
        audit_warnings=(),
        provider_state={
            "zhipu": {
                "last_probe_attempt_at": "2026-04-04T02:00:00+00:00",
                "last_probe_success_at": None,
                "last_probe_error": "ocr_extract: Provider tam thoi khong kha dung.",
                "last_runtime_success_at": "2026-04-04T02:01:00+00:00",
                "degraded": True,
                "degraded_reasons": ["ocr_extract: Provider tam thoi khong kha dung."],
                "last_runtime_observation_at": "2026-04-04T02:01:00+00:00",
                "capabilities": {
                    "ocr_extract": {
                        "last_probe_attempt_at": "2026-04-04T02:00:00+00:00",
                        "last_probe_success_at": None,
                        "last_probe_error": "Provider tam thoi khong kha dung.",
                        "last_runtime_observation_at": "2026-04-04T02:01:00+00:00",
                        "last_runtime_success_at": "2026-04-04T02:01:00+00:00",
                        "last_runtime_note": "OCR runtime da hoi phuc.",
                        "last_runtime_source": "runtime_call",
                    }
                },
            }
        },
    )

    with patch(
        "app.services.vision_runtime_audit_service.build_vision_runtime_audit_summary",
        return_value=summary,
    ):
        statuses = build_vision_runtime_provider_statuses(snapshot)

    assert statuses[0]["degraded"] is True
    assert statuses[0]["recovered"] is True
    assert statuses[0]["recovered_reasons"] == ["OCR / trich xuat"]
    assert statuses[0]["capabilities"][0]["recovered"] is True
    assert statuses[0]["capabilities"][0]["recovered_label"] == "Runtime da hoi phuc sau probe"


def test_build_vision_runtime_provider_statuses_does_not_mark_recovered_if_latest_runtime_observation_failed():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import (
        VisionRuntimeAuditSummary,
        build_vision_runtime_provider_statuses,
    )
    from app.services.vision_selectability_service import (
        VisionCapabilitySelectability,
        VisionProviderSelectability,
    )

    snapshot = [
        VisionProviderSelectability(
            provider="zhipu",
            display_name="Zhipu Vision",
            state="selectable",
            configured=True,
            available=True,
            in_failover_chain=True,
            is_default=False,
            is_active=False,
            selected_model="glm-ocr",
            reason_code=None,
            reason_label=None,
            capabilities=[
                VisionCapabilitySelectability(
                    capability=VisionCapability.OCR_EXTRACT.value,
                    display_name="OCR / trich xuat",
                    available=True,
                    selected_model="glm-ocr",
                    lane_fit="specialist",
                    lane_fit_label="OCR specialist",
                    reason_code=None,
                    reason_label=None,
                    resolved_base_url="https://open.bigmodel.cn/api/paas/v4",
                )
            ],
        )
    ]

    summary = VisionRuntimeAuditSummary(
        audit_updated_at="2026-04-04T02:10:00+00:00",
        last_live_probe_at="2026-04-04T02:00:00+00:00",
        audit_persisted=True,
        audit_warnings=(),
        provider_state={
            "zhipu": {
                "last_probe_attempt_at": "2026-04-04T02:00:00+00:00",
                "last_probe_success_at": None,
                "last_probe_error": "ocr_extract: Provider tam thoi khong kha dung.",
                "last_runtime_observation_at": "2026-04-04T02:05:00+00:00",
                "last_runtime_success_at": "2026-04-04T02:01:00+00:00",
                "last_runtime_error": "Provider tam thoi khong kha dung.",
                "degraded": True,
                "degraded_reasons": ["ocr_extract: Provider tam thoi khong kha dung."],
                "capabilities": {
                    "ocr_extract": {
                        "last_probe_attempt_at": "2026-04-04T02:00:00+00:00",
                        "last_probe_success_at": None,
                        "last_probe_error": "Provider tam thoi khong kha dung.",
                        "last_runtime_observation_at": "2026-04-04T02:05:00+00:00",
                        "last_runtime_success_at": "2026-04-04T02:01:00+00:00",
                        "last_runtime_error": "Provider tam thoi khong kha dung.",
                        "last_runtime_source": "runtime_call",
                    }
                },
            }
        },
    )

    with patch(
        "app.services.vision_runtime_audit_service.build_vision_runtime_audit_summary",
        return_value=summary,
    ):
        statuses = build_vision_runtime_provider_statuses(snapshot)

    assert statuses[0]["recovered"] is False
    assert statuses[0]["recovered_reasons"] == []
    assert statuses[0]["capabilities"][0]["recovered"] is False


def test_record_vision_runtime_observation_updates_runtime_fields():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import record_vision_runtime_observation

    persisted_payload = {}

    def _persist(snapshot):
        persisted_payload.update(snapshot)
        return SimpleNamespace(
            payload=snapshot,
            updated_at=datetime(2026, 4, 3, 1, 5, tzinfo=timezone.utc),
            persisted=True,
            warnings=(),
        )

    with patch(
        "app.services.vision_runtime_audit_service._current_audit_payload",
        return_value={
            "schema_version": 1,
            "audit_updated_at": None,
            "last_live_probe_at": None,
            "providers": {},
        },
    ), patch(
        "app.services.vision_runtime_audit_service.persist_vision_runtime_audit_snapshot",
        side_effect=_persist,
    ):
        record = record_vision_runtime_observation(
            provider="zhipu",
            capability=VisionCapability.OCR_EXTRACT,
            success=True,
            model_name="glm-ocr",
            note="OCR runtime thanh cong.",
        )

    assert record is not None
    capability_state = persisted_payload["providers"]["zhipu"]["capabilities"]["ocr_extract"]
    assert capability_state["selected_model"] == "glm-ocr"
    assert capability_state["last_runtime_success_at"] is not None
    assert capability_state["last_runtime_note"] == "OCR runtime thanh cong."
    assert capability_state["last_runtime_source"] == "runtime_call"


def test_persist_vision_runtime_audit_snapshot_returns_ephemeral_record_when_db_unavailable():
    from app.services.vision_runtime_audit_service import persist_vision_runtime_audit_snapshot

    repo = SimpleNamespace(upsert_settings=lambda *args, **kwargs: None)

    with patch(
        "app.services.vision_runtime_audit_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = persist_vision_runtime_audit_snapshot(
            {
                "schema_version": 1,
                "audit_updated_at": "2026-04-03T01:00:00+00:00",
                "last_live_probe_at": None,
                "providers": {},
            }
        )

    assert record is not None
    assert record.persisted is False
    assert record.payload["audit_updated_at"] == "2026-04-03T01:00:00+00:00"
    assert record.warnings


@pytest.mark.asyncio
async def test_run_live_vision_capability_probes_persists_probe_results():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import run_live_vision_capability_probes

    persisted_payload = {}

    def _persist(snapshot):
        persisted_payload.update(snapshot)
        return SimpleNamespace(
            payload=snapshot,
            updated_at=datetime(2026, 4, 3, 1, 5, tzinfo=timezone.utc),
            persisted=True,
            warnings=(),
        )

    def _provider_status(provider, capability):
        return SimpleNamespace(
            available=True,
            model_name="gemini-3.1-flash-lite-preview",
            reason_code=None,
            reason_label=None,
            resolved_base_url=None,
        )

    async def _probe(provider, capability):
        if capability == VisionCapability.OCR_EXTRACT:
            return False, "OCR probe fail."
        return True, f"{provider}:{capability.value}:ok"

    with patch(
        "app.services.vision_runtime_audit_service._current_audit_payload",
        return_value={
            "schema_version": 1,
            "audit_updated_at": None,
            "last_live_probe_at": None,
            "providers": {},
        },
    ), patch(
        "app.services.vision_runtime_audit_service._provider_status",
        side_effect=_provider_status,
    ), patch(
        "app.services.vision_runtime_audit_service._probe_capability",
        side_effect=_probe,
    ), patch(
        "app.services.vision_runtime_audit_service.persist_vision_runtime_audit_snapshot",
        side_effect=_persist,
    ):
        record = await run_live_vision_capability_probes(providers=["google"])

    assert record is not None
    google_state = persisted_payload["providers"]["google"]
    assert google_state["last_probe_success_at"] is not None
    assert google_state["degraded"] is True
    assert google_state["degraded_reasons"] == ["ocr_extract: OCR probe fail."]
    assert google_state["capabilities"]["visual_describe"]["live_probe_note"] == "google:visual_describe:ok"
    assert google_state["capabilities"]["ocr_extract"]["last_probe_error"] == "OCR probe fail."


@pytest.mark.asyncio
async def test_probe_capability_classifies_rate_limit_without_false_timeout():
    from app.engine.vision_runtime import VisionCapability
    from app.services.vision_runtime_audit_service import _probe_capability

    with patch(
        "app.services.vision_runtime_audit_service._provider_status",
        return_value=SimpleNamespace(
            available=True,
            model_name="gemini-3.1-flash-lite-preview",
            reason_code=None,
            reason_label=None,
            resolved_base_url=None,
        ),
    ), patch(
        "app.services.vision_runtime_audit_service._run_google_vision_request",
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded"),
    ):
        success, note = await _probe_capability("google", VisionCapability.VISUAL_DESCRIBE)

    assert success is False
    assert _ascii_fold(note or "") == "Provider vuot gioi han hoac dang bi quota/rate limit."


def test_probe_timeout_seconds_respects_lane_sla(monkeypatch):
    from app.engine.vision_runtime import VisionCapability
    from app.services import vision_runtime_audit_service as audit

    monkeypatch.setattr(audit.settings, "vision_timeout_seconds", 60.0, raising=False)

    assert audit._probe_timeout_seconds("google", VisionCapability.VISUAL_DESCRIBE) == 12.0
    assert audit._probe_timeout_seconds("ollama", VisionCapability.VISUAL_DESCRIBE) == 30.0
    assert audit._probe_timeout_seconds("zhipu", VisionCapability.OCR_EXTRACT) == 30.0


def test_probe_timeout_seconds_never_exceeds_operator_timeout(monkeypatch):
    from app.engine.vision_runtime import VisionCapability
    from app.services import vision_runtime_audit_service as audit

    monkeypatch.setattr(audit.settings, "vision_timeout_seconds", 8.0, raising=False)

    assert audit._probe_timeout_seconds("ollama", VisionCapability.VISUAL_DESCRIBE) == 8.0
    assert audit._probe_timeout_seconds("zhipu", VisionCapability.OCR_EXTRACT) == 8.0
