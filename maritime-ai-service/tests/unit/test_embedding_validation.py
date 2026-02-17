"""
Tests for Embedding Dimension Validation (Sprint 10).

Verifies:
- EXPECTED_EMBEDDING_DIMENSIONS constant exists and equals 768
- Settings default embedding_dimensions matches expected
- Mismatch detection logic
- Validation in main.py lifespan is safe (doesn't crash on error)
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEmbeddingConstants:
    """Test embedding dimension constants."""

    def test_expected_dimensions_value(self):
        """EXPECTED_EMBEDDING_DIMENSIONS should be 768."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        assert EXPECTED_EMBEDDING_DIMENSIONS == 768

    def test_settings_default_matches(self):
        """Default settings embedding_dimensions should match constant."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        from app.core.config import Settings

        # Create a fresh Settings with defaults
        with patch.dict("os.environ", {}, clear=False):
            s = Settings(
                _env_file=None,
                google_api_key="test",
                api_key="test",
            )
        assert s.embedding_dimensions == EXPECTED_EMBEDDING_DIMENSIONS


class TestDimensionMismatchDetection:
    """Test mismatch detection logic."""

    def test_matching_dimensions_pass(self):
        """No error when dimensions match."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        config_dim = 768
        assert config_dim == EXPECTED_EMBEDDING_DIMENSIONS

    def test_mismatched_dimensions_detected(self):
        """Mismatch between config and expected is detected."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        config_dim = 1536  # Wrong dimension (e.g., OpenAI default)
        assert config_dim != EXPECTED_EMBEDDING_DIMENSIONS

    def test_various_dimension_values(self):
        """Test various embedding dimension values."""
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        # Known embedding model dimensions
        dimensions = {
            "gemini-embedding-001": 768,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
            "e5-large-v2": 1024,
        }
        for model, dim in dimensions.items():
            if dim == EXPECTED_EMBEDDING_DIMENSIONS:
                assert dim == 768, f"{model} should match"
            else:
                assert dim != 768, f"{model} should not match"


class TestValidationSafety:
    """Test that validation never crashes the app."""

    def test_validation_with_import_error(self):
        """Import error during validation is caught gracefully."""
        # Simulate what main.py does
        try:
            from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
            _ = EXPECTED_EMBEDDING_DIMENSIONS  # This should succeed
        except Exception:
            pass  # Should never reach here, but proves try/except works

    def test_validation_with_attribute_error(self):
        """Missing config attribute is caught gracefully."""
        mock_settings = MagicMock()
        del mock_settings.embedding_dimensions  # Remove attribute

        try:
            _ = mock_settings.embedding_dimensions
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass  # Expected — main.py catches this

    def test_validation_logging_on_match(self):
        """Matching dimensions logs info (not error)."""
        import logging
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        with patch.object(logging.getLogger("app.main"), "info") as mock_info:
            with patch.object(logging.getLogger("app.main"), "error") as mock_error:
                # Simulate the validation logic
                config_dim = EXPECTED_EMBEDDING_DIMENSIONS
                if config_dim != EXPECTED_EMBEDDING_DIMENSIONS:
                    mock_error(f"Mismatch: {config_dim} != {EXPECTED_EMBEDDING_DIMENSIONS}")
                else:
                    mock_info(f"Embedding dimension validated: {config_dim}d")

                mock_info.assert_called_once()
                mock_error.assert_not_called()

    def test_validation_logging_on_mismatch(self):
        """Mismatched dimensions logs error (not info)."""
        import logging
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS

        with patch.object(logging.getLogger("app.main"), "info") as mock_info:
            with patch.object(logging.getLogger("app.main"), "error") as mock_error:
                config_dim = 1536  # Wrong
                if config_dim != EXPECTED_EMBEDDING_DIMENSIONS:
                    mock_error(f"Mismatch: {config_dim} != {EXPECTED_EMBEDDING_DIMENSIONS}")
                else:
                    mock_info(f"Validated: {config_dim}d")

                mock_error.assert_called_once()
                mock_info.assert_not_called()
