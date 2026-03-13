"""
Rich Visual Widget Generator — Claude-level educational diagrams.
Sprint 229: Custom SVG/HTML visuals rendered inline in chat via ```widget blocks.

Generates self-contained HTML+CSS+SVG for:
  - comparison: Side-by-side visual comparison (like Standard vs Linear Attention)
  - process: Step-by-step flow with arrows
  - matrix: Color-coded grid visualization
  - architecture: Layered system diagram
  - concept: Central idea with radiating branches
  - infographic: Stats/icons/mixed content

Feature-gated by enable_chart_tools (shared with chart_tools).
"""

import html as html_mod
import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Design System — shared across all visual types
# =============================================================================

_DESIGN_CSS = """
:root {
  --bg: #ffffff; --bg2: #f8fafc; --bg3: #f1f5f9;
  --text: #1e293b; --text2: #475569; --text3: #94a3b8;
  --accent: #2563eb; --accent-bg: #eff6ff;
  --red: #ef4444; --red-bg: #fef2f2;
  --green: #10b981; --green-bg: #ecfdf5;
  --amber: #f59e0b; --amber-bg: #fffbeb;
  --purple: #8b5cf6; --purple-bg: #f5f3ff;
  --teal: #14b8a6; --teal-bg: #f0fdfa;
  --pink: #ec4899; --pink-bg: #fdf2f8;
  --border: #e2e8f0; --shadow: rgba(0,0,0,0.06);
  --radius: 12px; --radius-sm: 8px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --bg2: #1e293b; --bg3: #334155;
    --text: #f1f5f9; --text2: #94a3b8; --text3: #64748b;
    --accent: #60a5fa; --accent-bg: #1e3a5f;
    --red: #f87171; --red-bg: #3b1111;
    --green: #34d399; --green-bg: #0d3320;
    --amber: #fbbf24; --amber-bg: #3b2e0a;
    --purple: #a78bfa; --purple-bg: #2d1b69;
    --teal: #2dd4bf; --teal-bg: #0d3331;
    --pink: #f472b6; --pink-bg: #3b1132;
    --border: #334155; --shadow: rgba(0,0,0,0.3);
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: var(--text); background: transparent; line-height: 1.5;
  padding: 16px; font-size: 14px;
}
.widget-title {
  font-size: 17px; font-weight: 700; text-align: center;
  margin-bottom: 16px; color: var(--text);
}
.widget-subtitle {
  font-size: 12px; color: var(--text2); text-align: center;
  margin-top: -12px; margin-bottom: 16px;
}
.code-badge {
  display: inline-block; font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px; background: var(--bg3); color: var(--red);
  padding: 2px 8px; border-radius: 6px; font-weight: 500;
}
.label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text3); }
"""


def _esc(s: str) -> str:
    """HTML-escape user content."""
    return html_mod.escape(str(s))


def _wrap_html(body_css: str, body_html: str, title: str = "", subtitle: str = "") -> str:
    """Wrap visual content in full HTML document with design system."""
    title_html = f'<div class="widget-title">{_esc(title)}</div>' if title else ""
    subtitle_html = f'<div class="widget-subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_DESIGN_CSS}
{body_css}</style></head>
<body>{title_html}{subtitle_html}{body_html}</body></html>"""


# =============================================================================
# COMPARISON — Side-by-side (like Claude's Standard vs Linear Attention)
# =============================================================================

def _build_comparison_html(spec: dict, title: str) -> str:
    left = spec.get("left", {})
    right = spec.get("right", {})
    left_color = left.get("color", "var(--red)")
    right_color = right.get("color", "var(--teal)")
    left_bg = left.get("bg", "var(--red-bg)")
    right_bg = right.get("bg", "var(--teal-bg)")

    def _render_items(items: list) -> str:
        parts = []
        for item in items:
            if isinstance(item, str):
                parts.append(f'<li>{_esc(item)}</li>')
            elif isinstance(item, dict):
                label = _esc(item.get("label", ""))
                value = _esc(item.get("value", ""))
                icon = _esc(item.get("icon", ""))
                parts.append(f'<li><span class="item-icon">{icon}</span> <strong>{label}</strong>: {value}</li>')
        return "\n".join(parts)

    def _render_side(side: dict, color: str, bg: str) -> str:
        side_title = _esc(side.get("title", ""))
        side_sub = _esc(side.get("subtitle", ""))
        items = side.get("items", [])
        svg_content = _esc(side.get("svg", ""))  # escaped for safety
        desc = _esc(side.get("description", ""))

        items_html = f'<ul class="side-items">{_render_items(items)}</ul>' if items else ""
        svg_html = f'<div class="side-svg">{svg_content}</div>' if svg_content else ""
        desc_html = f'<p class="side-desc">{desc}</p>' if desc else ""

        return f"""<div class="side" style="--side-color:{color};--side-bg:{bg}">
  <div class="side-header">
    <h3 class="side-title">{side_title}</h3>
    {f'<span class="side-sub">{side_sub}</span>' if side_sub else ''}
  </div>
  {svg_html}{items_html}{desc_html}
