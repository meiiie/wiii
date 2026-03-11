from app.engine.model_catalog import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_BENCHMARK_CANDIDATE,
    GOOGLE_DEFAULT_MODEL,
    get_chat_model_metadata,
    get_current_google_chat_models,
    get_embedding_dimensions,
    get_embedding_model_metadata,
    is_legacy_google_model,
)


def test_google_default_model_is_current():
    metadata = get_chat_model_metadata(GOOGLE_DEFAULT_MODEL)

    assert metadata is not None
    assert metadata.model_name == GOOGLE_DEFAULT_MODEL
    assert metadata.status == "current"


def test_legacy_google_model_is_marked_legacy():
    assert is_legacy_google_model("gemini-2.5-flash") is True


def test_current_google_chat_models_only_return_current_entries():
    current_models = get_current_google_chat_models()

    assert GOOGLE_DEFAULT_MODEL in current_models
    assert "gemini-2.5-flash" not in current_models


def test_embedding_models_expose_dimensions():
    default_metadata = get_embedding_model_metadata(DEFAULT_EMBEDDING_MODEL)
    candidate_metadata = get_embedding_model_metadata(EMBEDDING_BENCHMARK_CANDIDATE)

    assert default_metadata is not None
    assert default_metadata.dimensions == get_embedding_dimensions(DEFAULT_EMBEDDING_MODEL)
    assert candidate_metadata is not None
    assert candidate_metadata.dimensions == get_embedding_dimensions(
        EMBEDDING_BENCHMARK_CANDIDATE
    )
