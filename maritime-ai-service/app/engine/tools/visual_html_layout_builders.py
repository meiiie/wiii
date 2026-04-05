"""Pure HTML builders for non-chart structured visuals."""

from __future__ import annotations

from typing import Any

from app.engine.tools.visual_html_core import _esc, _wrap_html


def _build_comparison_html_impl(spec: dict, title: str) -> str:
    """Two-column comparison surface with preserved titles and highlights."""

    left = spec.get("left", {})
    right = spec.get("right", {})

    def _render_side(side: dict[str, Any], color: str, side_class: str) -> str:
        side_title = _esc(side.get("title", ""))
        side_subtitle = _esc(side.get("subtitle", ""))
        items = side.get("items", [])
        item_parts: list[str] = []
        for item in items:
            if isinstance(item, str):
                label = item
            elif isinstance(item, dict):
                label = item.get("label") or item.get("value") or ""
            else:
                label = ""
            if label:
                item_parts.append(f'<li class="comp-item">{_esc(label)}</li>')
        subtitle_html = (
            f'<div class="comp-subtitle">{side_subtitle}</div>'
            if side_subtitle
            else ""
        )
        items_html = (
            f'<ul class="comp-items">{"".join(item_parts)}</ul>' if item_parts else ""
        )
        return (
            f'<div class="comp-card {side_class}" style="--comp-color:{color}">'
            f'<div class="comp-side-label">{side_class.title()}</div>'
            f'<div class="comp-title">{side_title}</div>'
            f"{subtitle_html}"
            f"{items_html}"
            f"</div>"
        )

    colors = ["#D97757", "#85CDCA"]
    note_text = _esc(spec.get("note", ""))
    highlight_text = _esc(spec.get("highlight", ""))
    note_html = f'<div class="comp-note">{note_text}</div>' if note_text else ""
    highlight_html = (
        f'<div class="comp-highlight">{highlight_text}</div>'
        if highlight_text
        else ""
    )

    css = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,-apple-system,sans-serif; background:transparent; color:#333; }
.root { max-width:600px; margin:0 auto; padding:16px 0; }
.title { font-size:15px; font-weight:600; margin-bottom:4px; }
.comparison { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:16px; }
.comp-card { border:1.5px solid var(--border); border-left:4px solid var(--comp-color); border-radius:12px; padding:14px; background:var(--bg2); }
.comp-side-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--comp-color); margin-bottom:8px; }
.comp-title { font-size:15px; font-weight:700; color:var(--text); }
.comp-subtitle { font-size:12px; color:var(--text2); margin-top:4px; }
.comp-items { list-style:none; padding:0; margin:10px 0 0; display:flex; flex-direction:column; gap:6px; }
.comp-item { font-size:12px; color:var(--text2); }
.comp-item::before { content:'• '; color:var(--comp-color); font-weight:700; }
.comp-note { font-size:12px; color:var(--text3); margin-top:10px; }
.comp-highlight { margin-top:12px; padding:10px 12px; border-radius:10px; background:color-mix(in srgb, var(--accent) 10%, transparent); color:var(--text); font-size:12px; font-weight:600; }
@media (max-width: 520px) { .comparison { grid-template-columns:1fr; } }
"""

    body = '<div class="root">'
    body += f'<div class="title">{_esc(title)}</div>'
    body += '<div class="comparison">'
    body += _render_side(left, colors[0], "left")
    body += _render_side(right, colors[1], "right")
    body += "</div>"
    body += note_html
    body += highlight_html
    body += "</div>"
    return _wrap_html(css, body, title)


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
.step-desc { font-size: 12px; color: var(--text2); line-height: 1.5; }
.step-content { font-size: 11px; color: var(--text3); margin-top: 6px; line-height: 1.4; text-align: left; }
.step-signals { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; justify-content: center; }
.step-signal {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: color-mix(in srgb, var(--step-color) 12%, transparent);
  color: var(--step-color);
}
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

    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--pink)",
        "var(--teal)",
    ]
    arrow_svg = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="var(--text3)" stroke-width="2" stroke-linecap="round"/></svg>'

    parts = []
    for i, step in enumerate(steps):
        color = step.get("color", colors[i % len(colors)])
        num = _esc(step.get("icon", str(i + 1)))
        step_title = _esc(step.get("title", f"Buoc {i + 1}"))
        desc = _esc(step.get("description", ""))
        content = _esc(step.get("content", ""))
        signals = step.get("signals", [])
        desc_html = f'<div class="step-desc">{desc}</div>' if desc else ""
        content_html = f'<div class="step-content">{content}</div>' if content else ""
        signals_html = ""
        if signals:
            sig_parts = "".join(
                f'<span class="step-signal">{_esc(s)}</span>' for s in signals
            )
            signals_html = f'<div class="step-signals">{sig_parts}</div>'
        parts.append(
            f"""<div class="step-card" style="--step-color:{color}">
  <div class="step-num" style="background:{color}">{num}</div>
  <div class="step-title">{step_title}</div>
  {desc_html}{content_html}{signals_html}
