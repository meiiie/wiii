import types
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


def test_serialize_llm_runtime_includes_use_multi_agent():
    from app.api.v1.admin import _serialize_llm_runtime
    from app.core.config import settings

    original = getattr(settings, "use_multi_agent", True)
    original_google_api_key = getattr(settings, "google_api_key", None)
    original_google_model = getattr(settings, "google_model", None)
    original_zhipu_api_key = getattr(settings, "zhipu_api_key", None)
    original_zhipu_model = getattr(settings, "zhipu_model", None)
    original_ollama_api_key = getattr(settings, "ollama_api_key", None)
    original_vision_provider = getattr(settings, "vision_provider", "auto")
    original_vision_chain = list(getattr(settings, "vision_failover_chain", []))
    original_vision_timeout = getattr(settings, "vision_timeout_seconds", 30.0)
    original_embedding_model = getattr(settings, "embedding_model", None)
    original_embedding_dimensions = getattr(settings, "embedding_dimensions", None)
    original_llm_provider = getattr(settings, "llm_provider", "zhipu")
    try:
        settings.use_multi_agent = False
        settings.llm_provider = "google"
        settings.google_api_key = "gemini-test-key"
        settings.google_model = "gemini-3.1-flash-lite-preview"
        settings.zhipu_api_key = "zhipu-test-key"
        settings.zhipu_model = "glm-5"
        settings.ollama_api_key = "ollama-test-key"
        settings.vision_provider = "auto"
        settings.vision_failover_chain = ["google", "openai", "ollama"]
        settings.vision_timeout_seconds = 45.0
        settings.embedding_model = "models/gemini-embedding-001"
        settings.embedding_dimensions = 768

        def _embedding_status(**kwargs):
            return types.SimpleNamespace(**kwargs, to_dict=lambda: kwargs)

        def _vision_status(**kwargs):
            return types.SimpleNamespace(**kwargs, to_dict=lambda: kwargs)

        def _space_status(**kwargs):
            return types.SimpleNamespace(**kwargs, to_dict=lambda: kwargs)

        with patch(
            "app.engine.llm_pool.LLMPool.get_stats",
            return_value={
                "active_provider": "google",
                "providers_registered": ["google", "zhipu"],
                "request_selectable_providers": ["google", "zhipu"],
            },
        ), patch(
            "app.api.v1.admin.get_embedding_selectability_snapshot",
            return_value=[
                _embedding_status(
                    provider="google",
                    display_name="Gemini Embeddings",
                    state="selectable",
                    configured=True,
                    available=True,
                    in_failover_chain=True,
                    is_default=True,
                    is_active=True,
                    selected_model="models/gemini-embedding-001",
                    selected_dimensions=768,
                    supports_dimension_override=True,
                    reason_code=None,
                    reason_label=None,
                ),
                _embedding_status(
                    provider="zhipu",
                    display_name="Zhipu Embeddings",
                    state="disabled",
                    configured=True,
                    available=False,
                    in_failover_chain=False,
                    is_default=False,
                    is_active=False,
                    selected_model=None,
                    selected_dimensions=None,
                    supports_dimension_override=False,
                    reason_code="model_unverified",
                    reason_label="Provider nay chua co embedding model contract duoc xac nhan.",
                ),
            ],
        ), patch(
            "app.api.v1.admin.get_vision_selectability_snapshot",
            return_value=[
                _vision_status(
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
                        {
                            "capability": "visual_describe",
                            "display_name": "Mo ta anh",
                            "available": True,
                            "selected_model": "gemini-3.1-flash-lite-preview",
                            "lane_fit": "general",
                            "lane_fit_label": "General vision",
                            "reason_code": None,
                            "reason_label": None,
                            "resolved_base_url": None,
                        }
                    ],
                ),
            ],
        ), patch(
            "app.api.v1.admin.build_embedding_space_status_snapshot",
            return_value=_space_status(
                audit_available=True,
                policy_contract={
                    "provider": "google",
                    "model": "models/gemini-embedding-001",
                    "dimensions": 768,
                    "fingerprint": "google:models/gemini-embedding-001:768",
                    "label": "Gemini Embedding 001 [google, 768d]",
                },
                active_contract={
                    "provider": "google",
                    "model": "models/gemini-embedding-001",
                    "dimensions": 768,
                    "fingerprint": "google:models/gemini-embedding-001:768",
                    "label": "Gemini Embedding 001 [google, 768d]",
                },
                active_matches_policy=True,
                total_embedded_rows=3,
                total_tracked_rows=3,
                total_untracked_rows=0,
                tables=[
                    {
                        "table_name": "semantic_memories",
                        "embedded_row_count": 2,
                        "tracked_row_count": 2,
                        "untracked_row_count": 0,
                        "fingerprints": {"google:models/gemini-embedding-001:768": 2},
                    }
                ],
                warnings=[],
                error=None,
            ),
        ), patch(
            "app.api.v1.admin.build_embedding_migration_previews",
            return_value=[
                _space_status(
                    target_model="models/gemini-embedding-001",
                    target_provider="google",
                    target_dimensions=768,
                    target_label="Gemini Embedding 001",
                    target_status="stable",
                    same_space=True,
                    allowed=True,
                    requires_reembed=False,
                    target_backend_constructible=True,
                    maintenance_required=False,
                    embedded_row_count=3,
                    blocking_tables=[],
                    mixed_tables=[],
                    warnings=[],
                    recommended_steps=["noop"],
                    detail=None,
                )
            ],
        ), patch(
            "app.api.v1.admin.build_vision_runtime_audit_summary",
            return_value=types.SimpleNamespace(
                audit_updated_at="2026-04-03T01:00:00+00:00",
                last_live_probe_at="2026-04-03T01:01:00+00:00",
                audit_persisted=True,
                audit_warnings=("Vision runtime live probe persisted.",),
                provider_state={},
            ),
        ):
            result = _serialize_llm_runtime()

        assert result.use_multi_agent is False
        assert result.google_model == "gemini-3.1-flash-lite-preview"
        assert result.google_api_key_configured is True
        assert result.zhipu_api_key_configured is True
        assert result.zhipu_model == "glm-5"
        assert result.ollama_api_key_configured is True
        assert result.request_selectable_providers == ["google", "zhipu"]
        assert result.timeout_profiles.light_seconds == getattr(settings, "llm_primary_timeout_light_seconds")
        assert result.timeout_provider_overrides == {}
        assert result.vision_provider == "auto"
        assert result.vision_failover_chain == ["google", "openai", "ollama"]
        assert result.vision_timeout_seconds == 45.0
        assert result.vision_provider_status
        assert result.vision_audit_updated_at == "2026-04-03T01:00:00+00:00"
        assert result.vision_last_live_probe_at == "2026-04-03T01:01:00+00:00"
        assert result.vision_audit_persisted is True
        assert result.vision_audit_warnings == ["Vision runtime live probe persisted."]
        assert result.embedding_provider == getattr(settings, "embedding_provider")
        assert result.embedding_failover_chain == list(getattr(settings, "embedding_failover_chain"))
        assert result.embedding_model == getattr(settings, "embedding_model")
        assert result.embedding_dimensions == getattr(settings, "embedding_dimensions")
        assert result.embedding_provider_status
        assert result.embedding_space_status is not None
        assert result.embedding_space_status.total_embedded_rows == 3
        assert result.embedding_migration_previews
        assert result.provider_status
        google_status = next(item for item in result.provider_status if item.provider == "google")
        assert google_status.is_default is True
        assert google_status.request_selectable is True
        zhipu_status = next(item for item in result.provider_status if item.provider == "zhipu")
        assert zhipu_status.configurable_via_admin is True
        google_embedding_status = next(
            item for item in result.embedding_provider_status if item.provider == "google"
        )
        assert google_embedding_status.selected_model is not None
        assert result.embedding_migration_previews[0].same_space is True
    finally:
        settings.use_multi_agent = original
        settings.llm_provider = original_llm_provider
        settings.google_api_key = original_google_api_key
        settings.google_model = original_google_model
        settings.zhipu_api_key = original_zhipu_api_key
        settings.zhipu_model = original_zhipu_model
        settings.ollama_api_key = original_ollama_api_key
        settings.vision_provider = original_vision_provider
        settings.vision_failover_chain = original_vision_chain
        settings.vision_timeout_seconds = original_vision_timeout
        settings.embedding_model = original_embedding_model
        settings.embedding_dimensions = original_embedding_dimensions
        settings.refresh_nested_views()


