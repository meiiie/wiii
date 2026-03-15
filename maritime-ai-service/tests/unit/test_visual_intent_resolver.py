from app.engine.multi_agent.visual_intent_resolver import (
    detect_visual_patch_request,
    filter_tools_for_visual_intent,
    preferred_visual_tool_name,
    resolve_visual_intent,
)


def test_resolves_comparison_visual():
    decision = resolve_visual_intent("So sanh softmax attention voi linear attention")
    assert decision.mode == "template"
    assert decision.force_tool is True
    assert decision.visual_type == "comparison"


def test_resolves_process_visual():
    decision = resolve_visual_intent("Giai thich quy trinh docking step by step")
    assert decision.mode == "template"
    assert decision.visual_type == "process"


def test_resolves_architecture_visual():
    decision = resolve_visual_intent("Mo ta kien truc he thong RAG nhieu layer")
    assert decision.mode == "template"
    assert decision.visual_type == "architecture"


def test_resolves_chart_request_as_template():
    decision = resolve_visual_intent("Ve bieu do KPI theo thang")
    assert decision.mode == "template"
    assert decision.force_tool is True
    assert decision.visual_type == "chart"


def test_resolves_mermaid_request():
    decision = resolve_visual_intent("Ve flowchart quy trinh onboarding")
    assert decision.mode == "mermaid"
    assert decision.force_tool is True


def test_resolves_app_request():
    decision = resolve_visual_intent("Tao dashboard app HTML cho chien dich nay")
    assert decision.mode == "app"
    assert decision.force_tool is True


def test_resolves_vietnamese_simulation_request_as_app():
    decision = resolve_visual_intent("Hay mo phong vat ly con lac co the keo tha")
    assert decision.mode == "app"
    assert decision.force_tool is True
    assert decision.visual_type == "simulation"


def test_resolves_inline_html_request():
    decision = resolve_visual_intent("Hay lam mot editorial visual animated de giai thich Kimi linear attention")
    assert decision.mode == "inline_html"
    assert decision.force_tool is True


def test_ignores_false_positive_visual_terms():
    decision = resolve_visual_intent("Visual Studio Code khac Visual Basic the nao?")
    assert decision.mode == "text"
    assert decision.force_tool is False


def test_detects_visual_patch_followup():
    assert detect_visual_patch_request("Highlight only the bottleneck and keep the same visual session.")
    assert detect_visual_patch_request("Biến sơ đồ này thành 3 bước")


def test_does_not_detect_patch_for_fresh_visual_request():
    assert not detect_visual_patch_request("Explain Kimi linear attention in charts")


def test_preferred_visual_tool_name_prefers_structured_visual_tool():
    assert preferred_visual_tool_name(True) == "tool_generate_visual"
    assert preferred_visual_tool_name(False) == "tool_generate_rich_visual"


def test_filter_tools_for_visual_intent_drops_legacy_visual_tools():
    class _Tool:
        def __init__(self, name: str):
            self.name = name

    decision = resolve_visual_intent("Explain Kimi linear attention in charts")
    tools = [
        _Tool("tool_generate_interactive_chart"),
        _Tool("tool_generate_chart"),
        _Tool("tool_generate_rich_visual"),
        _Tool("tool_generate_visual"),
        _Tool("tool_web_search"),
    ]

    filtered = filter_tools_for_visual_intent(
        tools,
        decision,
        structured_visuals_enabled=True,
    )

    assert [tool.name for tool in filtered] == ["tool_generate_visual", "tool_web_search"]
