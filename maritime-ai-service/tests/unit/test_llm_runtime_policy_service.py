from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.repositories.admin_runtime_settings_repository import AdminRuntimeSettingsRecord


def test_apply_llm_runtime_policy_snapshot_updates_settings():
    from app.core.config import settings
    from app.services.llm_runtime_policy_service import apply_llm_runtime_policy_snapshot

    original_provider = settings.llm_provider
    original_chain = list(settings.llm_failover_chain)
    original_embedding_provider = getattr(settings, "embedding_provider", "google")
    original_embedding_chain = list(getattr(settings, "embedding_failover_chain", []))
    original_embedding_model = getattr(settings, "embedding_model", None)
    original_embedding_dimensions = getattr(settings, "embedding_dimensions", 768)
    original_vision_provider = getattr(settings, "vision_provider", "auto")
    original_vision_chain = list(getattr(settings, "vision_failover_chain", []))
    original_vision_timeout = getattr(settings, "vision_timeout_seconds", 30.0)
    original_google_model = settings.google_model
    original_use_multi_agent = getattr(settings, "use_multi_agent", True)
    original_light_timeout = getattr(settings, "llm_primary_timeout_light_seconds", 12.0)
    original_timeout_overrides = getattr(settings, "llm_timeout_provider_overrides", "{}")

    try:
        applied = apply_llm_runtime_policy_snapshot(
            {
                "llm_provider": "zhipu",
                "llm_failover_chain": ["zhipu", "google", "ollama"],
                "embedding_provider": "auto",
                "embedding_failover_chain": ["ollama", "google"],
                "embedding_model": "embeddinggemma",
                "embedding_dimensions": 768,
                "vision_provider": "auto",
                "vision_failover_chain": ["google", "openai"],
                "vision_timeout_seconds": 45.0,
                "google_model": "gemini-3.1-flash-lite-preview",
                "use_multi_agent": False,
                "llm_primary_timeout_light_seconds": 14.0,
                "timeout_provider_overrides": {
                    "google": {"deep_seconds": 55.0},
                },
            }
        )

        assert applied["llm_provider"] == "zhipu"
        assert settings.llm_provider == "zhipu"
        assert settings.llm_failover_chain == ["zhipu", "google", "ollama"]
        assert applied["embedding_provider"] == "auto"
        assert settings.embedding_provider == "auto"
        assert settings.embedding_failover_chain == ["ollama", "google"]
        assert settings.embedding_model == "embeddinggemma"
        assert settings.embedding_dimensions == 768
        assert settings.vision_provider == "auto"
        assert settings.vision_failover_chain == ["google", "openai"]
        assert settings.vision_timeout_seconds == 45.0
        assert settings.google_model == "gemini-3.1-flash-lite-preview"
        assert settings.use_multi_agent is False
        assert settings.llm_primary_timeout_light_seconds == 14.0
        assert settings.llm.timeout_provider_overrides["google"]["deep_seconds"] == 55.0
        assert settings.llm.provider == "zhipu"
        assert settings.llm.failover_chain == ["zhipu", "google", "ollama"]
    finally:
        settings.llm_provider = original_provider
        settings.llm_failover_chain = original_chain
        settings.embedding_provider = original_embedding_provider
        settings.embedding_failover_chain = original_embedding_chain
        settings.embedding_model = original_embedding_model
        settings.embedding_dimensions = original_embedding_dimensions
        settings.vision_provider = original_vision_provider
        settings.vision_failover_chain = original_vision_chain
        settings.vision_timeout_seconds = original_vision_timeout
        settings.google_model = original_google_model
        settings.use_multi_agent = original_use_multi_agent
        settings.llm_primary_timeout_light_seconds = original_light_timeout
        settings.llm_timeout_provider_overrides = original_timeout_overrides
        settings.refresh_nested_views()


def test_apply_llm_runtime_policy_snapshot_can_preserve_existing_secrets():
    from app.core.config import settings
    from app.services.llm_runtime_policy_service import apply_llm_runtime_policy_snapshot

    original_google_api_key = getattr(settings, "google_api_key", None)
    original_google_model = settings.google_model

    try:
        settings.google_api_key = "env-key"
        settings.google_model = "gemini-env-model"
        settings.refresh_nested_views()

        applied = apply_llm_runtime_policy_snapshot(
            {
                "google_api_key": "persisted-key",
                "google_model": "gemini-3.1-flash-lite-preview",
            },
            preserve_existing_secrets=True,
        )

        assert "google_api_key" not in applied
        assert settings.google_api_key == "env-key"
        assert settings.google_model == "gemini-3.1-flash-lite-preview"
    finally:
        settings.google_api_key = original_google_api_key
        settings.google_model = original_google_model
        settings.refresh_nested_views()


