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
import re
import uuid
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.engine.tools.runtime_context import get_current_tool_runtime_context

logger = logging.getLogger(__name__)


CORE_STRUCTURED_VISUAL_TYPES = (
    "comparison",
    "process",
    "matrix",
    "architecture",
    "concept",
    "infographic",
    "chart",
    "timeline",
    "map_lite",
)



class VisualPayloadV1(BaseModel):
    """Structured inline visual contract for streaming-first rendering."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    visual_session_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    renderer_kind: Literal["template", "inline_html", "app", "recharts"] = "template"
    shell_variant: Literal["editorial", "compact", "immersive"] = "editorial"
    patch_strategy: Literal["spec_merge", "replace_html", "app_state"] = "spec_merge"
    figure_group_id: str = Field(min_length=1)
    figure_index: int = Field(ge=1, default=1)
    figure_total: int = Field(ge=1, default=1)
    pedagogical_role: Literal[
        "problem",
        "mechanism",
        "comparison",
        "architecture",
        "result",
        "benchmark",
        "conclusion",
    ] = "mechanism"
    chrome_mode: Literal["editorial", "app", "immersive"] = "editorial"
    claim: str = Field(min_length=1)
    presentation_intent: Literal["text", "article_figure", "chart_runtime", "code_studio_app", "artifact"] = "article_figure"
    figure_budget: int = Field(ge=1, le=3, default=1)
    quality_profile: Literal["draft", "standard", "premium"] = "standard"
    renderer_contract: Literal["host_shell", "chart_runtime", "article_figure"] = "article_figure"
    studio_lane: Literal["app", "artifact", "widget"] | None = None
    artifact_kind: Literal["html_app", "code_widget", "search_widget", "document", "chart_widget"] | None = None
    narrative_anchor: str = "after-lead"
    runtime: Literal["svg", "sandbox_html", "sandbox_react"]
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    spec: dict[str, Any]
    scene: dict[str, Any] = Field(default_factory=dict)
    controls: list[dict[str, Any]] = Field(default_factory=list)
    annotations: list[dict[str, Any]] = Field(default_factory=list)
    interaction_mode: Literal["static", "guided", "explorable", "scrubbable", "filterable"] = "guided"
    ephemeral: bool = True
    lifecycle_event: Literal["visual_open", "visual_patch"] = "visual_open"
    subtitle: str | None = None
    fallback_html: str | None = None
    runtime_manifest: dict[str, Any] | None = None
    artifact_handoff_available: bool = False
    artifact_handoff_mode: Literal["none", "followup_prompt"] = "none"
    artifact_handoff_label: str | None = None
    artifact_handoff_prompt: str | None = None
    metadata: dict[str, Any] | None = None


def _default_visual_title(visual_type: str) -> str:
    return visual_type.replace("_", " ").strip().title() or "Inline visual"


def _generate_figure_group_id(visual_type: str) -> str:
    slug = (visual_type or "figure").replace("_", "-").strip("-") or "figure"
    return f"fg-{slug}-{uuid.uuid4().hex[:10]}"


def _clean_summary_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _spec_text(spec: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = spec.get(key)
        cleaned = _clean_summary_text(value)
        if cleaned:
            return cleaned
    return ""


def _named_count(items: Any) -> int:
    return len(items) if isinstance(items, list) else 0


def _sanitize_summary_candidate(value: str, visual_type: str, title: str) -> str:
    cleaned = _clean_summary_text(value)
    if not cleaned:
        return ""

    patterns = [
        r"^structured visual sẵn sàng:\s*",
        r"^structured visual summary\s*",
        rf"^visual\s+{re.escape(visual_type).replace('_', '[_ ]')}\s+để tóm tắt nhanh nội dung:\s*",
        rf"^visual\s+{re.escape(visual_type).replace('_', '[_ ]')}:\s*",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    if _clean_summary_text(cleaned).lower() == _clean_summary_text(title).lower():
        return ""
    return cleaned


def _default_visual_summary(visual_type: str, title: str, spec: dict[str, Any] | None = None) -> str:
    safe_title = title.strip() or _default_visual_title(visual_type)
    safe_spec = spec if isinstance(spec, dict) else {}

    direct_hint = _spec_text(
        safe_spec,
        "takeaway",
        "key_takeaway",
        "caption",
        "note",
        "description",
        "summary",
    )
    if direct_hint:
        return direct_hint

    if visual_type == "comparison":
        left = safe_spec.get("left") if isinstance(safe_spec.get("left"), dict) else {}
        right = safe_spec.get("right") if isinstance(safe_spec.get("right"), dict) else {}
        left_title = _clean_summary_text(left.get("title")) or "góc nhìn bên trái"
        right_title = _clean_summary_text(right.get("title")) or "góc nhìn bên phải"
        return f"Đặt {left_title} cạnh {right_title} để thấy điểm khác biệt chính."

    if visual_type == "process":
        step_count = _named_count(safe_spec.get("steps"))
        if step_count > 0:
            return f"Quy trình được chia thành {step_count} bước liên tiếp để dễ theo dõi."

    if visual_type == "matrix":
        row_count = _named_count(safe_spec.get("rows"))
        col_count = _named_count(safe_spec.get("cols"))
        if row_count and col_count:
            return f"Ma trận này cho thấy mức độ liên hệ giữa {row_count} hàng và {col_count} cột."

    if visual_type == "architecture":
        layer_count = _named_count(safe_spec.get("layers"))
        if layer_count:
            return f"Kiến trúc được tách thành {layer_count} lớp chính và cách chúng kết nối với nhau."

    if visual_type == "concept":
        center = safe_spec.get("center") if isinstance(safe_spec.get("center"), dict) else {}
        center_title = _clean_summary_text(center.get("title")) or safe_title
        return f"{center_title} được mở rộng thành các nhánh chính để dễ định vị ý tưởng."

    if visual_type == "infographic":
        stat_count = _named_count(safe_spec.get("stats"))
        section_count = _named_count(safe_spec.get("sections"))
        if stat_count or section_count:
            return f"Khung nhìn này gồm {stat_count or 0} chỉ số và {section_count or 0} điểm nhấn để đọc nhanh."

    if visual_type == "chart":
        label_count = _named_count(safe_spec.get("labels"))
        if label_count:
            return f"Biểu đồ này làm rõ xu hướng qua {label_count} mốc chính."

    if visual_type == "timeline":
        event_count = _named_count(safe_spec.get("events"))
        if event_count:
            return f"Dòng thời gian này gồm {event_count} mốc để theo dõi sự chuyển dịch theo thứ tự."

    if visual_type == "map_lite":
        region_count = _named_count(safe_spec.get("regions"))
        if region_count:
            return f"Bản đồ này nhấn vào {region_count} khu vực để so sánh nhanh."

    return f"{safe_title} trong một khung nhìn trực quan để đọc nhanh."


def _infer_pedagogical_role(
    visual_type: str,
    spec: dict[str, Any],
    provided: str = "",
) -> str:
    candidate = str(provided or spec.get("pedagogical_role") or "").strip().lower()
    if candidate in {
        "problem",
        "mechanism",
        "comparison",
        "architecture",
        "result",
        "benchmark",
        "conclusion",
    }:
        return candidate

    default_map = {
        "comparison": "comparison",
        "process": "mechanism",
        "matrix": "mechanism",
        "architecture": "architecture",
        "concept": "mechanism",
        "infographic": "result",
        "chart": "benchmark",
        "timeline": "mechanism",
        "map_lite": "mechanism",
        "simulation": "mechanism",
        "quiz": "conclusion",
        "interactive_table": "result",
        "react_app": "result",
    }
    return default_map.get(visual_type, "mechanism")


def _infer_chrome_mode(
    renderer_kind: str,
    shell_variant: str,
    provided: str = "",
) -> str:
    candidate = str(provided or "").strip().lower()
    if candidate in {"editorial", "app", "immersive"}:
        return candidate
    if renderer_kind == "app":
        return "app"
    if shell_variant == "immersive":
        return "immersive"
    return "editorial"


def _default_visual_claim(
    visual_type: str,
    title: str,
    summary: str,
    spec: dict[str, Any],
) -> str:
    explicit = _clean_summary_text(spec.get("claim"))
    if explicit:
        return explicit
    if summary:
        return summary
    if visual_type == "comparison":
        left = _spec_text(spec.get("left") if isinstance(spec.get("left"), dict) else {}, "title")
        right = _spec_text(spec.get("right") if isinstance(spec.get("right"), dict) else {}, "title")
        if left and right:
            return f"Đặt {left} cạnh {right} để thấy ra sự khác biệt chính."
    return f"{title} làm rõ một ý chính trong lời giải đang theo."


def _get_runtime_visual_metadata() -> dict[str, Any]:
    runtime = get_current_tool_runtime_context()
    if runtime and isinstance(runtime.metadata, dict):
        return runtime.metadata
    return {}


def _runtime_metadata_text(key: str, default: str = "") -> str:
    value = _get_runtime_visual_metadata().get(key, default)
    return str(value or default).strip()


def _runtime_metadata_int(key: str, default: int = 0) -> int:
    value = _get_runtime_visual_metadata().get(key, default)
    try:
        return int(value)
    except Exception:
        return default


def _runtime_presentation_intent() -> str:
    return _runtime_metadata_text("presentation_intent", "text")


def _runtime_renderer_contract() -> str:
    return _runtime_metadata_text("renderer_contract", "")


def _runtime_quality_profile() -> str:
    return _runtime_metadata_text("quality_profile", "standard")


def _runtime_studio_lane() -> str:
    return _runtime_metadata_text("studio_lane", "")


def _runtime_artifact_kind() -> str:
    return _runtime_metadata_text("artifact_kind", "")


def _runtime_code_studio_version() -> int:
    return max(0, _runtime_metadata_int("code_studio_version", 0))


def _runtime_visual_user_query() -> str:
    return _runtime_metadata_text("visual_user_query", "")


def _runtime_preferred_render_surface() -> str:
    return _runtime_metadata_text("preferred_render_surface", "")


def _runtime_planning_profile() -> str:
    return _runtime_metadata_text("planning_profile", "")


def _runtime_thinking_floor() -> str:
    return _runtime_metadata_text("thinking_floor", "")


def _runtime_critic_policy() -> str:
    return _runtime_metadata_text("critic_policy", "")


def _runtime_living_expression_mode() -> str:
    return _runtime_metadata_text("living_expression_mode", "")


def _metadata_text(metadata: dict[str, Any] | None, key: str, default: str = "") -> str:
    if not isinstance(metadata, dict):
        return default
    value = metadata.get(key, default)
    return str(value or default).strip()


def _build_artifact_handoff(
    *,
    presentation_intent: str,
    visual_type: str,
    title: str,
    summary: str,
) -> dict[str, Any]:
    if presentation_intent == "artifact":
        return {
            "available": False,
            "mode": "none",
            "label": None,
            "prompt": None,
        }

    clean_title = _clean_summary_text(title) or _default_visual_title(visual_type)
    clean_summary = _clean_summary_text(summary)

    if presentation_intent == "code_studio_app":
        prompt = (
            f"Biến app inline '{clean_title}' này thành một artifact HTML hoàn chỉnh, mở trong Code Studio để tôi có thể "
            "chỉnh sửa, lưu và chia sẻ tiếp. Giữ nguyên state model, controls, readouts, feedback hooks, và nâng chất lượng production nếu cần."
        )
    elif presentation_intent == "chart_runtime":
        prompt = (
            f"Biến chart inline '{clean_title}' này thành một artifact HTML/SVG hoàn chỉnh để tôi có thể chỉnh sửa, lưu và chia sẻ tiếp. "
            "Giữ scale, units, legend, source/provenance, takeaway, và cho tôi quyền inspect/chỉnh tiếp như một artifact thật."
        )
    else:
        prompt = (
            f"Biến visual inline '{clean_title}' này thành một artifact HTML/SVG hoàn chỉnh để tôi có thể chỉnh sửa, lưu và chia sẻ tiếp. "
            "Giữ claim, labels, annotations, và nâng trải nghiệm thành một artifact thật thay vì chỉ figure inline."
        )

    if clean_summary:
        prompt += f" Context ngắn: {clean_summary}"

    return {
        "available": True,
        "mode": "followup_prompt",
        "label": "Mo thanh Artifact",
        "prompt": prompt,
    }


def _llm_first_visual_codegen_enabled() -> bool:
    from app.core.config import get_settings

    return bool(getattr(get_settings(), "enable_llm_code_gen_visuals", False))


def _should_keep_structured_renderer(requested: str = "") -> bool:
    presentation_intent = _runtime_presentation_intent()
    if presentation_intent not in {"article_figure", "chart_runtime"}:
        return False
    if requested.strip() == "inline_html":
        return False
    return _runtime_metadata_text("visual_intent_mode", "") != "inline_html"


def _supports_auto_grouping(visual_type: str, renderer_kind: str) -> bool:
    if renderer_kind != "template":
        return False
    return visual_type in {
        "comparison",
        "process",
        "matrix",
        "architecture",
        "concept",
        "infographic",
        "chart",
        "timeline",
        "map_lite",
    }


def _collect_story_points(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
) -> list[str]:
    points: list[str] = []

    def add_point(value: Any) -> None:
        text = _clean_summary_text(value)
        if not text or text in points:
            return
        points.append(text)

    add_point(summary)
    add_point(spec.get("note"))
    add_point(spec.get("caption"))
    add_point(spec.get("takeaway"))

    if visual_type == "comparison":
        left = spec.get("left", {}) if isinstance(spec.get("left"), dict) else {}
        right = spec.get("right", {}) if isinstance(spec.get("right"), dict) else {}
        left_title = _spec_text(left, "title")
        right_title = _spec_text(right, "title")
        if left_title and right_title:
            add_point(f"{left_title} và {right_title} nên được đọc cạnh nhau để thấy độ lệch chính.")
        left_items = left.get("items") if isinstance(left.get("items"), list) else []
        right_items = right.get("items") if isinstance(right.get("items"), list) else []
        if left_items or right_items:
            add_point(
                f"Bên trái có {len(left_items)} điểm nhấn, bên phải có {len(right_items)} điểm nhấn."
            )

    elif visual_type == "process":
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        labels = [
            str((step if isinstance(step, dict) else {}).get("title") or f"Bước {index + 1}")
            for index, step in enumerate(steps[:3])
        ]
        if labels:
            add_point("Thứ tự xử lý: " + " -> ".join(labels))

    elif visual_type == "architecture":
        layers = spec.get("layers", []) if isinstance(spec.get("layers"), list) else []
        labels = [
            str((layer if isinstance(layer, dict) else {}).get("name") or f"Lớp {index + 1}")
            for index, layer in enumerate(layers[:4])
        ]
        if labels:
            add_point("Dòng xử lý đi qua các lớp: " + " -> ".join(labels))

    elif visual_type == "concept":
        center = spec.get("center", {}) if isinstance(spec.get("center"), dict) else {}
        branches = spec.get("branches", []) if isinstance(spec.get("branches"), list) else []
        center_title = _spec_text(center, "title") or title
        branch_titles = [
            str((branch if isinstance(branch, dict) else {}).get("title") or f"Nhánh {index + 1}")
            for index, branch in enumerate(branches[:3])
        ]
        if center_title and branch_titles:
            add_point(f"{center_title} được mở rộng qua: {', '.join(branch_titles)}.")

    elif visual_type == "chart":
        datasets = spec.get("datasets", []) if isinstance(spec.get("datasets"), list) else []
        labels = spec.get("labels", []) if isinstance(spec.get("labels"), list) else []
        dataset_labels = [
            str((dataset if isinstance(dataset, dict) else {}).get("label") or f"Series {index + 1}")
            for index, dataset in enumerate(datasets[:3])
        ]
        if dataset_labels:
            add_point("Biểu đồ theo dõi các đường: " + ", ".join(dataset_labels) + ".")
        if labels:
            add_point(f"Trục x gồm {len(labels)} mốc chính để đọc xu hướng.")

    elif visual_type == "matrix":
        rows = spec.get("rows", []) if isinstance(spec.get("rows"), list) else []
        cols = spec.get("cols", []) if isinstance(spec.get("cols"), list) else []
        if rows or cols:
            add_point(f"Ma trận này được đọc qua {len(rows)} hàng và {len(cols)} cột.")

    elif visual_type == "timeline":
        events = spec.get("events", []) if isinstance(spec.get("events"), list) else []
        labels = [
            str((event if isinstance(event, dict) else {}).get("title") or (event if isinstance(event, dict) else {}).get("label") or f"Mốc {index + 1}")
            for index, event in enumerate(events[:4])
        ]
        if labels:
            add_point("Các mốc cần theo dõi: " + " -> ".join(labels))

    elif visual_type == "map_lite":
        regions = spec.get("regions", []) if isinstance(spec.get("regions"), list) else []
        labels = [
            str((region if isinstance(region, dict) else {}).get("label") or f"Khu vực {index + 1}")
            for index, region in enumerate(regions[:4])
        ]
        if labels:
            add_point("Bản đồ đang nhấn vào: " + ", ".join(labels) + ".")

    return points[:3]


def _build_takeaway_infographic_spec(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
) -> dict[str, Any]:
    points = _collect_story_points(visual_type, spec, title, summary)
    if not points:
        points = [summary or f"{title} gồm một vài điểm nhấn để đọc nhanh."]

    stats: list[dict[str, Any]] = []
    if visual_type == "comparison":
        stats = [
            {"value": "2", "label": "Góc nhìn"},
            {"value": str(_named_count((spec.get("left") or {}).get("items")) + _named_count((spec.get("right") or {}).get("items"))), "label": "Điểm nhấn"},
        ]
    elif visual_type == "process":
        stats = [{"value": str(_named_count(spec.get("steps"))), "label": "Bước"}]
    elif visual_type == "architecture":
        stats = [{"value": str(_named_count(spec.get("layers"))), "label": "Lớp"}]
    elif visual_type == "concept":
        stats = [{"value": str(_named_count(spec.get("branches"))), "label": "Nhánh"}]
    elif visual_type == "chart":
        stats = [
            {"value": str(_named_count(spec.get("datasets")) or 1), "label": "Series"},
            {"value": str(_named_count(spec.get("labels"))), "label": "Mốc đọc"},
        ]
    elif visual_type == "matrix":
        stats = [
            {"value": str(_named_count(spec.get("rows"))), "label": "Hàng"},
            {"value": str(_named_count(spec.get("cols"))), "label": "Cột"},
        ]
    elif visual_type == "timeline":
        stats = [{"value": str(_named_count(spec.get("events"))), "label": "Mốc"}]
    elif visual_type == "map_lite":
        stats = [{"value": str(_named_count(spec.get("regions"))), "label": "Khu vực"}]

    sections = [
        {"title": "Cần nhìn gì", "content": points[0]},
    ]
    if len(points) > 1:
        sections.append({"title": "Vì sao quan trọng", "content": points[1]})
    sections.append({
        "title": "Điểm chốt",
        "content": points[-1],
    })

    return {
        "stats": stats,
        "sections": sections,
        "caption": summary or f"Điểm chốt từ {title}.",
    }


def _build_takeaway_claim(
    visual_type: str,
    title: str,
    summary: str,
    spec: dict[str, Any],
) -> str:
    if summary:
        return f"Điểm chốt của {title}: {summary}"
    if visual_type == "chart":
        return f"{title} cần được đọc như một xu hướng chứ không chỉ là một hình minh họa."
    if visual_type == "comparison":
        return f"{title} chốt lại sự khác biệt cần nhớ nhất giữa hai bên."
    return f"{title} cần được đọc thành một kết luận ngắn gọn sau figure chính."


def _normalize_visual_query_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().strip().split())


def _estimate_query_figure_pressure(query: str) -> int:
    normalized = _normalize_visual_query_text(query)
    if not normalized:
        return 0

    score = 0
    if (
        ("chart" in normalized or "bieu do" in normalized or "visual" in normalized)
        and any(token in normalized for token in ("explain", "giai thich", "intuition", "truc quan"))
    ):
        score += 1

    if any(
        phrase in normalized
        for phrase in (
            "step by step",
            "tung buoc",
            "theo buoc",
            "build intuition",
            "de hinh dung",
            "break it down",
            "co che",
            "mechanism",
            "evolution",
            "benchmark",
            "tradeoff",
            "kien truc",
            "architecture",
        )
    ):
        score += 1

    return min(score, 2)


def _estimate_spec_figure_pressure(visual_type: str, spec: dict[str, Any]) -> int:
    if visual_type == "comparison":
        left = spec.get("left", {}) if isinstance(spec.get("left"), dict) else {}
        right = spec.get("right", {}) if isinstance(spec.get("right"), dict) else {}
        total_items = _named_count(left.get("items")) + _named_count(right.get("items"))
        if total_items >= 8:
            return 1
        return 0

    if visual_type == "process":
        step_count = _named_count(spec.get("steps"))
        return 1 if step_count >= 5 else 0

    if visual_type == "architecture":
        layer_count = _named_count(spec.get("layers"))
        link_count = _named_count(spec.get("links"))
        return 1 if layer_count >= 4 or link_count >= 4 else 0

    if visual_type == "concept":
        return 1 if _named_count(spec.get("branches")) >= 4 else 0

    if visual_type == "infographic":
        section_count = _named_count(spec.get("sections"))
        stat_count = _named_count(spec.get("stats"))
        return 1 if section_count >= 4 or (section_count >= 3 and stat_count >= 2) else 0

    if visual_type == "chart":
        label_count = _named_count(spec.get("labels"))
        dataset_count = _named_count(spec.get("datasets"))
        return 1 if (label_count >= 5 and dataset_count >= 2) or label_count >= 7 else 0

    if visual_type == "matrix":
        row_count = _named_count(spec.get("rows"))
        col_count = _named_count(spec.get("cols"))
        return 1 if row_count * col_count >= 16 else 0

    if visual_type == "timeline":
        return 1 if _named_count(spec.get("events")) >= 5 else 0

    if visual_type == "map_lite":
        return 1 if _named_count(spec.get("regions")) >= 4 else 0

    return 0


def _plan_auto_group_figure_budget(
    *,
    visual_type: str,
    spec: dict[str, Any],
    renderer_kind: str,
    operation: str,
) -> int:
    if operation != "open":
        return 1
    if spec.get("allow_single_figure") or spec.get("disable_auto_group"):
        return 1
    if isinstance(spec.get("figures"), list) and spec.get("figures"):
        return 1
    if not _supports_auto_grouping(visual_type, renderer_kind):
        return 1

    metadata = _get_runtime_visual_metadata()
    if not (
        metadata.get("visual_force_tool")
        and str(metadata.get("visual_intent_mode") or "") == "template"
    ):
        return 1

    query = str(metadata.get("visual_user_query") or "")
    budget = 1
    budget += _estimate_query_figure_pressure(query)
    budget += _estimate_spec_figure_pressure(visual_type, spec)

    return max(1, min(3, budget))


def _build_bridge_infographic_spec(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
) -> dict[str, Any]:
    base = _build_takeaway_infographic_spec(visual_type, spec, title, summary)
    points = _collect_story_points(visual_type, spec, title, summary)
    if not points:
        points = [summary or f"{title} cần một nhóm điểm nhấn để đọc theo từng lớp."]

    sections = [{"title": "Cần để mắt tới", "content": points[0]}]
    if len(points) > 1:
        sections.append({"title": "Cơ chế chính", "content": points[1]})
    if len(points) > 2:
        sections.append({"title": "Dấu hiệu cần nhớ", "content": points[2]})

    return {
        **base,
        "sections": sections,
        "caption": f"Cách đọc {title} qua một vài điểm nhấn chính.",
    }


def _should_auto_group_visual_request(
    *,
    visual_type: str,
    spec: dict[str, Any],
    renderer_kind: str,
    operation: str,
) -> bool:
    return _plan_auto_group_figure_budget(
        visual_type=visual_type,
        spec=spec,
        renderer_kind=renderer_kind,
        operation=operation,
    ) > 1


def _build_auto_grouped_payloads(
    *,
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
    subtitle: str,
    operation: str,
    renderer_kind: str,
    shell_variant: str,
    patch_strategy: str,
    narrative_anchor: str,
    runtime_manifest: dict[str, Any] | None,
) -> list[VisualPayloadV1]:
    figure_budget = _plan_auto_group_figure_budget(
        visual_type=visual_type,
        spec=spec,
        renderer_kind=renderer_kind,
        operation=operation,
    )
    if figure_budget <= 1:
        return []

    primary_role = _infer_pedagogical_role(visual_type, spec)
    secondary_role = "conclusion" if primary_role != "conclusion" else "result"
    resolved_title = title.strip() or _default_visual_title(visual_type)
    resolved_summary = _sanitize_summary_candidate(summary, visual_type, resolved_title) or _default_visual_summary(
        visual_type,
        resolved_title,
        spec,
    )
    group_id = _generate_figure_group_id(visual_type)
    bridge_claim = _collect_story_points(visual_type, spec, resolved_title, resolved_summary)
    bridge_role = "mechanism" if primary_role in {"problem", "comparison", "benchmark"} else "result"
    figures: list[dict[str, Any]] = [
        {
            "type": visual_type,
            "title": resolved_title,
            "summary": resolved_summary,
            "subtitle": subtitle,
            "pedagogical_role": primary_role,
            "claim": _default_visual_claim(visual_type, resolved_title, resolved_summary, spec),
            "narrative_anchor": narrative_anchor or "after-lead",
            "spec": {
                **spec,
                "figure_group_id": group_id,
            },
        },
    ]

    if figure_budget >= 3:
        figures.append({
            "type": "infographic",
            "title": f"Cách đọc {resolved_title}",
            "summary": bridge_claim[1] if len(bridge_claim) > 1 else resolved_summary,
            "pedagogical_role": bridge_role,
            "claim": bridge_claim[1] if len(bridge_claim) > 1 else resolved_summary,
            "narrative_anchor": "after-figure-1",
            "spec": _build_bridge_infographic_spec(
                visual_type,
                spec,
                resolved_title,
                resolved_summary,
            ),
        })

    figures.append({
        "type": "infographic",
        "title": f"Điểm chốt từ {resolved_title}",
        "summary": _build_takeaway_claim(visual_type, resolved_title, resolved_summary, spec),
        "pedagogical_role": secondary_role,
        "claim": _build_takeaway_claim(visual_type, resolved_title, resolved_summary, spec),
        "narrative_anchor": "after-figure-1" if figure_budget == 2 else "after-figure-2",
        "spec": _build_takeaway_infographic_spec(
            visual_type,
            spec,
            resolved_title,
            resolved_summary,
        ),
    })

    raw_group = {
        "figure_group_id": group_id,
        "type": visual_type,
        "title": resolved_title,
        "summary": resolved_summary,
        "subtitle": subtitle,
        "operation": operation,
        "renderer_kind": renderer_kind,
        "shell_variant": shell_variant,
        "patch_strategy": patch_strategy,
        "narrative_anchor": narrative_anchor,
        "runtime_manifest": runtime_manifest,
        "figures": figures,
    }
    return _build_multi_figure_payloads(
        default_visual_type=visual_type,
        raw_group=raw_group,
    )


def _log_visual_telemetry(event_name: str, **fields: Any) -> None:
    """Structured logger hook for visual pipeline telemetry."""
    if fields:
        logger.info("[VISUAL_TELEMETRY] %s %s", event_name, json.dumps(fields, ensure_ascii=False, sort_keys=True))
    else:
        logger.info("[VISUAL_TELEMETRY] %s", event_name)


def _slugify_fragment(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
    cleaned = cleaned.strip("-")
    return cleaned or "item"


def _generate_visual_session_id(visual_type: str) -> str:
    return f"vs-{_slugify_fragment(visual_type)}-{uuid.uuid4().hex[:10]}"


def _build_scene(visual_type: str, spec: dict[str, Any], title: str) -> dict[str, Any]:
    provided_scene = spec.get("scene")
    if isinstance(provided_scene, dict):
        return provided_scene

    if visual_type == "comparison":
        left = spec.get("left", {}) if isinstance(spec.get("left"), dict) else {}
        right = spec.get("right", {}) if isinstance(spec.get("right"), dict) else {}
        return {
            "kind": "comparison",
            "nodes": [
                {"id": "left", "label": str(left.get("title") or "Left"), "kind": "column"},
                {"id": "right", "label": str(right.get("title") or "Right"), "kind": "column"},
            ],
            "panels": [
                {
                    "id": "summary",
                    "title": title or _default_visual_title(visual_type),
                    "body": str(spec.get("note") or ""),
                    "node_ids": ["left", "right"],
                }
            ],
        }

    if visual_type == "process":
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        nodes = []
        links = []
        for index, step in enumerate(steps):
            item = step if isinstance(step, dict) else {}
            node_id = f"step-{index + 1}"
            nodes.append({
                "id": node_id,
                "label": str(item.get("title") or f"Step {index + 1}"),
                "kind": "step",
            })
            if index > 0:
                links.append({"source": f"step-{index}", "target": node_id})
        return {
            "kind": "process",
            "nodes": nodes,
            "links": links,
        }

    if visual_type == "matrix":
        rows = spec.get("rows", []) if isinstance(spec.get("rows"), list) else []
        cols = spec.get("cols", []) if isinstance(spec.get("cols"), list) else []
        nodes = [{"id": f"row-{i}", "label": str(row), "kind": "row"} for i, row in enumerate(rows)]
        nodes.extend({"id": f"col-{i}", "label": str(col), "kind": "column"} for i, col in enumerate(cols))
        return {
            "kind": "matrix",
            "nodes": nodes,
            "metadata": {
                "row_count": len(rows),
                "column_count": len(cols),
            },
        }

    if visual_type == "architecture":
        layers = spec.get("layers", []) if isinstance(spec.get("layers"), list) else []
        nodes = []
        links = []
        for index, layer in enumerate(layers):
            item = layer if isinstance(layer, dict) else {}
            node_id = f"layer-{index + 1}"
            nodes.append({
                "id": node_id,
                "label": str(item.get("name") or f"Layer {index + 1}"),
                "kind": "layer",
            })
            if index > 0:
                links.append({"source": f"layer-{index}", "target": node_id})
        return {
            "kind": "architecture",
            "nodes": nodes,
            "links": links,
        }

    if visual_type == "concept":
        center = spec.get("center", {}) if isinstance(spec.get("center"), dict) else {}
        branches = spec.get("branches", []) if isinstance(spec.get("branches"), list) else []
        nodes = [{"id": "center", "label": str(center.get("title") or title or "Core concept"), "kind": "center"}]
        links = []
        for index, branch in enumerate(branches):
            item = branch if isinstance(branch, dict) else {}
            node_id = f"branch-{index + 1}"
            nodes.append({
                "id": node_id,
                "label": str(item.get("title") or f"Branch {index + 1}"),
                "kind": "branch",
            })
            links.append({"source": "center", "target": node_id})
        return {
            "kind": "concept",
            "nodes": nodes,
            "links": links,
        }

    if visual_type == "infographic":
        stats = spec.get("stats", []) if isinstance(spec.get("stats"), list) else []
        sections = spec.get("sections", []) if isinstance(spec.get("sections"), list) else []
        nodes = []
        for index, stat in enumerate(stats):
            item = stat if isinstance(stat, dict) else {}
            nodes.append({
                "id": f"stat-{index + 1}",
                "label": str(item.get("label") or f"Stat {index + 1}"),
                "kind": "stat",
            })
        for index, section in enumerate(sections):
            item = section if isinstance(section, dict) else {}
            nodes.append({
                "id": f"section-{index + 1}",
                "label": str(item.get("title") or f"Section {index + 1}"),
                "kind": "section",
            })
        return {
            "kind": "infographic",
            "nodes": nodes,
        }

    if visual_type == "chart":
        labels = spec.get("labels", []) if isinstance(spec.get("labels"), list) else []
        return {
            "kind": "chart",
            "nodes": [
                {"id": f"point-{index + 1}", "label": str(label), "kind": "point"}
                for index, label in enumerate(labels)
            ],
            "scales": {
                "x": {"kind": "categorical", "domain": labels},
            },
        }

    if visual_type == "timeline":
        events = spec.get("events", []) if isinstance(spec.get("events"), list) else []
        nodes = []
        links = []
        for index, event in enumerate(events):
            item = event if isinstance(event, dict) else {}
            node_id = f"milestone-{index + 1}"
            nodes.append({
                "id": node_id,
                "label": str(item.get("title") or item.get("label") or f"Milestone {index + 1}"),
                "kind": "milestone",
            })
            if index > 0:
                links.append({"source": f"milestone-{index}", "target": node_id})
        return {
            "kind": "timeline",
            "nodes": nodes,
            "links": links,
        }

    if visual_type == "map_lite":
        regions = spec.get("regions", []) if isinstance(spec.get("regions"), list) else []
        return {
            "kind": "map_lite",
            "nodes": [
                {
                    "id": f"region-{index + 1}",
                    "label": str((region if isinstance(region, dict) else {}).get("label") or f"Region {index + 1}"),
                    "kind": "region",
                }
                for index, region in enumerate(regions)
            ],
        }

    return {"kind": visual_type}


def _build_controls(visual_type: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    provided_controls = spec.get("controls")
    if isinstance(provided_controls, list):
        return [item for item in provided_controls if isinstance(item, dict)]

    if visual_type == "comparison":
        left = spec.get("left", {}) if isinstance(spec.get("left"), dict) else {}
        right = spec.get("right", {}) if isinstance(spec.get("right"), dict) else {}
        return [{
            "id": "focus_side",
            "type": "chips",
            "label": "Focus",
            "value": "both",
            "options": [
                {"value": "both", "label": "Both"},
                {"value": "left", "label": str(left.get("title") or "Left")},
                {"value": "right", "label": str(right.get("title") or "Right")},
            ],
        }]

    if visual_type == "process":
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        if len(steps) > 1:
            return [{
                "id": "current_step",
                "type": "range",
                "label": "Current step",
                "value": 1,
                "min": 1,
                "max": len(steps),
                "step": 1,
            }]
        return []

    if visual_type == "matrix":
        return [{
            "id": "show_values",
            "type": "toggle",
            "label": "Show values",
            "value": bool(spec.get("show_values")),
        }]

    if visual_type == "architecture":
        layers = spec.get("layers", []) if isinstance(spec.get("layers"), list) else []
        if layers:
            return [{
                "id": "active_layer",
                "type": "chips",
                "label": "Layer focus",
                "value": "all",
                "options": [{"value": "all", "label": "All"}] + [
                    {
                        "value": f"layer-{index + 1}",
                        "label": str((layer if isinstance(layer, dict) else {}).get("name") or f"Layer {index + 1}"),
                    }
                    for index, layer in enumerate(layers)
                ],
            }]
        return []

    if visual_type == "concept":
        branches = spec.get("branches", []) if isinstance(spec.get("branches"), list) else []
        if branches:
            return [{
                "id": "active_branch",
                "type": "chips",
                "label": "Branch focus",
                "value": "all",
                "options": [{"value": "all", "label": "All"}] + [
                    {
                        "value": f"branch-{index + 1}",
                        "label": str((branch if isinstance(branch, dict) else {}).get("title") or f"Branch {index + 1}"),
                    }
                    for index, branch in enumerate(branches)
                ],
            }]
        return []

    if visual_type == "infographic":
        sections = spec.get("sections", []) if isinstance(spec.get("sections"), list) else []
        if sections:
            return [{
                "id": "active_section",
                "type": "chips",
                "label": "Section focus",
                "value": "all",
                "options": [{"value": "all", "label": "All"}] + [
                    {
                        "value": f"section-{index + 1}",
                        "label": str((section if isinstance(section, dict) else {}).get("title") or f"Section {index + 1}"),
                    }
                    for index, section in enumerate(sections)
                ],
            }]
        return []

    if visual_type == "chart":
        return [{
            "id": "chart_style",
            "type": "chips",
            "label": "Chart style",
            "value": str(spec.get("chart_type") or "bar"),
            "options": [
                {"value": "bar", "label": "Bar"},
                {"value": "line", "label": "Line"},
                {"value": "area", "label": "Area"},
            ],
        }]

    if visual_type == "timeline":
        events = spec.get("events", []) if isinstance(spec.get("events"), list) else []
        if len(events) > 1:
            return [{
                "id": "current_event",
                "type": "range",
                "label": "Current milestone",
                "value": 1,
                "min": 1,
                "max": len(events),
                "step": 1,
            }]
        return []

    if visual_type == "map_lite":
        regions = spec.get("regions", []) if isinstance(spec.get("regions"), list) else []
        if regions:
            return [{
                "id": "active_region",
                "type": "chips",
                "label": "Region focus",
                "value": "all",
                "options": [{"value": "all", "label": "All"}] + [
                    {
                        "value": f"region-{index + 1}",
                        "label": str((region if isinstance(region, dict) else {}).get("label") or f"Region {index + 1}"),
                    }
                    for index, region in enumerate(regions)
                ],
            }]
        return []

    return []


def _build_annotations(visual_type: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    provided_annotations = spec.get("annotations")
    if isinstance(provided_annotations, list):
        for index, annotation in enumerate(provided_annotations):
            if not isinstance(annotation, dict):
                continue
            annotations.append({
                "id": str(annotation.get("id") or f"annotation-{index + 1}"),
                "title": str(annotation.get("title") or annotation.get("label") or f"Annotation {index + 1}"),
                "body": str(annotation.get("body") or annotation.get("content") or ""),
                "target_id": annotation.get("target_id"),
                "tone": annotation.get("tone") or "accent",
            })

    if not annotations:
        note = spec.get("note")
        caption = spec.get("caption")
        emphasis = spec.get("takeaway")
        fallback_body = note or caption or emphasis
        if fallback_body:
            annotations.append({
                "id": "summary-note",
                "title": "Takeaway",
                "body": str(fallback_body),
                "tone": "accent" if visual_type != "matrix" else "neutral",
            })

    return annotations


def _infer_interaction_mode(controls: list[dict[str, Any]]) -> str:
    if not controls:
        return "static"
    control_types = {str(control.get("type")) for control in controls}
    if "range" in control_types:
        return "scrubbable"
    if control_types & {"chips", "select", "toggle"}:
        return "filterable"
    return "guided"


def _infer_renderer_kind(visual_type: str, spec: dict[str, Any], requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"template", "inline_html", "app"}:
        return candidate
    if any(isinstance(spec.get(key), str) and str(spec.get(key)).strip() for key in ("html", "markup", "custom_html", "template_html")):
        return "inline_html"
    if _runtime_presentation_intent() in {"article_figure", "chart_runtime"}:
        return "inline_html" if _llm_first_visual_codegen_enabled() else "template"

    # Code-gen route: explanatory types with HTML builders → inline_html iframe
    from app.core.config import get_settings
    if getattr(get_settings(), "enable_code_gen_visuals", False):
        if visual_type in _BUILDERS:
            return "inline_html"

    return "template"


def _infer_runtime(renderer_kind: str, visual_type: str, spec: dict[str, Any]) -> str:
    if renderer_kind == "recharts":
        return "svg"
    if renderer_kind == "template":
        return "svg"
    if renderer_kind == "app":
        ui_runtime = str(spec.get("ui_runtime") or "")
        return "sandbox_react" if visual_type == "react_app" or ui_runtime == "react" else "sandbox_html"
    return "sandbox_html"


def _resolve_renderer_kind(visual_type: str, spec: dict[str, Any], requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"template", "inline_html", "app", "recharts"}:
        return candidate
    if _should_keep_structured_renderer(candidate):
        return "template"
    if any(
        isinstance(spec.get(key), str) and str(spec.get(key)).strip()
        for key in ("html", "markup", "custom_html", "template_html")
    ):
        return "inline_html"
    if _runtime_presentation_intent() in {"article_figure", "chart_runtime"}:
        return "inline_html" if _llm_first_visual_codegen_enabled() else "template"
    return "template"


_infer_renderer_kind = _resolve_renderer_kind


def _infer_shell_variant(renderer_kind: str, requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"editorial", "compact", "immersive"}:
        return candidate
    return "immersive" if renderer_kind == "app" else "editorial"


def _infer_patch_strategy(renderer_kind: str, requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"spec_merge", "replace_html", "app_state"}:
        return candidate
    if renderer_kind == "template":
        return "spec_merge"
    if renderer_kind == "app":
        return "app_state"
    return "replace_html"


def _resolve_code_html(
    code_html: str,
    visual_type: str,
    title: str,
    spec: dict[str, Any],
) -> str | None:
    """Validate and wrap LLM-provided code_html into a full HTML document.

    Returns wrapped HTML if code_html is valid and feature is enabled, None otherwise.
    The LLM provides HTML/CSS/SVG body content; we wrap it in the design system shell
    so it gets the same CSS variables, dark mode, and font stack as builder visuals.
    """
    raw = code_html.strip() if isinstance(code_html, str) else ""
    if not raw:
        return None

    from app.core.config import get_settings
    if not getattr(get_settings(), "enable_llm_code_gen_visuals", False):
        logger.info("code_html provided but enable_llm_code_gen_visuals=False, ignoring")
        return None

    # If LLM already provided a full HTML document, use as-is
    if raw.lstrip().lower().startswith("<!doctype") or raw.lstrip().lower().startswith("<html"):
        return raw

    # Otherwise, extract CSS and body parts and wrap in design system
    css_parts = []
    body_content = raw

    # Extract <style> blocks from the raw content
    style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
    for match in style_pattern.finditer(raw):
        css_parts.append(match.group(1))
    body_content = style_pattern.sub('', body_content).strip()

    return _wrap_html("\n".join(css_parts), body_content, title)


def _validate_code_studio_output(
    raw_html: str,
    *,
    requested_visual_type: str,
    studio_lane: str,
    artifact_kind: str,
    quality_profile: str,
) -> str | None:
    lowered = raw_html.lower()

    chart_like = requested_visual_type == "chart" or artifact_kind == "chart_widget"
    uses_chart_runtime = any(
        token in lowered
        for token in (
            "<svg",
            "<canvas",
            "chart.js",
            "new chart(",
            "plotly",
            "echarts",
            "apexcharts",
            "vega",
            "recharts",
            "d3.",
            "viewbox",
        )
    )
    looks_like_handmade_div_chart = (
        "chart-container" in lowered
        and ("bar-group" in lowered or "bar-wrapper" in lowered or 'class=\"bar\"' in lowered or "class='bar'" in lowered)
    )

    if chart_like and looks_like_handmade_div_chart and not uses_chart_runtime:
        return (
            "Error: chart/data visual nay dang di vao Code Studio theo kieu demo thu cong "
            "(div bars / CSS-only chart). Hay route qua chart_runtime/tool_generate_visual, "
            "hoac neu that su can code widget thi dung SVG/Canvas/Chart.js voi axis, legend, "
            "units, source, va takeaway ro rang."
        )

    if requested_visual_type == "simulation" and quality_profile == "premium":
        preferred_surface = _runtime_preferred_render_surface() or "canvas"
        has_canvas_surface = any(
            token in lowered
            for token in (
                "<canvas",
                "getcontext(",
            )
        )
        has_render_surface = any(
            token in lowered
            for token in (
                "<canvas",
                "<svg",
                "getcontext(",
                "viewbox",
                "id=\"sim\"",
                "id='sim'",
                "simulation-stage",
                "sim-stage",
            )
        )
        parameter_control_count = sum(
            lowered.count(token)
            for token in (
                'type="range"',
                "type='range'",
                'type="number"',
                "type='number'",
                "<select",
            )
        )
        has_live_readout = any(
            token in lowered
            for token in (
                "innertext",
                "textcontent",
                "aria-live",
                "readout",
                "telemetry",
                "velocity",
                "angle",
                "omega",
                "theta",
                "acceleration",
                "thoi gian",
                "goc lech",
                "van toc",
                "trang thai",
                "status",
            )
        )
        has_state_engine = any(
            token in lowered
            for token in (
                "requestanimationframe",
                "setinterval(",
                "performance.now",
                "deltatime",
                "delta_time",
                "time_step",
                "timestep",
                "velocity",
                "acceleration",
                "gravity",
                "friction",
                "omega",
                "theta",
            )
        )
        has_feedback_bridge = any(
            token in lowered
            for token in (
                "window.wiiivisualbridge.reportresult",
                "wiiivisualbridge.reportresult",
                "reportresult(",
            )
        )
        button_count = lowered.count("<button")

        if preferred_surface == "canvas" and not has_canvas_surface:
            return (
                "Error: premium simulation nay dang chua dung Canvas-first runtime. "
                "Hay dung canvas + render loop + state model ro rang, hoac de runtime "
                "nang cap sang scaffold canvas phu hop truoc khi preview."
            )

        if (
            not has_render_surface
            or parameter_control_count < 1
            or not has_live_readout
            or not has_state_engine
            or not has_feedback_bridge
        ):
            if button_count <= 2 and parameter_control_count == 0 and not has_render_surface:
                return (
                    "Error: premium simulation nay van qua giong demo minh hoa (vai div + nut bam) "
                    "va chua dat bar cua Code Studio. Hay nang cap thanh mot mo phong that su: "
                    "co render surface ro rang (canvas/svg), it nhat mot dieu khien tham so "
                    "(slider/number/select), readout song (goc/van toc/trang thai), va state/time "
                    "engine ro rang truoc khi preview."
                )
            if not has_feedback_bridge:
                return (
                    "Error: premium simulation can feedback bridge de Wiii biet nguoi dung "
                    "da tuong tac gi. Hay goi window.WiiiVisualBridge.reportResult(...) "
                    "cho cac hanh dong chinh hoac de runtime nang cap sang scaffold phu hop."
                )
            return (
                "Error: premium simulation can runtime giau hon truoc khi preview. "
                "Hay bo sung render surface ro rang, parameter controls, readout song, "
                "va state/time engine thay vi mot canh minh hoa script qua don gian."
            )

    if studio_lane == "widget":
        has_interaction = any(
            token in lowered
            for token in ("<button", "<input", "<select", "onclick=", "addeventlistener", "type=\"range\"", "type='range'")
        )
        if has_interaction and "reportresult" not in lowered:
            return (
                "Error: widget lane yeu cau feedback bridge. Hay goi "
                "window.WiiiVisualBridge.reportResult(...) khi user tuong tac xong "
                "de Wiii co the nho va phan hoi o luot sau."
            )

    return None


def _postprocess_visual_html(raw: str) -> str:
    """Auto-enhance LLM output with quality markers Gemini consistently misses.

    This compensates for Gemini's weak instruction compliance by injecting:
    - CSS variables + dark mode if missing
    - Responsive meta viewport if missing
    - Planning block comment if missing
    Idempotent: safe to run on already-compliant output.
    """
    import re as _pp_re

    # 1. Inject CSS variables + dark mode if missing
    if "--bg" not in raw and "--accent" not in raw and "<style" in raw.lower():
        _css_vars = (
            ":root {\n"
            "  --bg: #0f172a; --fg: #e2e8f0; --accent: #38bdf8;\n"
            "  --surface: #1e293b; --border: #475569; --text-secondary: #94a3b8;\n"
            "}\n"
            "@media (prefers-color-scheme: light) {\n"
            "  :root { --bg: #f8fafc; --fg: #0f172a; --accent: #0284c7; "
            "--surface: #fff; --border: #cbd5e1; --text-secondary: #64748b; }\n"
            "}\n"
        )
        # Inject after first <style> opening tag
        raw = _pp_re.sub(
            r'(<style[^>]*>)',
            r'\1\n' + _css_vars,
            raw,
            count=1,
        )
        # Replace common hardcoded dark backgrounds with CSS var
        raw = raw.replace("background: #050505", "background: var(--bg)")
        raw = raw.replace("background: #000", "background: var(--bg)")
        raw = raw.replace("background: #1a1a1a", "background: var(--bg)")
        raw = raw.replace("background: black", "background: var(--bg)")
        raw = raw.replace("color: white", "color: var(--fg)")
        raw = raw.replace("color: #fff", "color: var(--fg)")
        raw = raw.replace("color: #ffffff", "color: var(--fg)")

    # 2. Inject planning block if missing
    if "STATE MODEL" not in raw and "RENDER SURFACE" not in raw:
        _has_canvas = "<canvas" in raw.lower()
        _has_svg = "<svg" in raw.lower()
        _surface = "Canvas 2D" if _has_canvas else "SVG" if _has_svg else "HTML"
        _planning = (
            f"<!--\n"
            f"  STATE MODEL: [auto-detected]\n"
            f"  RENDER SURFACE: {_surface}\n"
            f"  CONTROLS: [see interactive elements below]\n"
            f"  READOUTS: [see output displays below]\n"
            f"  FEEDBACK: WiiiVisualBridge.reportResult\n"
            f"-->\n"
        )
        raw = _planning + raw

    return raw


def _quality_score_visual_output(raw_html: str, visual_type: str = "") -> tuple[int, list[str]]:
    """Score visual output 0-10 and return list of specific deficiency messages."""
    score = 0
    deficiencies: list[str] = []
    html_lower = raw_html.lower()

    # 1. CSS variables
    if "--bg" in raw_html and "--accent" in raw_html:
        score += 1
    else:
        deficiencies.append("Thieu CSS variables. Them :root { --bg: #0f172a; --fg: #e2e8f0; --accent: #38bdf8; --surface: #1e293b; --border: #475569; }")

    # 2. Dark/light mode
    if "prefers-color-scheme" in raw_html:
        score += 1
    else:
        deficiencies.append("Thieu dark/light mode. Them @media (prefers-color-scheme: light) { :root { --bg: #f8fafc; --fg: #0f172a; } }")

    # 3. Appropriate render surface
    is_simulation = visual_type in ("simulation", "physics", "animation")
    has_canvas = "<canvas" in html_lower
    has_svg = "<svg" in html_lower
    if is_simulation and has_canvas:
        score += 1
    elif not is_simulation and (has_canvas or has_svg or "<div" in html_lower):
        score += 1
    else:
        surface = "Canvas voi getContext('2d')" if is_simulation else "SVG hoac HTML"
        deficiencies.append(f"Thieu render surface phu hop. Simulation can {surface}.")

    # 4. Interactive controls
    range_count = html_lower.count('type="range"') + html_lower.count("type='range'")
    button_count = html_lower.count("<button")
    input_count = html_lower.count("<input")
    if range_count >= 2 or (range_count >= 1 and button_count >= 1) or input_count >= 2:
        score += 1
    else:
        deficiencies.append("Thieu controls tuong tac. Them it nhat 2 slider (type='range') hoac buttons de user dieu chinh tham so.")

    # 5. Live readouts
    has_readout = "readout" in html_lower or "aria-live" in raw_html or html_lower.count("<span id=") >= 2
    if has_readout:
        score += 1
    else:
        deficiencies.append("Thieu readouts song. Them cac phan tu hien thi gia tri tinh toan real-time (dung <span> voi aria-live='polite').")

    # 6. Animation/state engine (for simulations)
    has_raf = "requestanimationframe" in html_lower
    has_delta = "deltatime" in html_lower or "dt " in raw_html or "delta" in html_lower
    if is_simulation:
        if has_raf and has_delta:
            score += 1
        elif has_raf:
            score += 1  # Still good, just missing deltaTime
            if not has_delta:
                deficiencies.append("Them deltaTime cho physics frame-rate-independent: const dt = Math.min((now - lastTime) / 1000, 0.1);")
        else:
            deficiencies.append("Thieu animation loop. Dung requestAnimationFrame voi deltaTime cho simulation muot 60fps.")
    else:
        score += 1  # Non-simulation doesn't need rAF

    # 7. Feedback bridge
    if "wiiiVisualBridge" in html_lower or "wiiivisualbridge" in html_lower:
        score += 1
    else:
        deficiencies.append("Thieu WiiiVisualBridge. Them: function report(k,p,s,st){window.WiiiVisualBridge?.reportResult?.(k,p,s,st);}")

    # 8. Code depth
    line_count = raw_html.count("\n") + 1
    min_lines = 150 if is_simulation else 80
    if line_count >= min_lines:
        score += 1
    else:
        deficiencies.append(f"Code qua ngan ({line_count} dong). Simulation chat luong thuong co {min_lines}+ dong voi physics engine, controls, readouts day du.")

    # 9. No placeholder/demo markers
    has_placeholder = any(marker in html_lower for marker in ["todo", "lorem ipsum", "placeholder", "// ...", "/* ... */"])
    if not has_placeholder:
        score += 1
    else:
        deficiencies.append("Code chua hoan chinh — con chua TODO/placeholder. Viet day du, khong de trong.")

    # 10. Responsive layout
    has_responsive = "grid" in html_lower or ("flex" in html_lower and ("@media" in raw_html or "max-width" in html_lower))
    if has_responsive:
        score += 1
    else:
        deficiencies.append("Thieu responsive layout. Dung CSS Grid hoac Flexbox voi @media (max-width: 768px) de ho tro man hinh nho.")

    return score, deficiencies


def _looks_like_pendulum_simulation(raw_html: str, title: str, query: str) -> bool:
    haystack = " ".join(part for part in (raw_html, title, query) if part).lower()
    return any(
        token in haystack
        for token in (
            "pendulum",
            "con lac",
            "con lắc",
            "theta",
            "omega",
            "gravity",
            "damping",
            "dao dong",
            "dao động",
        )
    )


def _build_pendulum_simulation_scaffold(title: str, subtitle: str = "", query: str = "") -> str:
    return _build_pendulum_simulation_scaffold_v2(title, subtitle, query)
    safe_title = html_mod.escape(title.strip() or "Mini Pendulum Physics App")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Kéo quả nặng để đổi góc lệch, rồi quan sát chuyển động theo trọng lực và damping."
    )
    normalized_query = " ".join(part for part in (title, subtitle, query) if part).lower()
    wants_gravity = any(token in normalized_query for token in ("gravity", "trong luc", "trá»ng lá»±c"))
    wants_damping = any(token in normalized_query for token in ("damping", "ma sat", "ma sÃ¡t", "friction"))
    control_blocks: list[str] = []
    if wants_gravity:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Gravity</strong><span id="gravity-value">9.81 m/sÂ²</span></header>
        <input id="gravity-slider" type="range" min="1" max="20" step="0.1" value="9.81" aria-label="Gravity" />
      </div>
""".strip("\n")
        )
    if wants_damping:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Damping</strong><span id="damping-value">0.020</span></header>
        <input id="damping-slider" type="range" min="0" max="0.12" step="0.002" value="0.02" aria-label="Damping" />
      </div>
