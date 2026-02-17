"""
Unit tests for Wiii exception hierarchy.

Tests exception types, HTTP status codes, error codes, and serialization.
"""
import pytest

from app.core.exceptions import (
    WiiiException,
    ChatServiceError,
    RetrievalError,
    LLMError,
    RepositoryError,
    DomainError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test that all exceptions inherit from WiiiException."""

    @pytest.mark.parametrize("exc_class", [
        ChatServiceError,
        RetrievalError,
        LLMError,
        RepositoryError,
        DomainError,
        ValidationError,
    ])
    def test_inherits_from_wiii_exception(self, exc_class):
        assert issubclass(exc_class, WiiiException)

    @pytest.mark.parametrize("exc_class", [
        WiiiException,
        ChatServiceError,
        RetrievalError,
        LLMError,
        RepositoryError,
        DomainError,
        ValidationError,
    ])
    def test_inherits_from_base_exception(self, exc_class):
        assert issubclass(exc_class, Exception)


class TestHTTPStatusCodes:
    """Test that each exception maps to the correct HTTP status code."""

    def test_wiii_exception_500(self):
        assert WiiiException.http_status == 500

    def test_chat_service_error_500(self):
        assert ChatServiceError.http_status == 500

    def test_retrieval_error_503(self):
        assert RetrievalError.http_status == 503

    def test_llm_error_502(self):
        assert LLMError.http_status == 502

    def test_repository_error_503(self):
        assert RepositoryError.http_status == 503

    def test_domain_error_404(self):
        assert DomainError.http_status == 404

    def test_validation_error_400(self):
        assert ValidationError.http_status == 400


class TestErrorCodes:
    """Test that each exception has a unique error code."""

    def test_error_codes_are_unique(self):
        codes = [
            WiiiException.error_code,
            ChatServiceError.error_code,
            RetrievalError.error_code,
            LLMError.error_code,
            RepositoryError.error_code,
            DomainError.error_code,
            ValidationError.error_code,
        ]
        assert len(codes) == len(set(codes)), f"Duplicate error codes found: {codes}"

    @pytest.mark.parametrize("exc_class,expected_code", [
        (ChatServiceError, "CHAT_SERVICE_ERROR"),
        (RetrievalError, "RETRIEVAL_FAILED"),
        (LLMError, "LLM_ERROR"),
        (RepositoryError, "REPOSITORY_ERROR"),
        (DomainError, "DOMAIN_NOT_FOUND"),
        (ValidationError, "VALIDATION_ERROR"),
    ])
    def test_error_code_value(self, exc_class, expected_code):
        assert exc_class.error_code == expected_code


class TestExceptionInstantiation:
    """Test exception creation and attribute access."""

    def test_basic_creation(self):
        exc = WiiiException("something broke")
        assert exc.message == "something broke"
        assert str(exc) == "something broke"
        assert exc.details is None

    def test_creation_with_details(self):
        exc = RetrievalError("search failed", details="Neo4j connection timeout")
        assert exc.message == "search failed"
        assert exc.details == "Neo4j connection timeout"

    def test_empty_message(self):
        exc = LLMError()
        assert exc.message == ""

    def test_exception_can_be_raised_and_caught(self):
        with pytest.raises(WiiiException):
            raise ChatServiceError("pipeline failed")

    def test_specific_catch(self):
        with pytest.raises(RetrievalError):
            raise RetrievalError("no docs found")

    def test_base_catches_derived(self):
        with pytest.raises(WiiiException):
            raise LLMError("Gemini API timeout")
