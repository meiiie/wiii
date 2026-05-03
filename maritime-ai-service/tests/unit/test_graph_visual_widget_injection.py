from app.engine.messages import Message

from app.engine.multi_agent.graph import _inject_widget_blocks_from_tool_results


def test_skips_widget_injection_for_structured_explanatory_turns():
    response = Message(role="assistant", content="Day la cau tra loi dang prose.")
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
    response = Message(role="assistant",
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
    response = Message(role="assistant", content="Minh se chen mo phong ngay sau day.")
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


def test_strips_markdown_placeholder_when_visual_already_open():
    response = Message(role="assistant",
        content=(
            "Day la bieu do bien dong gia dau.\n\n"
            "![Bieu do gia dau](https://example.com/chart-placeholder)\n\n"
            "Takeaway ngan sau visual."
        )
    )
    tool_events = [
        {
            "type": "visual_open",
            "name": "tool_generate_visual",
            "visual_session_id": "vs-chart-1",
            "id": "tool-structured",
        }
    ]

    result = _inject_widget_blocks_from_tool_results(
        response,
        tool_events,
        query="Visual cho minh xem thong ke gia dau may ngay gan day",
        structured_visuals_enabled=True,
    )

    assert "chart-placeholder" not in result.content
    assert "![" not in result.content
    assert "Takeaway ngan sau visual." in result.content


def test_strips_markdown_placeholder_even_without_structured_visual_flag():
    response = Message(role="assistant",
        content=(
            "Day la bieu do bien dong gia dau.\n\n"
            "![Bieu do gia dau](https://example.com/chart-placeholder)\n\n"
            "Takeaway ngan sau visual."
        )
    )
    tool_events = [
        {
            "type": "visual_open",
            "name": "tool_generate_visual",
            "visual_session_id": "vs-chart-2",
            "id": "tool-structured",
        }
    ]

    result = _inject_widget_blocks_from_tool_results(
        response,
        tool_events,
        query="Visual cho minh xem thong ke gia dau may ngay gan day",
        structured_visuals_enabled=False,
    )

    assert "chart-placeholder" not in result.content
    assert "![" not in result.content