def test_build_provider_runtime_statuses_includes_selectability_reason():
    from app.api.v1.admin_llm_runtime import build_provider_runtime_statuses_impl
    from app.api.v1.admin_schemas import ProviderRuntimeStatus

    class _Provider:
        def __init__(self, configured: bool, available: bool):
            self._configured = configured
            self._available = available

        def is_configured(self):
            return self._configured

        def is_available(self):
            return self._available

    settings_obj = types.SimpleNamespace(
        llm_provider="google",
        llm_failover_chain=["google", "zhipu"],
    )
    statuses = build_provider_runtime_statuses_impl(
        {
            "providers_registered": ["google", "zhipu"],
            "request_selectable_providers": ["google", "zhipu"],
            "active_provider": "zhipu",
        },
        settings_obj=settings_obj,
        get_supported_provider_names_fn=lambda: ["google", "zhipu"],
        create_provider_fn=lambda provider: _Provider(
            configured=True,
            available=provider == "zhipu",
        ),
        get_provider_display_name_fn=lambda provider: provider.upper(),
        get_llm_selectability_snapshot_fn=lambda: [
            types.SimpleNamespace(
                provider="google",
                reason_code="busy",
                reason_label="Provider tam thoi ban hoac da cham gioi han.",
            ),
            types.SimpleNamespace(
                provider="zhipu",
                reason_code=None,
                reason_label=None,
            ),
        ],
        provider_runtime_status_cls=ProviderRuntimeStatus,
        configurable_providers={"google", "zhipu"},
        logger=types.SimpleNamespace(debug=lambda *args, **kwargs: None),
    )

    google_status = next(item for item in statuses if item.provider == "google")
    zhipu_status = next(item for item in statuses if item.provider == "zhipu")
    assert google_status.reason_code == "busy"
    assert google_status.reason_label == "Provider tam thoi ban hoac da cham gioi han."
    assert zhipu_status.reason_code is None