</div>"""

    note = spec.get("note", "")
    note_html = f'<div class="comp-note">{_esc(note)}</div>' if note else ""

    css = """
.comparison { display: grid; grid-template-columns: 1fr auto 1fr; gap: 0; align-items: stretch; }
.side {
  background: var(--side-bg); border-radius: var(--radius); padding: 20px;
  border: 1.5px solid color-mix(in srgb, var(--side-color) 25%, transparent);
}
.side-header { margin-bottom: 12px; }
.side-title { font-size: 15px; font-weight: 700; color: var(--side-color); }
.side-sub { font-size: 12px; color: var(--text2); display: block; margin-top: 2px; }
.side-items { list-style: none; padding: 0; }
.side-items li {
  padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text2);
}
.side-items li:last-child { border-bottom: none; }
.item-icon { font-size: 14px; }
.side-svg { display: flex; justify-content: center; margin: 12px 0; }
.side-svg svg { max-width: 100%; height: auto; }
.side-desc { font-size: 12px; color: var(--text3); margin-top: 8px; font-style: italic; }
.comp-divider {
  display: flex; align-items: center; justify-content: center; padding: 0 12px;
}
.comp-divider svg { width: 32px; height: 32px; }
.comp-note {
  grid-column: 1 / -1; text-align: center; font-size: 12px; color: var(--text3);
  margin-top: 12px; padding: 8px; background: var(--bg2); border-radius: var(--radius-sm);
}
@media (max-width: 500px) {
  .comparison { grid-template-columns: 1fr; gap: 8px; }
  .comp-divider { transform: rotate(90deg); padding: 4px; }
}"""

    divider_svg = """<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M10 16H22M22 16L17 11M22 16L17 21" stroke="var(--text3)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

    body = f"""<div class="comparison">
  {_render_side(left, left_color, left_bg)}
  <div class="comp-divider">{divider_svg}</div>
  {_render_side(right, right_color, right_bg)}
  {note_html}
</div>"""

    return _wrap_html(css, body, title)


# =============================================================================
# PROCESS — Step-by-step flow
# =============================================================================

def _build_process_html(spec: dict, title: str) -> str:
    steps = spec.get("steps", [])
    direction = spec.get("direction", "horizontal")

    css = """
.process { display: flex; gap: 0; align-items: stretch; }
.process.vertical { flex-direction: column; }
.step-card {
  flex: 1; background: var(--bg2); border-radius: var(--radius); padding: 16px;
  border: 1.5px solid var(--border); position: relative; text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
}
.step-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px var(--shadow); }
.step-num {
  width: 32px; height: 32px; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; font-weight: 700; font-size: 14px;
  margin-bottom: 8px; color: white;
}
.step-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.step-desc { font-size: 12px; color: var(--text2); }
.step-arrow {
  display: flex; align-items: center; justify-content: center;
  min-width: 32px; min-height: 32px;
}
.process.vertical .step-arrow { transform: rotate(90deg); }
.step-arrow svg { width: 24px; height: 24px; }
@media (max-width: 500px) {
  .process:not(.vertical) { flex-direction: column; }
  .process:not(.vertical) .step-arrow { transform: rotate(90deg); }
}"""

    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--pink)", "var(--teal)"]
    arrow_svg = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="var(--text3)" stroke-width="2" stroke-linecap="round"/></svg>'

    parts = []
    for i, step in enumerate(steps):
        color = step.get("color", colors[i % len(colors)])
        num = _esc(step.get("icon", str(i + 1)))
        step_title = _esc(step.get("title", f"Bước {i + 1}"))
        desc = _esc(step.get("description", ""))
        desc_html = f'<div class="step-desc">{desc}</div>' if desc else ""
        parts.append(f"""<div class="step-card">
  <div class="step-num" style="background:{color}">{num}</div>
  <div class="step-title">{step_title}</div>
  {desc_html}
</div>""")
        if i < len(steps) - 1:
            parts.append(f'<div class="step-arrow">{arrow_svg}</div>')

    dir_class = "vertical" if direction == "vertical" else ""
    body = f'<div class="process {dir_class}">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


# =============================================================================
# MATRIX — Color-coded grid (like attention matrix visualization)
# =============================================================================

