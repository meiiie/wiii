from app.engine.llm_runtime_metadata import resolve_runtime_llm_metadata


def test_resolve_runtime_llm_metadata_uses_zhipu_model_when_provider_is_zhipu():
    from app.core.config import settings

    original_provider = settings.llm_provider
    original_zhipu_model = getattr(settings, "zhipu_model", None)
    try:
        settings.llm_provider = "zhipu"
        settings.zhipu_model = "glm-5"

        metadata = resolve_runtime_llm_metadata()

        assert metadata == {
            "provider": "zhipu",
            "model": "glm-5",
            "runtime_authoritative": False,
            "failover": None,
        }
    finally:
        settings.llm_provider = original_provider
        settings.zhipu_model = original_zhipu_model
        settings.refresh_nested_views()


def test_resolve_runtime_llm_metadata_prefers_execution_metadata():
    metadata = resolve_runtime_llm_metadata(
        {
            "provider": "auto",
            "model": "gemini-3.1-flash-lite-preview",
            "_execution_provider": "zhipu",
            "_execution_model": "glm-5",
        }
    )

    assert metadata == {
        "provider": "zhipu",
        "model": "glm-5",
        "runtime_authoritative": True,
        "failover": None,
    }


def test_resolve_runtime_llm_metadata_hides_non_authoritative_user_facing_badge():
    metadata = resolve_runtime_llm_metadata(
        {
            "provider": "auto",
            "model": "gemini-3.1-flash-lite-preview",
        },
        allow_fallback=False,
    )

    assert metadata == {
        "provider": None,
        "model": None,
        "runtime_authoritative": False,
        "failover": None,
    }


def test_resolve_runtime_llm_metadata_summarizes_failover_route():
    metadata = resolve_runtime_llm_metadata(
        {
            "_requested_provider": "google",
            "_execution_provider": "zhipu",
            "_execution_model": "glm-5",
            "_llm_failover_events": [
                {
                    "from_provider": "google",
                    "to_provider": "zhipu",
                    "reason_code": "auth_error",
                    "reason_category": "auth_error",
                    "reason_label": "Xac thuc provider that bai.",
                    "detail": "401 invalid API key",
                }
            ],
        }
    )

    assert metadata["provider"] == "zhipu"
    assert metadata["model"] == "glm-5"
    assert metadata["runtime_authoritative"] is True
    assert metadata["failover"] == {
        "switched": True,
        "switch_count": 1,
        "initial_provider": "google",
        "final_provider": "zhipu",
        "last_reason_code": "auth_error",
        "last_reason_category": "auth_error",
        "last_reason_label": "Xac thuc provider that bai.",
        "route": [
            {
                "from_provider": "google",
                "to_provider": "zhipu",
                "reason_code": "auth_error",
                "reason_category": "auth_error",
                "reason_label": "Xac thuc provider that bai.",
                "detail": "401 invalid API key",
            }
        ],
    }
