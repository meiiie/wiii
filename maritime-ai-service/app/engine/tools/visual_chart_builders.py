"""Chart-specific HTML builders for structured visual tools."""

from __future__ import annotations

import logging
from typing import Any

from app.engine.tools.visual_html_core import _esc, _wrap_html

logger = logging.getLogger(__name__)


def _normalize_chart_spec(spec: dict[str, Any], title: str = "") -> dict[str, Any]:
    """Accept common chart payload shapes and coerce them into labels + datasets."""
    normalized_spec = dict(spec or {})
    chart_type = str(
        normalized_spec.get("chart_type")
        or normalized_spec.get("style")
        or normalized_spec.get("chart_style")
        or normalized_spec.get("type")
        or "bar"
    ).strip().lower()
    if chart_type not in {"bar", "line", "area"}:
        chart_type = "bar"

    labels = normalized_spec.get("labels")
    datasets = normalized_spec.get("datasets")

    if not isinstance(labels, list):
        labels = []
    if not isinstance(datasets, list):
        datasets = []

    raw_data = normalized_spec.get("data")
    if (not labels or not datasets) and isinstance(raw_data, list):
        if raw_data and all(isinstance(item, dict) for item in raw_data):
            row_labels: list[str] = []
            row_values: list[float] = []
            row_colors: list[str] = []
            for index, item in enumerate(raw_data):
                label = str(
                    item.get("label")
                    or item.get("name")
                    or item.get("x")
                    or item.get("category")
                    or f"Item {index + 1}"
                )
                raw_value = item.get("value", item.get("y"))
                if isinstance(raw_value, (int, float)):
                    value = float(raw_value)
                else:
                    try:
                        value = float(str(raw_value).strip())
                    except Exception:
                        value = 0.0
                row_labels.append(label)
                row_values.append(value)
                color = item.get("color")
                if isinstance(color, str) and color.strip():
                    row_colors.append(color.strip())
            labels = row_labels
            datasets = [{
                "label": str(
                    normalized_spec.get("series_label")
                    or normalized_spec.get("dataset_label")
                    or normalized_spec.get("title")
                    or title
                    or "Du lieu"
                ),
                "data": row_values,
                **({"colors": row_colors} if row_colors else {}),
            }]
        elif raw_data and all(isinstance(item, (int, float)) for item in raw_data):
            labels = [f"Item {index + 1}" for index, _ in enumerate(raw_data)]
            datasets = [{
                "label": str(
                    normalized_spec.get("series_label")
                    or normalized_spec.get("dataset_label")
                    or normalized_spec.get("title")
                    or title
                    or "Du lieu"
                ),
                "data": [float(item) for item in raw_data],
            }]

    normalized_spec["chart_type"] = chart_type
    normalized_spec["labels"] = labels
    normalized_spec["datasets"] = datasets
    return normalized_spec


def _build_chart_html_impl(spec: dict, title: str) -> str:
    """Lightweight SVG chart with legend and bar-summary fallback."""
    logger.info(
        "[CHART_BUILDER] Input spec keys: %s",
        list(spec.keys()) if spec else "None",
    )

    normalized_spec = _normalize_chart_spec(spec, title)
    chart_type = str(normalized_spec.get("chart_type") or "bar").lower()
    labels = normalized_spec.get("labels", [])
    datasets = normalized_spec.get("datasets", [])
    caption = normalized_spec.get("caption", "")
    colors = ["#D97757", "#85CDCA", "#FFD166", "#C9B1FF", "#E8A87C"]

    logger.info(
        "[CHART_BUILDER] After normalize: labels=%d, datasets=%d",
        len(labels),
        len(datasets),
    )

    css = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,-apple-system,sans-serif; background:transparent; color:#333; }