def _build_matrix_html(spec: dict, title: str) -> str:
    rows = spec.get("rows", [])
    cols = spec.get("cols", [])
    cells = spec.get("cells", [])  # 2D array of values (0-1 for heatmap, or labels)
    row_label = spec.get("row_label", "")
    col_label = spec.get("col_label", "")
    color = spec.get("color", "#ef4444")
    show_values = spec.get("show_values", False)

    css = f"""
.matrix-container {{ display: flex; align-items: center; gap: 8px; justify-content: center; }}
.matrix-row-label {{ writing-mode: vertical-rl; transform: rotate(180deg); font-size: 13px; font-weight: 600; color: var(--text2); }}
.matrix-col-label {{ text-align: center; font-size: 13px; font-weight: 600; color: var(--text2); margin-bottom: 4px; }}
.matrix-grid {{ display: inline-block; }}
.matrix-grid table {{ border-collapse: separate; border-spacing: 3px; }}
.matrix-grid th {{ font-size: 11px; font-weight: 600; color: var(--text2); padding: 4px 8px; text-align: center; }}
.matrix-grid td {{
  width: 40px; height: 36px; border-radius: 6px; text-align: center;
  font-size: 11px; font-weight: 500; transition: transform 0.15s;
  cursor: default;
}}
.matrix-grid td:hover {{ transform: scale(1.15); z-index: 1; }}
.matrix-caption {{ text-align: center; font-size: 12px; color: var(--text3); margin-top: 8px; }}
"""

    # Build table header
    col_header = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    header_row = f"<tr><th></th>{col_header}</tr>" if cols else ""

    # Build table body
    body_rows = []
    for i, row in enumerate(rows):
        row_cells = []
        for j in range(len(cols) if cols else (len(cells[i]) if i < len(cells) else 0)):
            val = cells[i][j] if i < len(cells) and j < len(cells[i]) else 0
            if isinstance(val, (int, float)):
                opacity = max(0.15, min(1.0, float(val)))
                cell_text = f"{val:.1f}" if show_values else ""
                text_color = "white" if opacity > 0.5 else "var(--text)"
                row_cells.append(
                    f'<td style="background:color-mix(in srgb,{color} {int(opacity*100)}%,var(--bg2));'
                    f'color:{text_color}" title="{row}→{cols[j] if j < len(cols) else j}: {val}">{cell_text}</td>'
                )
            else:
                row_cells.append(f'<td style="background:var(--bg3)">{_esc(str(val))}</td>')
        body_rows.append(f'<tr><th>{_esc(row)}</th>{"".join(row_cells)}</tr>')

    col_label_html = f'<div class="matrix-col-label">{_esc(col_label)}</div>' if col_label else ""
    row_label_html = f'<div class="matrix-row-label">{_esc(row_label)}</div>' if row_label else ""
    caption = spec.get("caption", "")
    caption_html = f'<div class="matrix-caption">{_esc(caption)}</div>' if caption else ""

    body = f"""{col_label_html}
<div class="matrix-container">
  {row_label_html}
  <div class="matrix-grid">
    <table>{header_row}{"".join(body_rows)}</table>
  </div>
</div>
{caption_html}"""

    return _wrap_html(css, body, title)


# =============================================================================
# ARCHITECTURE — Layered system diagram
# =============================================================================

def _build_architecture_html(spec: dict, title: str) -> str:
    layers = spec.get("layers", [])
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

    css = """
.arch { display: flex; flex-direction: column; gap: 0; align-items: center; }
.arch-layer {
  width: 100%; padding: 14px 20px; border-radius: var(--radius);
  border: 1.5px solid var(--border); position: relative;
}
.arch-layer-name { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.arch-components { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.arch-comp {
  background: white; border-radius: var(--radius-sm); padding: 8px 14px;
  font-size: 12px; font-weight: 500; color: var(--text);
  border: 1px solid var(--border); box-shadow: 0 1px 3px var(--shadow);
}
@media (prefers-color-scheme: dark) { .arch-comp { background: var(--bg); } }
.arch-arrow { display: flex; justify-content: center; padding: 4px 0; }
.arch-arrow svg { width: 20px; height: 20px; }
"""

    arrow_svg = '<svg viewBox="0 0 20 20" fill="none"><path d="M10 4V16M10 16L5 11M10 16L15 11" stroke="var(--text3)" stroke-width="2" stroke-linecap="round"/></svg>'

    parts = []
    for i, layer in enumerate(layers):
        color = layer.get("color", colors[i % len(colors)])
        name = _esc(layer.get("name", f"Layer {i + 1}"))
        components = layer.get("components", [])
        comps_html = "".join(f'<div class="arch-comp">{_esc(c)}</div>' for c in components)
        parts.append(f"""<div class="arch-layer" style="background:color-mix(in srgb,{color} 8%,var(--bg));border-color:color-mix(in srgb,{color} 30%,transparent)">
  <div class="arch-layer-name" style="color:{color}">{name}</div>
  <div class="arch-components">{comps_html}</div>
</div>""")
        if i < len(layers) - 1:
            parts.append(f'<div class="arch-arrow">{arrow_svg}</div>')

    body = f'<div class="arch">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


