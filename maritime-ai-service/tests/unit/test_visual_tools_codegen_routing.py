class TestCodeGenRouting:
    """Test enable_code_gen_visuals feature flag routing."""

    def test_flag_off_keeps_template_default(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}) == "template"
        assert _infer_renderer_kind("architecture", {}) == "template"

    def test_flag_on_keeps_explanatory_types_on_template(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}) == "template"
        assert _infer_renderer_kind("process", {}) == "template"
        assert _infer_renderer_kind("architecture", {}) == "template"
        assert _infer_renderer_kind("concept", {}) == "template"
        assert _infer_renderer_kind("infographic", {}) == "template"
        assert _infer_renderer_kind("matrix", {}) == "template"
        assert _infer_renderer_kind("chart", {}) == "template"
        assert _infer_renderer_kind("timeline", {}) == "template"
        assert _infer_renderer_kind("map_lite", {}) == "template"

    def test_flag_on_unknown_types_fall_through_to_template(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        # Types not in _BUILDERS fall through to template
        assert _infer_renderer_kind("simulation", {}) == "template"
        assert _infer_renderer_kind("quiz", {}) == "template"
        assert _infer_renderer_kind("react_app", {}) == "template"

    def test_explicit_renderer_kind_overrides_flag(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}, "template") == "template"

    def test_intent_resolver_prefers_inline_html_for_article_figures(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("so sanh TCP va UDP")
        assert decision.mode == "inline_html"
        assert decision.presentation_intent == "article_figure"
        assert decision.preferred_tool == "tool_generate_visual"
        assert decision.renderer_contract == "article_figure"

    def test_intent_resolver_keeps_inline_html_even_when_codegen_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("so sanh TCP va UDP")
        assert decision.mode == "inline_html"

    def test_intent_resolver_does_not_upgrade_app_mode(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("mo phong vat ly con lac")
        assert decision.mode == "app"

    def test_intent_resolver_does_not_upgrade_text_mode(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("hello world")
        assert decision.mode == "text"
