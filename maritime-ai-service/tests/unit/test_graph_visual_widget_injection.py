from langchain_core.messages import AIMessage

from app.engine.multi_agent.graph import _inject_widget_blocks_from_tool_results


def test_skips_widget_injection_for_structured_explanatory_turns():
    response = AIMessage(content="Day la cau tra loi dang prose.")
    tool_events = [
        {
            "type": "result",
            "name": "tool_generate_interactive_chart",
            "result": "```widget\n<div>Legacy chart</div>\n```",
            "id": "tool-1",
        }
    ]

    result = _inject_widget_blocks_from_tool_results(
        response,
        tool_events,
        query="Explain Kimi linear attention in charts",
        structured_visuals_enabled=True,
    )

    assert result.content == "Day la cau tra loi dang prose."


def test_strips_widget_blocks_when_structured_visual_events_exist():
    response = AIMessage(
        content="```widget\n<div>Legacy chart</div>\n```\n\nBridge prose sau visual.",
    )
    tool_events = [
        {
            "type": "visual_open",
            "name": "tool_generate_visual",
            "visual_session_id": "vs-1",
            "id": "tool-structured",
        }
    ]

    result = _inject_widget_blocks_from_tool_results(
        response,
        tool_events,
        query="Explain Kimi linear attention in charts",
        structured_visuals_enabled=True,
    )

    assert "```widget" not in result.content
    assert "Bridge prose sau visual." in result.content


def test_keeps_widget_injection_for_legacy_app_fallback():
    response = AIMessage(content="Minh se chen mo phong ngay sau day.")
    tool_events = [
        {
            "type": "result",
            "name": "tool_generate_rich_visual",
            "result": "```widget\n<div>App fallback</div>\n```",
            "id": "tool-app",
        }
    ]

    result = _inject_widget_blocks_from_tool_results(
        response,
        tool_events,
        query="Hay mo phong vat ly con lac",
        structured_visuals_enabled=True,
    )

    assert "```widget" in result.content
    assert "Minh se chen mo phong ngay sau day." in result.content
