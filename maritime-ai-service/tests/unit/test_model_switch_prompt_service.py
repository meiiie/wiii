from types import SimpleNamespace
from unittest.mock import patch

from app.services.model_switch_prompt_service import (
    build_model_switch_prompt_for_failover,
    build_model_switch_prompt_for_unavailable,
)


def _selectable_provider(
    provider: str,
    display_name: str,
    selected_model: str,
):
    return SimpleNamespace(
        provider=provider,
        display_name=display_name,
        selected_model=selected_model,
        state="selectable",
    )


@patch("app.services.model_switch_prompt_service.get_llm_selectability_snapshot")
def test_build_model_switch_prompt_for_unavailable_prefers_first_selectable_option(
    mock_snapshot,
):
    mock_snapshot.return_value = [
        _selectable_provider("zhipu", "Zhipu GLM", "glm-5"),
        _selectable_provider("openrouter", "OpenRouter", "openai/gpt-5.4-mini"),
    ]

    prompt = build_model_switch_prompt_for_unavailable(
        provider="google",
        reason_code="rate_limit",
    )

    assert prompt is not None
    assert prompt["trigger"] == "provider_unavailable"
    assert prompt["recommended_provider"] == "zhipu"
    assert prompt["allow_retry_once"] is True
    assert prompt["options"][0]["provider"] == "zhipu"


@patch("app.services.model_switch_prompt_service.get_llm_selectability_snapshot")
def test_build_model_switch_prompt_for_failover_prefers_final_provider(
    mock_snapshot,
):
    mock_snapshot.return_value = [
        _selectable_provider("zhipu", "Zhipu GLM", "glm-5"),
        _selectable_provider("openrouter", "OpenRouter", "openai/gpt-5.4-mini"),
    ]

    prompt = build_model_switch_prompt_for_failover(
        failover={
            "switched": True,
            "initial_provider": "google",
            "final_provider": "zhipu",
            "last_reason_code": "auth_error",
        },
        requested_provider="google",
    )

    assert prompt is not None
    assert prompt["trigger"] == "hard_failover"
    assert prompt["recommended_provider"] == "zhipu"
    assert prompt["allow_retry_once"] is False
    assert prompt["allow_session_switch"] is True


@patch("app.services.model_switch_prompt_service.get_llm_selectability_snapshot")
def test_build_model_switch_prompt_for_unavailable_returns_none_without_options(
    mock_snapshot,
):
    mock_snapshot.return_value = []

    prompt = build_model_switch_prompt_for_unavailable(
        provider="google",
        reason_code="auth_error",
    )

    assert prompt is None
