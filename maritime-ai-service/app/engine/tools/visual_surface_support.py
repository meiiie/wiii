import json
import re
import uuid
from typing import Any, Callable


def default_visual_title_impl(visual_type: str) -> str:
    return visual_type.replace("_", " ").strip().title() or "Inline visual"


def generate_figure_group_id_impl(visual_type: str) -> str:
    slug = (visual_type or "figure").replace("_", "-").strip("-") or "figure"
    return f"fg-{slug}-{uuid.uuid4().hex[:10]}"


def clean_summary_text_impl(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def spec_text_impl(
    spec: dict[str, Any],
    keys: tuple[str, ...],
    *,
    clean_summary_text: Callable[[Any], str],
) -> str:
    for key in keys:
        value = spec.get(key)
        cleaned = clean_summary_text(value)
        if cleaned:
            return cleaned
    return ""


def named_count_impl(items: Any) -> int:
    return len(items) if isinstance(items, list) else 0


def sanitize_summary_candidate_impl(
    value: str,
    visual_type: str,
    title: str,
    *,
    clean_summary_text: Callable[[Any], str],
) -> str:
    cleaned = clean_summary_text(value)
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

    if clean_summary_text(cleaned).lower() == clean_summary_text(title).lower():
        return ""
    return cleaned


def default_visual_summary_impl(
    visual_type: str,
    title: str,
    spec: dict[str, Any] | None = None,
    *,
    default_visual_title: Callable[[str], str],
    spec_text: Callable[..., str],
    clean_summary_text: Callable[[Any], str],
    named_count: Callable[[Any], int],
) -> str:
    safe_title = title.strip() or default_visual_title(visual_type)
    safe_spec = spec if isinstance(spec, dict) else {}

    direct_hint = spec_text(
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
        left_title = clean_summary_text(left.get("title")) or "góc nhìn bên trái"
        right_title = clean_summary_text(right.get("title")) or "góc nhìn bên phải"
        return f"Đặt {left_title} cạnh {right_title} để thấy điểm khác biệt chính."

    if visual_type == "process":
        step_count = named_count(safe_spec.get("steps"))
        if step_count > 0:
            return f"Quy trình được chia thành {step_count} bước liên tiếp để dễ theo dõi."

    if visual_type == "matrix":
        row_count = named_count(safe_spec.get("rows"))
        col_count = named_count(safe_spec.get("cols"))
        if row_count and col_count:
            return f"Ma trận này cho thấy mức độ liên hệ giữa {row_count} hàng và {col_count} cột."

    if visual_type == "architecture":
        layer_count = named_count(safe_spec.get("layers"))
        if layer_count:
            return f"Kiến trúc được tách thành {layer_count} lớp chính và cách chúng kết nối với nhau."

    if visual_type == "concept":
        center = safe_spec.get("center") if isinstance(safe_spec.get("center"), dict) else {}
        center_title = clean_summary_text(center.get("title")) or safe_title
        return f"{center_title} được mở rộng thành các nhánh chính để dễ định vị ý tưởng."

    if visual_type == "infographic":
        stat_count = named_count(safe_spec.get("stats"))
        section_count = named_count(safe_spec.get("sections"))
        if stat_count or section_count:
            return f"Khung nhìn này gồm {stat_count or 0} chỉ số và {section_count or 0} điểm nhấn để đọc nhanh."

    if visual_type == "chart":
        label_count = named_count(safe_spec.get("labels"))
        if label_count:
            return f"Biểu đồ này làm rõ xu hướng qua {label_count} mốc chính."

    if visual_type == "timeline":
        event_count = named_count(safe_spec.get("events"))
        if event_count:
            return f"Dòng thời gian này gồm {event_count} mốc để theo dõi sự chuyển dịch theo thứ tự."

    if visual_type == "map_lite":
        region_count = named_count(safe_spec.get("regions"))
        if region_count:
            return f"Bản đồ này nhấn vào {region_count} khu vực để so sánh nhanh."

    return f"{safe_title} trong một khung nhìn trực quan để đọc nhanh."


def infer_pedagogical_role_impl(
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


def infer_chrome_mode_impl(
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


def default_visual_claim_impl(
    visual_type: str,
    title: str,
    summary: str,
    spec: dict[str, Any],
    *,
    clean_summary_text: Callable[[Any], str],
    spec_text: Callable[..., str],
) -> str:
    explicit = clean_summary_text(spec.get("claim"))
    if explicit:
        return explicit
    if summary:
        return summary
    if visual_type == "comparison":
        left = spec_text(spec.get("left") if isinstance(spec.get("left"), dict) else {}, "title")
        right = spec_text(spec.get("right") if isinstance(spec.get("right"), dict) else {}, "title")
        if left and right:
            return f"Đặt {left} cạnh {right} để thấy ra sự khác biệt chính."
    return f"{title} làm rõ một ý chính trong lời giải đang theo."


def log_visual_telemetry_impl(
    event_name: str,
    *,
    logger: Any,
    fields: dict[str, Any] | None = None,
) -> None:
    if fields:
        logger.info("[VISUAL_TELEMETRY] %s %s", event_name, json.dumps(fields, ensure_ascii=False, sort_keys=True))
    else:
        logger.info("[VISUAL_TELEMETRY] %s", event_name)


def slugify_fragment_impl(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
    cleaned = cleaned.strip("-")
    return cleaned or "item"


def generate_visual_session_id_impl(
    visual_type: str,
    *,
    slugify_fragment: Callable[[str], str],
) -> str:
    return f"vs-{slugify_fragment(visual_type)}-{uuid.uuid4().hex[:10]}"


def should_keep_structured_renderer_impl(
    requested: str = "",
    *,
    runtime_presentation_intent: Callable[[], str],
    runtime_metadata_text: Callable[[str, str], str],
) -> bool:
    presentation_intent = runtime_presentation_intent()
    if presentation_intent not in {"article_figure", "chart_runtime"}:
        return False
    if requested.strip() == "inline_html":
        return False
    return runtime_metadata_text("visual_intent_mode", "") != "inline_html"


def resolve_renderer_kind_impl(
    visual_type: str,
    spec: dict[str, Any],
    requested: str = "",
    *,
    should_keep_structured_renderer: Callable[[str], bool],
    runtime_presentation_intent: Callable[[], str],
    llm_first_visual_codegen_enabled: Callable[[], bool],
) -> str:
    candidate = requested.strip()
    if candidate in {"template", "inline_html", "app", "recharts"}:
        return candidate
    if should_keep_structured_renderer(candidate):
        return "template"
    if any(
        isinstance(spec.get(key), str) and str(spec.get(key)).strip()
        for key in ("html", "markup", "custom_html", "template_html")
    ):
        return "inline_html"
    if runtime_presentation_intent() in {"article_figure", "chart_runtime"}:
        return "inline_html" if llm_first_visual_codegen_enabled() else "template"
    return "template"
