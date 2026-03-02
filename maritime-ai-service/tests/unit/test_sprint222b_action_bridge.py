"""Sprint 222b Phase 5: HostActionBridge — validate and emit host actions."""
import pytest


class TestHostActionBridge:
    def test_validate_action_allowed(self):
        from app.engine.context.action_bridge import HostActionBridge
        capabilities_tools = [
            {"name": "create_course", "description": "Create a course",
             "input_schema": {"type": "object"}, "roles": ["teacher", "admin"]},
        ]
        bridge = HostActionBridge(capabilities_tools=capabilities_tools)
        assert bridge.validate_action("create_course", {}, "teacher") is True
        assert bridge.validate_action("create_course", {}, "admin") is True

    def test_validate_action_denied_by_role(self):
        from app.engine.context.action_bridge import HostActionBridge
        capabilities_tools = [
            {"name": "create_course", "description": "Create a course",
             "roles": ["teacher", "admin"]},
        ]
        bridge = HostActionBridge(capabilities_tools=capabilities_tools)
        assert bridge.validate_action("create_course", {}, "student") is False

    def test_validate_unknown_action_denied(self):
        from app.engine.context.action_bridge import HostActionBridge
        bridge = HostActionBridge(capabilities_tools=[])
        assert bridge.validate_action("delete_everything", {}, "admin") is False

    def test_validate_action_no_roles_allows_all(self):
        from app.engine.context.action_bridge import HostActionBridge
        capabilities_tools = [
            {"name": "navigate", "description": "Navigate to page"},
        ]
        bridge = HostActionBridge(capabilities_tools=capabilities_tools)
        assert bridge.validate_action("navigate", {}, "student") is True

    def test_emit_action_request_returns_id(self):
        from app.engine.context.action_bridge import HostActionBridge
        bridge = HostActionBridge(capabilities_tools=[
            {"name": "create_course", "description": "Create"},
        ])
        request_id = bridge.emit_action_request(
            "create_course", {"name": "Test"}, event_bus_id="bus-1"
        )
        assert request_id.startswith("req-")

    def test_emit_action_tracks_pending(self):
        from app.engine.context.action_bridge import HostActionBridge
        bridge = HostActionBridge(capabilities_tools=[
            {"name": "create_course", "description": "Create"},
        ])
        req_id = bridge.emit_action_request("create_course", {}, "bus-1")
        assert req_id in bridge.pending_requests

    def test_get_available_actions_for_role(self):
        from app.engine.context.action_bridge import HostActionBridge
        caps = [
            {"name": "create_course", "description": "Create", "roles": ["teacher", "admin"]},
            {"name": "view_grades", "description": "View", "roles": ["student", "teacher", "admin"]},
            {"name": "delete_user", "description": "Delete", "roles": ["admin"]},
        ]
        bridge = HostActionBridge(capabilities_tools=caps)
        student_actions = bridge.get_available_actions("student")
        assert len(student_actions) == 1
        assert student_actions[0]["name"] == "view_grades"
        teacher_actions = bridge.get_available_actions("teacher")
        assert len(teacher_actions) == 2

    def test_resolve_action(self):
        from app.engine.context.action_bridge import HostActionBridge
        bridge = HostActionBridge(capabilities_tools=[
            {"name": "test", "description": "Test"},
        ])
        req_id = bridge.emit_action_request("test", {}, "bus-1")
        assert req_id in bridge.pending_requests
        bridge.resolve_action(req_id, {"success": True, "data": {"id": 123}})
        assert req_id not in bridge.pending_requests

    def test_resolve_unknown_request_no_error(self):
        from app.engine.context.action_bridge import HostActionBridge
        bridge = HostActionBridge(capabilities_tools=[])
        bridge.resolve_action("nonexistent", {"success": False})
