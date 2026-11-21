class TestCreateVisualCodeTool:
    """Test tool_create_visual_code — dedicated code-gen visual tool."""

    def test_requires_code_html(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": "",
            "title": "Empty",
        })
        assert "Error" in result
        assert "BẮT BUỘC" in result

    def test_rejects_too_short_code_html(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": "<div>Hi</div>",  # Too short (< 50 chars)
            "title": "Short",
        })
        assert "Error" in result
        assert "quá ngắn" in result

    def test_rejects_when_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = False
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": "<div>Hello</div>",
            "title": "Test",
        })
        assert "Error" in result

    def test_produces_code_studio_app_payload(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": '<style>.box{color:var(--accent);padding:20px;border:1.5px solid var(--border);border-radius:var(--radius);background:var(--bg2)}</style><div class="box">Hello World — visual content with real styling</div>',
            "title": "Test Visual",
        })
        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.renderer_kind == "app"
        assert payload.shell_variant == "immersive"
        assert payload.patch_strategy == "app_state"
        assert payload.title == "Test Visual"
        assert payload.presentation_intent == "code_studio_app"
        assert payload.renderer_contract == "host_shell"
        assert payload.studio_lane == "app"
        assert payload.fallback_html is not None
        assert "<!DOCTYPE html>" in payload.fallback_html
        assert "Hello World" in payload.fallback_html
        assert ".box" in payload.fallback_html

    def test_app_lane_never_returns_template_renderer_even_for_comparison_visual_type(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-comparison-app",
            user_id="user-1",
            user_role="admin",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "comparison",
            },
        )

        # Quality-gate-compliant HTML (score >= 6/10): CSS vars, dark/light,
        # controls, readouts, bridge, grid layout, sufficient depth
        _rich_html = "\n".join([
            "<style>",
            ":root { --bg: #0f172a; --fg: #e2e8f0; --accent: #38bdf8; --surface: #1e293b; --border: #475569; }",
            "@media (prefers-color-scheme: light) { :root { --bg: #f8fafc; --fg: #0f172a; } }",
            ".layout { display: grid; grid-template-columns: 1fr 300px; gap: 16px; padding: 16px; }",
            "@media (max-width: 768px) { .layout { grid-template-columns: 1fr; } }",
            ".box { padding: 20px; background: var(--surface); border-radius: 8px; }",
            ".readout { color: var(--accent); font-variant-numeric: tabular-nums; }",
            "</style>",
            '<div class="layout">',
            '  <div class="box">',
            "    <h2>Container Speed Explorer</h2>",
            "    <p>Comparison app with custom interaction surface and enough detail for validation.</p>",
            '    <div class="readout"><span id="val-a">0</span> vs <span id="val-b">0</span></div>',
            "  </div>",
            '  <div class="box">',
            '    <label>Speed A <input type="range" min="0" max="100" value="50" id="speed-a"></label>',
            '    <label>Speed B <input type="range" min="0" max="100" value="50" id="speed-b"></label>',
            "    <button id=\"reset\">Reset</button>",
            "  </div>",
            "</div>",
            "<script>",
            "(function() {",
            "  const a = document.getElementById('speed-a');",
            "  const b = document.getElementById('speed-b');",
            "  const va = document.getElementById('val-a');",
            "  const vb = document.getElementById('val-b');",
            "  function update() { va.textContent = a.value; vb.textContent = b.value; }",
            "  a.addEventListener('input', update);",
            "  b.addEventListener('input', update);",
            "  document.getElementById('reset').addEventListener('click', function() {",
            "    a.value = 50; b.value = 50; update();",
            "    window.WiiiVisualBridge?.reportResult?.('reset', {a:50,b:50}, 'Reset done', 'ok');",
            "  });",
            "  update();",
        ] + [f"  // line {i}" for i in range(80)] + [
            "})();",
            "</script>",
        ])

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": _rich_html,
                "title": "Container Speed Explorer",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.renderer_kind == "app"
        assert payload.shell_variant == "immersive"
        assert payload.patch_strategy == "app_state"
        assert payload.fallback_html is not None
        assert "Container Speed Explorer" in payload.fallback_html

    def test_artifact_lane_returns_inline_html_with_fallback(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-artifact",
            user_id="user-1",
            user_role="admin",
            metadata={
                "presentation_intent": "artifact",
                "studio_lane": "artifact",
                "artifact_kind": "html_app",
                "visual_requested_type": "comparison",
            },
        )

        # Quality-gate-compliant HTML (score >= 6/10)
        _rich_html = "\n".join([
            "<style>",
            ":root { --bg: #0f172a; --fg: #e2e8f0; --accent: #38bdf8; --surface: #1e293b; --border: #475569; }",
            "@media (prefers-color-scheme: light) { :root { --bg: #f8fafc; --fg: #0f172a; } }",
            ".layout { display: grid; grid-template-columns: 1fr 300px; gap: 16px; padding: 16px; }",
            "@media (max-width: 768px) { .layout { grid-template-columns: 1fr; } }",
            ".box { padding: 20px; background: var(--surface); border-radius: 8px; }",
            ".readout { color: var(--accent); }",
            "</style>",
            '<div class="layout">',
            '  <div class="box">',
            "    <h2>Embeddable HTML App</h2>",
            "    <p>Artifact shell with embeddable inline HTML output and complete fallback payload.</p>",
            '    <div class="readout" aria-live="polite"><span id="out">Ready</span></div>',
            "  </div>",
            '  <div class="box">',
            '    <label>Param A <input type="range" min="0" max="100" value="50" id="pa"></label>',
            '    <label>Param B <input type="range" min="0" max="100" value="50" id="pb"></label>',
            "    <button id=\"go\">Apply</button>",
            "  </div>",
            "</div>",
            "<script>",
            "(function() {",
            "  const pa = document.getElementById('pa');",
            "  const pb = document.getElementById('pb');",
            "  const out = document.getElementById('out');",
            "  function update() { out.textContent = 'A=' + pa.value + ' B=' + pb.value; }",
            "  pa.addEventListener('input', update);",
            "  pb.addEventListener('input', update);",
            "  document.getElementById('go').addEventListener('click', function() {",
            "    window.WiiiVisualBridge?.reportResult?.('apply', {a: pa.value, b: pb.value}, 'Applied', 'ok');",
            "  });",
            "  update();",
        ] + [f"  // padding line {i}" for i in range(80)] + [
            "})();",
            "</script>",
        ])

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": _rich_html,
                "title": "Embeddable HTML App",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.shell_variant == "editorial"
        assert payload.patch_strategy == "replace_html"
        assert payload.fallback_html is not None
        assert "<!DOCTYPE html>" in payload.fallback_html
        assert payload.artifact_handoff_available is False
        assert payload.artifact_handoff_mode == "none"
        assert payload.artifact_handoff_prompt is None

    def test_rejects_chart_runtime_lane_for_code_studio(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="chart-runtime-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "presentation_intent": "chart_runtime",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": '<style>.box{height:100px;background:var(--bg2)}</style><div class="box">Chart-like content with enough length for validation and lane rejection.</div>',
                "title": "Wrong Lane",
            })

        assert "tool_generate_visual" in result

    def test_rejects_high_severity_ai_slop_before_preview(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": (
                "<style>"
                ".hero{padding:24px;background:#0f172a;color:white}"
                ".action{border:1px solid #475569;padding:12px}"
                "</style>"
                "<div class='hero'>"
                "<h2>" + "\U0001F680" + " Launch Panel</h2>"
                "<button class='action'>" + "\U0001F680" + " Start</button>"
                "<p>Interactive shell with enough visible content for validation.</p>"
                "</div>"
            ),
            "title": "Slop Gate",
        })

        assert "AI slop" in result
        assert "emoji_in_code_elements" in result

    def test_full_html_passthrough(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        full_html = '<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><style>body{font-family:system-ui;color:#1e293b}</style></head><body><h1>Full document with styling</h1><p>Content here</p></body></html>'
        result = tool_create_visual_code.invoke({
            "code_html": full_html,
            "title": "Full Doc",
        })
        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.fallback_html is not None
        assert "Full document with styling" in payload.fallback_html

    def test_code_studio_payload_metadata_canonicalizes_presentation_intent(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-ctx",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "text",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "renderer_contract": "host_shell",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": '<style>.box{padding:20px;background:var(--bg2);border-radius:var(--radius)}</style><div class="box">Pendulum app with enough detail for code studio output validation.</div>',
                "title": "Pendulum App",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.presentation_intent == "code_studio_app"
        assert payload.metadata is not None
        assert payload.metadata["presentation_intent"] == "code_studio_app"
        assert payload.metadata["studio_lane"] == "app"
        assert payload.metadata["artifact_kind"] == "html_app"
        assert payload.artifact_handoff_available is True
        assert payload.artifact_handoff_mode == "followup_prompt"
        assert payload.artifact_handoff_prompt is not None

    def test_code_studio_runtime_context_promotes_followup_to_patch(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-patch",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "renderer_contract": "host_shell",
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-pendulum-keep",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": '<style>.app{padding:20px;background:var(--bg2);border-radius:var(--radius)}</style><div class="app">Pendulum app upgraded with sliders, preserved as the same interactive session for patch testing.</div>',
                "title": "Pendulum App V2",
                "visual_session_id": "hallucinated-new-session",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.visual_session_id == "vs-pendulum-keep"
        assert payload.lifecycle_event == "visual_patch"
        assert payload.metadata is not None
        assert payload.metadata["presentation_intent"] == "code_studio_app"
        assert payload.metadata["studio_lane"] == "app"

    def test_code_studio_runtime_context_accepts_preferred_code_session_id(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-patch",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "renderer_contract": "host_shell",
                "preferred_visual_operation": "patch",
                "preferred_code_studio_session_id": "vs-pendulum-keep",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": '<style>.app{padding:20px;background:var(--bg2);border-radius:var(--radius)}</style><div class="app">Pendulum app patched from active Code Studio context without opening a new session.</div>',
                "title": "Pendulum App V2",
                "visual_session_id": "hallucinated-new-session",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.visual_session_id == "vs-pendulum-keep"
        assert payload.lifecycle_event == "visual_patch"

    def test_rejects_premium_simulation_that_is_too_shallow(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-sim-shallow",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
            },
        )

        shallow_html = """
<style>
#canvas-container { position: relative; width: 600px; height: 400px; }
.ship { position: absolute; width: 40px; height: 20px; }
</style>
<div id="canvas-container"><div id="ship-a" class="ship"></div><div id="ship-b" class="ship"></div></div>
<div class="controls"><button onclick="runSimulation()">Chạy mô phỏng</button><button onclick="reset()">Đặt lại</button></div>
<script>
function reset(){ document.getElementById('msg').innerText = 'reset'; }
function runSimulation(){ document.getElementById('msg').innerText = 'run'; }
</script>
<div id="msg">Quy tắc 15</div>
"""

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": shallow_html,
                "title": "Mô phỏng Quy tắc 15",
            })

        assert "Error" in result
        assert "premium simulation" in result

    def test_rejects_premium_simulation_without_canvas_first_surface(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-sim-svg-only",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
                "preferred_render_surface": "canvas",
            },
        )

        svg_only_html = """
<style>
.sim-shell { display:grid; gap:16px; }
svg { width:100%; height:auto; background:var(--bg2); border-radius:var(--radius); }
</style>
<div class="sim-shell">
  <svg viewBox="0 0 640 320" role="img" aria-label="Rule 15 scene"><rect x="120" y="220" width="120" height="18" fill="var(--accent)" /><rect x="360" y="80" width="120" height="18" fill="var(--green)" /></svg>
  <label>CPA target <input id="cpa" type="range" min="0.1" max="2.0" value="0.8" step="0.1" /></label>
  <div class="readout" aria-live="polite">CPA: <span id="cpa-readout">0.8</span> nm</div>
</div>
<script>
let cpa = 0.8;
function step(){ cpa = Math.max(0.1, cpa - 0.01); requestAnimationFrame(step); }
requestAnimationFrame(step);
window.WiiiVisualBridge?.reportResult?.('simulation', { cpa }, 'tick', 'running');
</script>
"""

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": svg_only_html,
                "title": "Rule 15 SVG Only Simulation",
            })

        assert "Error" in result
        assert "Canvas-first runtime" in result

    def test_upgrades_shallow_pendulum_simulation_to_approved_scaffold(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-pendulum-upgrade",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
                "visual_user_query": "Build a mini pendulum physics app in chat with drag interaction.",
            },
        )

        shallow_html = """
<div class="pendulum-demo">
  <div id="ball"></div>
  <button onclick="run()">Run</button>
  <script>
    function run() { document.getElementById('ball').style.left = '120px'; }
  </script>
</div>
"""
        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": shallow_html,
                "title": "Mini Pendulum Physics App",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.renderer_kind == "app"
        assert payload.fallback_html is not None
        assert "pendulum-sim" in payload.fallback_html
        assert "length-slider" in payload.fallback_html
        assert 'input id="gravity-slider"' not in payload.fallback_html
        assert 'input id="damping-slider"' not in payload.fallback_html
        assert "requestAnimationFrame" in payload.fallback_html
        assert "reportResult" in payload.fallback_html

    def test_upgrades_pendulum_simulation_without_feedback_bridge(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-pendulum-feedback-upgrade",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
                "visual_user_query": "Build a premium pendulum simulation with drag interaction.",
            },
        )

        rich_but_silent_html = """
<style>
.sim-shell { display:grid; gap:16px; }
canvas { width:100%; height:260px; background:var(--bg2); border-radius:var(--radius); }
.controls { display:grid; gap:10px; }
.readout { font-size:13px; color:var(--text2); }
</style>
<div class="sim-shell">
  <canvas id="sim" width="640" height="320"></canvas>
  <div class="controls">
    <label>Gravity <input id="gravity" type="range" min="1" max="20" value="9.8" step="0.1" /></label>
    <label>Damping <input id="damping" type="range" min="0" max="0.2" value="0.03" step="0.01" /></label>
  </div>
  <div class="readout" aria-live="polite">Angle: <span id="theta">0.52</span> rad · Velocity: <span id="omega">0.00</span> rad/s</div>
</div>
<script>
const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
const gravityInput = document.getElementById('gravity');
const dampingInput = document.getElementById('damping');
let theta = 0.52;
let omega = 0;
let last = performance.now();
function frame(now){
  const deltaTime = Math.min((now - last) / 1000, 0.05);
  last = now;
  const gravity = Number(gravityInput.value);
  const damping = Number(dampingInput.value);
  const acceleration = -(gravity / 2) * Math.sin(theta) - damping * omega;
  omega += acceleration * deltaTime;
  theta += omega * deltaTime;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
"""

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": rich_but_silent_html,
                "title": "Pendulum Lab",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.fallback_html is not None
        assert "pendulum-sim" in payload.fallback_html
        assert "length-slider" in payload.fallback_html
        assert 'input id="gravity-slider"' not in payload.fallback_html
        assert "reportResult" in payload.fallback_html

    def test_upgraded_pendulum_scaffold_adds_requested_gravity_and_damping_controls(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-pendulum-parameter-patch",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
                "visual_user_query": "Keep the pendulum app and add gravity and damping sliders.",
            },
        )

        shallow_html = """
<div class="pendulum-demo">
  <div id="ball"></div>
</div>
"""
        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": shallow_html,
                "title": "Pendulum Lab",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.fallback_html is not None
        assert 'input id="gravity-slider"' in payload.fallback_html
        assert 'input id="damping-slider"' in payload.fallback_html
        assert 'input id="length-slider"' in payload.fallback_html

    def test_accepts_premium_simulation_with_surface_controls_and_live_readout(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        runtime = build_tool_runtime_context(
            session_id="code-studio-sim-rich",
            user_id="user-1",
            user_role="student",
            metadata={
                "presentation_intent": "code_studio_app",
                "studio_lane": "app",
                "artifact_kind": "html_app",
                "visual_requested_type": "simulation",
                "quality_profile": "premium",
                "renderer_contract": "host_shell",
            },
        )

        rich_html = """
<style>
.sim-shell { display:grid; gap:16px; }
canvas { width:100%; height:260px; background:var(--bg2); border-radius:var(--radius); }
.controls { display:grid; gap:10px; }
.readout { font-size:13px; color:var(--text2); }
</style>
<div class="sim-shell">
  <canvas id="sim" width="640" height="320"></canvas>
  <div class="controls">
    <label>Gravity <input id="gravity" type="range" min="1" max="20" value="9.8" step="0.1" /></label>
    <label>Friction <input id="friction" type="range" min="0" max="1" value="0.05" step="0.01" /></label>
    <button id="reset">Đặt lại</button>
  </div>
  <div class="readout" aria-live="polite">Góc lệch: <span id="theta">0.52</span> rad · Vận tốc: <span id="omega">0.00</span> rad/s</div>
</div>
<script>
const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
const gravityInput = document.getElementById('gravity');
const frictionInput = document.getElementById('friction');
const resetButton = document.getElementById('reset');
const thetaNode = document.getElementById('theta');
const omegaNode = document.getElementById('omega');
let theta = 0.52;
let omega = 0;
let last = performance.now();
function frame(now){
  const deltaTime = Math.min((now - last) / 1000, 0.05);
  last = now;
  const gravity = Number(gravityInput.value);
  const friction = Number(frictionInput.value);
  const acceleration = -(gravity / 2) * Math.sin(theta) - friction * omega;
  omega += acceleration * deltaTime;
  theta += omega * deltaTime;
  thetaNode.textContent = theta.toFixed(2);
  omegaNode.textContent = omega.toFixed(2);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  requestAnimationFrame(frame);
}
function report(reason){
  if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.reportResult === 'function') {
    window.WiiiVisualBridge.reportResult('simulation', {
      gravity: Number(gravityInput.value),
      friction: Number(frictionInput.value),
      theta,
      omega,
      reason,
    }, 'Simulation updated', 'success');
  }
}
gravityInput.addEventListener('input', () => report('gravity-change'));
frictionInput.addEventListener('input', () => report('friction-change'));
resetButton.addEventListener('click', () => report('reset'));
requestAnimationFrame(frame);
</script>
"""

        with tool_runtime_scope(runtime):
            result = tool_create_visual_code.invoke({
                "code_html": rich_html,
                "title": "Mô phỏng Con lắc",
            })

        payload = parse_visual_payload(result)
        assert payload is not None
        assert payload.renderer_kind == "app"
        assert payload.metadata is not None
        assert payload.metadata["quality_profile"] == "premium"
        assert payload.fallback_html is not None
        assert "reportResult" in payload.fallback_html

    def test_svg_content(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": '<svg viewBox="0 0 400 200" style="width:100%;height:auto"><rect x="10" y="10" width="380" height="180" rx="12" fill="var(--bg2)" stroke="var(--border)"/><circle cx="200" cy="100" r="40" fill="var(--accent)" opacity="0.8"/><text x="200" y="105" text-anchor="middle" fill="white" font-size="14">Visual</text></svg>',
            "title": "SVG Visual",
        })
        payload = parse_visual_payload(result)
        assert payload is not None
        assert "svg" in payload.fallback_html.lower()
        assert "circle" in payload.fallback_html

    def test_with_javascript(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_create_visual_code

        result = tool_create_visual_code.invoke({
            "code_html": '<style>#app{padding:20px;background:var(--bg2);border-radius:var(--radius);min-height:100px}</style><div id="app">Loading...</div><script>document.getElementById("app").textContent="Dynamic content loaded successfully";</script>',
            "title": "JS Visual",
        })
        payload = parse_visual_payload(result)
        assert payload is not None
        assert "<script>" in payload.fallback_html

    def test_included_in_get_visual_tools_when_flag_on(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = True
            enable_llm_code_gen_visuals = True
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools

        tools = get_visual_tools()
        tool_names = [t.name for t in tools]
        assert "tool_create_visual_code" in tool_names

    def test_not_included_when_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = True
            enable_llm_code_gen_visuals = False
        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools

        tools = get_visual_tools()
        tool_names = [t.name for t in tools]
        assert "tool_create_visual_code" not in tool_names