@pytest.mark.asyncio
async def test_get_model_catalog_exposes_provider_capability_metadata():
    from app.api.v1.admin import ProviderRuntimeStatus, get_model_catalog

    auth = types.SimpleNamespace(role="admin", auth_method="oauth")

    with patch(
        "app.engine.model_catalog.ModelCatalogService.get_full_catalog",
        return_value={
            "providers": {
                "google": {
                    "gemini-3.1-flash-lite-preview": types.SimpleNamespace(
                        provider="google",
                        model_name="gemini-3.1-flash-lite-preview",
                        display_name="Gemini 3.1 Flash-Lite Preview",
                        status="current",
                        released_on="2026-03-03",
                    ),
                },
                "openai": {},
            },
            "provider_metadata": {
                "google": {
                    "catalog_source": "mixed",
                    "supports_runtime_discovery": True,
                    "runtime_discovery_enabled": True,
                    "runtime_discovery_succeeded": True,
                    "discovered_model_count": 3,
                    "model_count": 4,
                },
                "openai": {
                    "catalog_source": "static",
                    "supports_runtime_discovery": True,
                    "runtime_discovery_enabled": False,
                    "runtime_discovery_succeeded": False,
                    "discovered_model_count": 0,
                    "model_count": 0,
                },
            },
            "embedding_models": {},
            "ollama_discovered": False,
            "timestamp": "2026-03-22T08:00:00+00:00",
        },
    ), patch(
        "app.services.llm_runtime_audit_service.record_runtime_discovery_snapshot",
        return_value=types.SimpleNamespace(
            payload={
                "providers": {
                    "google": {
                        "last_discovery_attempt_at": "2026-03-23T08:00:00+00:00",
                        "last_discovery_success_at": "2026-03-23T08:00:00+00:00",
                        "last_live_probe_attempt_at": "2026-03-23T08:05:00+00:00",
                        "last_live_probe_error": "provider probe: quota_or_rate_limited (429)",
                        "last_runtime_observation_at": "2026-03-23T08:06:00+00:00",
                        "last_runtime_success_at": "2026-03-23T08:06:00+00:00",
                        "last_runtime_note": "chat_sync: completed via google/gemini-3.1-flash-lite-preview.",
                        "last_runtime_source": "chat_sync",
                        "tool_calling_supported": True,
                        "tool_calling_source": "live_probe",
                        "structured_output_supported": True,
                        "structured_output_source": "live_probe",
                        "streaming_supported": True,
                        "streaming_source": "live_probe",
                        "context_window_tokens": 1048576,
                        "context_window_source": "runtime",
                        "max_output_tokens": 65536,
                        "max_output_source": "runtime",
                        "degraded": False,
                        "degraded_reasons": [],
                    },
                    "openai": {
                        "degraded": False,
                        "degraded_reasons": [],
                    },
                }
            },
            updated_at=datetime(2026, 3, 23, 8, 0, tzinfo=timezone.utc),
        ),
    ), patch(
        "app.services.llm_runtime_audit_service.build_runtime_audit_summary",
        return_value={
            "audit_updated_at": "2026-03-23T08:00:00+00:00",
            "last_live_probe_at": "2026-03-23T08:05:00+00:00",
            "degraded_providers": [],
            "audit_persisted": True,
            "audit_warnings": [],
        },
    ), patch(
        "app.engine.llm_pool.LLMPool.get_stats",
        return_value={},
    ), patch(
        "app.api.v1.admin._build_provider_runtime_statuses",
        return_value=[
            ProviderRuntimeStatus(
                provider="google",
                display_name="Google Gemini",
                configured=True,
                available=True,
                registered=True,
                request_selectable=True,
                in_failover_chain=True,
                is_default=True,
                is_active=True,
                configurable_via_admin=True,
            ),
            ProviderRuntimeStatus(
                provider="openai",
                display_name="OpenAI-Compatible",
                configured=False,
                available=False,
                registered=False,
                request_selectable=False,
                in_failover_chain=False,
                is_default=False,
                is_active=False,
                configurable_via_admin=True,
            ),
        ],
    ):
        result = await get_model_catalog(auth)

    assert result.provider_capabilities["google"].catalog_source == "mixed"
    assert result.provider_capabilities["google"].runtime_discovery_succeeded is True
    assert result.provider_capabilities["google"].model_count == 4
    assert result.provider_capabilities["google"].selected_model == "gemini-3.1-flash-lite-preview"
    assert result.provider_capabilities["google"].tool_calling_supported is True
    assert result.provider_capabilities["google"].context_window_tokens == 1048576
    assert result.provider_capabilities["google"].last_runtime_success_at == "2026-03-23T08:06:00+00:00"
    assert result.provider_capabilities["google"].recovered is True
    assert result.provider_capabilities["google"].recovered_reasons == [
        "Runtime da hoi phuc sau live probe"
    ]
    assert result.provider_capabilities["openai"].catalog_source == "static"
    assert result.audit_updated_at == "2026-03-23T08:00:00+00:00"
    assert result.audit_persisted is True
    assert result.audit_warnings == []


