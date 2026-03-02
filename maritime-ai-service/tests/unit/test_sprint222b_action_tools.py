"""Sprint 222b Phase 5: Dynamic tool generation from host capabilities."""
import pytest


class TestGenerateHostActionTools:
    def test_generates_tools_for_role(self):
        from app.engine.context.action_tools import generate_host_action_tools
        capabilities_tools = [
            {"name": "create_course", "description": "Create a new course",
             "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
             "roles": ["teacher", "admin"]},
            {"name": "view_grades", "description": "View student grades",
             "roles": ["student", "teacher", "admin"]},
        ]
        tools = generate_host_action_tools(capabilities_tools, "student", event_bus_id="bus-1")
        assert len(tools) == 1
        assert tools[0].name == "host_action__view_grades"

    def test_generates_all_for_admin(self):
        from app.engine.context.action_tools import generate_host_action_tools
        capabilities_tools = [
            {"name": "create_course", "description": "Create", "roles": ["teacher", "admin"]},
            {"name": "view_grades", "description": "View", "roles": ["student", "teacher", "admin"]},
        ]
        tools = generate_host_action_tools(capabilities_tools, "admin", event_bus_id="bus-1")
        assert len(tools) == 2

    def test_tool_name_prefix(self):
        from app.engine.context.action_tools import generate_host_action_tools
        tools = generate_host_action_tools(
            [{"name": "navigate", "description": "Navigate to page"}],
            "student", event_bus_id="bus-1",
        )
        assert tools[0].name == "host_action__navigate"

    def test_tool_is_callable(self):
        from app.engine.context.action_tools import generate_host_action_tools
        tools = generate_host_action_tools(
            [{"name": "navigate", "description": "Go to page",
              "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}}}],
            "student", event_bus_id="bus-1",
        )
        result = tools[0].invoke({"url": "/course/123"})
        assert "navigate" in str(result).lower() or "req-" in str(result)

    def test_empty_capabilities_returns_empty(self):
        from app.engine.context.action_tools import generate_host_action_tools
        tools = generate_host_action_tools([], "admin", event_bus_id="bus-1")
        assert tools == []

    def test_no_roles_means_all_allowed(self):
        from app.engine.context.action_tools import generate_host_action_tools
        tools = generate_host_action_tools(
            [{"name": "open_help", "description": "Open help panel"}],
            "student", event_bus_id="bus-1",
        )
        assert len(tools) == 1