.root { max-width:600px; margin:0 auto; padding:16px 0; }
.title { font-size:15px; font-weight:600; margin-bottom:4px; }
.subtitle { font-size:13px; color:#999; margin-bottom:20px; }
.bar-rows { display:flex; flex-direction:column; gap:12px; }
.bar-row { display:flex; align-items:center; gap:12px; }
.bar-label { min-width:140px; max-width:200px; font-size:13px; color:#555; text-align:right; font-weight:500; flex-shrink:0; word-wrap:break-word; }
.bar-track { flex:1; height:28px; background:#f5f2ef; border-radius:6px; overflow:hidden; }
.bar-fill { height:100%; border-radius:6px; }
.bar-value { font-size:12px; font-weight:600; color:#555; min-width:48px; }
.chart-wrap { margin-bottom: 16px; }
.chart-svg { width:100%; height:auto; display:block; }
.chart-legend { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 14px; }
.chart-legend-item { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text2); }
.chart-legend-swatch { width:10px; height:10px; border-radius:999px; display:inline-block; }
.chart-empty { text-align:center; color:#999; padding:20px; font-size:14px; }
"""
    if not labels or not datasets:
        body = '<div class="chart-empty">No chart data provided.</div>'
        return _wrap_html(css, body, title)

    all_values = []
    for dataset in datasets:
        all_values.extend(v for v in dataset.get("data", []) if isinstance(v, (int, float)))
    min_val = min(min(all_values), 0) if all_values else 0
    max_val = max(max(all_values), 0) if all_values else 1
    val_range = max(max_val - min_val, 1)

    chart_w = 560
    chart_h = 240
    pad_left = 48
    pad_right = 20
    pad_top = 18
    pad_bottom = 32
    plot_w = chart_w - pad_left - pad_right
    plot_h = chart_h - pad_top - pad_bottom
    n_labels = len(labels)
    bar_group_w = plot_w / n_labels if n_labels else plot_w
    n_datasets = len(datasets)
    svg_parts = [
        f'<line x1="{pad_left}" y1="{pad_top + plot_h}" x2="{pad_left + plot_w}" y2="{pad_top + plot_h}" stroke="#cbd5e1" stroke-width="1"/>',
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{pad_top + plot_h}" stroke="#cbd5e1" stroke-width="1"/>',
    ]

    for idx, label in enumerate(labels):
        x = pad_left + (idx + 0.5) * bar_group_w
        svg_parts.append(
            f'<text x="{x:.1f}" y="{chart_h - 8}" text-anchor="middle" font-size="11" fill="#64748b">{_esc(str(label))}</text>'
        )

    for dataset_index, dataset in enumerate(datasets):
        dataset_colors = dataset.get("colors") if isinstance(dataset.get("colors"), list) else []
        color = dataset.get("color", colors[dataset_index % len(colors)])
        data = dataset.get("data", [])
        points = []

        for i, _label in enumerate(labels):
            value = data[i] if i < len(data) else 0
            x = pad_left + (i + 0.5) * bar_group_w
            y = pad_top + plot_h - ((value - min_val) / val_range) * plot_h
            points.append((x, y, value))

        if chart_type == "line":
            path_d = " ".join(
                f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}"
                for j, (x, y, _) in enumerate(points)
            )
            svg_parts.append(
                f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            for x, y, _ in points:
                svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        else:
            bar_width = bar_group_w * 0.7 / n_datasets
            for i, (x, y, value) in enumerate(points):
                bar_x = x - (n_datasets * bar_width / 2) + dataset_index * bar_width
                base_y = pad_top + plot_h - ((0 - min_val) / val_range) * plot_h
                bar_h = base_y - y
                bar_color = (
                    dataset_colors[i]
                    if i < len(dataset_colors)
                    and isinstance(dataset_colors[i], str)
                    and dataset_colors[i].strip()
                    else color
                )
                svg_parts.append(
                    f'<rect x="{bar_x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" fill="{bar_color}" rx="2" opacity="0.85"/>'
                )

    legend_html = "".join(
        f'<div class="chart-legend-item"><span class="chart-legend-swatch" style="background:{dataset.get("color", colors[i % len(colors)])}"></span>{_esc(dataset.get("label", f"Series {i + 1}"))}</div>'
        for i, dataset in enumerate(datasets)
    )

    bar_rows = []
    primary_dataset = datasets[0] if datasets else {}
    data_values = primary_dataset.get("data", [])
    for i, label in enumerate(labels):
        value = data_values[i] if i < len(data_values) else 0
        pct = int((value / max_val) * 100) if max_val else 0
        color = colors[i % len(colors)]
        bar_rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{_esc(str(label))}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:linear-gradient(90deg,{color},{color}cc)"></div></div>'
            f'<div class="bar-value">{value:,.0f}</div>'
            f"</div>"
        )

    if not bar_rows:
        body = (
            f'<div style="padding:20px;font-size:14px;color:#555;">{_esc(title)}<br>'
            '<span style="color:#999;font-size:13px;">Du lieu chua du de ve bieu do — xem noi dung text ben tren.</span></div>'
        )
        return _wrap_html(css, body, title)

    caption_html = f'<div class="subtitle">{_esc(caption)}</div>' if caption else ""
    svg_html = (
        f'<div class="chart-wrap"><svg class="chart-svg" viewBox="0 0 {chart_w} {chart_h}" role="img" aria-label="{_esc(title)}">'
        + "".join(svg_parts)
        + "</svg></div>"
    )

    body = '<div class="root">'
    body += f'<div class="title">{_esc(title)}</div>'
    body += caption_html
    body += svg_html
    if legend_html:
        body += f'<div class="chart-legend">{legend_html}</div>'
    body += '<div class="bar-rows">' + "\n".join(bar_rows) + "</div>"
    body += "</div>"
    return _wrap_html(css, body, title)
