from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.llm_runtime_audit_service import LlmRuntimeAuditRecord


def _provider(*, configured: bool = True, available: bool = True):
    mock = MagicMock()
    mock.is_configured.return_value = configured
    mock.is_available.return_value = available
    return mock


def _audit_record(google_state: dict) -> LlmRuntimeAuditRecord:
    return LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-03-23T10:00:00+00:00",
            "last_live_probe_at": "2026-03-23T10:00:00+00:00",
            "providers": {
                "google": google_state,
                "zhipu": {"provider": "zhipu"},
                "openai": {"provider": "openai"},
                "openrouter": {"provider": "openrouter"},
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        persisted=True,
    )


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_configured_healthy_provider_is_selectable(mock_stats, mock_provider_info, mock_settings):
    from app.services.llm_selectability_service import get_llm_selectability_snapshot, invalidate_llm_selectability_cache

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google"],
        "active_provider": "google",
        "fallback_provider": "zhipu",
    }
    mock_provider_info.side_effect = lambda name: _provider(configured=(name == "google"), available=(name == "google"))

    google_state = {
        "provider": "google",
        "selected_model": "gemini-3.1-flash-lite-preview",
        "selected_model_in_catalog": True,
        "model_count": 3,
        "last_discovery_attempt_at": "2026-03-23T09:59:00+00:00",
        "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
        "last_live_probe_success_at": "2026-03-23T10:00:00+00:00",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
        "degraded_reasons": [],
    }

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=_audit_record(google_state),
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    assert google.state == "selectable"
    assert google.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_rate_limited_provider_is_disabled_busy(mock_stats, mock_provider_info, mock_settings):
    from app.services.llm_selectability_service import get_llm_selectability_snapshot, invalidate_llm_selectability_cache

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google"],
        "active_provider": "google",
        "fallback_provider": None,
    }
    mock_provider_info.side_effect = lambda name: _provider(configured=(name == "google"), available=True)

    google_state = {
        "provider": "google",
        "selected_model": "gemini-3.1-flash-lite-preview",
        "selected_model_in_catalog": True,
        "model_count": 3,
        "last_discovery_attempt_at": "2026-03-23T09:59:00+00:00",
        "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
        "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
        "degraded_reasons": ["Live capability probe failed."],
    }

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=_audit_record(google_state),
    ), patch(
        "app.services.llm_selectability_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 3, 23, 10, 1, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    assert google.state == "disabled"
    assert google.reason_code == "busy"


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_stale_busy_provider_recovers_to_selectable_when_runtime_available(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google"],
        "active_provider": "google",
        "fallback_provider": None,
    }
    mock_provider_info.side_effect = lambda name: _provider(configured=(name == "google"), available=True)

    google_state = {
        "provider": "google",
        "selected_model": "gemini-3.1-flash-lite-preview",
        "selected_model_in_catalog": True,
        "model_count": 3,
        "last_discovery_attempt_at": "2026-03-23T09:50:00+00:00",
        "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
        "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
        "degraded_reasons": ["Live capability probe failed."],
    }

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=_audit_record(google_state),
    ), patch(
        "app.services.llm_selectability_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 3, 23, 10, 20, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        mock_datetime.timezone = timezone
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    assert google.state == "selectable"
    assert google.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_probe_failed_capability_does_not_disable_otherwise_healthy_provider(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "zhipu"],
        "active_provider": "google",
        "fallback_provider": "zhipu",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "zhipu"}),
        available=(name in {"google", "zhipu"}),
    )

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-03-23T10:00:00+00:00",
            "last_live_probe_at": "2026-03-23T10:00:00+00:00",
            "providers": {
                "google": {"provider": "google"},
                "zhipu": {
                    "provider": "zhipu",
                    "selected_model": "glm-4.5-air",
                    "selected_model_in_catalog": True,
                    "model_count": 6,
                    "last_discovery_attempt_at": "2026-03-23T09:59:00+00:00",
                    "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
                    "last_live_probe_success_at": "2026-03-23T10:00:00+00:00",
                    "last_live_probe_error": "tool calling: timeout",
                    "tool_calling_supported": None,
                    "tool_calling_source": "probe_failed",
                    "structured_output_supported": True,
                    "structured_output_source": "live_probe",
                    "streaming_supported": True,
                    "streaming_source": "live_probe",
                    "degraded_reasons": ["Live capability probe failed."],
                },
                "openai": {"provider": "openai"},
                "openrouter": {"provider": "openrouter"},
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    zhipu = next(item for item in snapshot if item.provider == "zhipu")
    assert zhipu.state == "selectable"
    assert zhipu.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_missing_audit_does_not_hide_runtime_available_provider(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "zhipu"],
        "active_provider": "zhipu",
        "fallback_provider": None,
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "zhipu"}),
        available=(name == "zhipu"),
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=None,
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    zhipu = next(item for item in snapshot if item.provider == "zhipu")
    assert zhipu.state == "selectable"
    assert zhipu.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_empty_provider_audit_state_does_not_block_new_runtime_available_provider(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_settings.openrouter_model = "qwen/qwen3.6-plus:free"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "openrouter"],
        "active_provider": "google",
        "fallback_provider": "openrouter",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "openrouter"}),
        available=(name == "openrouter"),
    )

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-04-04T07:00:00+00:00",
            "last_live_probe_at": "2026-04-04T07:00:00+00:00",
            "providers": {
                "google": {
                    "provider": "google",
                    "selected_model": "gemini-3.1-flash-lite-preview",
                    "selected_model_in_catalog": True,
                    "model_count": 3,
                    "last_live_probe_attempt_at": "2026-04-04T07:00:00+00:00",
                },
                "zhipu": {"provider": "zhipu"},
                "openai": {"provider": "openai"},
                "openrouter": {"provider": "openrouter"},
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    openrouter = next(item for item in snapshot if item.provider == "openrouter")
    assert openrouter.state == "selectable"
    assert openrouter.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_changed_provider_model_ignores_stale_audit_until_new_probe(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_settings.openrouter_model = "qwen/qwen3.6-plus:free"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "openrouter"],
        "active_provider": "google",
        "fallback_provider": "openrouter",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "openrouter"}),
        available=(name == "openrouter"),
    )

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-04-04T07:48:08.962524+00:00",
            "last_live_probe_at": "2026-04-04T07:48:08.962524+00:00",
            "providers": {
                "google": {
                    "provider": "google",
                    "selected_model": "gemini-3.1-flash-lite-preview",
                    "selected_model_in_catalog": True,
                    "model_count": 3,
                    "last_live_probe_attempt_at": "2026-04-04T07:48:08.962524+00:00",
                },
                "zhipu": {"provider": "zhipu"},
                "openai": {"provider": "openai"},
                "openrouter": {
                    "provider": "openrouter",
                    "selected_model": "openai/gpt-oss-20b:free",
                    "selected_model_in_catalog": True,
                    "model_count": 2,
                    "last_runtime_observation_at": "2026-04-04T07:48:08.962524+00:00",
                    "last_runtime_error": "He thong dang xac minh trang thai runtime.",
                    "last_runtime_note": "chat_stream:error: requested provider openrouter unavailable (verifying).",
                    "streaming_supported": True,
                    "streaming_source": "static",
                },
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 4, 4, 7, 48, 8, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    openrouter = next(item for item in snapshot if item.provider == "openrouter")
    assert openrouter.state == "selectable"
    assert openrouter.reason_code is None
    assert openrouter.selected_model == "qwen/qwen3.6-plus:free"
    assert openrouter.verified_at is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_latest_runtime_success_keeps_provider_selectable_without_catalog_confirmation(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_settings.openrouter_model = "qwen/qwen3.6-plus:free"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "openrouter"],
        "active_provider": "google",
        "fallback_provider": "openrouter",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "openrouter"}),
        available=(name == "openrouter"),
    )

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-04-04T08:00:00+00:00",
            "last_live_probe_at": "2026-04-04T08:00:00+00:00",
            "providers": {
                "google": {
                    "provider": "google",
                    "selected_model": "gemini-3.1-flash-lite-preview",
                    "selected_model_in_catalog": True,
                    "model_count": 3,
                    "last_live_probe_attempt_at": "2026-04-04T08:00:00+00:00",
                },
                "zhipu": {"provider": "zhipu"},
                "openai": {"provider": "openai"},
                "openrouter": {
                    "provider": "openrouter",
                    "selected_model": "qwen/qwen3.6-plus:free",
                    "selected_model_in_catalog": None,
                    "model_count": 2,
                    "last_runtime_observation_at": "2026-04-04T08:05:00+00:00",
                    "last_runtime_success_at": "2026-04-04T08:05:00+00:00",
                    "last_runtime_error": None,
                    "streaming_supported": True,
                    "streaming_source": "static",
                },
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 4, 4, 8, 5, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ):
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    openrouter = next(item for item in snapshot if item.provider == "openrouter")
    assert openrouter.state == "selectable"
    assert openrouter.reason_code is None


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_choose_best_runtime_provider_prefers_degraded_but_routable_provider_over_busy_primary(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        choose_best_runtime_provider,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "zhipu", "ollama"],
        "active_provider": "google",
        "fallback_provider": "zhipu",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "zhipu", "ollama"}),
        available=(name in {"google", "zhipu"}),
    )

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-03-24T08:00:00+00:00",
            "last_live_probe_at": "2026-03-24T08:00:00+00:00",
            "providers": {
                "google": {
                    "provider": "google",
                    "selected_model": "gemini-3.1-flash-lite-preview",
                    "selected_model_in_catalog": True,
                    "model_count": 3,
                    "last_live_probe_attempt_at": "2026-03-24T08:00:00+00:00",
                    "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
                    "streaming_supported": True,
                    "structured_output_supported": True,
                    "tool_calling_supported": True,
                    "degraded_reasons": ["Live capability probe failed."],
                },
                "zhipu": {
                    "provider": "zhipu",
                    "selected_model": "glm-4.5-air",
                    "selected_model_in_catalog": True,
                    "model_count": 6,
                    "last_live_probe_attempt_at": "2026-03-24T08:00:00+00:00",
                    "last_live_probe_success_at": "2026-03-24T08:00:00+00:00",
                    "streaming_supported": True,
                    "streaming_source": "live_probe",
                    "structured_output_supported": False,
                    "structured_output_source": "live_probe",
                    "tool_calling_supported": True,
                    "tool_calling_source": "live_probe",
                    "degraded_reasons": ["Structured output probe returned false."],
                },
                "openai": {"provider": "openai"},
                "openrouter": {"provider": "openrouter"},
                "ollama": {
                    "provider": "ollama",
                    "selected_model": "qwen3:8b",
                    "selected_model_in_catalog": False,
                    "last_live_probe_error": "host unreachable",
                },
            },
        },
        updated_at=datetime(2026, 3, 24, 8, 0, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ), patch(
        "app.services.llm_selectability_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 3, 24, 8, 1, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        chosen = choose_best_runtime_provider(
            preferred_provider="google",
            provider_order=["google", "zhipu", "ollama"],
            allow_degraded_fallback=True,
            force_refresh=True,
        )

    assert chosen is not None
    assert chosen.provider == "zhipu"
    assert chosen.reason_code == "capability_missing"


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_recent_runtime_failure_keeps_provider_disabled_even_when_probe_busy_signal_is_stale(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google", "zhipu"],
        "active_provider": "google",
        "fallback_provider": "zhipu",
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name in {"google", "zhipu"}),
        available=(name in {"google", "zhipu"}),
    )

    google_state = {
        "provider": "google",
        "selected_model": "gemini-3.1-flash-lite-preview",
        "selected_model_in_catalog": True,
        "model_count": 3,
        "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
        "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
        "last_runtime_observation_at": "2026-03-23T10:19:00+00:00",
        "last_runtime_success_at": "2026-03-23T10:05:00+00:00",
        "last_runtime_error": "Cannot connect to host generativelanguage.googleapis.com",
        "last_runtime_note": "chat_stream:error: requested provider google unavailable (timeout).",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
    }

    zhipu_state = {
        "provider": "zhipu",
        "selected_model": "glm-4.5-air",
        "selected_model_in_catalog": True,
        "model_count": 6,
        "last_live_probe_attempt_at": "2026-03-23T10:19:00+00:00",
        "last_live_probe_success_at": "2026-03-23T10:19:00+00:00",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
    }

    record = LlmRuntimeAuditRecord(
        payload={
            "schema_version": 1,
            "audit_updated_at": "2026-03-23T10:19:00+00:00",
            "last_live_probe_at": "2026-03-23T10:00:00+00:00",
            "providers": {
                "google": google_state,
                "zhipu": zhipu_state,
                "openai": {"provider": "openai"},
                "openrouter": {"provider": "openrouter"},
                "ollama": {"provider": "ollama"},
            },
        },
        updated_at=datetime(2026, 3, 23, 10, 19, tzinfo=timezone.utc),
        persisted=True,
    )

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=record,
    ), patch(
        "app.services.llm_selectability_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 3, 23, 10, 20, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        mock_datetime.timezone = timezone
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    zhipu = next(item for item in snapshot if item.provider == "zhipu")
    assert google.state == "disabled"
    assert google.reason_code == "busy"
    assert zhipu.state == "selectable"


@patch("app.services.llm_selectability_service.settings")
@patch("app.services.llm_selectability_service.LLMPool.get_provider_info")
@patch("app.services.llm_selectability_service.LLMPool.get_stats")
def test_runtime_success_newer_than_probe_busy_signal_recovers_provider(
    mock_stats,
    mock_provider_info,
    mock_settings,
):
    from app.services.llm_selectability_service import (
        get_llm_selectability_snapshot,
        invalidate_llm_selectability_cache,
    )

    invalidate_llm_selectability_cache()
    mock_settings.use_multi_agent = True
    mock_settings.google_model = "gemini-3.1-flash-lite-preview"
    mock_settings.zhipu_model = "glm-4.5-air"
    mock_settings.ollama_model = "qwen3:8b"
    mock_settings.llm_provider = "google"
    mock_settings.openai_base_url = None
    mock_settings.openai_model = "gpt-5-mini"
    mock_stats.return_value = {
        "request_selectable_providers": ["google"],
        "active_provider": "google",
        "fallback_provider": None,
    }
    mock_provider_info.side_effect = lambda name: _provider(
        configured=(name == "google"),
        available=(name == "google"),
    )

    google_state = {
        "provider": "google",
        "selected_model": "gemini-3.1-flash-lite-preview",
        "selected_model_in_catalog": True,
        "model_count": 3,
        "last_live_probe_attempt_at": "2026-03-23T10:00:00+00:00",
        "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
        "last_runtime_observation_at": "2026-03-23T10:19:00+00:00",
        "last_runtime_success_at": "2026-03-23T10:19:00+00:00",
        "last_runtime_error": None,
        "last_runtime_note": "chat_stream: completed via google/gemini-3.1-flash-lite-preview.",
        "streaming_supported": True,
        "structured_output_supported": True,
        "tool_calling_supported": True,
    }

    with patch(
        "app.services.llm_selectability_service.get_persisted_llm_runtime_audit",
        return_value=_audit_record(google_state),
    ), patch(
        "app.services.llm_selectability_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 3, 23, 10, 20, tzinfo=timezone.utc)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        mock_datetime.timezone = timezone
        snapshot = get_llm_selectability_snapshot(force_refresh=True)

    google = next(item for item in snapshot if item.provider == "google")
    assert google.state == "selectable"
    assert google.reason_code is None