""".strip("\n")
        )
    control_blocks.append(
        """
      <div class="pendulum-control">
        <header><strong>Length</strong><span id="length-value">1.20 m</span></header>
        <input id="length-slider" type="range" min="0.6" max="2.2" step="0.05" value="1.2" aria-label="Length" />
      </div>
""".strip("\n")
    )
    controls_markup = "\n".join(control_blocks)
    return f"""
<style>
  .pendulum-lab {{
    display: grid;
    gap: 14px;
    grid-template-columns: minmax(0, 1.55fr) minmax(240px, 0.95fr);
    align-items: stretch;
  }}
  .pendulum-stage {{
    position: relative;
    min-height: 360px;
    border-radius: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background:
      radial-gradient(circle at top, rgba(37,99,235,0.10), transparent 42%),
      linear-gradient(180deg, color-mix(in srgb, var(--bg2) 92%, white) 0%, color-mix(in srgb, var(--bg) 90%, white) 100%);
    overflow: hidden;
  }}
  .pendulum-canvas {{
    width: 100%;
    height: 100%;
    display: block;
    touch-action: none;
    cursor: grab;
  }}
  .pendulum-canvas.is-dragging {{
    cursor: grabbing;
  }}
  .pendulum-overlay {{
    position: absolute;
    inset: 12px 12px auto;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    pointer-events: none;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-chip {{
    background: color-mix(in srgb, var(--bg) 82%, white);
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    border-radius: 999px;
    padding: 6px 10px;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  }}
  .pendulum-panel {{
    display: grid;
    gap: 12px;
    align-content: start;
  }}
  .pendulum-card {{
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--border) 74%, transparent);
    background: color-mix(in srgb, var(--bg) 95%, white);
    padding: 14px;
  }}
  .pendulum-card h3 {{
    margin: 0 0 6px;
    font-family: var(--wiii-serif, "Georgia", serif);
    font-size: 17px;
    color: var(--text);
  }}
  .pendulum-card p {{
    margin: 0;
    color: var(--text2);
    font-size: 13px;
    line-height: 1.55;
  }}
  .pendulum-controls {{
    display: grid;
    gap: 12px;
  }}
  .pendulum-control {{
    display: grid;
    gap: 6px;
  }}
  .pendulum-control header {{
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: baseline;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-control strong {{
    color: var(--text);
    font-size: 13px;
  }}
  .pendulum-readouts {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }}
  .pendulum-readout {{
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg2) 80%, white);
    border: 1px solid color-mix(in srgb, var(--border) 66%, transparent);
    padding: 10px 12px;
  }}
  .pendulum-readout label {{
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text3);
    margin-bottom: 6px;
  }}
  .pendulum-readout strong {{
    font-size: 18px;
    color: var(--text);
  }}
  .pendulum-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .pendulum-actions button {{
    min-width: 108px;
  }}
  .pendulum-note {{
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-live {{
    min-height: 18px;
  }}
  @media (max-width: 720px) {{
    .pendulum-lab {{
      grid-template-columns: 1fr;
    }}
    .pendulum-stage {{
      min-height: 320px;
    }}
  }}
</style>

<div class="pendulum-lab" data-sim-kind="pendulum">
  <section class="pendulum-stage" aria-label="{safe_title}">
    <canvas id="pendulum-sim" class="pendulum-canvas"></canvas>
    <div class="pendulum-overlay">
      <div class="pendulum-chip">Kéo quả nặng để đổi góc lệch</div>
      <div class="pendulum-chip">Canvas runtime + live telemetry</div>
    </div>
  </section>

  <aside class="pendulum-panel">
    <section class="pendulum-card">
      <h3>{safe_title}</h3>
      <p>{safe_subtitle}</p>
    </section>

    <section class="pendulum-card pendulum-controls" aria-label="Điều chỉnh tham số">
      <div class="pendulum-control">
        <header><strong>Gravity</strong><span id="gravity-value">9.81 m/s²</span></header>
        <input id="gravity-slider" type="range" min="1" max="20" step="0.1" value="9.81" aria-label="Gravity" />
      </div>
      <div class="pendulum-control">
        <header><strong>Damping</strong><span id="damping-value">0.020</span></header>
        <input id="damping-slider" type="range" min="0" max="0.12" step="0.002" value="0.02" aria-label="Damping" />
      </div>
      <div class="pendulum-control">
        <header><strong>Length</strong><span id="length-value">1.20 m</span></header>
        <input id="length-slider" type="range" min="0.6" max="2.2" step="0.05" value="1.2" aria-label="Length" />
      </div>
    </section>

    <section class="pendulum-card pendulum-readouts" aria-live="polite">
      <div class="pendulum-readout">
        <label>Góc lệch</label>
        <strong id="angle-readout">18.0°</strong>
      </div>
      <div class="pendulum-readout">
        <label>Vận tốc góc</label>
        <strong id="velocity-readout">0.00 rad/s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Chu kỳ xấp xỉ</label>
        <strong id="period-readout">2.20 s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Trạng thái</label>
        <strong id="status-readout">Đang chạy</strong>
      </div>
    </section>

    <section class="pendulum-card">
      <div class="pendulum-actions">
        <button type="button" id="play-toggle">Tạm dừng</button>
        <button type="button" id="reset-btn">Đặt lại</button>
      </div>
      <p class="pendulum-note pendulum-live" id="pendulum-live">Bạn có thể kéo trực tiếp quả nặng để đặt góc ban đầu mới.</p>
    </section>
  </aside>
</div>

<script>
  (function () {{
    const canvas = document.getElementById('pendulum-sim');
    const ctx = canvas.getContext('2d');
    const gravitySlider = document.getElementById('gravity-slider');
    const dampingSlider = document.getElementById('damping-slider');
    const lengthSlider = document.getElementById('length-slider');
    const playToggle = document.getElementById('play-toggle');
    const resetBtn = document.getElementById('reset-btn');
    const gravityValue = document.getElementById('gravity-value');
    const dampingValue = document.getElementById('damping-value');
    const lengthValue = document.getElementById('length-value');
    const angleReadout = document.getElementById('angle-readout');
    const velocityReadout = document.getElementById('velocity-readout');
    const periodReadout = document.getElementById('period-readout');
    const statusReadout = document.getElementById('status-readout');
    const live = document.getElementById('pendulum-live');

    const baseState = {{
      gravity: 9.81,
      damping: 0.02,
      length: 1.2,
      theta: Math.PI / 10,
      omega: 0,
      running: true,
      dragging: false,
    }};
    const state = Object.assign({{}}, baseState);

    let rafId = 0;
    let lastTime = performance.now();
    let pivot = {{ x: 0, y: 40 }};
    let bobRadius = 18;
    let pixelsPerMeter = 180;

    function report(kind, payload, summary, status) {{
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.reportResult === 'function') {{
        window.WiiiVisualBridge.reportResult(kind, payload, summary, status);
      }}
    }}

    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.max(1, window.devicePixelRatio || 1);
      canvas.width = Math.max(320, Math.floor(rect.width * ratio));
      canvas.height = Math.max(280, Math.floor(rect.height * ratio));
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(ratio, ratio);
      pivot = {{ x: rect.width / 2, y: 44 }};
      pixelsPerMeter = Math.max(110, rect.height * 0.52);
      draw();
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.resize === 'function') {{
        window.WiiiVisualBridge.resize();
      }}
    }}

    function pendulumMetrics() {{
      const angleDeg = state.theta * 180 / Math.PI;
      const approxPeriod = 2 * Math.PI * Math.sqrt(state.length / Math.max(state.gravity, 0.1));
      return {{ angleDeg, approxPeriod }};
    }}

    function syncReadouts() {{
      const metrics = pendulumMetrics();
      gravityValue.textContent = state.gravity.toFixed(2) + ' m/s²';
      dampingValue.textContent = state.damping.toFixed(3);
      lengthValue.textContent = state.length.toFixed(2) + ' m';
      angleReadout.textContent = metrics.angleDeg.toFixed(1) + '°';
      velocityReadout.textContent = state.omega.toFixed(2) + ' rad/s';
      periodReadout.textContent = metrics.approxPeriod.toFixed(2) + ' s';
      statusReadout.textContent = state.dragging ? 'Đang kéo' : (state.running ? 'Đang chạy' : 'Tạm dừng');
      live.textContent = state.dragging
        ? 'Thả chuột để xem con lắc tiếp tục dao động từ góc mới.'
        : (state.running
          ? 'Mô phỏng đang chạy với gravity, damping và chiều dài hiện tại.'
          : 'Mô phỏng đang tạm dừng. Bạn có thể kéo quả nặng hoặc tiếp tục chạy.');
    }}

    function bobPosition() {{
      const rect = canvas.getBoundingClientRect();
      const rodLength = state.length * pixelsPerMeter;
      return {{
        x: pivot.x + rodLength * Math.sin(state.theta),
        y: pivot.y + rodLength * Math.cos(state.theta),
        width: rect.width,
        height: rect.height,
        rodLength: rodLength,
      }};
    }}

    function drawGrid(width, height) {{
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
      ctx.lineWidth = 1;
      for (let x = 24; x < width; x += 32) {{
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }}
      for (let y = 24; y < height; y += 32) {{
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }}
      ctx.restore();
    }}

    function draw() {{
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);
      drawGrid(width, height);

      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.06)';
      ctx.fillRect(0, height - 38, width, 38);
      ctx.restore();

      const bob = bobPosition();

      ctx.save();
      ctx.strokeStyle = 'rgba(37, 99, 235, 0.85)';
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(pivot.x, pivot.y);
      ctx.lineTo(bob.x, bob.y);
      ctx.stroke();

      ctx.fillStyle = 'rgba(148, 163, 184, 0.42)';
      ctx.beginPath();
      ctx.arc(pivot.x, pivot.y, 8, 0, Math.PI * 2);
      ctx.fill();

      const bobGradient = ctx.createRadialGradient(bob.x - 8, bob.y - 10, 4, bob.x, bob.y, 22);
      bobGradient.addColorStop(0, '#93c5fd');
      bobGradient.addColorStop(0.45, '#2563eb');
      bobGradient.addColorStop(1, '#1e3a8a');
      ctx.fillStyle = bobGradient;
      ctx.beginPath();
      ctx.arc(bob.x, bob.y, bobRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(255,255,255,0.7)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(bob.x - 5, bob.y - 6, 6, Math.PI * 1.2, Math.PI * 1.9);
      ctx.stroke();
      ctx.restore();

      syncReadouts();
    }}

    function advance(dt) {{
      const acceleration = -(state.gravity / Math.max(state.length, 0.25)) * Math.sin(state.theta) - state.damping * state.omega;
      state.omega += acceleration * dt;
      state.theta += state.omega * dt;
    }}

    function loop(now) {{
      const dt = Math.min(0.032, Math.max(0.001, (now - lastTime) / 1000));
      lastTime = now;
      if (state.running && !state.dragging) {{
        advance(dt);
      }}
      draw();
      rafId = window.requestAnimationFrame(loop);
    }}

    function pointerToTheta(clientX, clientY) {{
      const rect = canvas.getBoundingClientRect();
      const dx = clientX - rect.left - pivot.x;
      const dy = clientY - rect.top - pivot.y;
      return Math.atan2(dx, Math.max(24, dy));
    }}

    function onPointerDown(event) {{
      const bob = bobPosition();
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const distance = Math.hypot(x - bob.x, y - bob.y);
      if (distance > bobRadius + 16) return;
      state.dragging = true;
      state.running = false;
      state.omega = 0;
      canvas.classList.add('is-dragging');
      canvas.setPointerCapture(event.pointerId);
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerMove(event) {{
      if (!state.dragging) return;
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerUp(event) {{
      if (!state.dragging) return;
      state.dragging = false;
      state.running = true;
      canvas.classList.remove('is-dragging');
      try {{
        canvas.releasePointerCapture(event.pointerId);
      }} catch (_error) {{}}
      const metrics = pendulumMetrics();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          angle_deg: Number(metrics.angleDeg.toFixed(1)),
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
          length_m: Number(state.length.toFixed(2)),
        }},
        'Nguoi dung vua tha con lac o goc ' + metrics.angleDeg.toFixed(1) + '°.',
        'completed'
      );
    }}

    gravitySlider.addEventListener('input', function () {{
      state.gravity = Number(gravitySlider.value);
      draw();
    }});
    dampingSlider.addEventListener('input', function () {{
      state.damping = Number(dampingSlider.value);
      draw();
    }});
    lengthSlider.addEventListener('input', function () {{
      state.length = Number(lengthSlider.value);
      draw();
    }});

    playToggle.addEventListener('click', function () {{
      state.running = !state.running;
      playToggle.textContent = state.running ? 'Tạm dừng' : 'Tiếp tục';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: state.running ? 'resume' : 'pause',
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
        }},
        state.running ? 'Nguoi dung tiep tuc mo phong con lac.' : 'Nguoi dung tam dung mo phong con lac.',
        state.running ? 'running' : 'paused'
      );
    }});

    resetBtn.addEventListener('click', function () {{
      Object.assign(state, baseState);
      gravitySlider.value = String(baseState.gravity);
      dampingSlider.value = String(baseState.damping);
      lengthSlider.value = String(baseState.length);
      playToggle.textContent = 'Tạm dừng';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: 'reset',
          angle_deg: 18,
        }},
        'Nguoi dung da dat lai mo phong con lac ve trang thai mac dinh.',
        'reset'
      );
    }});

    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    window.addEventListener('resize', resizeCanvas);

    resizeCanvas();
    draw();
    rafId = window.requestAnimationFrame(loop);

    window.addEventListener('beforeunload', function () {{
      if (rafId) window.cancelAnimationFrame(rafId);
    }});
  }})();
