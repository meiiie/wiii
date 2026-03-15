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

LEGACY_SANDBOX_VISUAL_TYPES = (
    "simulation",
    "quiz",
    "interactive_table",
    "react_app",
)


class VisualPayloadV1(BaseModel):
    """Structured inline visual contract for streaming-first rendering."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    visual_session_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    renderer_kind: Literal["template", "inline_html", "app"] = "template"
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
        r"^structured visual san sang:\s*",
        r"^structured visual summary\s*",
        rf"^visual\s+{re.escape(visual_type).replace('_', '[_ ]')}\s+de tom tat nhanh noi dung:\s*",
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
        left_title = _clean_summary_text(left.get("title")) or "goc nhin ben trai"
        right_title = _clean_summary_text(right.get("title")) or "goc nhin ben phai"
        return f"Dat {left_title} canh {right_title} de thay diem khac biet chinh."

    if visual_type == "process":
        step_count = _named_count(safe_spec.get("steps"))
        if step_count > 0:
            return f"Quy trinh duoc chia thanh {step_count} buoc lien tiep de de theo doi."

    if visual_type == "matrix":
        row_count = _named_count(safe_spec.get("rows"))
        col_count = _named_count(safe_spec.get("cols"))
        if row_count and col_count:
            return f"Ma tran nay cho thay muc do lien he giua {row_count} hang va {col_count} cot."

    if visual_type == "architecture":
        layer_count = _named_count(safe_spec.get("layers"))
        if layer_count:
            return f"Kien truc duoc tach thanh {layer_count} lop chinh va cach chung ket noi voi nhau."

    if visual_type == "concept":
        center = safe_spec.get("center") if isinstance(safe_spec.get("center"), dict) else {}
        center_title = _clean_summary_text(center.get("title")) or safe_title
        return f"{center_title} duoc mo rong thanh cac nhanh chinh de de dinh vi y tuong."

    if visual_type == "infographic":
        stat_count = _named_count(safe_spec.get("stats"))
        section_count = _named_count(safe_spec.get("sections"))
        if stat_count or section_count:
            return f"Khung nhin nay gom {stat_count or 0} chi so va {section_count or 0} diem nhan de doc nhanh."

    if visual_type == "chart":
        label_count = _named_count(safe_spec.get("labels"))
        if label_count:
            return f"Bieu do nay lam ro xu huong qua {label_count} moc chinh."

    if visual_type == "timeline":
        event_count = _named_count(safe_spec.get("events"))
        if event_count:
            return f"Dong thoi gian nay gom {event_count} moc de theo doi su chuyen dich theo thu tu."

    if visual_type == "map_lite":
        region_count = _named_count(safe_spec.get("regions"))
        if region_count:
            return f"Ban do nay nhan vao {region_count} khu vuc de so sanh nhanh."

    return f"{safe_title} trong mot khung nhin truc quan de doc nhanh."


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
            return f"Dat {left} canh {right} de thay ra su khac biet chinh."
    return f"{title} lam ro mot y chinh trong loi giai dang theo."


def _get_runtime_visual_metadata() -> dict[str, Any]:
    runtime = get_current_tool_runtime_context()
    if runtime and isinstance(runtime.metadata, dict):
        return runtime.metadata
    return {}


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
            add_point(f"{left_title} va {right_title} nen duoc doc canh nhau de thay do lech chinh.")
        left_items = left.get("items") if isinstance(left.get("items"), list) else []
        right_items = right.get("items") if isinstance(right.get("items"), list) else []
        if left_items or right_items:
            add_point(
                f"Ben trai co {len(left_items)} diem nhan, ben phai co {len(right_items)} diem nhan."
            )

    elif visual_type == "process":
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        labels = [
            str((step if isinstance(step, dict) else {}).get("title") or f"Buoc {index + 1}")
            for index, step in enumerate(steps[:3])
        ]
        if labels:
            add_point("Thu tu xu ly: " + " -> ".join(labels))

    elif visual_type == "architecture":
        layers = spec.get("layers", []) if isinstance(spec.get("layers"), list) else []
        labels = [
            str((layer if isinstance(layer, dict) else {}).get("name") or f"Lop {index + 1}")
            for index, layer in enumerate(layers[:4])
        ]
        if labels:
            add_point("Dong xu ly di qua cac lop: " + " -> ".join(labels))

    elif visual_type == "concept":
        center = spec.get("center", {}) if isinstance(spec.get("center"), dict) else {}
        branches = spec.get("branches", []) if isinstance(spec.get("branches"), list) else []
        center_title = _spec_text(center, "title") or title
        branch_titles = [
            str((branch if isinstance(branch, dict) else {}).get("title") or f"Nhanh {index + 1}")
            for index, branch in enumerate(branches[:3])
        ]
        if center_title and branch_titles:
            add_point(f"{center_title} duoc mo rong qua: {', '.join(branch_titles)}.")

    elif visual_type == "chart":
        datasets = spec.get("datasets", []) if isinstance(spec.get("datasets"), list) else []
        labels = spec.get("labels", []) if isinstance(spec.get("labels"), list) else []
        dataset_labels = [
            str((dataset if isinstance(dataset, dict) else {}).get("label") or f"Series {index + 1}")
            for index, dataset in enumerate(datasets[:3])
        ]
        if dataset_labels:
            add_point("Bieu do theo doi cac duong: " + ", ".join(dataset_labels) + ".")
        if labels:
            add_point(f"Truc x gom {len(labels)} moc chinh de doc xu huong.")

    elif visual_type == "matrix":
        rows = spec.get("rows", []) if isinstance(spec.get("rows"), list) else []
        cols = spec.get("cols", []) if isinstance(spec.get("cols"), list) else []
        if rows or cols:
            add_point(f"Ma tran nay duoc doc qua {len(rows)} hang va {len(cols)} cot.")

    elif visual_type == "timeline":
        events = spec.get("events", []) if isinstance(spec.get("events"), list) else []
        labels = [
            str((event if isinstance(event, dict) else {}).get("title") or (event if isinstance(event, dict) else {}).get("label") or f"Moc {index + 1}")
            for index, event in enumerate(events[:4])
        ]
        if labels:
            add_point("Cac moc can theo doi: " + " -> ".join(labels))

    elif visual_type == "map_lite":
        regions = spec.get("regions", []) if isinstance(spec.get("regions"), list) else []
        labels = [
            str((region if isinstance(region, dict) else {}).get("label") or f"Khu vuc {index + 1}")
            for index, region in enumerate(regions[:4])
        ]
        if labels:
            add_point("Ban do dang nhan vao: " + ", ".join(labels) + ".")

    return points[:3]


def _build_takeaway_infographic_spec(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
) -> dict[str, Any]:
    points = _collect_story_points(visual_type, spec, title, summary)
    if not points:
        points = [summary or f"{title} gom mot vai diem nhan de doc nhanh."]

    stats: list[dict[str, Any]] = []
    if visual_type == "comparison":
        stats = [
            {"value": "2", "label": "Goc nhin"},
            {"value": str(_named_count((spec.get("left") or {}).get("items")) + _named_count((spec.get("right") or {}).get("items"))), "label": "Diem nhan"},
        ]
    elif visual_type == "process":
        stats = [{"value": str(_named_count(spec.get("steps"))), "label": "Buoc"}]
    elif visual_type == "architecture":
        stats = [{"value": str(_named_count(spec.get("layers"))), "label": "Lop"}]
    elif visual_type == "concept":
        stats = [{"value": str(_named_count(spec.get("branches"))), "label": "Nhanh"}]
    elif visual_type == "chart":
        stats = [
            {"value": str(_named_count(spec.get("datasets")) or 1), "label": "Series"},
            {"value": str(_named_count(spec.get("labels"))), "label": "Moc doc"},
        ]
    elif visual_type == "matrix":
        stats = [
            {"value": str(_named_count(spec.get("rows"))), "label": "Hang"},
            {"value": str(_named_count(spec.get("cols"))), "label": "Cot"},
        ]
    elif visual_type == "timeline":
        stats = [{"value": str(_named_count(spec.get("events"))), "label": "Moc"}]
    elif visual_type == "map_lite":
        stats = [{"value": str(_named_count(spec.get("regions"))), "label": "Khu vuc"}]

    sections = [
        {"title": "Can nhin gi", "content": points[0]},
    ]
    if len(points) > 1:
        sections.append({"title": "Vi sao quan trong", "content": points[1]})
    sections.append({
        "title": "Diem chot",
        "content": points[-1],
    })

    return {
        "stats": stats,
        "sections": sections,
        "caption": summary or f"Diem chot tu {title}.",
    }


def _build_takeaway_claim(
    visual_type: str,
    title: str,
    summary: str,
    spec: dict[str, Any],
) -> str:
    if summary:
        return f"Diem chot cua {title}: {summary}"
    if visual_type == "chart":
        return f"{title} can duoc doc nhu mot xu huong chu khong chi la mot hinh minh hoa."
    if visual_type == "comparison":
        return f"{title} chot lai su khac biet can nho nhat giua hai ben."
    return f"{title} can duoc doc thanh mot ket luan ngan gon sau figure chinh."


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
        points = [summary or f"{title} can mot nhom diem nhan de doc theo tung lop."]

    sections = [{"title": "Can de mat toi", "content": points[0]}]
    if len(points) > 1:
        sections.append({"title": "Co che chinh", "content": points[1]})
    if len(points) > 2:
        sections.append({"title": "Dau hieu can nho", "content": points[2]})

    return {
        **base,
        "sections": sections,
        "caption": f"Cach doc {title} qua mot vai diem nhan chinh.",
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
            "title": f"Cach doc {resolved_title}",
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
        "title": f"Diem chot tu {resolved_title}",
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
    if visual_type in LEGACY_SANDBOX_VISUAL_TYPES:
        return "app"
    if any(isinstance(spec.get(key), str) and str(spec.get(key)).strip() for key in ("html", "markup", "custom_html", "template_html")):
        return "inline_html"
    return "template"


def _infer_runtime(renderer_kind: str, visual_type: str, spec: dict[str, Any]) -> str:
    if renderer_kind == "template":
        return "svg"
    if renderer_kind == "app":
        ui_runtime = str(spec.get("ui_runtime") or "")
        return "sandbox_react" if visual_type == "react_app" or ui_runtime == "react" else "sandbox_html"
    return "sandbox_html"


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


def _resolve_fallback_html(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    builder_output: str | None,
) -> str | None:
    if builder_output:
        return builder_output
    for key in ("html", "markup", "custom_html", "template_html", "app_html"):
        value = spec.get(key)
        if isinstance(value, str) and value.strip():
            return value
    if visual_type == "react_app":
        code = spec.get("code")
        if isinstance(code, str) and code.strip():
            return _build_react_app_html(spec, title)
    return None


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
    resolved_renderer_kind = _infer_renderer_kind(visual_type, spec, renderer_kind)
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
            "title": "Diem chot",
            "body": resolved_summary,
            "tone": "accent",
        }]
    lifecycle_event = "visual_patch" if operation == "patch" else "visual_open"
    resolved_metadata = {
        "contract_version": "visual_payload_v3",
        "source_tool": "tool_generate_visual",
        "figure_group_id": figure_group_id.strip() or spec.get("figure_group_id") or "",
        "pedagogical_role": resolved_pedagogical_role,
        **(metadata or {}),
    }
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
    coerced["renderer_kind"] = _infer_renderer_kind(
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
    preferred_session_id = str(metadata.get("preferred_visual_session_id") or "").strip()

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
        resolved_renderer_kind = _infer_renderer_kind(
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
  padding: 8px 4px; font-size: 14px;
}
.widget-title {
  font-size: 15px; font-weight: 600; text-align: left;
  margin-bottom: 12px; color: var(--text); padding-left: 2px;
}
.widget-subtitle {
  font-size: 12px; color: var(--text2); text-align: left;
  margin-top: -8px; margin-bottom: 12px; padding-left: 2px;
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
  background: transparent; padding: 16px 14px;
  border-top: 2px solid color-mix(in srgb, var(--side-color) 40%, transparent);
}
.side-header { margin-bottom: 10px; }
.side-title { font-size: 14px; font-weight: 700; color: var(--side-color); }
.side-sub { font-size: 11px; color: var(--text3); display: block; margin-top: 2px; }
.side-items { list-style: none; padding: 0; }
.side-items li {
  padding: 5px 0; border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
  font-size: 13px; color: var(--text2); line-height: 1.55;
}
.side-items li:last-child { border-bottom: none; }
.item-icon { font-size: 14px; }
.side-svg { display: flex; justify-content: center; margin: 12px 0; }
.side-svg svg { max-width: 100%; height: auto; }
.side-desc { font-size: 12px; color: var(--text3); margin-top: 8px; font-style: italic; }
.comp-divider {
  display: flex; align-items: center; justify-content: center; padding: 0 8px;
}
.comp-divider svg { width: 24px; height: 24px; opacity: 0.35; }
.comp-note {
  grid-column: 1 / -1; text-align: center; font-size: 11px; color: var(--text3);
  margin-top: 10px; padding: 6px 0; border-top: 1px solid color-mix(in srgb, var(--border) 40%, transparent);
}
@media (max-width: 500px) {
  .comparison { grid-template-columns: 1fr; gap: 4px; }
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
) -> str:
    """Generate a structured visual payload for inline visuals or app runtime.

    Use this as the PRIMARY path for Wiii Visual Runtime V3:
    - template: native React + SVG/CSS explanatory visuals
    - inline_html: bespoke HTML/CSS/JS visuals inside Wiii shell
    - app: MCP-style iframe app runtime for simulations and mini tools

    Unlike tool_generate_rich_visual, this tool returns JSON payload data for the
    frontend visual renderer. Do NOT copy this payload verbatim into prose.
    """
    valid_types = CORE_STRUCTURED_VISUAL_TYPES + LEGACY_SANDBOX_VISUAL_TYPES
    if visual_type not in valid_types:
        valid = ", ".join(valid_types)
        return f"Error: visual_type '{visual_type}' khong hop le cho visual runtime. Chon mot trong: {valid}"

    if operation not in {"open", "patch"}:
        return "Error: operation phai la 'open' hoac 'patch'."

    try:
        spec = json.loads(spec_json)
        if not isinstance(spec, dict):
            return "Error: spec_json phai la mot JSON object."
    except json.JSONDecodeError as exc:
        return f"Error: JSON khong hop le: {exc}"

    runtime_manifest = None
    if runtime_manifest_json.strip():
        try:
            runtime_manifest = json.loads(runtime_manifest_json)
            if not isinstance(runtime_manifest, dict):
                return "Error: runtime_manifest_json phai la mot JSON object."
        except json.JSONDecodeError as exc:
            return f"Error: runtime_manifest_json khong hop le: {exc}"

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
            return "Error: Khong the tao nhom figure tu spec_json.figures."

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

    resolved_renderer_kind = _infer_renderer_kind(visual_type, spec, renderer_kind)
    resolved_visual_session_id, resolved_operation = _apply_runtime_patch_defaults(
        visual_session_id=visual_session_id,
        operation=operation,
    )
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

    fallback_html = _resolve_fallback_html(visual_type, spec, title, builder_html)

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
def tool_generate_rich_visual(
    visual_type: str,
    spec_json: str,
    title: str = "",
) -> str:
    """Generate a rich interactive visual widget (HTML+CSS+JS) rendered INLINE in chat.

    Creates Claude-level interactive widgets: comparisons, simulations, quizzes,
    interactive tables, architecture diagrams, and more. Returns a ```widget
    code block that the frontend renders as a fully interactive visual.

    PRIORITY: Use this only as a legacy/fallback sandbox runtime for simulation,
    quiz, interactive_table, react_app, or highly bespoke HTML/JS cases.
    For explanatory visuals, comparisons, article-style charts, and inline figures,
    prefer tool_generate_visual.
    Use tool_generate_interactive_chart only for standalone numeric dashboard charts.
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

    tools = []
    if getattr(settings, "enable_structured_visuals", False):
        tools.append(tool_generate_visual)
    tools.append(tool_generate_rich_visual)
    return tools