</div>"""
        )
        if i < len(steps) - 1:
            parts.append(f'<div class="step-arrow">{arrow_svg}</div>')

    dir_class = "vertical" if direction == "vertical" else ""
    body = f'<div class="process {dir_class}">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


def _build_matrix_html(spec: dict, title: str) -> str:
    rows = spec.get("rows", [])
    cols = spec.get("cols", [])
    cells = spec.get("cells", [])
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

    col_header = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    header_row = f"<tr><th></th>{col_header}</tr>" if cols else ""

    body_rows = []
    for i, row in enumerate(rows):
        row_cells = []
        cell_count = len(cols) if cols else (len(cells[i]) if i < len(cells) else 0)
        for j in range(cell_count):
            val = cells[i][j] if i < len(cells) and j < len(cells[i]) else 0
            if isinstance(val, (int, float)):
                opacity = max(0.15, min(1.0, float(val)))
                cell_text = f"{val:.1f}" if show_values else ""
                text_color = "white" if opacity > 0.5 else "var(--text)"
                row_cells.append(
                    f'<td style="background:color-mix(in srgb,{color} {int(opacity*100)}%,var(--bg2));'
                    f'color:{text_color}" title="{row}->{cols[j] if j < len(cols) else j}: {val}">{cell_text}</td>'
                )
            else:
                row_cells.append(
                    f'<td style="background:var(--bg3)">{_esc(str(val))}</td>'
                )
        body_rows.append(f'<tr><th>{_esc(row)}</th>{"".join(row_cells)}</tr>')

    col_label_html = (
        f'<div class="matrix-col-label">{_esc(col_label)}</div>' if col_label else ""
    )
    row_label_html = (
        f'<div class="matrix-row-label">{_esc(row_label)}</div>' if row_label else ""
    )
    caption = spec.get("caption", "")
    caption_html = (
        f'<div class="matrix-caption">{_esc(caption)}</div>' if caption else ""
    )

    body = f"""{col_label_html}
<div class="matrix-container">
  {row_label_html}
  <div class="matrix-grid">
    <table>{header_row}{"".join(body_rows)}</table>
  </div>
</div>
{caption_html}"""

    return _wrap_html(css, body, title)


def _build_architecture_html(spec: dict, title: str) -> str:
    layers = spec.get("layers", [])
    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--teal)",
        "var(--pink)",
    ]

    css = """
