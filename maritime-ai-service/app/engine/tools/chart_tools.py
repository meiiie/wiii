"""
Chart and diagram generation tools for Wiii agents.
Sprint 179: "Bieu Do Song" — Mermaid diagrams + data chart generation.
Sprint 228: Interactive Chart.js widgets rendered inline in chat.

Tools return Mermaid markdown syntax that the desktop app renders as SVG,
or self-contained HTML+Chart.js widgets rendered inline via ```widget code blocks.
Feature-gated by enable_chart_tools in config.
"""

import json
import logging

from app.engine.tools.native_tool import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Chart.js HTML Templates (Sprint 228)
# =============================================================================

_CHART_COLORS = [
    "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981",
    "#ec4899", "#06b6d4", "#f97316", "#6366f1", "#14b8a6",
]

_CHART_BORDERS = [
    "#dc2626", "#d97706", "#2563eb", "#7c3aed", "#059669",
    "#db2777", "#0891b2", "#ea580c", "#4f46e5", "#0d9488",
]


def _build_chart_html(
    chart_type: str,
    labels: list[str],
    datasets: list[dict],
    title: str,
    options: dict | None = None,
) -> str:
    """Build self-contained HTML with Chart.js for inline widget rendering."""
    # Assign colors to datasets if not provided
    for i, ds in enumerate(datasets):
        if "backgroundColor" not in ds:
            if chart_type in ("pie", "doughnut", "polarArea"):
                ds["backgroundColor"] = _CHART_COLORS[: len(labels)]
                ds["borderColor"] = _CHART_BORDERS[: len(labels)]
                ds["borderWidth"] = 2
            else:
                color = _CHART_COLORS[i % len(_CHART_COLORS)]
                ds["backgroundColor"] = color + "cc"  # 80% opacity
                ds["borderColor"] = color
                ds["borderWidth"] = 2

    chart_data = json.dumps(
        {"labels": labels, "datasets": datasets},
        ensure_ascii=False,
    )

    default_options = {
        "responsive": True,
        "maintainAspectRatio": True,
        "plugins": {
            "legend": {"position": "bottom", "labels": {"font": {"size": 12}}},
            "tooltip": {"enabled": True},
        },
    }
    if title:
        default_options["plugins"]["title"] = {
            "display": True,
            "text": title,
            "font": {"size": 15, "weight": "bold"},
        }
    if options:
        default_options.update(options)

    chart_options = json.dumps(default_options, ensure_ascii=False)

    return f"""<div style="max-width:500px;margin:0 auto;">
  <canvas id="chart"></canvas>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
new Chart(document.getElementById('chart'), {{
  type: '{chart_type}',
  data: {chart_data},
  options: {chart_options}
}});
</script>"""


@tool
def tool_generate_mermaid(
    description: str,
    diagram_type: str = "flowchart",
    direction: str = "TD",
) -> str:
    """Generate a Mermaid diagram from a natural language description.

    Use this when the user asks to visualize a process, relationship, or structure.
    Returns Mermaid syntax wrapped in a markdown code block.

    Args:
        description: What the diagram should show. Be specific about nodes and relationships.
        diagram_type: One of: flowchart, sequence, class, state, er, gantt, pie, mindmap, timeline
        direction: For flowchart: TD (top-down), LR (left-right), BT (bottom-top), RL (right-left)

    Returns:
        Mermaid markdown code block ready for rendering.
    """
    valid_types = {
        "flowchart", "sequence", "class", "state",
        "er", "gantt", "pie", "mindmap", "timeline",
    }
    if diagram_type not in valid_types:
        diagram_type = "flowchart"

    valid_directions = {"TD", "LR", "BT", "RL", "TB"}
    if direction not in valid_directions:
        direction = "TD"

    # Return instruction for LLM to generate the actual Mermaid syntax
    # The LLM will use this tool's output format to produce the diagram
    header = diagram_type if diagram_type != "flowchart" else f"flowchart {direction}"

    return (
        f"Generate a Mermaid diagram with the following specifications:\n"
        f"- Type: {diagram_type}\n"
        f"- Direction: {direction}\n"
        f"- Description: {description}\n\n"
        f"IMPORTANT: Return the diagram as a markdown code block with ```mermaid\n"
        f"Start with: {header}\n"
        f"Use Vietnamese labels where appropriate."
    )


