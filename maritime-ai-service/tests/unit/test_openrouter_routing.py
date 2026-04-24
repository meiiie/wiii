from types import SimpleNamespace

from app.engine.openrouter_routing import (
    build_openrouter_extra_body,
    is_openrouter_base_url,
)


def _make_settings(**overrides):
    defaults = {
        "openai_base_url": "https://openrouter.ai/api/v1",
        "openrouter_model_fallbacks": [],
        "openrouter_provider_order": [],
        "openrouter_allowed_providers": [],
        "openrouter_ignored_providers": [],
        "openrouter_allow_fallbacks": None,
        "openrouter_require_parameters": None,
        "openrouter_data_collection": None,
        "openrouter_zdr": None,
        "openrouter_provider_sort": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestIsOpenRouterBaseUrl:
    def test_true_for_openrouter_url(self):
        assert is_openrouter_base_url("https://openrouter.ai/api/v1")

    def test_false_for_openai_url(self):
        assert not is_openrouter_base_url("https://api.openai.com/v1")

    def test_false_for_none(self):
        assert not is_openrouter_base_url(None)


class TestBuildOpenRouterExtraBody:
    def test_returns_empty_for_non_openrouter_base_url(self):
        settings = _make_settings(openai_base_url="https://api.openai.com/v1")
        assert build_openrouter_extra_body(settings, primary_model="openai/gpt-oss-20b:free") == {}

    def test_includes_models_and_provider_preferences(self):
        settings = _make_settings(
            openrouter_api_key="sk-or-test",
            openrouter_model_fallbacks=[
                "openai/gpt-oss-120b:free",
                "openai/gpt-oss-20b:free",
                "openai/gpt-oss-120b:free",
            ],
            openrouter_provider_order=["anthropic", "openai", "anthropic"],
            openrouter_allowed_providers=["anthropic", "openai"],
            openrouter_ignored_providers=["targon"],
            openrouter_allow_fallbacks=False,
            openrouter_require_parameters=True,
            openrouter_data_collection="deny",
            openrouter_zdr=True,
            openrouter_provider_sort="latency",
        )

        body = build_openrouter_extra_body(
            settings,
            primary_model="openai/gpt-oss-20b:free",
        )

        assert body == {
            "models": ["openai/gpt-oss-120b:free"],
            "provider": {
                "order": ["anthropic", "openai"],
                "only": ["anthropic", "openai"],
                "ignore": ["targon"],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
                "zdr": True,
                "sort": "latency",
            },
        }

    def test_omits_empty_provider_block(self):
        settings = _make_settings()
        assert build_openrouter_extra_body(settings, primary_model="openai/gpt-oss-20b:free") == {}