def test_get_persisted_llm_runtime_policy_sanitizes_invalid_payload():
    from app.services.llm_runtime_policy_service import get_persisted_llm_runtime_policy

    repo = MagicMock()
    repo.get_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "llm_provider": "BAD_PROVIDER",
            "embedding_provider": "bad-provider",
            "google_model": "gemini-3.1-flash-lite-preview",
            "llm_failover_chain": ["google", "bad-provider", "zhipu"],
            "embedding_failover_chain": ["ollama", "bad-provider", "google"],
            "vision_provider": "bad-provider",
            "vision_failover_chain": ["openai", "bad-provider", "google"],
            "vision_timeout_seconds": 180,
            "embedding_dimensions": 768,
            "openrouter_provider_sort": "latency",
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 2, 0, tzinfo=timezone.utc),
    )

    with patch(
        "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = get_persisted_llm_runtime_policy()

    assert record is not None
    assert "llm_provider" not in record.payload
    assert "embedding_provider" not in record.payload
    assert "vision_provider" not in record.payload
    assert record.payload["google_model"] == "gemini-3.1-flash-lite-preview"
    assert record.payload["llm_failover_chain"] == ["google", "zhipu"]
    assert record.payload["embedding_failover_chain"] == ["ollama", "google"]
    assert record.payload["vision_failover_chain"] == ["openai", "google"]
    assert record.payload["embedding_dimensions"] == 768
    assert "vision_timeout_seconds" not in record.payload
    assert record.payload["openrouter_provider_sort"] == "latency"


def test_get_persisted_llm_runtime_policy_ignores_invalid_embedding_dimensions():
    from app.services.llm_runtime_policy_service import get_persisted_llm_runtime_policy

    repo = MagicMock()
    repo.get_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "embedding_dimensions": 64,
            "embedding_model": "embeddinggemma",
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 2, 0, tzinfo=timezone.utc),
    )

    with patch(
        "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = get_persisted_llm_runtime_policy()

    assert record is not None
    assert record.payload["embedding_model"] == "embeddinggemma"
    assert "embedding_dimensions" not in record.payload


def test_get_persisted_llm_runtime_policy_sanitizes_timeout_overrides():
    from app.services.llm_runtime_policy_service import get_persisted_llm_runtime_policy

    repo = MagicMock()
    repo.get_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "timeout_provider_overrides": {
                "google": {"deep_seconds": 90},
                "bad-provider": {"deep_seconds": 30},
                "zhipu": {"unknown": 40},
            }
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 2, 0, tzinfo=timezone.utc),
    )

    with patch(
        "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = get_persisted_llm_runtime_policy()

    assert record is not None
    assert record.payload["timeout_provider_overrides"] == {
        "google": {"deep_seconds": 90.0},
    }


def test_get_persisted_llm_runtime_policy_keeps_model_timeout_overrides():
    from app.services.llm_runtime_policy_service import get_persisted_llm_runtime_policy

    repo = MagicMock()
    repo.get_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "timeout_provider_overrides": {
                "nvidia": {
                    "moderate_seconds": 20,
                    "models": {
                        "deepseek-ai/deepseek-v4-flash": {"moderate_seconds": 7},
                        "bad-empty": {"unknown": 99},
                    },
                },
            }
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 2, 0, tzinfo=timezone.utc),
    )

    with patch(
        "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = get_persisted_llm_runtime_policy()

    assert record is not None
    assert record.payload["timeout_provider_overrides"] == {
        "nvidia": {
            "moderate_seconds": 20.0,
            "models": {
                "deepseek-ai/deepseek-v4-flash": {"moderate_seconds": 7.0},
            },
        },
    }


def test_persist_current_llm_runtime_policy_uses_repo_snapshot():
    from app.core.config import settings
    from app.services.llm_runtime_policy_service import persist_current_llm_runtime_policy

    repo = MagicMock()
    repo.upsert_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "llm_provider": settings.llm_provider,
            "google_model": settings.google_model,
            "llm_failover_chain": list(settings.llm_failover_chain),
            "use_multi_agent": getattr(settings, "use_multi_agent", True),
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 3, 0, tzinfo=timezone.utc),
    )

    with patch(
        "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
        return_value=repo,
    ):
        record = persist_current_llm_runtime_policy()

    assert record is not None
    repo.upsert_settings.assert_called_once()
    _, kwargs = repo.upsert_settings.call_args
    assert kwargs["description"] == "Persisted system-wide LLM runtime policy"
    assert record.updated_at == datetime(2026, 3, 22, 3, 0, tzinfo=timezone.utc)


def test_apply_persisted_llm_runtime_policy_preserves_existing_env_secret():
    from app.core.config import settings
    from app.services.llm_runtime_policy_service import apply_persisted_llm_runtime_policy

    original_google_api_key = getattr(settings, "google_api_key", None)
    repo = MagicMock()
    repo.get_settings.return_value = AdminRuntimeSettingsRecord(
        key="llm_runtime",
        settings={
            "google_api_key": "persisted-key",
            "google_model": "gemini-3.1-flash-lite-preview",
        },
        description="Persisted runtime policy",
        created_at=datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, 3, 0, tzinfo=timezone.utc),
    )

    try:
        settings.google_api_key = "env-key"
        settings.refresh_nested_views()
        with patch(
            "app.services.llm_runtime_policy_service.get_admin_runtime_settings_repository",
            return_value=repo,
        ):
            record = apply_persisted_llm_runtime_policy()

        assert record is not None
        assert settings.google_api_key == "env-key"
        assert settings.google_model == "gemini-3.1-flash-lite-preview"
    finally:
        settings.google_api_key = original_google_api_key
        settings.refresh_nested_views()