</script>
""".strip()


def _build_pendulum_simulation_scaffold_v2(title: str, subtitle: str = "", query: str = "") -> str:
    safe_title = html_mod.escape(title.strip() or "Mini Pendulum Physics App")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Keo qua nang de doi goc lech, roi quan sat chuyen dong cua con lac."
    )
    normalized_query = " ".join(part for part in (title, subtitle, query) if part).lower()
    wants_gravity = any(token in normalized_query for token in ("gravity", "trong luc", "trong-luc"))
    wants_damping = any(token in normalized_query for token in ("damping", "ma sat", "ma-sat", "friction"))

    control_blocks: list[str] = []
    if wants_gravity:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Gravity</strong><span id="gravity-value">9.81 m/s^2</span></header>
        <input id="gravity-slider" type="range" min="1" max="20" step="0.1" value="9.81" aria-label="Gravity" />
      </div>
""".strip("\n")
        )
    if wants_damping:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Damping</strong><span id="damping-value">0.020</span></header>
        <input id="damping-slider" type="range" min="0" max="0.12" step="0.002" value="0.02" aria-label="Damping" />
      </div>
""".strip("\n")
        )
    control_blocks.append(
        """
      <div class="pendulum-control">
        <header><strong>Length</strong><span id="length-value">1.20 m</span></header>
        <input id="length-slider" type="range" min="0.6" max="2.2" step="0.05" value="1.2" aria-label="Length" />
      </div>