@pytest.mark.asyncio
async def test_update_llm_runtime_config_updates_use_multi_agent_and_resets_services():
    from app.api.v1.admin import LlmRuntimeConfigUpdate, update_llm_runtime_config
    from app.core.config import settings

    auth = types.SimpleNamespace(role="admin", auth_method="oauth")
    request = types.SimpleNamespace(
        client=types.SimpleNamespace(host="127.0.0.1"),
        headers={},
        method="PATCH",
        url=types.SimpleNamespace(path="/api/v1/admin/llm-runtime"),
    )
    original = getattr(settings, "use_multi_agent", True)
    original_google_api_key = getattr(settings, "google_api_key", None)
    original_google_model = getattr(settings, "google_model", None)
    original_provider = getattr(settings, "llm_provider", "google")
    original_zhipu_api_key = getattr(settings, "zhipu_api_key", None)
    original_zhipu_model = getattr(settings, "zhipu_model", None)
    original_zhipu_model_advanced = getattr(settings, "zhipu_model_advanced", None)
    original_zhipu_base_url = getattr(settings, "zhipu_base_url", None)
    original_ollama_api_key = getattr(settings, "ollama_api_key", None)
    original_timeout_light = getattr(settings, "llm_primary_timeout_light_seconds", 12.0)
    original_timeout_overrides = getattr(settings, "llm_timeout_provider_overrides", "{}")
    original_vision_provider = getattr(settings, "vision_provider", "auto")
    original_vision_describe_provider = getattr(settings, "vision_describe_provider", "auto")
    original_vision_describe_model = getattr(settings, "vision_describe_model", None)
    original_vision_ocr_provider = getattr(settings, "vision_ocr_provider", "auto")
    original_vision_ocr_model = getattr(settings, "vision_ocr_model", None)
    original_vision_grounded_provider = getattr(settings, "vision_grounded_provider", "auto")
    original_vision_grounded_model = getattr(settings, "vision_grounded_model", None)
    original_vision_chain = list(getattr(settings, "vision_failover_chain", []))
    original_vision_timeout = getattr(settings, "vision_timeout_seconds", 30.0)
    original_embedding_provider = getattr(settings, "embedding_provider", "google")
    original_embedding_chain = list(getattr(settings, "embedding_failover_chain", []))
    original_embedding_model = getattr(settings, "embedding_model", None)
    try:
        settings.use_multi_agent = True
        settings.google_api_key = None
        settings.google_model = "gemini-3.1-flash-lite-preview"
        settings.llm_provider = "ollama"
        settings.zhipu_api_key = None
        settings.zhipu_model = "glm-5"
        settings.zhipu_model_advanced = "glm-5"
        settings.zhipu_base_url = "https://open.bigmodel.cn/api/paas/v4"
        settings.ollama_api_key = None
        settings.vision_provider = "auto"
        settings.vision_describe_provider = "auto"
        settings.vision_describe_model = None
        settings.vision_ocr_provider = "auto"
        settings.vision_ocr_model = "glm-ocr"
        settings.vision_grounded_provider = "auto"
        settings.vision_grounded_model = None
        settings.vision_failover_chain = ["google", "openai", "ollama"]
        settings.vision_timeout_seconds = 30.0
        settings.embedding_provider = "google"
        settings.embedding_failover_chain = ["google", "openai", "ollama"]
        settings.embedding_model = "models/gemini-embedding-001"
        persisted_now = datetime.now(timezone.utc)
        with patch(
            "app.services.llm_runtime_policy_service.persist_current_llm_runtime_policy",
            return_value=types.SimpleNamespace(payload={"llm_provider": "zhipu"}, updated_at=persisted_now),
        ), patch(
            "app.services.embedding_space_guard.validate_embedding_space_transition",
            return_value=types.SimpleNamespace(allowed=True, warnings=(), detail=None),
        ), patch(
            "app.services.embedding_space_guard.build_runtime_embedding_space_warnings",
            return_value=[],
        ), patch(
            "app.engine.llm_pool.LLMPool.reset"
        ) as mock_pool_reset, patch(
            "app.engine.llm_pool.LLMPool.initialize"
        ) as mock_pool_initialize, patch(
            "app.engine.llm_pool.LLMPool.get_stats",
            return_value={
                "active_provider": "zhipu",
                "providers_registered": ["google", "zhipu", "ollama"],
                "request_selectable_providers": ["google", "zhipu", "ollama"],
            },
        ), patch(
            "app.services.chat_service.reset_chat_service"
        ) as mock_reset_chat, patch(
            "app.engine.embedding_runtime.reset_embedding_backend"
        ) as mock_reset_embedding, patch(
            "app.engine.vision_runtime.reset_vision_runtime_caches"
        ) as mock_reset_vision, patch(
            "app.services.embedding_selectability_service.invalidate_embedding_selectability_cache"
        ) as mock_invalidate_embedding_cache, patch(
            "app.services.vision_selectability_service.invalidate_vision_selectability_cache"
        ) as mock_invalidate_vision_cache:
            result = await update_llm_runtime_config(
                request,
                LlmRuntimeConfigUpdate(
                    provider="zhipu",
                    use_multi_agent=False,
                    google_api_key="gemini-runtime-key",
                    google_model="gemini-3.1-flash-lite-preview",
                    zhipu_api_key="zhipu-runtime-key",
                    zhipu_model="glm-5",
                    zhipu_model_advanced="glm-5",
                    zhipu_base_url="https://open.bigmodel.cn/api/paas/v4",
                    ollama_api_key="ollama-cloud-key",
                    timeout_profiles={
                        "light_seconds": 14,
                        "moderate_seconds": 28,
                        "deep_seconds": 50,
                        "structured_seconds": 70,
                        "background_seconds": 0,
                        "stream_keepalive_interval_seconds": 15,
                        "stream_idle_timeout_seconds": 0,
                    },
                    timeout_provider_overrides={
                        "google": {"deep_seconds": 80},
                    },
                    vision_provider="openai",
                    vision_describe_provider="openrouter",
                    vision_describe_model="qwen/qwen2.5-vl-7b-instruct",
                    vision_ocr_provider="zhipu",
                    vision_ocr_model="glm-ocr",
                    vision_grounded_provider="openrouter",
                    vision_grounded_model="qwen/qwen2.5-vl-32b-instruct",
                    vision_failover_chain=["openai", "google"],
                    vision_timeout_seconds=40,
                    embedding_provider="ollama",
                    embedding_failover_chain=["ollama", "google"],
                    embedding_model="embeddinggemma",
                ),
                auth,
            )

        assert settings.use_multi_agent is False
        assert settings.llm_provider == "zhipu"
        assert settings.google_api_key == "gemini-runtime-key"
        assert settings.google_model == "gemini-3.1-flash-lite-preview"
        assert settings.zhipu_api_key == "zhipu-runtime-key"
        assert settings.zhipu_model == "glm-5"
        assert settings.zhipu_model_advanced == "glm-5"
        assert settings.zhipu_base_url == "https://open.bigmodel.cn/api/paas/v4"
        assert settings.llm.google_api_key == "gemini-runtime-key"
        assert settings.llm.google_model == "gemini-3.1-flash-lite-preview"
        assert settings.ollama_api_key == "ollama-cloud-key"
        assert settings.llm_primary_timeout_light_seconds == 14
        assert settings.llm.timeout_provider_overrides["google"]["deep_seconds"] == 80
        assert settings.vision_provider == "openai"
        assert settings.vision_describe_provider == "openrouter"
        assert settings.vision_describe_model == "qwen/qwen2.5-vl-7b-instruct"
        assert settings.vision_ocr_provider == "zhipu"
        assert settings.vision_ocr_model == "glm-ocr"
        assert settings.vision_grounded_provider == "openrouter"
        assert settings.vision_grounded_model == "qwen/qwen2.5-vl-32b-instruct"
        assert settings.vision_failover_chain == ["openai", "google"]
        assert settings.vision_timeout_seconds == 40
        assert settings.embedding_provider == "ollama"
        assert settings.embedding_failover_chain == ["ollama", "google"]
        assert settings.embedding_model == "embeddinggemma"
        assert result.use_multi_agent is False
        assert result.provider == "zhipu"
        assert result.google_model == "gemini-3.1-flash-lite-preview"
        assert result.google_api_key_configured is True
        assert result.zhipu_api_key_configured is True
        assert result.zhipu_model == "glm-5"
        assert result.ollama_api_key_configured is True
        assert result.request_selectable_providers == ["google", "zhipu", "ollama"]
        assert any(item.provider == "zhipu" for item in result.provider_status)
        assert result.vision_provider == "openai"
        assert result.vision_describe_provider == "openrouter"
        assert result.vision_describe_model == "qwen/qwen2.5-vl-7b-instruct"
        assert result.vision_ocr_provider == "zhipu"
        assert result.vision_ocr_model == "glm-ocr"
        assert result.vision_grounded_provider == "openrouter"
        assert result.vision_grounded_model == "qwen/qwen2.5-vl-32b-instruct"
        assert result.vision_failover_chain == ["openai", "google"]
        assert result.vision_timeout_seconds == 40
        assert result.embedding_provider == "ollama"
        assert result.embedding_failover_chain == ["ollama", "google"]
        assert result.embedding_model == "embeddinggemma"
        assert result.timeout_profiles.deep_seconds == 50
        assert result.timeout_provider_overrides["google"].deep_seconds == 80
        assert result.runtime_policy_persisted is True
        assert result.runtime_policy_updated_at == persisted_now.isoformat()
        mock_pool_reset.assert_called_once()
        mock_pool_initialize.assert_not_called()
        mock_reset_embedding.assert_called_once()
        mock_reset_vision.assert_called_once()
        mock_invalidate_embedding_cache.assert_called_once()
        mock_invalidate_vision_cache.assert_called_once()
        mock_reset_chat.assert_called_once()
    finally:
        settings.use_multi_agent = original
        settings.google_api_key = original_google_api_key
        settings.google_model = original_google_model
        settings.llm_provider = original_provider
        settings.zhipu_api_key = original_zhipu_api_key
        settings.zhipu_model = original_zhipu_model
        settings.zhipu_model_advanced = original_zhipu_model_advanced
        settings.zhipu_base_url = original_zhipu_base_url
        settings.ollama_api_key = original_ollama_api_key
        settings.llm_primary_timeout_light_seconds = original_timeout_light
        settings.llm_timeout_provider_overrides = original_timeout_overrides
        settings.vision_provider = original_vision_provider
        settings.vision_describe_provider = original_vision_describe_provider
        settings.vision_describe_model = original_vision_describe_model
        settings.vision_ocr_provider = original_vision_ocr_provider
        settings.vision_ocr_model = original_vision_ocr_model
        settings.vision_grounded_provider = original_vision_grounded_provider
        settings.vision_grounded_model = original_vision_grounded_model
        settings.vision_failover_chain = original_vision_chain
        settings.vision_timeout_seconds = original_vision_timeout
        settings.embedding_provider = original_embedding_provider
        settings.embedding_failover_chain = original_embedding_chain
        settings.embedding_model = original_embedding_model
        settings.refresh_nested_views()


