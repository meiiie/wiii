import json
import logging
from unittest.mock import patch

from app.api.v1.chat_endpoint_presenter import build_chat_completion_error_response
from app.core.exceptions import ProviderUnavailableError


def test_build_chat_completion_error_response_includes_model_switch_prompt():
    with patch(
        "app.api.v1.chat_endpoint_presenter.build_model_switch_prompt_for_unavailable",
        return_value={"trigger": "provider_unavailable"},
    ), patch(
        "app.api.v1.chat_endpoint_presenter.record_llm_runtime_observation",
    ) as mock_record:
        response = build_chat_completion_error_response(
            logger=logging.getLogger(__name__),
            error=ProviderUnavailableError(
                provider="google",
                reason_code="rate_limit",
                message="Provider tam thoi ban hoac da cham gioi han.",
            ),
            request_id="req-model-switch",
        )

    payload = json.loads(response.body)
    assert payload["error_code"] == "PROVIDER_UNAVAILABLE"
    assert payload["provider"] == "google"
    assert payload["reason_code"] == "rate_limit"
    assert payload["model_switch_prompt"]["trigger"] == "provider_unavailable"
    mock_record.assert_called_once()
