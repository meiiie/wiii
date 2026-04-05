from typing import Any, Callable


def supports_auto_grouping_impl(visual_type: str, renderer_kind: str) -> bool:
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


def collect_story_points_impl(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
    *,
    clean_summary_text: Callable[[Any], str],
    spec_text: Callable[[dict[str, Any], str], str],
) -> list[str]:
    points: list[str] = []

    def add_point(value: Any) -> None:
        text = clean_summary_text(value)
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
        left_title = spec_text(left, "title")
        right_title = spec_text(right, "title")
        if left_title and right_title:
            add_point(f"{left_title} và {right_title} nên được đọc cạnh nhau để thấy độ lệch chính.")
        left_items = left.get("items") if isinstance(left.get("items"), list) else []
        right_items = right.get("items") if isinstance(right.get("items"), list) else []
        if left_items or right_items:
            add_point(f"Bên trái có {len(left_items)} điểm nhấn, bên phải có {len(right_items)} điểm nhấn.")
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
        center_title = spec_text(center, "title") or title
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


def build_takeaway_infographic_spec_impl(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
    *,
    collect_story_points: Callable[[str, dict[str, Any], str, str], list[str]],
    named_count: Callable[[Any], int],
) -> dict[str, Any]:
    points = collect_story_points(visual_type, spec, title, summary)
    if not points:
        points = [summary or f"{title} gồm một vài điểm nhấn để đọc nhanh."]

    stats: list[dict[str, Any]] = []
    if visual_type == "comparison":
        stats = [
            {"value": "2", "label": "Góc nhìn"},
            {"value": str(named_count((spec.get("left") or {}).get("items")) + named_count((spec.get("right") or {}).get("items"))), "label": "Điểm nhấn"},
        ]
    elif visual_type == "process":
        stats = [{"value": str(named_count(spec.get("steps"))), "label": "Bước"}]
    elif visual_type == "architecture":
        stats = [{"value": str(named_count(spec.get("layers"))), "label": "Lớp"}]
    elif visual_type == "concept":
        stats = [{"value": str(named_count(spec.get("branches"))), "label": "Nhánh"}]
    elif visual_type == "chart":
        stats = [
            {"value": str(named_count(spec.get("datasets")) or 1), "label": "Series"},
            {"value": str(named_count(spec.get("labels"))), "label": "Mốc đọc"},
        ]
    elif visual_type == "matrix":
        stats = [
            {"value": str(named_count(spec.get("rows"))), "label": "Hàng"},
            {"value": str(named_count(spec.get("cols"))), "label": "Cột"},
        ]
    elif visual_type == "timeline":
        stats = [{"value": str(named_count(spec.get("events"))), "label": "Mốc"}]
    elif visual_type == "map_lite":
        stats = [{"value": str(named_count(spec.get("regions"))), "label": "Khu vực"}]

    sections = [{"title": "Cần nhìn gì", "content": points[0]}]
    if len(points) > 1:
        sections.append({"title": "Vì sao quan trọng", "content": points[1]})
    sections.append({"title": "Điểm chốt", "content": points[-1]})

    return {"stats": stats, "sections": sections, "caption": summary or f"Điểm chốt từ {title}."}


def build_takeaway_claim_impl(visual_type: str, title: str, summary: str) -> str:
    if summary:
        return f"Điểm chốt của {title}: {summary}"
    if visual_type == "chart":
        return f"{title} cần được đọc như một xu hướng chứ không chỉ là một hình minh họa."
    if visual_type == "comparison":
        return f"{title} chốt lại sự khác biệt cần nhớ nhất giữa hai bên."
    return f"{title} cần được đọc thành một kết luận ngắn gọn sau figure chính."


def normalize_visual_query_text_impl(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().strip().split())


def estimate_query_figure_pressure_impl(query: str, *, normalize_visual_query_text: Callable[[Any], str]) -> int:
    normalized = normalize_visual_query_text(query)
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


