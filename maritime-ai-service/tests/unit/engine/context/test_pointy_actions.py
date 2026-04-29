"""Smoke tests for the Wiii Pointy action reference module."""
from app.engine.context.pointy_actions import (
    POINTY_ACTION_HIGHLIGHT,
    POINTY_ACTION_NAVIGATE,
    POINTY_ACTION_SCROLL_TO,
    POINTY_ACTION_SHOW_TOUR,
    POINTY_ACTIONS,
    reference_capabilities,
)


def test_action_names_are_stable():
    assert POINTY_ACTION_HIGHLIGHT == "ui.highlight"
    assert POINTY_ACTION_SCROLL_TO == "ui.scroll_to"
    assert POINTY_ACTION_NAVIGATE == "ui.navigate"
    assert POINTY_ACTION_SHOW_TOUR == "ui.show_tour"
    assert set(POINTY_ACTIONS) == {
        POINTY_ACTION_HIGHLIGHT,
        POINTY_ACTION_SCROLL_TO,
        POINTY_ACTION_NAVIGATE,
        POINTY_ACTION_SHOW_TOUR,
    }


def test_reference_capabilities_shape():
    caps = reference_capabilities()
    assert caps["host_type"] == "lms"
    assert "page" in caps["surfaces"]
    tool_names = [t["name"] for t in caps["tools"]]
    assert tool_names == list(POINTY_ACTIONS)
    for tool in caps["tools"]:
        assert tool["mutates_state"] is False
        assert tool["requires_confirmation"] is False
        assert tool["surface"] == "page"
        assert "input_schema" in tool


def test_reference_capabilities_is_valid_for_pydantic_host_capabilities():
    """The reference payload must be accepted by HostCapabilities unchanged."""
    from app.engine.context.host_context import HostCapabilities

    caps = HostCapabilities(**reference_capabilities())
    assert caps.host_type == "lms"
    assert len(caps.tools) == len(POINTY_ACTIONS)