# =============================================================================
# CONCEPT — Central idea with radiating branches
# =============================================================================

def _build_concept_html(spec: dict, title: str) -> str:
    center = spec.get("center", {})
    branches = spec.get("branches", [])
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

    css = """
.concept { display: flex; flex-direction: column; align-items: center; gap: 16px; }
.concept-center {
  background: var(--accent-bg); border: 2px solid var(--accent); border-radius: var(--radius);
  padding: 16px 24px; text-align: center; max-width: 300px;
}
.concept-center-title { font-size: 16px; font-weight: 700; color: var(--accent); }
.concept-center-desc { font-size: 12px; color: var(--text2); margin-top: 4px; }
.concept-branches { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; width: 100%; }
.concept-branch {
  flex: 1; min-width: 140px; max-width: 220px; border-radius: var(--radius);
  padding: 14px; border: 1.5px solid var(--border);
}
.concept-branch-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.concept-branch-items { list-style: none; padding: 0; }
.concept-branch-items li { font-size: 12px; color: var(--text2); padding: 3px 0; }
.concept-branch-items li::before { content: '→ '; color: var(--text3); }
.concept-connector { color: var(--text3); font-size: 20px; }
"""

    center_title = _esc(center.get("title", ""))
    center_desc = _esc(center.get("description", ""))
    center_html = f"""<div class="concept-center">
  <div class="concept-center-title">{center_title}</div>
  {f'<div class="concept-center-desc">{center_desc}</div>' if center_desc else ''}
</div>"""

    branch_parts = []
    for i, branch in enumerate(branches):
        color = branch.get("color", colors[i % len(colors)])
        b_title = _esc(branch.get("title", ""))
        items = branch.get("items", [])
        items_html = "".join(f"<li>{_esc(item)}</li>" for item in items)
        branch_parts.append(f"""<div class="concept-branch" style="background:color-mix(in srgb,{color} 6%,var(--bg));border-color:color-mix(in srgb,{color} 30%,transparent)">
  <div class="concept-branch-title" style="color:{color}">{b_title}</div>
  <ul class="concept-branch-items">{items_html}</ul>
</div>""")

    body = f"""<div class="concept">
  {center_html}
  <div class="concept-connector">↓</div>
  <div class="concept-branches">{"".join(branch_parts)}</div>
</div>"""

    return _wrap_html(css, body, title)


# =============================================================================
# INFOGRAPHIC — Stats, highlights, mixed content
# =============================================================================

def _build_infographic_html(spec: dict, title: str) -> str:
    stats = spec.get("stats", [])
    sections = spec.get("sections", [])
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

    css = """
.infographic { display: flex; flex-direction: column; gap: 16px; }
.info-stats { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
.info-stat {
  flex: 1; min-width: 100px; text-align: center; padding: 16px;
  border-radius: var(--radius); border: 1.5px solid var(--border);
}
.info-stat-value { font-size: 28px; font-weight: 800; line-height: 1; }
.info-stat-label { font-size: 11px; color: var(--text2); margin-top: 6px; font-weight: 500; }
.info-section {
  background: var(--bg2); border-radius: var(--radius); padding: 16px;
  border: 1px solid var(--border);
}
.info-section-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 8px; }
.info-section-content { font-size: 13px; color: var(--text2); line-height: 1.6; }
.info-highlight {
  display: inline-block; padding: 2px 8px; border-radius: 6px;
  font-weight: 600; font-size: 12px;
}
"""

    stats_html = ""
    if stats:
        stat_parts = []
        for i, stat in enumerate(stats):
            color = stat.get("color", colors[i % len(colors)])
            value = _esc(stat.get("value", ""))
            label = _esc(stat.get("label", ""))
            stat_parts.append(f"""<div class="info-stat" style="background:color-mix(in srgb,{color} 6%,var(--bg))">
  <div class="info-stat-value" style="color:{color}">{value}</div>
  <div class="info-stat-label">{label}</div>
</div>""")
        stats_html = f'<div class="info-stats">{"".join(stat_parts)}</div>'

    section_parts = []
    for section in sections:
        s_title = _esc(section.get("title", ""))
        s_content = _esc(section.get("content", ""))
        section_parts.append(f"""<div class="info-section">
  <div class="info-section-title">{s_title}</div>
  <div class="info-section-content">{s_content}</div>
</div>""")

    body = f"""<div class="infographic">
  {stats_html}
  {"".join(section_parts)}
</div>"""

    return _wrap_html(css, body, title)