.arch { display: flex; flex-direction: column; gap: 0; align-items: center; }
.arch-layer {
  width: 100%; padding: 14px 16px;
  border-left: 3px solid var(--layer-color, var(--border));
  position: relative; transition: background 0.2s;
}
.arch-layer:hover { background: color-mix(in srgb, var(--layer-color) 6%, transparent); }
.arch-layer-header { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.arch-layer-name { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.arch-layer-desc { font-size: 12px; color: var(--text2); margin-bottom: 8px; line-height: 1.5; }
.arch-components { display: flex; flex-wrap: wrap; gap: 6px; }
.arch-comp {
  background: transparent; border-radius: 6px; padding: 6px 12px;
  font-size: 12px; font-weight: 500; color: var(--text);
  border: 0.5px solid var(--border); transition: border-color 0.15s, background 0.15s;
}
.arch-comp:hover { border-color: var(--layer-color); background: color-mix(in srgb, var(--layer-color) 8%, transparent); }
.arch-arrow { display: flex; justify-content: center; padding: 2px 0; }
.arch-arrow svg { width: 20px; height: 20px; }
"""

    arrow_svg = '<svg viewBox="0 0 20 20" fill="none"><path d="M10 4V16M10 16L5 11M10 16L15 11" stroke="var(--text3)" stroke-width="1.5" stroke-linecap="round"/></svg>'

    parts = []
    for i, layer in enumerate(layers):
        color = layer.get("color", colors[i % len(colors)])
        name = _esc(layer.get("name", f"Layer {i + 1}"))
        desc = _esc(layer.get("description", ""))
        components = layer.get("components", [])
        comps_html = "".join(f'<div class="arch-comp">{_esc(c)}</div>' for c in components)
        desc_html = f'<div class="arch-layer-desc">{desc}</div>' if desc else ""
        parts.append(
            f"""<div class="arch-layer" style="--layer-color:{color}">
  <div class="arch-layer-header"><div class="arch-layer-name" style="color:{color}">{name}</div></div>
  {desc_html}
  <div class="arch-components">{comps_html}</div>
</div>"""
        )
        if i < len(layers) - 1:
            parts.append(f'<div class="arch-arrow">{arrow_svg}</div>')

    body = f'<div class="arch">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


def _build_concept_html(spec: dict, title: str) -> str:
    center = spec.get("center", {})
    branches = spec.get("branches", [])
    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--teal)",
        "var(--pink)",
    ]

    css = """
.concept { display: flex; flex-direction: column; align-items: center; gap: 16px; }
.concept-center {
  background: transparent; border-left: 3px solid var(--accent);
  padding: 12px 16px; text-align: left; max-width: 400px;
}
.concept-center-title { font-size: 16px; font-weight: 700; color: var(--accent); }
.concept-center-desc { font-size: 12px; color: var(--text2); margin-top: 4px; line-height: 1.5; }
.concept-branches { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; width: 100%; }
.concept-branch {
  flex: 1; min-width: 140px; max-width: 220px;
  padding: 10px 12px; background: transparent;
  transition: background 0.15s;
}
.concept-branch:hover { background: color-mix(in srgb, var(--branch-color, var(--accent)) 6%, transparent); }
.concept-branch-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.concept-branch-desc { font-size: 11px; color: var(--text3); margin-bottom: 6px; line-height: 1.4; }
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
        branch_title = _esc(branch.get("title", ""))
        branch_desc = _esc(branch.get("description", ""))
        items = branch.get("items", [])
        items_html = "".join(f"<li>{_esc(item)}</li>" for item in items)
        desc_html = (
            f'<div class="concept-branch-desc">{branch_desc}</div>'
            if branch_desc
            else ""
        )
        branch_parts.append(
            f"""<div class="concept-branch" style="--branch-color:{color};border-left:2px solid color-mix(in srgb,{color} 40%,transparent)">
  <div class="concept-branch-title" style="color:{color}">{branch_title}</div>
  {desc_html}
  <ul class="concept-branch-items">{items_html}</ul>
</div>"""
        )

    body = f"""<div class="concept">
  {center_html}
  <div class="concept-connector">↓</div>
  <div class="concept-branches">{"".join(branch_parts)}</div>
</div>"""

    return _wrap_html(css, body, title)


def _build_infographic_html(spec: dict, title: str) -> str:
    stats = spec.get("stats", [])
    sections = spec.get("sections", [])
    highlights = spec.get("highlights", [])
    takeaway = spec.get("takeaway", "")
    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--teal)",
        "var(--pink)",
    ]

    css = """
.infographic { display: flex; flex-direction: column; gap: 16px; }
.info-stats { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
.info-stat {
  flex: 1; min-width: 100px; text-align: center; padding: 16px;
  border-radius: var(--radius); border: 1.5px solid var(--border);
  transition: transform 0.15s, box-shadow 0.15s;
}
.info-stat:hover { transform: translateY(-2px); box-shadow: 0 4px 12px var(--shadow); }
.info-stat-value { font-size: 28px; font-weight: 800; line-height: 1; }
.info-stat-label { font-size: 11px; color: var(--text2); margin-top: 6px; font-weight: 500; }
.info-stat-desc { font-size: 10px; color: var(--text3); margin-top: 4px; }
.info-section {
  background: var(--bg2); border-radius: var(--radius); padding: 16px;
  border: 1px solid var(--border);
}
.info-section-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 8px; }
.info-section-content { font-size: 13px; color: var(--text2); line-height: 1.6; }
.info-highlights { display: flex; flex-wrap: wrap; gap: 8px; }
.info-highlight {
  display: inline-block; padding: 4px 10px; border-radius: 6px;
  font-weight: 600; font-size: 12px;
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
}
.info-takeaway {
  font-size: 12px; color: var(--text3); padding-top: 12px;
  border-top: 1px solid color-mix(in srgb, var(--border) 30%, transparent);
  font-style: italic;
}
"""

    stats_html = ""
    if stats:
        stat_parts = []
        for i, stat in enumerate(stats):
            color = stat.get("color", colors[i % len(colors)])
            value = _esc(stat.get("value", ""))
            label = _esc(stat.get("label", ""))
            desc = _esc(stat.get("description", ""))
            desc_html = f'<div class="info-stat-desc">{desc}</div>' if desc else ""
            stat_parts.append(
                f"""<div class="info-stat">
  <div class="info-stat-value" style="color:{color}">{value}</div>
  <div class="info-stat-label">{label}</div>
  {desc_html}
</div>"""
            )
        stats_html = f'<div class="info-stats">{"".join(stat_parts)}</div>'

    highlights_html = ""
    if highlights:
        hl_parts = "".join(f'<span class="info-highlight">{_esc(h)}</span>' for h in highlights)
        highlights_html = f'<div class="info-highlights">{hl_parts}</div>'

    section_parts = []
    for section in sections:
        section_title = _esc(section.get("title", ""))
        section_content = _esc(section.get("content", ""))
        section_parts.append(
            f"""<div class="info-section">
  <div class="info-section-title">{section_title}</div>
  <div class="info-section-content">{section_content}</div>
</div>"""
        )

    takeaway_html = f'<div class="info-takeaway">{_esc(takeaway)}</div>' if takeaway else ""

    body = f"""<div class="infographic">
  {stats_html}
  {highlights_html}
  {"".join(section_parts)}
  {takeaway_html}
</div>"""

    return _wrap_html(css, body, title)


