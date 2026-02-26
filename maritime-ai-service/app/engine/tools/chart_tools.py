"""
Chart and diagram generation tools for Wiii agents.
Sprint 179: "Bieu Do Song" — Mermaid diagrams + data chart generation.

Tools return Mermaid markdown syntax that the desktop app renders as SVG.
Feature-gated by enable_chart_tools in config.
"""

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


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


def get_chart_tools() -> list:
    """Return list of chart generation tools. Feature-gated by enable_chart_tools."""
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "enable_chart_tools", False):
        return []

    return [tool_generate_mermaid, tool_generate_chart]
