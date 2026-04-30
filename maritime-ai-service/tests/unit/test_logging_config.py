import logging

from app.core.logging_config import setup_logging


def test_setup_logging_silences_openai_sdk_request_logs():
    setup_logging(json_output=False, log_level="INFO")

    assert logging.getLogger("openai").level == logging.WARNING
    assert logging.getLogger("openai._base_client").level == logging.WARNING


def test_settings_repr_hides_provider_secrets():
    from app.core.config import Settings
    from app.core.config.llm import LLMConfig

    flat_settings = Settings(
        nvidia_api_key="nvapi-super-secret",
        openai_api_key="sk-super-secret",
    )
    nested_settings = LLMConfig(nvidia_api_key="nvapi-super-secret")

    assert "nvapi-super-secret" not in repr(flat_settings)
    assert "sk-super-secret" not in repr(flat_settings)
    assert "nvapi-super-secret" not in repr(nested_settings)