# =============================================================================
# SIMULATION — Interactive Canvas with controls (physics, math, animations)
# =============================================================================

def _build_simulation_html(spec: dict, title: str) -> str:
    """Interactive simulation with Canvas, sliders, and live state."""
    variables = spec.get("variables", [])  # [{name, label, min, max, value, step}]
    setup_code = spec.get("setup", "")     # JS: initialize state
    draw_code = spec.get("draw", "")       # JS: draw frame (receives ctx, canvas, vars, t)
    update_code = spec.get("update", "")   # JS: update state each frame
    description = spec.get("description", "")
    fps = spec.get("fps", 60)
    canvas_height = spec.get("height", 300)

    css = f"""
canvas#sim {{ width:100%; height:{canvas_height}px; border-radius:var(--radius); background:var(--bg2); display:block; cursor:crosshair; }}
.sim-controls {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; align-items:center; }}
.sim-control {{ flex:1; min-width:150px; }}
.sim-control label {{ font-size:11px; font-weight:600; color:var(--text2); display:block; margin-bottom:2px; }}
.sim-control input[type=range] {{ width:100%; accent-color:var(--accent); }}
.sim-value {{ font-size:11px; color:var(--text3); font-family:monospace; }}
.sim-desc {{ font-size:12px; color:var(--text2); margin-top:8px; font-style:italic; }}
.sim-btns {{ display:flex; gap:8px; margin-top:8px; }}
.sim-btn {{
  padding:6px 14px; border-radius:var(--radius-sm); border:1px solid var(--border);
  background:var(--bg2); color:var(--text); font-size:12px; cursor:pointer;
}}
.sim-btn:hover {{ background:var(--bg3); }}
.sim-btn.active {{ background:var(--accent); color:white; border-color:var(--accent); }}
"""

    # Build slider controls
    controls_html = ""
    vars_init = "const vars = {};\n"
    for v in variables:
        vname = _esc(v.get("name", "x"))
        vlabel = _esc(v.get("label", vname))
        vmin = v.get("min", 0)
        vmax = v.get("max", 100)
        vval = v.get("value", 50)
        vstep = v.get("step", 1)
        controls_html += f"""<div class="sim-control">
  <label>{vlabel}: <span class="sim-value" id="val_{vname}">{vval}</span></label>
  <input type="range" id="sl_{vname}" min="{vmin}" max="{vmax}" value="{vval}" step="{vstep}"
    oninput="vars.{vname}=+this.value;document.getElementById('val_{vname}').textContent=this.value">
</div>\n"""
        vars_init += f"vars.{vname} = {vval};\n"

    desc_html = f'<div class="sim-desc">{_esc(description)}</div>' if description else ""

    body = f"""<canvas id="sim" width="800" height="{canvas_height}"></canvas>
<div class="sim-btns">
  <button class="sim-btn active" id="btnPlay" onclick="togglePlay()">⏸ Pause</button>
  <button class="sim-btn" onclick="resetSim()">↺ Reset</button>
</div>
<div class="sim-controls">{controls_html}</div>
{desc_html}
<script>
const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
{vars_init}
let t = 0, running = true, animId = null;
function resizeCanvas() {{
  canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
  canvas.height = {canvas_height} * (window.devicePixelRatio || 1);
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
}}
resizeCanvas();
/* USER SETUP */
{setup_code}
/* ANIMATION LOOP */
function frame() {{
  if (!running) return;
  ctx.clearRect(0, 0, canvas.offsetWidth, {canvas_height});
  /* USER UPDATE */
  {update_code}
  /* USER DRAW */
  {draw_code}
  t += 1/{fps};
  animId = requestAnimationFrame(frame);
}}
function togglePlay() {{
  running = !running;
  document.getElementById('btnPlay').textContent = running ? '⏸ Pause' : '▶ Play';
  document.getElementById('btnPlay').classList.toggle('active', running);
  if (running) frame();
}}
function resetSim() {{
  t = 0;
  {setup_code}
  if (!running) {{ running = true; document.getElementById('btnPlay').textContent = '⏸ Pause'; document.getElementById('btnPlay').classList.add('active'); }}
  frame();
}}
frame();
</script>"""

    return _wrap_html(css, body, title)


# =============================================================================
# QUIZ — Multiple choice with instant feedback
# =============================================================================

