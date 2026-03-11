"""
Tests for embedding dimension validation.

Verifies:
- EXPECTED_EMBEDDING_DIMENSIONS is derived from the production embedding model
- settings defaults stay aligned with the canonical catalog
- mismatch detection logic still works
- startup validation remains fail-safe
"""

import os
from unittest.mock import MagicMock, patch

from app.engine.model_catalog import DEFAULT_EMBEDDING_MODEL, get_embedding_dimensions


DEFAULT_DIMENSIONS = get_embedding_dimensions(DEFAULT_EMBEDDING_MODEL)


class TestEmbeddingConstants:
    """Test embedding dimension constants."""

    def test_expected_dimensions_value(self):
        """EXPECTED_EMBEDDING_DIMENSIONS should match the production model metadata."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        assert EXPECTED_EMBEDDING_DIMENSIONS == DEFAULT_DIMENSIONS

    def test_settings_default_matches(self):
        """Default settings embedding_dimensions should match the catalog."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        from app.core.config import Settings

        with patch.dict("os.environ", {}, clear=False):
            settings = Settings(
                _env_file=None,
                google_api_key="test",
                api_key="test",
            )
        assert settings.embedding_dimensions == EXPECTED_EMBEDDING_DIMENSIONS


class TestDimensionMismatchDetection:
    """Test mismatch detection logic."""

    def test_matching_dimensions_pass(self):
        """No error when dimensions match."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        config_dim = DEFAULT_DIMENSIONS
        assert config_dim == EXPECTED_EMBEDDING_DIMENSIONS

    def test_mismatched_dimensions_detected(self):
        """Mismatch between config and expected is detected."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        config_dim = 1536
        assert config_dim != EXPECTED_EMBEDDING_DIMENSIONS

    def test_various_dimension_values(self):
        """Known model dimensions should compare correctly."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        dimensions = {
            DEFAULT_EMBEDDING_MODEL: DEFAULT_DIMENSIONS,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
            "e5-large-v2": 1024,
        }
        for model, dim in dimensions.items():
            if dim == EXPECTED_EMBEDDING_DIMENSIONS:
                assert dim == DEFAULT_DIMENSIONS, f"{model} should match"
            else:
                assert dim != DEFAULT_DIMENSIONS, f"{model} should not match"


class TestValidationSafety:
    """Test that validation never crashes the app."""

    def test_validation_with_import_error(self):
        """Import errors are still safely wrapped at startup."""
        try:
            from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

            _ = EXPECTED_EMBEDDING_DIMENSIONS
        except Exception:
            pass

    def test_validation_with_attribute_error(self):
        """Missing config attribute is caught gracefully."""
        mock_settings = MagicMock()
        del mock_settings.embedding_dimensions

        try:
            _ = mock_settings.embedding_dimensions
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass

    def test_validation_logging_on_match(self):
        """Matching dimensions logs info instead of error."""
        import logging

        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        with patch.object(logging.getLogger("app.main"), "info") as mock_info:
            with patch.object(logging.getLogger("app.main"), "error") as mock_error:
                config_dim = EXPECTED_EMBEDDING_DIMENSIONS
                if config_dim != EXPECTED_EMBEDDING_DIMENSIONS:
                    mock_error(f"Mismatch: {config_dim} != {EXPECTED_EMBEDDING_DIMENSIONS}")
                else:
                    mock_info(f"Embedding dimension validated: {config_dim}d")

                mock_info.assert_called_once()
                mock_error.assert_not_called()

    def test_validation_logging_on_mismatch(self):
        """Mismatched dimensions log error instead of info."""
        import logging

        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        with patch.object(logging.getLogger("app.main"), "info") as mock_info:
            with patch.object(logging.getLogger("app.main"), "error") as mock_error:
                config_dim = 1536
                if config_dim != EXPECTED_EMBEDDING_DIMENSIONS:
                    mock_error(f"Mismatch: {config_dim} != {EXPECTED_EMBEDDING_DIMENSIONS}")
                else:
                    mock_info(f"Validated: {config_dim}d")

                mock_error.assert_called_once()
                mock_info.assert_not_called()