def _build_timeline_html(spec: dict, title: str) -> str:
    events = spec.get("events", spec.get("steps", []))
    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--teal)",
        "var(--pink)",
    ]

    css = """
.timeline { position: relative; padding-left: 28px; }
.timeline::before {
  content: ""; position: absolute; left: 10px; top: 0; bottom: 0;
  width: 2px; background: var(--border);
}
.tl-event { position: relative; padding: 0 0 24px 20px; }
.tl-event:last-child { padding-bottom: 0; }
.tl-dot {
  position: absolute; left: -23px; top: 4px;
  width: 12px; height: 12px; border-radius: 50%;
  border: 2px solid var(--event-color, var(--accent));
  background: var(--bg);
}
.tl-event:hover .tl-dot { background: var(--event-color, var(--accent)); }
.tl-date { font-size: 10px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; }
.tl-title { font-size: 14px; font-weight: 600; color: var(--text); margin: 2px 0; }
.tl-desc { font-size: 12px; color: var(--text2); line-height: 1.5; }
"""

    parts = []
    for i, event in enumerate(events):
        color = event.get("color", colors[i % len(colors)])
        date = _esc(event.get("date", event.get("time", "")))
        event_title = _esc(event.get("title", ""))
        desc = _esc(event.get("description", ""))
        date_html = f'<div class="tl-date">{date}</div>' if date else ""
        desc_html = f'<div class="tl-desc">{desc}</div>' if desc else ""
        parts.append(
            f"""<div class="tl-event" style="--event-color:{color}">
  <div class="tl-dot"></div>
  {date_html}
  <div class="tl-title">{event_title}</div>
  {desc_html}
</div>"""
        )

    body = f'<div class="timeline">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


def _build_map_lite_html(spec: dict, title: str) -> str:
    regions = spec.get("regions", spec.get("items", []))
    colors = [
        "var(--accent)",
        "var(--green)",
        "var(--purple)",
        "var(--amber)",
        "var(--teal)",
        "var(--pink)",
    ]

    css = """
.map-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.map-card {
  padding: 14px; border-radius: var(--radius); border: 1.5px solid var(--border);
  background: var(--bg2); transition: transform 0.15s, box-shadow 0.15s;
}
.map-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px var(--shadow); }
.map-card-name { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
.map-card-value { font-size: 20px; font-weight: 800; line-height: 1.2; }
.map-card-desc { font-size: 11px; color: var(--text2); margin-top: 4px; line-height: 1.4; }
.map-card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.map-card-tag {
  font-size: 9px; padding: 1px 6px; border-radius: 4px;
  background: color-mix(in srgb, var(--region-color) 10%, transparent);
  color: var(--region-color);
}
"""

    parts = []
    for i, region in enumerate(regions):
        color = region.get("color", colors[i % len(colors)])
        name = _esc(region.get("name", region.get("title", "")))
        value = _esc(region.get("value", ""))
        desc = _esc(region.get("description", ""))
        tags = region.get("tags", [])
        value_html = f'<div class="map-card-value" style="color:{color}">{value}</div>' if value else ""
        desc_html = f'<div class="map-card-desc">{desc}</div>' if desc else ""
        tags_html = ""
        if tags:
            tag_parts = "".join(f'<span class="map-card-tag">{_esc(t)}</span>' for t in tags)
            tags_html = f'<div class="map-card-tags">{tag_parts}</div>'
        parts.append(
            f"""<div class="map-card" style="--region-color:{color}">
  <div class="map-card-name" style="color:{color}">{name}</div>
  {value_html}{desc_html}{tags_html}
</div>"""
        )

    body = f'<div class="map-grid">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)