def _build_quiz_html(spec: dict, title: str) -> str:
    questions = spec.get("questions", [])
    # [{question, options: [{text, correct: bool}], explanation}]

    css = """
.quiz { display:flex; flex-direction:column; gap:16px; }
.q-card { background:var(--bg2); border-radius:var(--radius); padding:16px; border:1.5px solid var(--border); }
.q-text { font-size:14px; font-weight:600; color:var(--text); margin-bottom:10px; }
.q-options { display:flex; flex-direction:column; gap:6px; }
.q-opt {
  padding:10px 14px; border-radius:var(--radius-sm); border:1.5px solid var(--border);
  background:var(--bg); cursor:pointer; font-size:13px; color:var(--text); transition:all 0.2s;
  display:flex; align-items:center; gap:8px;
}
.q-opt:hover:not(.disabled) { border-color:var(--accent); background:var(--accent-bg); }
.q-opt.correct { border-color:var(--green); background:var(--green-bg); color:var(--green); }
.q-opt.wrong { border-color:var(--red); background:var(--red-bg); color:var(--red); }
.q-opt.disabled { cursor:default; opacity:0.7; }
.q-opt .q-icon { width:20px; text-align:center; }
.q-explain { margin-top:10px; padding:10px; border-radius:var(--radius-sm); background:var(--accent-bg); font-size:12px; color:var(--text2); display:none; }
.q-explain.show { display:block; }
.q-score { text-align:center; font-size:15px; font-weight:700; color:var(--accent); padding:12px; background:var(--accent-bg); border-radius:var(--radius); }
"""

    q_cards = []
    for i, q in enumerate(questions):
        q_text = _esc(q.get("question", ""))
        explanation = _esc(q.get("explanation", ""))
        options = q.get("options", [])

        opts_html = ""
        for j, opt in enumerate(options):
            opt_text = _esc(opt.get("text", ""))
            is_correct = "true" if opt.get("correct", False) else "false"
            opts_html += f'<div class="q-opt" id="q{i}o{j}" onclick="checkAnswer({i},{j},{is_correct})">'
            opts_html += f'<span class="q-icon" id="q{i}o{j}i">○</span> {opt_text}</div>\n'

        explain_html = f'<div class="q-explain" id="q{i}exp">{explanation}</div>' if explanation else ""

        q_cards.append(f"""<div class="q-card">
  <div class="q-text">Câu {i + 1}: {q_text}</div>
  <div class="q-options">{opts_html}</div>
  {explain_html}
</div>""")

    total = len(questions)
    body = f"""<div class="quiz">
  {"".join(q_cards)}
  <div class="q-score" id="scoreBoard" style="display:none"></div>
</div>
<script>
let score = 0, answered = 0, total = {total};
function checkAnswer(qi, oi, correct) {{
  const opts = document.querySelectorAll('[id^="q'+qi+'o"]');
  if (opts[0] && opts[0].classList.contains('disabled')) return;
  opts.forEach((el, idx) => {{
    el.classList.add('disabled');
    const isCorrect = el.getAttribute('onclick').includes('true');
    if (idx === oi) {{
      el.classList.add(correct ? 'correct' : 'wrong');
      document.getElementById('q'+qi+'o'+oi+'i').textContent = correct ? '✓' : '✗';
    }} else if (isCorrect) {{
      el.classList.add('correct');
      el.querySelector('.q-icon').textContent = '✓';
    }}
  }});
  const exp = document.getElementById('q'+qi+'exp');
  if (exp) exp.classList.add('show');
  if (correct) score++;
  answered++;
  if (answered === total) {{
    const board = document.getElementById('scoreBoard');
    board.style.display = 'block';
    board.textContent = 'Kết quả: ' + score + '/' + total + ' (' + Math.round(score/total*100) + '%)';
  }}
}}
</script>"""

    return _wrap_html(css, body, title)


# =============================================================================
# INTERACTIVE TABLE — Sortable, filterable, clickable
# =============================================================================