""".strip("\n")
    )
    controls_markup = "\n".join(control_blocks)

    live_running = "Mo phong dang chay voi cac tham so hien tai."
    if wants_gravity and wants_damping:
        live_running = "Mo phong dang chay voi gravity, damping va chieu dai hien tai."
    elif wants_gravity:
        live_running = "Mo phong dang chay voi gravity va chieu dai hien tai."
    elif wants_damping:
        live_running = "Mo phong dang chay voi damping va chieu dai hien tai."

    return f"""
<style>
  .pendulum-lab {{
    display: grid;
    gap: 14px;
    grid-template-columns: minmax(0, 1.55fr) minmax(240px, 0.95fr);
    align-items: stretch;
  }}
  .pendulum-stage {{
    position: relative;
    min-height: 360px;
    border-radius: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background:
      radial-gradient(circle at top, rgba(37,99,235,0.10), transparent 42%),
      linear-gradient(180deg, color-mix(in srgb, var(--bg2) 92%, white) 0%, color-mix(in srgb, var(--bg) 90%, white) 100%);
    overflow: hidden;
  }}
  .pendulum-canvas {{
    width: 100%;
    height: 100%;
    display: block;
    touch-action: none;
    cursor: grab;
  }}
  .pendulum-canvas.is-dragging {{
    cursor: grabbing;
  }}
  .pendulum-overlay {{
    position: absolute;
    inset: 12px 12px auto;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    pointer-events: none;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-chip {{
    background: color-mix(in srgb, var(--bg) 82%, white);
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    border-radius: 999px;
    padding: 6px 10px;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  }}
  .pendulum-panel {{
    display: grid;
    gap: 12px;
    align-content: start;
  }}
  .pendulum-card {{
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--border) 74%, transparent);
    background: color-mix(in srgb, var(--bg) 95%, white);
    padding: 14px;
  }}
  .pendulum-card h3 {{
    margin: 0 0 6px;
    font-family: var(--wiii-serif, "Georgia", serif);
    font-size: 17px;
    color: var(--text);
  }}
  .pendulum-card p {{
    margin: 0;
    color: var(--text2);
    font-size: 13px;
    line-height: 1.55;
  }}
  .pendulum-controls {{
    display: grid;
    gap: 12px;
  }}
  .pendulum-control {{
    display: grid;
    gap: 6px;
  }}
  .pendulum-control header {{
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: baseline;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-control strong {{
    color: var(--text);
    font-size: 13px;
  }}
  .pendulum-readouts {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }}
  .pendulum-readout {{
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg2) 80%, white);
    border: 1px solid color-mix(in srgb, var(--border) 66%, transparent);
    padding: 10px 12px;
  }}
  .pendulum-readout label {{
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text3);
    margin-bottom: 6px;
  }}
  .pendulum-readout strong {{
    font-size: 18px;
    color: var(--text);
  }}
  .pendulum-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .pendulum-actions button {{
    min-width: 108px;
  }}
  .pendulum-note {{
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-live {{
    min-height: 18px;
  }}
  @media (max-width: 720px) {{
    .pendulum-lab {{
      grid-template-columns: 1fr;
    }}
    .pendulum-stage {{
      min-height: 320px;
    }}
  }}
</style>

<div class="pendulum-lab" data-sim-kind="pendulum">
  <section class="pendulum-stage" aria-label="{safe_title}">
    <canvas id="pendulum-sim" class="pendulum-canvas"></canvas>
    <div class="pendulum-overlay">
      <div class="pendulum-chip">Keo qua nang de doi goc lech</div>
      <div class="pendulum-chip">Canvas runtime + live telemetry</div>
    </div>
  </section>

  <aside class="pendulum-panel">
    <section class="pendulum-card">
      <h3>{safe_title}</h3>
      <p>{safe_subtitle}</p>
    </section>

    <section class="pendulum-card pendulum-controls" aria-label="Dieu chinh tham so">
{controls_markup}
    </section>

    <section class="pendulum-card pendulum-readouts" aria-live="polite">
      <div class="pendulum-readout">
        <label>Goc lech</label>
        <strong id="angle-readout">18.0 deg</strong>
      </div>
      <div class="pendulum-readout">
        <label>Van toc goc</label>
        <strong id="velocity-readout">0.00 rad/s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Chu ky xap xi</label>
        <strong id="period-readout">2.20 s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Trang thai</label>
        <strong id="status-readout">Dang chay</strong>
      </div>
    </section>

    <section class="pendulum-card">
      <div class="pendulum-actions">
        <button type="button" id="play-toggle">Tam dung</button>
        <button type="button" id="reset-btn">Dat lai</button>
      </div>
      <p class="pendulum-note pendulum-live" id="pendulum-live">Ban co the keo truc tiep qua nang de dat goc ban dau moi.</p>
    </section>
  </aside>
</div>

<script>
  (function () {{
    const canvas = document.getElementById('pendulum-sim');
    const ctx = canvas.getContext('2d');
    const gravitySlider = document.getElementById('gravity-slider');
    const dampingSlider = document.getElementById('damping-slider');
    const lengthSlider = document.getElementById('length-slider');
    const playToggle = document.getElementById('play-toggle');
    const resetBtn = document.getElementById('reset-btn');
    const gravityValue = document.getElementById('gravity-value');
    const dampingValue = document.getElementById('damping-value');
    const lengthValue = document.getElementById('length-value');
    const angleReadout = document.getElementById('angle-readout');
    const velocityReadout = document.getElementById('velocity-readout');
    const periodReadout = document.getElementById('period-readout');
    const statusReadout = document.getElementById('status-readout');
    const live = document.getElementById('pendulum-live');

    const baseState = {{
      gravity: 9.81,
      damping: 0.02,
      length: 1.2,
      theta: Math.PI / 10,
      omega: 0,
      running: true,
      dragging: false,
    }};
    const state = Object.assign({{}}, baseState);

    let rafId = 0;
    let lastTime = performance.now();
    let pivot = {{ x: 0, y: 40 }};
    let bobRadius = 18;
    let pixelsPerMeter = 180;

    function report(kind, payload, summary, status) {{
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.reportResult === 'function') {{
        window.WiiiVisualBridge.reportResult(kind, payload, summary, status);
      }}
    }}

    function setText(node, value) {{
      if (node) {{
        node.textContent = value;
      }}
    }}

    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.max(1, window.devicePixelRatio || 1);
      canvas.width = Math.max(320, Math.floor(rect.width * ratio));
      canvas.height = Math.max(280, Math.floor(rect.height * ratio));
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(ratio, ratio);
      pivot = {{ x: rect.width / 2, y: 44 }};
      pixelsPerMeter = Math.max(110, rect.height * 0.52);
      draw();
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.resize === 'function') {{
        window.WiiiVisualBridge.resize();
      }}
    }}

    function pendulumMetrics() {{
      const angleDeg = state.theta * 180 / Math.PI;
      const approxPeriod = 2 * Math.PI * Math.sqrt(state.length / Math.max(state.gravity, 0.1));
      return {{ angleDeg, approxPeriod }};
    }}

    function syncReadouts() {{
      const metrics = pendulumMetrics();
      setText(gravityValue, state.gravity.toFixed(2) + ' m/s^2');
      setText(dampingValue, state.damping.toFixed(3));
      setText(lengthValue, state.length.toFixed(2) + ' m');
      setText(angleReadout, metrics.angleDeg.toFixed(1) + ' deg');
      setText(velocityReadout, state.omega.toFixed(2) + ' rad/s');
      setText(periodReadout, metrics.approxPeriod.toFixed(2) + ' s');
      setText(statusReadout, state.dragging ? 'Dang keo' : (state.running ? 'Dang chay' : 'Tam dung'));
      if (live) {{
        live.textContent = state.dragging
          ? 'Tha chuot de xem con lac tiep tuc dao dong tu goc moi.'
          : (state.running
            ? '{live_running}'
            : 'Mo phong dang tam dung. Ban co the keo qua nang hoac tiep tuc chay.');
      }}
    }}

    function bobPosition() {{
      const rect = canvas.getBoundingClientRect();
      const rodLength = state.length * pixelsPerMeter;
      return {{
        x: pivot.x + rodLength * Math.sin(state.theta),
        y: pivot.y + rodLength * Math.cos(state.theta),
        width: rect.width,
        height: rect.height,
        rodLength: rodLength,
      }};
    }}

    function drawGrid(width, height) {{
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
      ctx.lineWidth = 1;
      for (let x = 24; x < width; x += 32) {{
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }}
      for (let y = 24; y < height; y += 32) {{
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }}
      ctx.restore();
    }}

    function draw() {{
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);
      drawGrid(width, height);

      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.06)';
      ctx.fillRect(0, height - 38, width, 38);
      ctx.restore();

      const bob = bobPosition();

      ctx.save();
      ctx.strokeStyle = 'rgba(37, 99, 235, 0.85)';
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(pivot.x, pivot.y);
      ctx.lineTo(bob.x, bob.y);
      ctx.stroke();

      ctx.fillStyle = 'rgba(148, 163, 184, 0.42)';
      ctx.beginPath();
      ctx.arc(pivot.x, pivot.y, 8, 0, Math.PI * 2);
      ctx.fill();

      const bobGradient = ctx.createRadialGradient(bob.x - 8, bob.y - 10, 4, bob.x, bob.y, 22);
      bobGradient.addColorStop(0, '#93c5fd');
      bobGradient.addColorStop(0.45, '#2563eb');
      bobGradient.addColorStop(1, '#1e3a8a');
      ctx.fillStyle = bobGradient;
      ctx.beginPath();
      ctx.arc(bob.x, bob.y, bobRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(255,255,255,0.7)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(bob.x - 5, bob.y - 6, 6, Math.PI * 1.2, Math.PI * 1.9);
      ctx.stroke();
      ctx.restore();

      syncReadouts();
    }}

    function advance(dt) {{
      const acceleration = -(state.gravity / Math.max(state.length, 0.25)) * Math.sin(state.theta) - state.damping * state.omega;
      state.omega += acceleration * dt;
      state.theta += state.omega * dt;
    }}

    function loop(now) {{
      const dt = Math.min(0.032, Math.max(0.001, (now - lastTime) / 1000));
      lastTime = now;
      if (state.running && !state.dragging) {{
        advance(dt);
      }}
      draw();
      rafId = window.requestAnimationFrame(loop);
    }}

    function pointerToTheta(clientX, clientY) {{
      const rect = canvas.getBoundingClientRect();
      const dx = clientX - rect.left - pivot.x;
      const dy = clientY - rect.top - pivot.y;
      return Math.atan2(dx, Math.max(24, dy));
    }}

    function onPointerDown(event) {{
      const bob = bobPosition();
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const distance = Math.hypot(x - bob.x, y - bob.y);
      if (distance > bobRadius + 16) return;
      state.dragging = true;
      state.running = false;
      state.omega = 0;
      canvas.classList.add('is-dragging');
      canvas.setPointerCapture(event.pointerId);
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerMove(event) {{
      if (!state.dragging) return;
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerUp(event) {{
      if (!state.dragging) return;
      state.dragging = false;
      state.running = true;
      canvas.classList.remove('is-dragging');
      try {{
        canvas.releasePointerCapture(event.pointerId);
      }} catch (_error) {{}}
      const metrics = pendulumMetrics();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          angle_deg: Number(metrics.angleDeg.toFixed(1)),
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
          length_m: Number(state.length.toFixed(2)),
        }},
        'Nguoi dung vua tha con lac o goc ' + metrics.angleDeg.toFixed(1) + ' deg.',
        'completed'
      );
    }}

    if (gravitySlider) {{
      gravitySlider.addEventListener('input', function () {{
        state.gravity = Number(gravitySlider.value);
        draw();
      }});
    }}
    if (dampingSlider) {{
      dampingSlider.addEventListener('input', function () {{
        state.damping = Number(dampingSlider.value);
        draw();
      }});
    }}
    if (lengthSlider) {{
      lengthSlider.addEventListener('input', function () {{
        state.length = Number(lengthSlider.value);
        draw();
      }});
    }}

    playToggle.addEventListener('click', function () {{
      state.running = !state.running;
      playToggle.textContent = state.running ? 'Tam dung' : 'Tiep tuc';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: state.running ? 'resume' : 'pause',
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
          length_m: Number(state.length.toFixed(2)),
        }},
        state.running ? 'Nguoi dung tiep tuc mo phong con lac.' : 'Nguoi dung tam dung mo phong con lac.',
        state.running ? 'running' : 'paused'
      );
    }});

    resetBtn.addEventListener('click', function () {{
      Object.assign(state, baseState);
      if (gravitySlider) gravitySlider.value = String(baseState.gravity);
      if (dampingSlider) dampingSlider.value = String(baseState.damping);
      if (lengthSlider) lengthSlider.value = String(baseState.length);
      playToggle.textContent = 'Tam dung';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: 'reset',
          angle_deg: 18,
        }},
        'Nguoi dung da dat lai mo phong con lac ve trang thai mac dinh.',
        'reset'
      );
    }});

    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    window.addEventListener('resize', resizeCanvas);

    resizeCanvas();
    draw();
    rafId = window.requestAnimationFrame(loop);

    window.addEventListener('beforeunload', function () {{
      if (rafId) window.cancelAnimationFrame(rafId);
    }});
  }})();