@pytest.mark.asyncio
async def test_update_llm_runtime_config_blocks_unsafe_embedding_space_switch():
    from fastapi import HTTPException

    from app.api.v1.admin import LlmRuntimeConfigUpdate, update_llm_runtime_config
    from app.core.config import settings

    auth = types.SimpleNamespace(role="admin", auth_method="oauth")
    request = types.SimpleNamespace(
        client=types.SimpleNamespace(host="127.0.0.1"),
        headers={},
        method="PATCH",
        url=types.SimpleNamespace(path="/api/v1/admin/llm-runtime"),
    )
    original_embedding_provider = getattr(settings, "embedding_provider", "google")
    original_embedding_model = getattr(settings, "embedding_model", None)
    original_embedding_dimensions = getattr(settings, "embedding_dimensions", 768)
    try:
        settings.embedding_provider = "ollama"
        settings.embedding_model = "embeddinggemma"
        settings.embedding_dimensions = 768
        settings.refresh_nested_views()

        with patch(
            "app.services.embedding_space_guard.validate_embedding_space_transition",
            return_value=types.SimpleNamespace(
                allowed=False,
                warnings=(),
                detail="unsafe vector-space switch",
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_llm_runtime_config(
                    request,
                    LlmRuntimeConfigUpdate(
                        embedding_provider="openai",
                        embedding_model="text-embedding-3-small",
                        embedding_dimensions=768,
                    ),
                    auth,
                )

        assert exc_info.value.status_code == 409
        assert "unsafe vector-space switch" in str(exc_info.value.detail)
    finally:
        settings.embedding_provider = original_embedding_provider
        settings.embedding_model = original_embedding_model
        settings.embedding_dimensions = original_embedding_dimensions
        settings.refresh_nested_views()


@pytest.mark.asyncio
async def test_update_llm_runtime_config_normalizes_embedding_dimensions_for_non_override_model():
    from app.api.v1.admin import LlmRuntimeConfigUpdate, update_llm_runtime_config
    from app.core.config import settings

    auth = types.SimpleNamespace(role="admin", auth_method="oauth")
    request = types.SimpleNamespace(
        client=types.SimpleNamespace(host="127.0.0.1"),
        headers={},
        method="PATCH",
        url=types.SimpleNamespace(path="/api/v1/admin/llm-runtime"),
    )
    original_embedding_provider = getattr(settings, "embedding_provider", "google")
    original_embedding_model = getattr(settings, "embedding_model", None)
    original_embedding_dimensions = getattr(settings, "embedding_dimensions", 768)
    try:
        settings.embedding_provider = "openai"
        settings.embedding_model = "text-embedding-3-small"
        settings.embedding_dimensions = 1536
        settings.refresh_nested_views()

        persisted_now = datetime.now(timezone.utc)
        with patch(
            "app.services.llm_runtime_policy_service.persist_current_llm_runtime_policy",
            return_value=types.SimpleNamespace(payload={"embedding_model": "embeddinggemma"}, updated_at=persisted_now),
        ), patch(
            "app.services.embedding_space_guard.validate_embedding_space_transition",
            return_value=types.SimpleNamespace(allowed=True, warnings=(), detail=None),
        ), patch(
            "app.services.embedding_space_guard.build_runtime_embedding_space_warnings",
            return_value=[],
        ), patch(
            "app.engine.llm_pool.LLMPool.reset"
        ), patch(
            "app.engine.llm_pool.LLMPool.get_stats",
            return_value={
                "active_provider": "ollama",
                "providers_registered": ["openai", "ollama"],
                "request_selectable_providers": ["openai", "ollama"],
            },
        ), patch(
            "app.services.chat_service.reset_chat_service"
        ), patch(
            "app.engine.embedding_runtime.reset_embedding_backend"
        ), patch(
            "app.services.embedding_selectability_service.invalidate_embedding_selectability_cache"
        ):
            result = await update_llm_runtime_config(
                request,
                LlmRuntimeConfigUpdate(
                    embedding_provider="ollama",
                    embedding_model="embeddinggemma",
                ),
                auth,
            )

        assert settings.embedding_model == "embeddinggemma"
        assert settings.embedding_dimensions == 768
        assert result.embedding_dimensions == 768
    finally:
        settings.embedding_provider = original_embedding_provider
        settings.embedding_model = original_embedding_model
        settings.embedding_dimensions = original_embedding_dimensions
        settings.refresh_nested_views()