def _build_interactive_table_html(spec: dict, title: str) -> str:
    headers = spec.get("headers", [])
    rows = spec.get("rows", [])  # 2D array
    searchable = spec.get("searchable", True)
    sortable = spec.get("sortable", True)
    row_click = spec.get("row_click", "")  # JS template: receives rowData array

    css = """
.itbl-search {
  width:100%; padding:8px 12px; border-radius:var(--radius-sm); border:1.5px solid var(--border);
  background:var(--bg); color:var(--text); font-size:13px; margin-bottom:12px; outline:none;
}
.itbl-search:focus { border-color:var(--accent); }
.itbl-wrap { overflow-x:auto; border-radius:var(--radius); border:1px solid var(--border); }
table.itbl { width:100%; border-collapse:collapse; font-size:13px; }
.itbl th {
  padding:10px 12px; text-align:left; font-weight:600; font-size:11px; text-transform:uppercase;
  letter-spacing:0.5px; color:var(--text2); background:var(--bg2); border-bottom:2px solid var(--border);
  cursor:pointer; user-select:none; white-space:nowrap;
}
.itbl th:hover { color:var(--accent); }
.itbl th .sort-icon { margin-left:4px; font-size:10px; }
.itbl td { padding:8px 12px; border-bottom:1px solid var(--border); color:var(--text); }
.itbl tr:hover td { background:var(--accent-bg); }
.itbl tr { transition:background 0.15s; cursor:default; }
.itbl-count { font-size:11px; color:var(--text3); margin-top:6px; text-align:right; }
"""

    headers_json = json.dumps(headers, ensure_ascii=False)
    rows_json = json.dumps(rows, ensure_ascii=False)

    search_html = '<input class="itbl-search" id="tblSearch" placeholder="Tìm kiếm..." oninput="filterTable()">' if searchable else ""

    body = f"""{search_html}
<div class="itbl-wrap"><table class="itbl" id="dataTable">
  <thead><tr id="tblHead"></tr></thead>
  <tbody id="tblBody"></tbody>
</table></div>
<div class="itbl-count" id="tblCount"></div>
<script>
const headers = {headers_json};
const allRows = {rows_json};
let sortCol = -1, sortAsc = true;

function renderHead() {{
  const head = document.getElementById('tblHead');
  head.innerHTML = '';
  headers.forEach((h, i) => {{
    const th = document.createElement('th');
    const icon = sortCol === i ? (sortAsc ? ' ▲' : ' ▼') : '';
    th.innerHTML = h + '<span class="sort-icon">' + icon + '</span>';
    th.onclick = () => {{ sortCol = sortCol === i && sortAsc ? i : i; sortAsc = sortCol === i ? !sortAsc : true; sortCol = i; render(); }};
    head.appendChild(th);
  }});
}}

function render() {{
  const q = (document.getElementById('tblSearch') || {{}}).value || '';
  let filtered = allRows.filter(r => !q || r.some(c => String(c).toLowerCase().includes(q.toLowerCase())));
  if (sortCol >= 0) {{
    filtered.sort((a, b) => {{
      const va = a[sortCol], vb = b[sortCol];
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return sortAsc ? na - nb : nb - na;
      return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    }});
  }}
  const body = document.getElementById('tblBody');
  body.innerHTML = '';
  filtered.forEach(r => {{
    const tr = document.createElement('tr');
    r.forEach(c => {{ const td = document.createElement('td'); td.textContent = c; tr.appendChild(td); }});
    body.appendChild(tr);
  }});
  document.getElementById('tblCount').textContent = filtered.length + '/' + allRows.length + ' dòng';
  renderHead();
}}

function filterTable() {{ render(); }}
render();
</script>"""

    return _wrap_html(css, body, title)


# =============================================================================
# REACT APP — Full React component (Claude-level architecture)
# Uses React 18 + Tailwind Play CDN + Recharts + Lucide in sandboxed iframe.
# AI writes JSX component code → tool wraps in runtime shell → rendered live.
# =============================================================================