</script>
""".strip()


def _maybe_upgrade_code_studio_output(
    raw_html: str,
    *,
    title: str,
    subtitle: str,
    requested_visual_type: str,
    studio_lane: str,
    artifact_kind: str,
    quality_profile: str,
) -> str:
    quality_error = _validate_code_studio_output(
        raw_html,
        requested_visual_type=requested_visual_type,
        studio_lane=studio_lane,
        artifact_kind=artifact_kind,
        quality_profile=quality_profile,
    )
    if not quality_error:
        return raw_html

    if (
        requested_visual_type == "simulation"
        and quality_profile == "premium"
        and _looks_like_pendulum_simulation(raw_html, title, _runtime_visual_user_query())
    ):
        upgraded = _build_pendulum_simulation_scaffold(title, subtitle, _runtime_visual_user_query())
        if not _validate_code_studio_output(
            upgraded,
            requested_visual_type=requested_visual_type,
            studio_lane=studio_lane,
            artifact_kind=artifact_kind,
            quality_profile=quality_profile,
        ):
            return upgraded

    return raw_html


def _infer_scene_render_surface(renderer_kind: str, visual_type: str) -> str:
    preferred = _runtime_preferred_render_surface()
    if preferred in {"svg", "canvas", "html", "video"}:
        return preferred
    if visual_type == "simulation":
        return "canvas"
    if renderer_kind == "template":
        return "svg"
    if renderer_kind == "app":
        return "canvas" if visual_type == "simulation" else "html"
    return "html"


def _infer_scene_motion_profile(
    *,
    visual_type: str,
    presentation_intent: str,
    render_surface: str,
) -> str:
    if render_surface == "canvas":
        return "continuous_simulation" if visual_type == "simulation" else "continuous_canvas"
    if presentation_intent == "chart_runtime":
        return "guided_focus"
    if visual_type in {"process", "timeline"}:
        return "stepwise_reveal"
    if visual_type in {"comparison", "architecture", "concept", "infographic", "chart"}:
        return "guided_focus"
    return "static"


def _infer_scene_pedagogy_arc(
    *,
    presentation_intent: str,
    visual_type: str,
    summary: str,
    claim: str,
) -> dict[str, str]:
    headline = claim or summary or _default_visual_title(visual_type)
    if presentation_intent == "chart_runtime":
        return {
            "opening": "Orient the learner with scale, units, and what to compare.",
            "focus": headline,
            "closing": "Land one concise takeaway from the pattern, not just the picture.",
        }
    if presentation_intent == "code_studio_app" and visual_type == "simulation":
        return {
            "opening": "Set the opening scene before motion starts.",
            "focus": headline,
            "closing": "Use readouts and a short reflection to connect interaction back to understanding.",
        }
    return {
        "opening": "Set context quickly and make the visual claim obvious.",
        "focus": headline,
        "closing": "End with one takeaway the learner can reuse.",
    }


def _infer_scene_state_model(
    *,
    presentation_intent: str,
    visual_type: str,
    render_surface: str,
) -> dict[str, Any]:
    if visual_type == "simulation" or render_surface == "canvas":
        return {
            "kind": "continuous_state",
            "driver": "animation_loop",
            "patchable": True,
        }
    if presentation_intent == "chart_runtime":
        return {
            "kind": "declarative_chart",
            "driver": "chart_spec",
            "patchable": True,
        }
    if presentation_intent == "article_figure":
        return {
            "kind": "semantic_svg_scene",
            "driver": "figure_spec",
            "patchable": True,
        }
    return {
        "kind": "artifact_state",
        "driver": "html_runtime",
        "patchable": True,
    }


def _infer_scene_narrative_voice(presentation_intent: str) -> dict[str, Any]:
    mode = _runtime_living_expression_mode() or ("expressive" if presentation_intent == "article_figure" else "subtle")
    return {
        "mode": mode,
        "stance": "guide",
        "character_forward": True,
        "tone": "clear_vivid" if mode == "expressive" else "clear_precise",
    }


def _enrich_scene_contract(
    *,
    scene: dict[str, Any],
    visual_type: str,
    renderer_kind: str,
    presentation_intent: str,
    pedagogical_role: str,
    summary: str,
    claim: str,
) -> dict[str, Any]:
    enriched = dict(scene)
    enriched["kind"] = str(enriched.get("kind") or visual_type)
    render_surface = _infer_scene_render_surface(renderer_kind, visual_type)
    enriched["render_surface"] = enriched.get("render_surface") or render_surface
    enriched["motion_profile"] = enriched.get("motion_profile") or _infer_scene_motion_profile(
        visual_type=visual_type,
        presentation_intent=presentation_intent,
        render_surface=render_surface,
    )
    enriched["pedagogy_arc"] = enriched.get("pedagogy_arc") or _infer_scene_pedagogy_arc(
        presentation_intent=presentation_intent,
        visual_type=visual_type,
        summary=summary,
        claim=claim,
    )
    enriched["state_model"] = enriched.get("state_model") or _infer_scene_state_model(
        presentation_intent=presentation_intent,
        visual_type=visual_type,
        render_surface=render_surface,
    )
    enriched["narrative_voice"] = enriched.get("narrative_voice") or _infer_scene_narrative_voice(presentation_intent)
    if "focus_states" not in enriched:
        enriched["focus_states"] = [{
            "id": "default",
            "claim": claim or summary,
            "pedagogical_role": pedagogical_role or "overview",
        }]
    return enriched


def _resolve_fallback_html(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    builder_output: str | None,
) -> str | None:
    html = None
    if builder_output:
        html = builder_output
    else:
        for key in ("html", "markup", "custom_html", "template_html", "app_html"):
            value = spec.get(key)
            if isinstance(value, str) and value.strip():
                html = value
                break
    if html:
        html = _postprocess_visual_html(html)
    return html


def _build_runtime_manifest(
    *,
    renderer_kind: str,
    visual_type: str,
    spec: dict[str, Any],
    provided: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if renderer_kind != "app":
        return None
    manifest = {
        "ui_runtime": str((provided or {}).get("ui_runtime") or spec.get("ui_runtime") or ("react" if visual_type == "react_app" else "html")),
        "storage": bool((provided or {}).get("storage", spec.get("storage", False))),
        "mcp_access": bool((provided or {}).get("mcp_access", spec.get("mcp_access", False))),
        "file_export": bool((provided or {}).get("file_export", spec.get("file_export", False))),
        "shareability": str((provided or {}).get("shareability") or spec.get("shareability") or "session"),
    }
    return manifest


def _normalize_visual_payload(
    *,
    visual_type: str,
    spec: dict[str, Any],
    title: str = "",
    summary: str = "",
    subtitle: str = "",
    visual_session_id: str = "",
    operation: str = "open",
    renderer_kind: str = "",
    shell_variant: str = "",
    patch_strategy: str = "",
    narrative_anchor: str = "",
    runtime: str = "",
    fallback_html: str | None = None,
    runtime_manifest: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    figure_group_id: str = "",
    figure_index: int = 1,
    figure_total: int = 1,
    pedagogical_role: str = "",
    chrome_mode: str = "",
    claim: str = "",
) -> VisualPayloadV1:
    resolved_title = title.strip() or _default_visual_title(visual_type)
    resolved_summary = _sanitize_summary_candidate(summary, visual_type, resolved_title) or _default_visual_summary(
        visual_type,
        resolved_title,
        spec,
    )
    resolved_subtitle = subtitle.strip() or None
    resolved_renderer_kind = _resolve_renderer_kind(visual_type, spec, renderer_kind)
    resolved_runtime = runtime.strip() or _infer_runtime(resolved_renderer_kind, visual_type, spec)
    resolved_shell_variant = _infer_shell_variant(resolved_renderer_kind, shell_variant)
    resolved_patch_strategy = _infer_patch_strategy(resolved_renderer_kind, patch_strategy)
    resolved_pedagogical_role = _infer_pedagogical_role(visual_type, spec, pedagogical_role)
    resolved_chrome_mode = _infer_chrome_mode(
        resolved_renderer_kind,
        resolved_shell_variant,
        chrome_mode,
    )
    resolved_claim = _clean_summary_text(claim) or _default_visual_claim(
        visual_type,
        resolved_title,
        resolved_summary,
        spec,
    )
    resolved_controls = _build_controls(visual_type, spec)
    resolved_scene = _build_scene(visual_type, spec, resolved_title)
    resolved_annotations = _build_annotations(visual_type, spec)
    if not resolved_annotations:
        resolved_annotations = [{
            "id": "takeaway",
            "title": "Điểm chốt",
            "body": resolved_summary,
            "tone": "accent",
        }]
    lifecycle_event = "visual_patch" if operation == "patch" else "visual_open"
    metadata = metadata or {}
    metadata_presentation_intent = _metadata_text(metadata, "presentation_intent", "")
    resolved_presentation_intent = _runtime_presentation_intent() or metadata_presentation_intent
    if not resolved_presentation_intent or resolved_presentation_intent == "text":
        if resolved_renderer_kind == "app":
            resolved_presentation_intent = "code_studio_app"
        elif visual_type == "chart":
            resolved_presentation_intent = "chart_runtime"
        else:
            resolved_presentation_intent = "article_figure"
    resolved_renderer_contract = _runtime_renderer_contract() or _metadata_text(metadata, "renderer_contract", "")
    if not resolved_renderer_contract:
        resolved_renderer_contract = "host_shell" if resolved_renderer_kind == "app" else (
            "chart_runtime" if resolved_presentation_intent == "chart_runtime" else "article_figure"
        )
    resolved_quality_profile = _metadata_text(metadata, "quality_profile", _runtime_quality_profile()) or "standard"
    resolved_studio_lane = _runtime_studio_lane() or _metadata_text(metadata, "studio_lane", "") or None
    resolved_artifact_kind = _runtime_artifact_kind() or _metadata_text(metadata, "artifact_kind", "") or None
    resolved_preferred_render_surface = _metadata_text(
        metadata,
        "preferred_render_surface",
        _runtime_preferred_render_surface(),
    ) or _infer_scene_render_surface(resolved_renderer_kind, visual_type)
    resolved_planning_profile = _metadata_text(
        metadata,
        "planning_profile",
        _runtime_planning_profile(),
    ) or ("simulation_canvas" if visual_type == "simulation" else "article_svg")
    resolved_thinking_floor = _metadata_text(
        metadata,
        "thinking_floor",
        _runtime_thinking_floor(),
    ) or "medium"
    resolved_critic_policy = _metadata_text(
        metadata,
        "critic_policy",
        _runtime_critic_policy(),
    ) or "standard"
    resolved_living_expression_mode = _metadata_text(
        metadata,
        "living_expression_mode",
        _runtime_living_expression_mode(),
    ) or ("expressive" if resolved_presentation_intent == "article_figure" else "subtle")
    runtime_metadata = _get_runtime_visual_metadata()
    raw_figure_budget = runtime_metadata.get("figure_budget", metadata.get("figure_budget", figure_total or 1))
    try:
        resolved_figure_budget = max(1, min(3, int(raw_figure_budget or 1)))
    except Exception:
        resolved_figure_budget = max(1, min(3, int(figure_total or 1)))
    resolved_metadata = dict(metadata)
    resolved_metadata["contract_version"] = "visual_payload_v3"
    resolved_metadata["source_tool"] = str(resolved_metadata.get("source_tool") or "tool_generate_visual")
    resolved_metadata["figure_group_id"] = figure_group_id.strip() or spec.get("figure_group_id") or ""
    resolved_metadata["pedagogical_role"] = resolved_pedagogical_role
    resolved_metadata["presentation_intent"] = resolved_presentation_intent
    resolved_metadata["figure_budget"] = resolved_figure_budget
    resolved_metadata["quality_profile"] = resolved_quality_profile
    resolved_metadata["renderer_contract"] = resolved_renderer_contract
    resolved_metadata["preferred_render_surface"] = resolved_preferred_render_surface
    resolved_metadata["planning_profile"] = resolved_planning_profile
    resolved_metadata["thinking_floor"] = resolved_thinking_floor
    resolved_metadata["critic_policy"] = resolved_critic_policy
    resolved_metadata["living_expression_mode"] = resolved_living_expression_mode
    if resolved_studio_lane:
        resolved_metadata["studio_lane"] = resolved_studio_lane
    else:
        resolved_metadata.pop("studio_lane", None)
    if resolved_artifact_kind:
        resolved_metadata["artifact_kind"] = resolved_artifact_kind
    else:
        resolved_metadata.pop("artifact_kind", None)
    artifact_handoff = _build_artifact_handoff(
        presentation_intent=resolved_presentation_intent,
        visual_type=visual_type,
        title=resolved_title,
        summary=resolved_summary,
    )
    resolved_metadata["artifact_handoff_available"] = artifact_handoff["available"]
    resolved_metadata["artifact_handoff_mode"] = artifact_handoff["mode"]
    if artifact_handoff["label"]:
        resolved_metadata["artifact_handoff_label"] = artifact_handoff["label"]
    else:
        resolved_metadata.pop("artifact_handoff_label", None)
    if artifact_handoff["prompt"]:
        resolved_metadata["artifact_handoff_prompt"] = artifact_handoff["prompt"]
    else:
        resolved_metadata.pop("artifact_handoff_prompt", None)
    resolved_scene = _enrich_scene_contract(
        scene=resolved_scene,
        visual_type=visual_type,
        renderer_kind=resolved_renderer_kind,
        presentation_intent=resolved_presentation_intent,
        pedagogical_role=resolved_pedagogical_role,
        summary=resolved_summary,
        claim=resolved_claim,
    )
    return VisualPayloadV1(
        id=f"visual-{uuid.uuid4().hex[:12]}",
        visual_session_id=visual_session_id.strip() or _generate_visual_session_id(visual_type),
        type=visual_type,
        renderer_kind=resolved_renderer_kind,  # type: ignore[arg-type]
        shell_variant=resolved_shell_variant,  # type: ignore[arg-type]
        patch_strategy=resolved_patch_strategy,  # type: ignore[arg-type]
        figure_group_id=figure_group_id.strip() or str(spec.get("figure_group_id") or _generate_figure_group_id(visual_type)),
        figure_index=max(1, int(figure_index or 1)),
        figure_total=max(1, int(figure_total or 1)),
        pedagogical_role=resolved_pedagogical_role,  # type: ignore[arg-type]
        chrome_mode=resolved_chrome_mode,  # type: ignore[arg-type]
        claim=resolved_claim,
        presentation_intent=resolved_presentation_intent,  # type: ignore[arg-type]
        figure_budget=resolved_figure_budget,
        quality_profile=resolved_quality_profile,  # type: ignore[arg-type]
        renderer_contract=resolved_renderer_contract,  # type: ignore[arg-type]
        studio_lane=resolved_studio_lane,  # type: ignore[arg-type]
        artifact_kind=resolved_artifact_kind,  # type: ignore[arg-type]
        narrative_anchor=narrative_anchor.strip() or str(spec.get("narrative_anchor") or "after-lead"),
        runtime=resolved_runtime,  # type: ignore[arg-type]
        title=resolved_title,
        summary=resolved_summary,
        spec=spec,
        scene=resolved_scene,
        controls=resolved_controls,
        annotations=resolved_annotations,
        interaction_mode=_infer_interaction_mode(resolved_controls),  # type: ignore[arg-type]
        ephemeral=True,
        lifecycle_event=lifecycle_event,  # type: ignore[arg-type]
        subtitle=resolved_subtitle,
        fallback_html=fallback_html,
        runtime_manifest=_build_runtime_manifest(
            renderer_kind=resolved_renderer_kind,
            visual_type=visual_type,
            spec=spec,
            provided=runtime_manifest,
        ),
        artifact_handoff_available=artifact_handoff["available"],
        artifact_handoff_mode=artifact_handoff["mode"],  # type: ignore[arg-type]
        artifact_handoff_label=artifact_handoff["label"],
        artifact_handoff_prompt=artifact_handoff["prompt"],
        metadata=resolved_metadata,
    )


def _coerce_visual_payload_data(data: dict[str, Any]) -> dict[str, Any]:
    visual_type = str(data.get("type") or "comparison")
    spec = data.get("spec") if isinstance(data.get("spec"), dict) else {}
    controls = data.get("controls")
    if not isinstance(controls, list):
        controls = _build_controls(visual_type, spec)

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    metadata = {
        "contract_version": metadata.get("contract_version") or "visual_payload_v3",
        **metadata,
    }

    coerced = dict(data)
    coerced["visual_session_id"] = str(
        data.get("visual_session_id") or _generate_visual_session_id(visual_type)
    )
    coerced["renderer_kind"] = _resolve_renderer_kind(
        visual_type,
        spec,
        str(data.get("renderer_kind") or ""),
    )
    coerced["shell_variant"] = _infer_shell_variant(
        str(coerced["renderer_kind"]),
        str(data.get("shell_variant") or ""),
    )
    coerced["patch_strategy"] = _infer_patch_strategy(
        str(coerced["renderer_kind"]),
        str(data.get("patch_strategy") or ""),
    )
    coerced["figure_group_id"] = str(
        data.get("figure_group_id")
        or metadata.get("figure_group_id")
        or spec.get("figure_group_id")
        or _generate_figure_group_id(visual_type)
    )
    coerced["figure_index"] = max(1, int(data.get("figure_index") or 1))
    coerced["figure_total"] = max(
        coerced["figure_index"],
        int(data.get("figure_total") or 1),
    )
    coerced["pedagogical_role"] = _infer_pedagogical_role(
        visual_type,
        spec,
        str(data.get("pedagogical_role") or metadata.get("pedagogical_role") or ""),
    )
    coerced["chrome_mode"] = _infer_chrome_mode(
        str(coerced["renderer_kind"]),
        str(coerced["shell_variant"]),
        str(data.get("chrome_mode") or ""),
    )
    coerced["claim"] = _clean_summary_text(str(data.get("claim") or "")) or _default_visual_claim(
        visual_type,
        str(data.get("title") or _default_visual_title(visual_type)),
        str(data.get("summary") or ""),
        spec,
    )
    coerced["narrative_anchor"] = str(data.get("narrative_anchor") or "after-lead")
    coerced["runtime"] = str(
        data.get("runtime")
        or _infer_runtime(str(coerced["renderer_kind"]), visual_type, spec)
    )
    coerced["scene"] = data.get("scene") if isinstance(data.get("scene"), dict) else _build_scene(
        visual_type,
        spec,
        str(data.get("title") or ""),
    )
    coerced["controls"] = controls
    coerced["annotations"] = (
        data.get("annotations")
        if isinstance(data.get("annotations"), list)
        else _build_annotations(visual_type, spec)
    )
    coerced["interaction_mode"] = str(
        data.get("interaction_mode") or _infer_interaction_mode(controls)
    )
    coerced["ephemeral"] = bool(data.get("ephemeral", True))
    coerced["lifecycle_event"] = str(data.get("lifecycle_event") or "visual_open")
    coerced["runtime_manifest"] = _build_runtime_manifest(
        renderer_kind=str(coerced["renderer_kind"]),
        visual_type=visual_type,
        spec=spec,
        provided=data.get("runtime_manifest") if isinstance(data.get("runtime_manifest"), dict) else None,
    )
    coerced["artifact_handoff_available"] = bool(
        data.get("artifact_handoff_available", metadata.get("artifact_handoff_available", False))
    )
    coerced["artifact_handoff_mode"] = str(
        data.get("artifact_handoff_mode")
        or metadata.get("artifact_handoff_mode")
        or ("followup_prompt" if coerced["artifact_handoff_available"] else "none")
    )
    coerced["artifact_handoff_label"] = (
        str(data.get("artifact_handoff_label") or metadata.get("artifact_handoff_label") or "").strip() or None
    )
    coerced["artifact_handoff_prompt"] = (
        str(data.get("artifact_handoff_prompt") or metadata.get("artifact_handoff_prompt") or "").strip() or None
    )
    coerced["metadata"] = metadata
    return coerced


def _apply_runtime_patch_defaults(
    *,
    visual_session_id: str,
    operation: str,
) -> tuple[str, str]:
    """Fill patch defaults from tool runtime metadata for visual follow-up edits."""
    runtime = get_current_tool_runtime_context()
    metadata = runtime.metadata if runtime and isinstance(runtime.metadata, dict) else {}
    preferred_operation = str(metadata.get("preferred_visual_operation") or "").strip()
    preferred_session_id = str(
        metadata.get("preferred_visual_session_id")
        or metadata.get("preferred_code_studio_session_id")
        or ""
    ).strip()

    resolved_session_id = visual_session_id.strip()
    resolved_operation = operation.strip() or "open"

    if preferred_operation != "patch" or not preferred_session_id:
        return resolved_session_id, resolved_operation

    # Model-generated session IDs are not trustworthy on follow-up patch turns.
    # When the client tells us which session is active, keep patches anchored there.
    resolved_session_id = preferred_session_id
    if resolved_operation == "open":
        resolved_operation = "patch"

    return resolved_session_id, resolved_operation


def _build_multi_figure_payloads(
    *,
    default_visual_type: str,
    raw_group: dict[str, Any],
) -> list[VisualPayloadV1]:
    figures = raw_group.get("figures")
    if not isinstance(figures, list) or not figures:
        return []

    figure_total = len(figures)
    group_id = str(raw_group.get("figure_group_id") or _generate_figure_group_id(default_visual_type))
    payloads: list[VisualPayloadV1] = []

    for index, figure in enumerate(figures, start=1):
        if not isinstance(figure, dict):
            continue

        figure_visual_type = str(figure.get("type") or figure.get("visual_type") or default_visual_type or "comparison").strip()
        figure_spec = figure.get("spec") if isinstance(figure.get("spec"), dict) else {}
        if not isinstance(figure_spec, dict):
            figure_spec = {}
        figure_title = str(figure.get("title") or raw_group.get("title") or "")
        builder = _BUILDERS.get(figure_visual_type)
        builder_html = None
        if builder is not None:
            try:
                builder_html = builder(figure_spec, figure_title)
            except Exception as exc:
                logger.warning("Structured visual fallback HTML failed for grouped type=%s: %s", figure_visual_type, exc)
        resolved_renderer_kind = _resolve_renderer_kind(
            figure_visual_type,
            figure_spec,
            str(figure.get("renderer_kind") or raw_group.get("renderer_kind") or ""),
        )
        fallback_html = str(figure.get("fallback_html") or "") or _resolve_fallback_html(
            figure_visual_type,
            figure_spec,
            figure_title,
            builder_html,
        )
        runtime_manifest = (
            figure.get("runtime_manifest")
            if isinstance(figure.get("runtime_manifest"), dict)
            else raw_group.get("runtime_manifest")
            if isinstance(raw_group.get("runtime_manifest"), dict)
            else None
        )

        payloads.append(
            _normalize_visual_payload(
                visual_type=figure_visual_type,
                spec={
                    **figure_spec,
                    "figure_group_id": group_id,
                },
                title=figure_title,
                summary=str(figure.get("summary") or ""),
                subtitle=str(figure.get("subtitle") or ""),
                visual_session_id=str(figure.get("visual_session_id") or ""),
                operation=str(figure.get("operation") or raw_group.get("operation") or "open"),
                renderer_kind=resolved_renderer_kind,
                shell_variant=str(figure.get("shell_variant") or raw_group.get("shell_variant") or ""),
                patch_strategy=str(figure.get("patch_strategy") or ""),
                narrative_anchor=str(figure.get("narrative_anchor") or raw_group.get("narrative_anchor") or ""),
                runtime=str(figure.get("runtime") or ""),
                fallback_html=fallback_html,
                runtime_manifest=runtime_manifest,
                metadata=figure.get("metadata") if isinstance(figure.get("metadata"), dict) else None,
                figure_group_id=group_id,
                figure_index=index,
                figure_total=figure_total,
                pedagogical_role=str(figure.get("pedagogical_role") or ""),
                chrome_mode=str(figure.get("chrome_mode") or raw_group.get("chrome_mode") or ""),
                claim=str(figure.get("claim") or ""),
            )
        )

    return payloads


def parse_visual_payloads(raw: Any) -> list[VisualPayloadV1]:
    """Best-effort parser for single or grouped structured visual tool results."""
    if isinstance(raw, VisualPayloadV1):
        return [raw]

    if isinstance(raw, list):
        payloads: list[VisualPayloadV1] = []
        for item in raw:
            payloads.extend(parse_visual_payloads(item))
        return payloads

    if isinstance(raw, dict):
        if isinstance(raw.get("figures"), list):
            payloads = _build_multi_figure_payloads(
                default_visual_type=str(raw.get("type") or raw.get("visual_type") or "comparison"),
                raw_group=raw,
            )
            if payloads:
                return payloads
        try:
            return [VisualPayloadV1.model_validate(_coerce_visual_payload_data(raw))]
        except ValidationError:
            return []

    if not raw:
        return []

    text = str(raw).strip()
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    return parse_visual_payloads(data)


def parse_visual_payload(raw: Any) -> VisualPayloadV1 | None:
    """Backward-compatible parser that returns the first structured visual payload."""
    payloads = parse_visual_payloads(raw)
    return payloads[0] if payloads else None


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
  padding: 4px 0; font-size: 14px;
}
.widget-title {
  font-size: 13px; font-weight: 700; text-align: left;
  margin-bottom: 14px; color: var(--text2); letter-spacing: 0.02em;
}
.widget-subtitle {
  font-size: 11px; color: var(--text3); text-align: left;
  margin-top: -10px; margin-bottom: 12px;
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
    title_html = f'<div class="wiii-frame-title widget-title">{_esc(title)}</div>' if title else ""
    subtitle_html = f'<div class="wiii-frame-subtitle widget-subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<style>{_DESIGN_CSS}
{body_css}</style></head>
<body>{title_html}{subtitle_html}{body_html}</body></html>"""


