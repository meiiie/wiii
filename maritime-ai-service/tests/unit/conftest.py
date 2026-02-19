"""
Unit test conftest — shared fixtures for all unit tests.

Sprint 154: Added mock_agent_state and patch_settings factory fixtures.
"""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """Disable slowapi rate limiting in unit tests.

    The in-memory rate limiter accumulates request counts across the full
    test suite.  Since all tests share the same client IP (127.0.0.1),
    rate limits can be hit when many endpoint tests run together.
    Disabling the limiter prevents cross-test interference.
    """
    from app.core.rate_limit import limiter

    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture
def mock_agent_state():
    """Factory for AgentState dict with all required fields.

    Use directly or override fields:
        state = mock_agent_state
        state["query"] = "custom query"
    """
    return {
        "query": "test query",
        "user_id": "test-user",
        "session_id": "test-session",
        "response": "",
        "final_response": "",
        "thinking_content": "",
        "routing_decision": {},
        "routing_metadata": {},
        "tool_call_events": [],
        "domain_id": "maritime",
        "domain_config": {"name_vi": "Hàng hải"},
        "_trace_id": None,
        "_event_bus_id": None,
        "context": {
            "user_name": "Test User",
            "pronoun_style": "tôi-bạn",
            "is_follow_up": False,
            "user_facts": [],
            "recent_phrases": [],
            "langchain_messages": [],
            "total_responses": 0,
            "name_usage_count": 0,
            "mood_hint": "",
        },
        "current_agent": "",
        "next_agent": "",
        "agent_outputs": {},
    }


@pytest.fixture
def patch_settings(mock_settings):
    """Patch get_settings() globally for the test.

    Usage:
        def test_something(patch_settings):
            patch_settings.enable_product_search = True
            # ... test code using settings ...
    """
    with patch("app.core.config.get_settings", return_value=mock_settings):
        yield mock_settings