_REACT_RUNTIME_SHELL = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/recharts@2.12.7/umd/Recharts.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script>
// Expose Recharts components globally for JSX
if (window.Recharts) {
  Object.keys(window.Recharts).forEach(k => window[k] = window.Recharts[k]);
}
</script>
<style>
body { margin: 0; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
%COMPONENT_CODE%

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
</script>
</body>
</html>"""


def _build_react_app_html(spec: dict, title: str) -> str:
    """Render a React component in full Claude-like runtime environment."""
    component_code = spec.get("code", "")
    if not component_code:
        return _wrap_html("", "<p>Error: no React component code provided</p>", title)

    # Insert component code into runtime shell
    # Note: we do NOT escape the code — it's JS, expected to contain JSX/HTML
    html = _REACT_RUNTIME_SHELL.replace("%COMPONENT_CODE%", component_code)

    # Inject title if provided
    if title:
        title_html = f'<h2 style="text-align:center;font-size:17px;font-weight:700;margin-bottom:12px">{_esc(title)}</h2>'
        html = html.replace('<div id="root"></div>', f'{title_html}<div id="root"></div>')

    return html


# =============================================================================
# Dispatcher
# =============================================================================

_BUILDERS = {
    "comparison": _build_comparison_html,
    "process": _build_process_html,
    "matrix": _build_matrix_html,
    "architecture": _build_architecture_html,
    "concept": _build_concept_html,
    "infographic": _build_infographic_html,
    "simulation": _build_simulation_html,
    "quiz": _build_quiz_html,
    "interactive_table": _build_interactive_table_html,
    "react_app": _build_react_app_html,
}


@tool
def tool_generate_rich_visual(
    visual_type: str,
    spec_json: str,
    title: str = "",
) -> str:
    """Generate a rich interactive visual widget (HTML+CSS+JS) rendered INLINE in chat.

    Creates Claude-level interactive widgets: comparisons, simulations, quizzes,
    interactive tables, architecture diagrams, and more. Returns a ```widget
    code block that the frontend renders as a fully interactive visual.

    PRIORITY: Use this for EXPLANATIONS, COMPARISONS, SIMULATIONS, QUIZZES.
    Use tool_generate_interactive_chart for DATA/STATISTICS (bar, pie, line charts).
    Use tool_generate_mermaid for simple FLOWCHARTS and SEQUENCE diagrams.

    Args:
        visual_type: One of: comparison, process, matrix, architecture, concept,
                     infographic, simulation, quiz, interactive_table, react_app
        spec_json: JSON object describing the visual content. Structure depends on visual_type:

            comparison: {
              "left": {"title": "A", "subtitle": "...", "items": ["item1", ...], "color": "#ef4444", "bg": "#fef2f2"},
              "right": {"title": "B", "subtitle": "...", "items": ["item1", ...], "color": "#14b8a6", "bg": "#f0fdfa"},
              "note": "Optional bottom note"
            }

            process: {
              "steps": [{"title": "Step 1", "description": "...", "icon": "1"}, ...],
              "direction": "horizontal" or "vertical"
            }

            matrix: {
              "rows": ["Row1", "Row2"], "cols": ["Col1", "Col2"],
              "cells": [[0.9, 0.3], [0.1, 0.8]],
              "row_label": "Queries", "col_label": "Keys",
              "color": "#ef4444", "show_values": true,
              "caption": "Hover to see values"
            }

            architecture: {
              "layers": [{"name": "Layer Name", "components": ["Comp1", "Comp2"]}, ...]
            }

            concept: {
              "center": {"title": "Main Idea", "description": "..."},
              "branches": [{"title": "Branch 1", "items": ["detail1", ...]}, ...]
            }

            infographic: {
              "stats": [{"value": "95%", "label": "Accuracy"}, ...],
              "sections": [{"title": "Key Finding", "content": "..."}, ...]
            }

            simulation: {
              "variables": [{"name": "speed", "label": "Tốc độ", "min": 1, "max": 100, "value": 50, "step": 1}],
              "setup": "// JS: initialize state (runs once)",
              "update": "// JS: update physics each frame (has vars, t)",
              "draw": "// JS: draw on canvas (has ctx, canvas, vars, t)",
              "fps": 60, "height": 300,
              "description": "Mô phỏng vật lý tương tác"
            }

            quiz: {
              "questions": [
                {
                  "question": "Câu hỏi?",
                  "options": [
                    {"text": "Đáp án A", "correct": false},
                    {"text": "Đáp án B", "correct": true}
                  ],
                  "explanation": "Giải thích đáp án đúng"
                }
              ]
            }

            interactive_table: {
              "headers": ["Tên", "Giá trị", "Ghi chú"],
              "rows": [["Item 1", 100, "OK"], ["Item 2", 200, "Good"]],
              "searchable": true, "sortable": true
            }

            react_app: {
              "code": "function App() { const [count, setCount] = React.useState(0); return (<div className='p-4'><h1 className='text-2xl font-bold'>Count: {count}</h1><button className='mt-2 px-4 py-2 bg-blue-500 text-white rounded' onClick={() => setCount(c => c+1)}>+1</button></div>); }"
            }
            NOTE: react_app has React 18 + Tailwind CSS + Recharts available.
            Write a function App() component. Use Tailwind classes for styling.
            Use Recharts components (BarChart, LineChart, PieChart, etc.) for data viz.
            BEST FOR: Complex interactive UIs, dashboards, multi-component layouts.

        title: Visual title in Vietnamese (displayed above the diagram).

    Returns:
        A ```widget code block. Include this DIRECTLY in your response.
    """
    builder = _BUILDERS.get(visual_type)
    if not builder:
        valid = ", ".join(sorted(_BUILDERS.keys()))
        return f"Error: visual_type '{visual_type}' không hợp lệ. Chọn một trong: {valid}"

    try:
        spec = json.loads(spec_json)
        if not isinstance(spec, dict):
            return "Error: spec_json phải là một JSON object."
    except json.JSONDecodeError as e:
        return f"Error: JSON không hợp lệ: {e}"

    try:
        html = builder(spec, title)
    except Exception as e:
        logger.exception("Rich visual generation failed for type=%s", visual_type)
        return f"Error: Không thể tạo visual: {e}"

    return (
        f"Visual đã tạo thành công! Include đoạn code block sau TRỰC TIẾP trong response:\n\n"
        f"```widget\n{html}\n```\n\n"
        f"Giải thích nội dung bằng tiếng Việt bên ngoài widget."
    )


def get_visual_tools() -> list:
    """Return list of rich visual tools. Feature-gated by enable_chart_tools."""
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "enable_chart_tools", False):
        return []

    return [tool_generate_rich_visual]