# =============================================================================
# COMPARISON — Side-by-side (like Claude's Standard vs Linear Attention)
# =============================================================================

def _build_comparison_html(spec: dict, title: str) -> str:
    """Clean horizontal bar comparison — matching demo benchmark."""
    logger.info("[COMPARISON_BUILDER] Input spec keys: %s", list(spec.keys()) if spec else "None")

    # If spec has data array (chart format), delegate to chart builder
    if "data" in spec and isinstance(spec.get("data"), list) and "left" not in spec:
        return _build_chart_html(spec, title)

    left = spec.get("left", {})
    right = spec.get("right", {})

    # Extract items from both sides for bar comparison
    COLORS = ["#D97757", "#85CDCA", "#FFD166", "#C9B1FF", "#E8A87C"]
    bars_html = []

    def _add_bars(side: dict, color_idx: int) -> None:
        side_title = _esc(side.get("title", ""))
        items = side.get("items", [])
        for item in items:
            label = ""
            if isinstance(item, str):
                label = item
            elif isinstance(item, dict):
                label = item.get("label", item.get("value", ""))
            if label:
                bars_html.append((side_title, _esc(str(label)), COLORS[color_idx % 5]))

    _add_bars(left, 0)
    _add_bars(right, 1)

    # Build clean horizontal bars
    bar_rows = []
    for side_name, label, color in bars_html:
        bar_rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{label[:40]}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:75%;background:linear-gradient(90deg,{color},{color}cc)"></div></div>'
            f'</div>'
        )

    subtitle = _esc(spec.get("note", spec.get("highlight", "")))

    css = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,-apple-system,sans-serif; background:transparent; color:#333; }
