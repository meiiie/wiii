from unittest.mock import patch

from app.engine.multi_agent.graph import (
    route_decision,
    _build_domain_config,
    _build_visual_tool_runtime_metadata,
    _get_domain_greetings,
)


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


class TestVisualRuntimeMetadata:
    def test_chart_runtime_metadata_prefers_inline_html_svg(self):
        metadata = _build_visual_tool_runtime_metadata({}, "Ve bieu do so sanh toc do cac loai tau container")

        assert metadata is not None
        assert metadata["presentation_intent"] == "chart_runtime"
        assert metadata["visual_intent_mode"] == "inline_html"
        assert metadata["preferred_render_surface"] == "svg"
        assert metadata["planning_profile"] == "chart_svg"
        assert metadata["preferred_visual_tool"] == "tool_generate_visual"


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
