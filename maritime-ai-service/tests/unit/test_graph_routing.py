"""
Unit tests for Multi-Agent Graph routing logic.

Tests:
- route_decision() for all 4 routes
- should_skip_grader() with confidence above/below threshold
- _build_domain_config() fallback behavior
- _get_domain_greetings() fallback behavior
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.multi_agent.graph import (
    route_decision,
    should_skip_grader,
    _build_domain_config,
    _get_domain_greetings,
)


# =============================================================================
# Tests: route_decision
# =============================================================================

class TestRouteDecision:
    def test_routes_to_rag_agent(self):
        state = {"next_agent": "rag_agent"}
        assert route_decision(state) == "rag_agent"

    def test_routes_to_tutor_agent(self):
        state = {"next_agent": "tutor_agent"}
        assert route_decision(state) == "tutor_agent"

    def test_routes_to_memory_agent(self):
        state = {"next_agent": "memory_agent"}
        assert route_decision(state) == "memory_agent"

    def test_routes_to_direct(self):
        state = {"next_agent": "direct"}
        assert route_decision(state) == "direct"

    def test_routes_to_code_studio_agent(self):
        state = {"next_agent": "code_studio_agent"}
        assert route_decision(state) == "code_studio_agent"

    def test_unknown_agent_defaults_to_direct(self):
        state = {"next_agent": "unknown_agent"}
        assert route_decision(state) == "direct"

    def test_missing_next_agent_defaults_to_rag(self):
        state = {}
        assert route_decision(state) == "rag_agent"

    def test_empty_next_agent_defaults_to_direct(self):
        state = {"next_agent": ""}
        assert route_decision(state) == "direct"


# =============================================================================
# Tests: should_skip_grader
# =============================================================================

class TestShouldSkipGrader:
    def test_skip_when_trace_confidence_high(self):
        trace = MagicMock()
        trace.final_confidence = 0.92
        state = {"reasoning_trace": trace}
        assert should_skip_grader(state) == "synthesizer"

    def test_no_skip_when_trace_confidence_low(self):
        trace = MagicMock()
        trace.final_confidence = 0.60
        state = {"reasoning_trace": trace}
        assert should_skip_grader(state) == "grader"

    def test_skip_when_crag_confidence_high(self):
        state = {"crag_confidence": 0.90}
        assert should_skip_grader(state) == "synthesizer"

    def test_no_skip_when_crag_confidence_low(self):
        state = {"crag_confidence": 0.50}
        assert should_skip_grader(state) == "grader"

    def test_no_skip_with_empty_state(self):
        state = {}
        assert should_skip_grader(state) == "grader"

    def test_no_skip_when_trace_has_no_confidence(self):
        trace = MagicMock(spec=[])  # No attributes
        state = {"reasoning_trace": trace}
        assert should_skip_grader(state) == "grader"

    def test_skip_at_exact_threshold(self):
        trace = MagicMock()
        trace.final_confidence = 0.85
        state = {"reasoning_trace": trace}
        assert should_skip_grader(state) == "synthesizer"

    @patch("app.engine.multi_agent.graph.settings")
    def test_uses_settings_threshold(self, mock_settings):
        mock_settings.quality_skip_threshold = 0.95
        trace = MagicMock()
        trace.final_confidence = 0.90
        state = {"reasoning_trace": trace}
        # 0.90 < 0.95 so should NOT skip
        assert should_skip_grader(state) == "grader"


# =============================================================================
# Tests: _build_domain_config
# =============================================================================

class TestBuildDomainConfig:
    def test_fallback_returns_dict(self):
        """When domain registry returns None, returns generic fallback."""
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert isinstance(config, dict)
        assert "domain_name" in config
        assert "domain_id" in config
        assert "routing_keywords" in config

    def test_fallback_has_rag_description(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert "rag_description" in config
        assert len(config["rag_description"]) > 0

    def test_fallback_has_tutor_description(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert "tutor_description" in config
        assert len(config["tutor_description"]) > 0


# =============================================================================
# Tests: _get_domain_greetings
# =============================================================================

class TestGetDomainGreetings:
    def test_fallback_returns_dict(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert isinstance(greetings, dict)

    def test_fallback_has_vietnamese_greetings(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert "xin chào" in greetings
        assert "hi" in greetings

    def test_fallback_has_english_greetings(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert "hello" in greetings
        assert "thanks" in greetings