.root { max-width:600px; margin:0 auto; padding:16px 0; }
.title { font-size:15px; font-weight:600; margin-bottom:4px; }
.subtitle { font-size:13px; color:#999; margin-bottom:20px; }
.bar-rows { display:flex; flex-direction:column; gap:10px; }
.bar-row { display:flex; align-items:center; gap:12px; }
.bar-label { width:140px; font-size:13px; color:#555; text-align:right; font-weight:500; flex-shrink:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bar-track { flex:1; height:28px; background:#f5f2ef; border-radius:6px; overflow:hidden; }
.bar-fill { height:100%; border-radius:6px; }
"""

    body = f'<div class="root">'
    body += f'<div class="title">{_esc(title)}</div>'
    if subtitle:
        body += f'<div class="subtitle">{subtitle}</div>'
    body += '<div class="bar-rows">'
    body += "\n".join(bar_rows)
    body += '</div></div>'

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

    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--pink)", "var(--teal)"]
    arrow_svg = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="var(--text3)" stroke-width="2" stroke-linecap="round"/></svg>'

    parts = []
    for i, step in enumerate(steps):
        color = step.get("color", colors[i % len(colors)])
        num = _esc(step.get("icon", str(i + 1)))
        step_title = _esc(step.get("title", f"Bước {i + 1}"))
        desc = _esc(step.get("description", ""))
        content = _esc(step.get("content", ""))
        signals = step.get("signals", [])
        desc_html = f'<div class="step-desc">{desc}</div>' if desc else ""
        content_html = f'<div class="step-content">{content}</div>' if content else ""
        signals_html = ""
        if signals:
            sig_parts = "".join(f'<span class="step-signal">{_esc(s)}</span>' for s in signals)
            signals_html = f'<div class="step-signals">{sig_parts}</div>'
        parts.append(f"""<div class="step-card" style="--step-color:{color}">
  <div class="step-num" style="background:{color}">{num}</div>
  <div class="step-title">{step_title}</div>
  {desc_html}{content_html}{signals_html}
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
        parts.append(f"""<div class="arch-layer" style="--layer-color:{color}">
  <div class="arch-layer-header"><div class="arch-layer-name" style="color:{color}">{name}</div></div>
  {desc_html}
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
        b_title = _esc(branch.get("title", ""))
        b_desc = _esc(branch.get("description", ""))
        items = branch.get("items", [])
        items_html = "".join(f"<li>{_esc(item)}</li>" for item in items)
        desc_html = f'<div class="concept-branch-desc">{b_desc}</div>' if b_desc else ""
        branch_parts.append(f"""<div class="concept-branch" style="--branch-color:{color};border-left:2px solid color-mix(in srgb,{color} 40%,transparent)">
  <div class="concept-branch-title" style="color:{color}">{b_title}</div>
  {desc_html}
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
    highlights = spec.get("highlights", [])
    takeaway = spec.get("takeaway", "")
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

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
            stat_parts.append(f"""<div class="info-stat">
  <div class="info-stat-value" style="color:{color}">{value}</div>
  <div class="info-stat-label">{label}</div>
  {desc_html}
</div>""")
        stats_html = f'<div class="info-stats">{"".join(stat_parts)}</div>'

    highlights_html = ""
    if highlights:
        hl_parts = "".join(f'<span class="info-highlight">{_esc(h)}</span>' for h in highlights)
        highlights_html = f'<div class="info-highlights">{hl_parts}</div>'

    section_parts = []
    for section in sections:
        s_title = _esc(section.get("title", ""))
        s_content = _esc(section.get("content", ""))
        section_parts.append(f"""<div class="info-section">
  <div class="info-section-title">{s_title}</div>
  <div class="info-section-content">{s_content}</div>
</div>""")

    takeaway_html = f'<div class="info-takeaway">{_esc(takeaway)}</div>' if takeaway else ""

    body = f"""<div class="infographic">
  {stats_html}
  {highlights_html}
  {"".join(section_parts)}
  {takeaway_html}
</div>"""

    return _wrap_html(css, body, title)


# =============================================================================
# CHART — SVG bar/line chart (lightweight, no JS dependency)
# =============================================================================

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

def _build_chart_html(spec: dict, title: str) -> str:
    """Clean horizontal bar chart — matching demo benchmark. No sidebar, no tabs."""
    logger.info("[CHART_BUILDER] Input spec keys: %s", list(spec.keys()) if spec else "None")

    # Try comparison format first (left/right → extract items as bars)
    if "left" in spec or "right" in spec:
        return _build_comparison_html(spec, title)

    normalized_spec = _normalize_chart_spec(spec, title)
    labels = normalized_spec.get("labels", [])
    datasets = normalized_spec.get("datasets", [])
    caption = normalized_spec.get("caption", "")
    COLORS = ["#D97757", "#85CDCA", "#FFD166", "#C9B1FF", "#E8A87C"]

    logger.info("[CHART_BUILDER] After normalize: labels=%d, datasets=%d", len(labels), len(datasets))

    css = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,-apple-system,sans-serif; background:transparent; color:#333; }
.root { max-width:600px; margin:0 auto; padding:16px 0; }
.title { font-size:15px; font-weight:600; margin-bottom:4px; }
.subtitle { font-size:13px; color:#999; margin-bottom:20px; }
.bar-rows { display:flex; flex-direction:column; gap:12px; }
.bar-row { display:flex; align-items:center; gap:12px; }
.bar-label { width:72px; font-size:13px; color:#555; text-align:right; font-weight:500; flex-shrink:0; }
.bar-track { flex:1; height:28px; background:#f5f2ef; border-radius:6px; overflow:hidden; }
.bar-fill { height:100%; border-radius:6px; }
.bar-value { font-size:12px; font-weight:600; color:#555; min-width:48px; }
"""
    if not labels or not datasets:
        body = '<div style="text-align:center;color:#999;padding:20px;font-size:14px">Không đủ dữ liệu để vẽ biểu đồ.</div>'
        return _wrap_html(css, body, title)

    # Collect all values for scaling
    all_values = []
    for ds in datasets:
        all_values.extend(v for v in ds.get("data", []) if isinstance(v, (int, float)))
    max_val = max(all_values) if all_values else 1

    n_labels = len(labels)
    bar_group_w = plot_w / n_labels if n_labels else plot_w
    n_datasets = len(datasets)

    for ds_idx, ds in enumerate(datasets):
        ds_colors = ds.get("colors") if isinstance(ds.get("colors"), list) else []
        color = ds.get("color", colors[ds_idx % len(colors)])
        data = ds.get("data", [])
        points = []

        for i, label in enumerate(labels):
            val = data[i] if i < len(data) else 0
            x = pad_left + (i + 0.5) * bar_group_w
            y = pad_top + plot_h - ((val - min_val) / val_range) * plot_h
            points.append((x, y, val))

        if chart_type == "line":
            path_d = " ".join(f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}" for j, (x, y, _) in enumerate(points))
            svg_parts.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
            for x, y, _ in points:
                svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        else:
            bw = bar_group_w * 0.7 / n_datasets
            for i, (x, y, val) in enumerate(points):
                bx = x - (n_datasets * bw / 2) + ds_idx * bw
                base_y = pad_top + plot_h - ((0 - min_val) / val_range) * plot_h
                bar_h = base_y - y
                bar_color = ds_colors[i] if i < len(ds_colors) and isinstance(ds_colors[i], str) and ds_colors[i].strip() else color
                svg_parts.append(f'<rect x="{bx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{bar_color}" rx="2" opacity="0.85"/>')

    # Build clean horizontal bars from first dataset
    bar_rows = []
    ds = datasets[0] if datasets else {}
    data_values = ds.get("data", [])
    for i, label in enumerate(labels):
        val = data_values[i] if i < len(data_values) else 0
        pct = int((val / max_val) * 100) if max_val else 0
        color = COLORS[i % len(COLORS)]
        bar_rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{_esc(str(label))}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:linear-gradient(90deg,{color},{color}cc)"></div></div>'
            f'<div class="bar-value">{val:,.0f}</div>'
            f'</div>'
        )

    caption_html = f'<div class="subtitle">{_esc(caption)}</div>' if caption else ""

    body = f'<div class="root">'
    body += f'<div class="title">{_esc(title)}</div>'
    body += caption_html
    body += '<div class="bar-rows">' + "\n".join(bar_rows) + '</div>'
    body += '</div>'

    return _wrap_html(css, body, title)


# =============================================================================
# TIMELINE — Vertical timeline with events
# =============================================================================

def _build_timeline_html(spec: dict, title: str) -> str:
    events = spec.get("events", spec.get("steps", []))
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

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
        ev_title = _esc(event.get("title", ""))
        desc = _esc(event.get("description", ""))
        date_html = f'<div class="tl-date">{date}</div>' if date else ""
        desc_html = f'<div class="tl-desc">{desc}</div>' if desc else ""
        parts.append(f"""<div class="tl-event" style="--event-color:{color}">
  <div class="tl-dot"></div>
  {date_html}
  <div class="tl-title">{ev_title}</div>
  {desc_html}
</div>""")

    body = f'<div class="timeline">{"".join(parts)}</div>'
    return _wrap_html(css, body, title)


# =============================================================================
# MAP_LITE — Region/category cards grid
# =============================================================================

def _build_map_lite_html(spec: dict, title: str) -> str:
    regions = spec.get("regions", spec.get("items", []))
    colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--amber)", "var(--teal)", "var(--pink)"]

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
        parts.append(f"""<div class="map-card" style="--region-color:{color}">
  <div class="map-card-name" style="color:{color}">{name}</div>
  {value_html}{desc_html}{tags_html}
</div>""")

    body = f'<div class="map-grid">{"".join(parts)}</div>'
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
    "chart": _build_chart_html,
    "timeline": _build_timeline_html,
    "map_lite": _build_map_lite_html,
    "recharts_chart": lambda spec, title: "",
}


@tool
def tool_generate_visual(
    visual_type: str,
    spec_json: str,
    title: str = "",
    summary: str = "",
    subtitle: str = "",
    visual_session_id: str = "",
    operation: str = "open",
    renderer_kind: str = "",
    shell_variant: str = "",
    patch_strategy: str = "",
    narrative_anchor: str = "",
    runtime_manifest_json: str = "",
    code_html: str = "",
) -> str:
    """Generate a structured visual payload for inline visuals or app runtime.

    Use this as the PRIMARY path for Wiii Visual Runtime V3:
    - template: native React + SVG/CSS explanatory visuals
    - inline_html: bespoke HTML/CSS/JS visuals inside Wiii shell
    - app: MCP-style iframe app runtime for simulations and mini tools

    This tool returns JSON payload data for the frontend visual renderer.
    Do NOT copy this payload verbatim into prose.

    IMPORTANT — Spec Quality Rules:
    - LUÔN cung cấp description/content cho mỗi layer/step/branch. KHÔNG để trống.
    - Mỗi item phải có title VÀ description hoặc content.

    Example specs for rich output:

    architecture:
      {"layers": [
        {"name": "API Gateway", "description": "Nhận request từ client, xác thực, rate limiting", "components": ["Auth", "Rate Limiter", "Router"]},
        {"name": "Service Layer", "description": "Xử lý business logic, orchestrate giữa các service", "components": ["UserService", "OrderService", "PaymentService"]},
        {"name": "Data Layer", "description": "Lưu trữ và truy vấn dữ liệu", "components": ["PostgreSQL", "Redis Cache", "S3"]}
      ]}

    comparison:
      {"left": {"title": "Monolith", "subtitle": "Kiến trúc truyền thống", "highlight": "Đơn giản triển khai, khó scale", "items": ["Single codebase", "Shared database", "Tight coupling"]},
       "right": {"title": "Microservices", "subtitle": "Kiến trúc phân tán", "highlight": "Scale linh hoạt, phức tạp vận hành", "items": ["Independent services", "Own database", "Loose coupling"]}}

    process:
      {"steps": [
        {"title": "Request đến", "description": "Client gửi HTTP request tới API Gateway", "icon": "1", "signals": ["HTTP/HTTPS", "REST/GraphQL"]},
        {"title": "Xác thực", "description": "Gateway kiểm tra JWT token và quyền truy cập", "icon": "2", "signals": ["JWT", "RBAC"]},
        {"title": "Xử lý", "description": "Service xử lý business logic và trả kết quả", "icon": "3", "signals": ["Business Logic", "Response"]}
      ]}

    code_html:
      HTML/CSS trực tiếp cho visual. Font: system-ui.
      Màu: #D97757 (cam), #85CDCA (mint), #FFD166 (vàng), #C9B1FF (tím nhạt), #E8A87C (cam nhạt).
      Title nhỏ (15px font-weight:600), background transparent, rounded corners (6-8px).

      Ví dụ horizontal bar chart:
        code_html='<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:transparent;color:#333}.root{max-width:600px;padding:16px 0}.title{font-size:15px;font-weight:600;margin-bottom:4px}.sub{font-size:13px;color:#999;margin-bottom:20px}.rows{display:flex;flex-direction:column;gap:12px}.row{display:flex;align-items:center;gap:12px}.lbl{width:72px;font-size:13px;color:#555;text-align:right;font-weight:500}.track{flex:1;height:28px;background:#f5f2ef;border-radius:6px;overflow:hidden}.fill{height:100%;border-radius:6px}.val{font-size:12px;font-weight:600;color:#555;min-width:48px}</style><div class="root"><div class="title">Tai nạn hàng hải theo năm</div><div class="sub">Số vụ, nguồn IMO</div><div class="rows"><div class="row"><div class="lbl">2019</div><div class="track"><div class="fill" style="width:92%;background:linear-gradient(90deg,#D97757,#e89a7c)"></div></div><div class="val">2,698</div></div><div class="row"><div class="lbl">2020</div><div class="track"><div class="fill" style="width:100%;background:linear-gradient(90deg,#D97757,#e89a7c)"></div></div><div class="val">2,934</div></div><div class="row"><div class="lbl">2021</div><div class="track"><div class="fill" style="width:88%;background:linear-gradient(90deg,#85CDCA,#a8ddd8)"></div></div><div class="val">2,578</div></div><div class="row"><div class="lbl">2022</div><div class="track"><div class="fill" style="width:82%;background:linear-gradient(90deg,#85CDCA,#a8ddd8)"></div></div><div class="val">2,401</div></div><div class="row"><div class="lbl">2023</div><div class="track"><div class="fill" style="width:73%;background:linear-gradient(90deg,#FFD166,#ffe09a)"></div></div><div class="val">2,137</div></div></div></div>'
    """
    valid_types = CORE_STRUCTURED_VISUAL_TYPES
    if visual_type not in valid_types:
        valid = ", ".join(valid_types)
        return f"Error: visual_type '{visual_type}' không hợp lệ cho visual runtime. Chọn một trong: {valid}"

    if operation not in {"open", "patch"}:
        return "Error: operation phải là 'open' hoặc 'patch'."

    try:
        spec = json.loads(spec_json)
        if not isinstance(spec, dict):
            return "Error: spec_json phải là một JSON object."
    except json.JSONDecodeError as exc:
        return f"Error: JSON không hợp lệ: {exc}"

    # Phase 4: LLM-generated HTML — code_html takes priority over builder
    resolved_code_html = _resolve_code_html(code_html, visual_type, title, spec)

    runtime_manifest = None
    if runtime_manifest_json.strip():
        try:
            runtime_manifest = json.loads(runtime_manifest_json)
            if not isinstance(runtime_manifest, dict):
                return "Error: runtime_manifest_json phải là một JSON object."
        except json.JSONDecodeError as exc:
            return f"Error: runtime_manifest_json không hợp lệ: {exc}"

    if isinstance(spec.get("figures"), list) and spec.get("figures"):
        group_payloads = _build_multi_figure_payloads(
            default_visual_type=visual_type,
            raw_group={
                **spec,
                "type": visual_type,
                "title": title,
                "summary": summary,
                "subtitle": subtitle,
                "operation": operation,
                "renderer_kind": renderer_kind,
                "shell_variant": shell_variant,
                "patch_strategy": patch_strategy,
                "narrative_anchor": narrative_anchor,
                "runtime_manifest": runtime_manifest,
            },
        )
        if not group_payloads:
            return "Error: Không thể tạo nhóm figure từ spec_json.figures."

        for payload in group_payloads:
            _log_visual_telemetry(
                "tool_generate_visual",
                visual_id=payload.id,
                visual_session_id=payload.visual_session_id,
                visual_type=payload.type,
                renderer_kind=payload.renderer_kind,
                shell_variant=payload.shell_variant,
                patch_strategy=payload.patch_strategy,
                runtime=payload.runtime,
                lifecycle_event=payload.lifecycle_event,
                figure_group_id=payload.figure_group_id,
                figure_index=payload.figure_index,
                figure_total=payload.figure_total,
                pedagogical_role=payload.pedagogical_role,
            )
        return json.dumps(
            [payload.model_dump(mode="json") for payload in group_payloads],
            ensure_ascii=False,
        )

    builder = _BUILDERS.get(visual_type)
    builder_html = None
    if builder is not None:
        try:
            builder_html = builder(spec, title)
        except Exception as exc:
            logger.warning("Structured visual fallback HTML failed for type=%s: %s", visual_type, exc)

    # FORCE inline_html for chart/comparison types — template path is REMOVED
    if visual_type in ("chart", "comparison", "infographic") and renderer_kind in ("template", ""):
        renderer_kind = "inline_html"
    # Apply renderer_kind_hint from visual intent resolver
    hint = _runtime_metadata_text("renderer_kind_hint", "")
    if hint and not renderer_kind.strip():
        renderer_kind = hint

    if resolved_code_html and _should_keep_structured_renderer(renderer_kind):
        resolved_code_html = None
    if resolved_code_html:
        renderer_kind = "inline_html"
    resolved_renderer_kind = _resolve_renderer_kind(visual_type, spec, renderer_kind)
    resolved_visual_session_id, resolved_operation = _apply_runtime_patch_defaults(
        visual_session_id=visual_session_id,
        operation=operation,
    )
    # Skip auto-grouping when code_html provided — LLM's custom HTML is self-contained
    if not resolved_code_html:
        auto_group_payloads = _build_auto_grouped_payloads(
            visual_type=visual_type,
            spec=spec,
            title=title,
            summary=summary,
            subtitle=subtitle,
            operation=resolved_operation,
            renderer_kind=resolved_renderer_kind,
            shell_variant=shell_variant,
            patch_strategy=patch_strategy,
            narrative_anchor=narrative_anchor,
            runtime_manifest=runtime_manifest,
        )
        if auto_group_payloads:
            for payload in auto_group_payloads:
                _log_visual_telemetry(
                    "tool_generate_visual",
                    visual_id=payload.id,
                    visual_session_id=payload.visual_session_id,
                    visual_type=payload.type,
                    renderer_kind=payload.renderer_kind,
                    shell_variant=payload.shell_variant,
                    patch_strategy=payload.patch_strategy,
                    runtime=payload.runtime,
                    lifecycle_event=payload.lifecycle_event,
                    figure_group_id=payload.figure_group_id,
                    figure_index=payload.figure_index,
                    figure_total=payload.figure_total,
                    pedagogical_role=payload.pedagogical_role,
                    auto_grouped=True,
                )
            return json.dumps(
                [payload.model_dump(mode="json") for payload in auto_group_payloads],
                ensure_ascii=False,
            )

    # code_html takes priority → builder_html as fallback
    fallback_html = resolved_code_html or _resolve_fallback_html(visual_type, spec, title, builder_html)

    payload = _normalize_visual_payload(
        visual_type=visual_type,
        spec=spec,
        title=title,
        summary=summary,
        subtitle=subtitle,
        visual_session_id=resolved_visual_session_id,
        operation=resolved_operation,
        renderer_kind=resolved_renderer_kind,
        shell_variant=shell_variant,
        patch_strategy=patch_strategy,
        narrative_anchor=narrative_anchor,
        fallback_html=fallback_html,
        runtime_manifest=runtime_manifest,
    )
    _log_visual_telemetry(
        "tool_generate_visual",
        visual_id=payload.id,
        visual_session_id=payload.visual_session_id,
        visual_type=payload.type,
        renderer_kind=payload.renderer_kind,
        shell_variant=payload.shell_variant,
        patch_strategy=payload.patch_strategy,
        runtime=payload.runtime,
        lifecycle_event=payload.lifecycle_event,
    )
    return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)


@tool
def tool_create_visual_code(
    code_html: str,
    title: str = "",
    subtitle: str = "",
    visual_session_id: str = "",
) -> str:
    """Create Code Studio app/widget/artifact markup for host-governed runtimes.

    Use this only for `code_studio_app` or `artifact` lanes such as simulations,
    quiz widgets, search/code widgets, mini tools, and embeddable HTML apps.
    Ordinary explanatory figures and chart runtime outputs should stay on
    `tool_generate_visual`.
    """
    raw = code_html.strip() if isinstance(code_html, str) else ""
    if not raw:
        return (
            "Error: code_html là BẮT BUỘC — không để trống. "
            "Viết HTML/CSS/SVG/JS trực tiếp với đồ họa thật. "
            "Ít nhất phải có <style> + HTML elements + visual content (SVG, divs styled, canvas). "
            "Xem VISUAL_CODE_GEN.md để tham khảo patterns."
        )

    # Chống empty/placeholder — không ép rigid length
    _MIN_CODE_HTML_LENGTH = 50
    if len(raw) < _MIN_CODE_HTML_LENGTH:
        return (
            f"Error: code_html quá ngắn ({len(raw)} ký tự). "
            "Viết HTML/CSS/SVG hoàn chỉnh — model tự quyết complexity phù hợp với nội dung."
        )

    # Fragment-only enforcement: strip DOCTYPE/html/head/body wrapper if present
    _stripped = raw.lstrip()
    if _stripped.lower().startswith("<!doctype") or _stripped.lower().startswith("<html"):
        import re as _re
        # Extract <style> blocks from <head> before removing it
        _head_styles = _re.findall(r'(?si)<style[^>]*>.*?</style>', raw)
        raw = _re.sub(r'(?si)<!DOCTYPE[^>]*>\s*', '', raw)
        raw = _re.sub(r'(?si)</?html[^>]*>\s*', '', raw)
        raw = _re.sub(r'(?si)<head[^>]*>.*?</head>\s*', '', raw)
        raw = _re.sub(r'(?si)</?body[^>]*>\s*', '', raw)
        # Re-inject extracted styles at the top
        if _head_styles:
            raw = "\n".join(_head_styles) + "\n" + raw.strip()
        raw = raw.strip()

    from app.core.config import get_settings
    if not getattr(get_settings(), "enable_llm_code_gen_visuals", False):
        return "Error: Visual code generation chưa được bật (enable_llm_code_gen_visuals=False)."

    presentation_intent = _runtime_presentation_intent()
    if presentation_intent in {"article_figure", "chart_runtime"}:
        return (
            "Error: tool_create_visual_code khong phai lane dung cho article figure/chart runtime. "
            "Hay dung tool_generate_visual de tao figure giai thich hoac chart runtime chuan."
        )

    studio_lane = _runtime_studio_lane() or "app"
    artifact_kind = _runtime_artifact_kind() or "html_app"
    requested_visual_type = _runtime_metadata_text("visual_requested_type", "concept")
    resolved_visual_type = requested_visual_type if requested_visual_type in {
        "comparison", "process", "matrix", "architecture", "concept",
        "infographic", "chart", "timeline", "map_lite", "simulation",
        "quiz", "interactive_table", "react_app",
    } else "concept"
    resolved_renderer_kind = "app" if studio_lane in {"app", "widget"} else "inline_html"
    resolved_shell_variant = "immersive" if resolved_renderer_kind == "app" else "editorial"
    resolved_patch_strategy = "app_state" if resolved_renderer_kind == "app" else "replace_html"
    quality_profile = _runtime_quality_profile()

    raw = _maybe_upgrade_code_studio_output(
        raw,
        title=title,
        subtitle=subtitle,
        requested_visual_type=resolved_visual_type,
        studio_lane=studio_lane,
        artifact_kind=artifact_kind,
        quality_profile=quality_profile,
    )

    quality_error = _validate_code_studio_output(
        raw,
        requested_visual_type=resolved_visual_type,
        studio_lane=studio_lane,
        artifact_kind=artifact_kind,
        quality_profile=quality_profile,
    )
    if quality_error:
        return quality_error

    # Quality scoring gate — fires on non-trivial HTML (> 500 chars).
    # LLM output for simulations is typically 800-4000 chars before _wrap_html expansion.
    _raw_len = len(raw)
    if _raw_len > 500:
        _q_score, _q_deficiencies = _quality_score_visual_output(raw, resolved_visual_type)
        logger.info("[QUALITY_GATE] raw=%d chars, score=%d/10, type=%s, deficiencies=%d",
                    _raw_len, _q_score, resolved_visual_type, len(_q_deficiencies))
        if _q_score < 6 and _q_deficiencies:
            return (
                f"Quality score {_q_score}/10 — chua dat. Hay sua cac van de sau:\n"
                + "\n".join(f"- {d}" for d in _q_deficiencies)
                + "\n\nViet lai code_html hoan chinh hon."
            )

    # Wrap in design system if not a full HTML document
    if raw.lstrip().lower().startswith("<!doctype") or raw.lstrip().lower().startswith("<html"):
        final_html = raw
    else:
        css_parts = []
        body_content = raw
        style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
        for match in style_pattern.finditer(raw):
            css_parts.append(match.group(1))
        body_content = style_pattern.sub('', body_content).strip()
        final_html = _wrap_html("\n".join(css_parts), body_content, title, subtitle)

    safe_title = title.strip() or "Visual"
    safe_summary = f"{safe_title} — custom visual code"

    resolved_visual_session_id, resolved_operation = _apply_runtime_patch_defaults(
        visual_session_id=visual_session_id,
        operation="open",
    )

    payload = _normalize_visual_payload(
        visual_type=resolved_visual_type,
        spec={},
        title=safe_title,
        summary=safe_summary,
        subtitle=subtitle,
        visual_session_id=resolved_visual_session_id,
        operation=resolved_operation,
        renderer_kind=resolved_renderer_kind,
        shell_variant=resolved_shell_variant,
        patch_strategy=resolved_patch_strategy,
        narrative_anchor="after-lead",
        fallback_html=final_html,
        runtime_manifest={
            "ui_runtime": "html",
            "storage": False,
            "mcp_access": False,
            "file_export": studio_lane == "artifact",
            "shareability": "session" if studio_lane == "app" else "artifact",
        } if resolved_renderer_kind == "app" else None,
        metadata={
            "source_tool": "tool_create_visual_code",
            "presentation_intent": presentation_intent or "code_studio_app",
            "studio_lane": studio_lane,
            "artifact_kind": artifact_kind,
            "quality_profile": quality_profile,
            "renderer_contract": "host_shell",
            **({"code_studio_version": _runtime_code_studio_version()} if _runtime_code_studio_version() > 0 else {}),
        },
    )
    _log_visual_telemetry(
        "tool_create_visual_code",
        visual_id=payload.id,
        visual_session_id=payload.visual_session_id,
        renderer_kind=payload.renderer_kind,
        has_code_html=True,
    )
    return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)

tool_create_visual_code.description = (
    "Create app/widget/artifact UI with raw HTML/CSS/SVG/JS for Code Studio. "
    "Use only for code_studio_app or artifact lanes such as simulation, quiz, "
    "search/code widget, mini tool, or HTML app. Do not use as the default path "
    "for ordinary explanatory visuals or normal charts when tool_generate_visual is sufficient."
)


def get_visual_tools() -> list:
    """Return list of rich visual tools. Feature-gated by enable_chart_tools."""
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "enable_chart_tools", False):
        return []

    tools = []
    if getattr(settings, "enable_structured_visuals", False):
        tools.append(tool_generate_visual)
    # tool_create_visual_code: tool riêng cho LLM code-gen visuals
    if getattr(settings, "enable_llm_code_gen_visuals", False):
        tools.append(tool_create_visual_code)
    return tools
