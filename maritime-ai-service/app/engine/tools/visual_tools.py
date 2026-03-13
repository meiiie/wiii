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
# Dispatcher
# =============================================================================

_BUILDERS = {
    "comparison": _build_comparison_html,
    "process": _build_process_html,
    "matrix": _build_matrix_html,
    "architecture": _build_architecture_html,
    "concept": _build_concept_html,
    "infographic": _build_infographic_html,
}


@tool
def tool_generate_rich_visual(
    visual_type: str,
    spec_json: str,
    title: str = "",
) -> str:
    """Generate a rich educational visual widget (SVG/HTML) rendered INLINE in chat.

    Creates Claude-level custom diagrams: comparisons, process flows, matrices,
    architecture diagrams, concept maps, and infographics. Returns a ```widget
    code block that the frontend renders as a beautiful interactive visual.

    PRIORITY: Use this for EXPLANATIONS, COMPARISONS, ARCHITECTURES.
    Use tool_generate_interactive_chart for DATA/STATISTICS (bar, pie, line charts).
    Use tool_generate_mermaid for simple FLOWCHARTS and SEQUENCE diagrams.

    Args:
        visual_type: One of: comparison, process, matrix, architecture, concept, infographic
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
              "layers": [
                {"name": "Layer Name", "components": ["Comp1", "Comp2"]},
                ...
              ]
            }

            concept: {
              "center": {"title": "Main Idea", "description": "..."},
              "branches": [
                {"title": "Branch 1", "items": ["detail1", "detail2"]},
                ...
              ]
            }

            infographic: {
              "stats": [{"value": "95%", "label": "Accuracy"}, ...],
              "sections": [{"title": "Key Finding", "content": "..."}, ...]
            }

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