def estimate_spec_figure_pressure_impl(visual_type: str, spec: dict[str, Any], *, named_count: Callable[[Any], int]) -> int:
    if visual_type == "comparison":
        left = spec.get("left", {}) if isinstance(spec.get("left"), dict) else {}
        right = spec.get("right", {}) if isinstance(spec.get("right"), dict) else {}
        return 1 if named_count(left.get("items")) + named_count(right.get("items")) >= 8 else 0
    if visual_type == "process":
        return 1 if named_count(spec.get("steps")) >= 5 else 0
    if visual_type == "architecture":
        return 1 if named_count(spec.get("layers")) >= 4 or named_count(spec.get("links")) >= 4 else 0
    if visual_type == "concept":
        return 1 if named_count(spec.get("branches")) >= 4 else 0
    if visual_type == "infographic":
        section_count = named_count(spec.get("sections"))
        stat_count = named_count(spec.get("stats"))
        return 1 if section_count >= 4 or (section_count >= 3 and stat_count >= 2) else 0
    if visual_type == "chart":
        label_count = named_count(spec.get("labels"))
        dataset_count = named_count(spec.get("datasets"))
        return 1 if (label_count >= 5 and dataset_count >= 2) or label_count >= 7 else 0
    if visual_type == "matrix":
        return 1 if named_count(spec.get("rows")) * named_count(spec.get("cols")) >= 16 else 0
    if visual_type == "timeline":
        return 1 if named_count(spec.get("events")) >= 5 else 0
    if visual_type == "map_lite":
        return 1 if named_count(spec.get("regions")) >= 4 else 0
    return 0


def plan_auto_group_figure_budget_impl(
    *,
    visual_type: str,
    spec: dict[str, Any],
    renderer_kind: str,
    operation: str,
    supports_auto_grouping: Callable[[str, str], bool],
    get_runtime_visual_metadata: Callable[[], dict[str, Any]],
    estimate_query_figure_pressure: Callable[[str], int],
    estimate_spec_figure_pressure: Callable[[str, dict[str, Any]], int],
) -> int:
    if operation != "open":
        return 1
    if spec.get("allow_single_figure") or spec.get("disable_auto_group"):
        return 1
    if isinstance(spec.get("figures"), list) and spec.get("figures"):
        return 1
    if not supports_auto_grouping(visual_type, renderer_kind):
        return 1
    metadata = get_runtime_visual_metadata()
    if not (metadata.get("visual_force_tool") and str(metadata.get("visual_intent_mode") or "") == "template"):
        return 1
    query = str(metadata.get("visual_user_query") or "")
    budget = 1
    budget += estimate_query_figure_pressure(query)
    budget += estimate_spec_figure_pressure(visual_type, spec)
    return max(1, min(3, budget))


def build_bridge_infographic_spec_impl(
    visual_type: str,
    spec: dict[str, Any],
    title: str,
    summary: str,
    *,
    build_takeaway_infographic_spec: Callable[[str, dict[str, Any], str, str], dict[str, Any]],
    collect_story_points: Callable[[str, dict[str, Any], str, str], list[str]],
) -> dict[str, Any]:
    base = build_takeaway_infographic_spec(visual_type, spec, title, summary)
    points = collect_story_points(visual_type, spec, title, summary)
    if not points:
        points = [summary or f"{title} cần một nhóm điểm nhấn để đọc theo từng lớp."]
    sections = [{"title": "Cần để mắt tới", "content": points[0]}]
    if len(points) > 1:
        sections.append({"title": "Cơ chế chính", "content": points[1]})
    if len(points) > 2:
        sections.append({"title": "Dấu hiệu cần nhớ", "content": points[2]})
    return {**base, "sections": sections, "caption": f"Cách đọc {title} qua một vài điểm nhấn chính."}


def should_auto_group_visual_request_impl(
    *,
    visual_type: str,
    spec: dict[str, Any],
    renderer_kind: str,
    operation: str,
    plan_auto_group_figure_budget: Callable[..., int],
) -> bool:
    return plan_auto_group_figure_budget(
        visual_type=visual_type,
        spec=spec,
        renderer_kind=renderer_kind,
        operation=operation,
    ) > 1
