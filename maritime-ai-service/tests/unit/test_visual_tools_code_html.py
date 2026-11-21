import json


class TestCodeHtmlResolve:
    """Test _resolve_code_html helper."""

    def test_empty_code_html_returns_none(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        assert _resolve_code_html("", "comparison", "T", {}) is None
        assert _resolve_code_html("   ", "comparison", "T", {}) is None

    def test_flag_off_ignores_code_html(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        result = _resolve_code_html("<div>Custom</div>", "comparison", "T", {})
        assert result is None

    def test_wraps_body_in_design_system(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        result = _resolve_code_html(
            '<div class="custom">Hello World</div>',
            "concept",
            "Test Title",
            {},
        )
        assert result is not None
        assert "<!DOCTYPE html>" in result
        assert "Hello World" in result
        assert "Test Title" in result  # title rendered
        assert "--accent" in result  # design system CSS vars

    def test_extracts_style_blocks(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        code = '<style>.box{color:red}</style><div class="box">Hi</div>'
        result = _resolve_code_html(code, "concept", "", {})
        assert result is not None
        assert ".box{color:red}" in result
        assert '<div class="box">Hi</div>' in result

    def test_full_html_document_passthrough(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        full_doc = "<!DOCTYPE html><html><body><p>Full doc</p></body></html>"
        result = _resolve_code_html(full_doc, "concept", "T", {})
        assert result == full_doc  # returned as-is


class TestCodeHtmlToolIntegration:
    """Test code_html param in tool_generate_visual."""

    def test_code_html_produces_inline_html_payload(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "architecture",
            "spec_json": json.dumps({"layers": [{"name": "L1", "components": ["C1"]}]}),
            "title": "Custom Arch",
            "summary": "LLM-generated HTML",
            "code_html": '<style>.custom{color:var(--accent)}</style><div class="custom">Custom SVG diagram here</div>',
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.fallback_html is not None
        assert "Custom SVG diagram here" in payload.fallback_html
        assert ".custom{color:var(--accent)}" in payload.fallback_html
        assert "<!DOCTYPE html>" in payload.fallback_html

    def test_code_html_ignored_when_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = False
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "A"},
                "right": {"title": "B"},
            }),
            "title": "Test",
            "code_html": "<div>Should be ignored</div>",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        # fallback_html should be builder output, not code_html
        if payload.fallback_html:
            assert "Should be ignored" not in payload.fallback_html

    def test_code_html_skips_auto_grouping(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope

        runtime = build_tool_runtime_context(
            session_id="session-codegen-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "presentation_intent": "chart_runtime",
                "renderer_contract": "chart_runtime",
                "visual_user_query": "Explain with charts",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({"labels": ["A"], "datasets": [{"label": "S", "data": [1]}]}),
                "title": "Custom Chart",
                "code_html": '<svg><rect width="100" height="50" fill="var(--accent)"/></svg>',
            })

        payloads = parse_visual_payloads(result)
        assert len(payloads) == 1
        assert payloads[0].renderer_kind == "inline_html"
        assert payloads[0].patch_strategy == "replace_html"
        assert payloads[0].fallback_html is not None
        assert "<rect" in payloads[0].fallback_html
