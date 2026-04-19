"""Tests for Tweaks Protocol (Phase 2 — Claude Design pattern)."""

import json
import re

from app.engine.tools.visual_html_core import (
    _TWEAKS_CSS,
    _TWEAKS_JS,
    _tweaks_inject,
    _wrap_html,
    _wrap_html_react,
)
from app.engine.tools.visual_scaffolds import build_scaffold


class TestTweaksInjection:
    """Verify Tweaks protocol is injected into HTML wrappers."""

    def test_wrap_html_includes_tweaks_js(self):
        html = _wrap_html("", "<p>Hello</p>")
        assert "__edit_mode_available" in html

    def test_wrap_html_includes_editmode_markers(self):
        html = _wrap_html("", "<p>Hello</p>")
        assert "/*EDITMODE-BEGIN*/" in html
        assert "/*EDITMODE-END*/" in html

    def test_wrap_html_react_includes_tweaks_js(self):
        html = _wrap_html_react("", "const App = () => <div/>;")
        assert "__edit_mode_available" in html

    def test_wrap_html_react_includes_editmode_markers(self):
        html = _wrap_html_react("", "const App = () => <div/>;")
        assert "/*EDITMODE-BEGIN*/" in html

    def test_tweaks_js_registers_message_listener(self):
        assert "addEventListener" in _TWEAKS_JS
        assert "message" in _TWEAKS_JS

    def test_tweaks_js_posts_availability(self):
        assert "__edit_mode_available" in _TWEAKS_JS
        assert "postMessage" in _TWEAKS_JS

    def test_tweaks_js_handles_activate(self):
        assert "__activate_edit_mode" in _TWEAKS_JS

    def test_tweaks_js_handles_deactivate(self):
        assert "__deactivate_edit_mode" in _TWEAKS_JS

    def test_tweaks_js_persists_edits(self):
        assert "__edit_mode_set_keys" in _TWEAKS_JS

    def test_tweaks_panel_css_hidden_by_default(self):
        assert "display:none" in _TWEAKS_CSS.replace(" ", "")
        assert ".wiii-tweaks-panel" in _TWEAKS_CSS

    def test_tweaks_inject_custom_state(self):
        block = _tweaks_inject('{"--accent":"#D97757"}')
        assert '/*EDITMODE-BEGIN*/{"--accent":"#D97757"}/*EDITMODE-END*/' in block

    def test_tweaks_inject_empty_state(self):
        block = _tweaks_inject("{}")
        assert "/*EDITMODE-BEGIN*/{}/*EDITMODE-END*/" in block


class TestScaffoldTweaks:
    """Verify scaffolds include scaffold-specific tweak defaults."""

    def test_simulation_scaffold_has_tweak_defaults(self):
        html = build_scaffold("simulation", "Physics Sim")
        assert "--sim-speed" in html
        assert "--sim-intensity" in html
        assert "/*EDITMODE-BEGIN*/" in html

    def test_quiz_scaffold_has_tweak_defaults(self):
        html = build_scaffold("quiz", "Quiz")
        assert "--quiz-accent" in html
        assert "/*EDITMODE-BEGIN*/" in html

    def test_dashboard_scaffold_has_tweak_defaults(self):
        html = build_scaffold("dashboard", "Dash")
        assert "--dash-accent" in html
        assert "/*EDITMODE-BEGIN*/" in html

    def test_tweak_defaults_are_valid_json(self):
        """Extract JSON between EDITMODE markers and verify it is valid."""
        for kind in ("simulation", "quiz", "dashboard"):
            html = build_scaffold(kind, "Test")
            match = re.search(
                r'/\*EDITMODE-BEGIN\*/(.*?)/\*EDITMODE-END\*/',
                html,
            )
            assert match is not None, f"No EDITMODE markers in {kind} scaffold"
            json_str = match.group(1)
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict), f"{kind} defaults not a dict"
            assert len(parsed) > 0, f"{kind} defaults empty"