@tool
def tool_generate_chart(
    data_description: str,
    chart_type: str = "pie",
    title: str = "",
) -> str:
    """Generate a data visualization chart using Mermaid syntax.

    Use this when the user asks for statistics, comparisons, distributions, or timelines.
    Supports pie charts, Gantt charts, and timeline diagrams via Mermaid.

    Args:
        data_description: Description of the data to visualize. Include specific numbers/percentages.
        chart_type: One of: pie, gantt, timeline, mindmap
        title: Chart title (in Vietnamese if appropriate)

    Returns:
        Mermaid markdown code block with the chart.
    """
    valid_chart_types = {"pie", "gantt", "timeline", "mindmap"}
    if chart_type not in valid_chart_types:
        chart_type = "pie"

    result = (
        f"Generate a Mermaid {chart_type} chart:\n"
        f"- Title: {title or 'Bieu do'}\n"
        f"- Data: {data_description}\n\n"
        f"IMPORTANT: Return as a markdown code block with ```mermaid\n"
        f"Use Vietnamese labels. Include real data values."
    )

    return result


@tool
def tool_generate_interactive_chart(
    chart_type: str,
    labels_json: str,
    datasets_json: str,
    title: str = "",
) -> str:
    """Generate an interactive Chart.js widget rendered INLINE in chat.

    Use this when the user needs a standalone numeric chart with hover/click interaction.
    This is NOT the primary tool for explanatory article-style visuals when
    tool_generate_visual is available.
    Returns a ```widget code block that the frontend renders as an interactive chart.

    PRIORITY: Use this INSTEAD of tool_generate_chart when data has specific numbers
    and the goal is a standalone interactive dashboard/chart.
    tool_generate_chart → static Mermaid pie only.
    tool_generate_interactive_chart → interactive Chart.js (bar, line, doughnut, radar, etc.)

    Args:
        chart_type: One of: bar, line, pie, doughnut, radar, polarArea, horizontalBar
        labels_json: JSON array of label strings. Example: '["Thang 1", "Thang 2", "Thang 3"]'
        datasets_json: JSON array of dataset objects. Each has "label" and "data" keys.
            Example: '[{"label": "Doanh thu", "data": [100, 200, 150]}]'
        title: Chart title in Vietnamese.

    Returns:
        A ```widget code block containing self-contained HTML+Chart.js.
        Only include this directly in the response for legacy/fallback widget paths.
    """
    valid_types = {"bar", "line", "pie", "doughnut", "radar", "polarArea", "horizontalBar"}
    if chart_type not in valid_types:
        chart_type = "bar"

    # Handle horizontalBar → bar with indexAxis
    options = None
    actual_type = chart_type
    if chart_type == "horizontalBar":
        actual_type = "bar"
        options = {"indexAxis": "y"}

    try:
        labels = json.loads(labels_json)
        if not isinstance(labels, list):
            return "Error: labels_json must be a JSON array of strings."
    except json.JSONDecodeError as e:
        return f"Error: Invalid labels_json: {e}"

    try:
        datasets = json.loads(datasets_json)
        if not isinstance(datasets, list):
            return "Error: datasets_json must be a JSON array of objects."
    except json.JSONDecodeError as e:
        return f"Error: Invalid datasets_json: {e}"

    html = _build_chart_html(
        chart_type=actual_type,
        labels=labels,
        datasets=datasets,
        title=title,
        options=options,
    )

    return (
        f"Widget đã tạo thành công! Include đoạn code block sau TRỰC TIẾP trong response:\n\n"
        f"```widget\n{html}\n```\n\n"
        f"Giải thích dữ liệu bằng tiếng Việt bên ngoài widget."
    )


def get_chart_tools() -> list:
    """Return list of chart generation tools. Feature-gated by enable_chart_tools."""
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "enable_chart_tools", False):
        return []

    return [tool_generate_mermaid, tool_generate_chart, tool_generate_interactive_chart]
