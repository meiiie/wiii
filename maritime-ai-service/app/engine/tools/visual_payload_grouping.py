from typing import Any, Callable


def apply_runtime_patch_defaults_impl(
    *,
    visual_session_id: str,
    operation: str,
    get_runtime_context: Callable[[], Any],
) -> tuple[str, str]:
    runtime = get_runtime_context()
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

    resolved_session_id = preferred_session_id
    if resolved_operation == "open":
        resolved_operation = "patch"

    return resolved_session_id, resolved_operation


def build_auto_grouped_payloads_impl(
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
    plan_auto_group_figure_budget: Callable[..., int],
    infer_pedagogical_role: Callable[[str, dict[str, Any], str], str],
    sanitize_summary_candidate: Callable[[str, str, str], str],
    default_visual_summary: Callable[[str, str, dict[str, Any] | None], str],
    generate_figure_group_id: Callable[[str], str],
    default_visual_claim: Callable[[str, str, str, dict[str, Any]], str],
    collect_story_points: Callable[[str, dict[str, Any], str, str], list[str]],
    build_bridge_infographic_spec: Callable[[str, dict[str, Any], str, str], dict[str, Any]],
    build_takeaway_claim: Callable[[str, str, str], str],
    normalize_visual_payload: Callable[..., Any],
) -> list[Any]:
    figure_budget = plan_auto_group_figure_budget(
        visual_type=visual_type,
        spec=spec,
        renderer_kind=renderer_kind,
        operation=operation,
    )
    if figure_budget <= 1:
        return []

    primary_role = infer_pedagogical_role(visual_type, spec, "")
    secondary_role = "conclusion" if primary_role != "conclusion" else "result"
    resolved_title = title.strip() or visual_type.replace("_", " ").strip().title() or "Inline visual"
    resolved_summary = sanitize_summary_candidate(summary, visual_type, resolved_title) or default_visual_summary(
        visual_type,
        resolved_title,
        spec,
    )
    group_id = generate_figure_group_id(visual_type)
    bridge_claim = collect_story_points(visual_type, spec, resolved_title, resolved_summary)
    bridge_role = "mechanism" if primary_role in {"problem", "comparison", "benchmark"} else "result"
    figures: list[dict[str, Any]] = [
        {
            "type": visual_type,
            "title": resolved_title,
            "summary": resolved_summary,
            "subtitle": subtitle,
            "pedagogical_role": primary_role,
            "claim": default_visual_claim(visual_type, resolved_title, resolved_summary, spec),
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
            "spec": build_bridge_infographic_spec(
                visual_type,
                spec,
                resolved_title,
                resolved_summary,
            ),
        })

    figures.append({
        "type": "infographic",
        "title": f"Điểm chốt từ {resolved_title}",
        "summary": build_takeaway_claim(visual_type, resolved_title, resolved_summary),
        "pedagogical_role": secondary_role,
        "claim": build_takeaway_claim(visual_type, resolved_title, resolved_summary),
        "narrative_anchor": "after-figure-2" if figure_budget >= 3 else "after-figure-1",
        "spec": {
            **build_bridge_infographic_spec(
                visual_type,
                spec,
                resolved_title,
                resolved_summary,
            ),
            "caption": build_takeaway_claim(visual_type, resolved_title, resolved_summary),
        },
    })

    figure_total = len(figures)
    payloads: list[Any] = []
    for index, figure in enumerate(figures, start=1):
        payloads.append(
            normalize_visual_payload(
                visual_type=str(figure.get("type") or visual_type),
                spec=figure.get("spec") if isinstance(figure.get("spec"), dict) else {},
                title=str(figure.get("title") or resolved_title),
                summary=str(figure.get("summary") or resolved_summary),
                subtitle=str(figure.get("subtitle") or subtitle),
                visual_session_id="",
                operation=operation,
                renderer_kind=renderer_kind,
                shell_variant=shell_variant,
                patch_strategy=patch_strategy,
                narrative_anchor=str(figure.get("narrative_anchor") or "after-lead"),
                runtime_manifest=runtime_manifest,
                figure_group_id=group_id,
                figure_index=index,
                figure_total=figure_total,
                pedagogical_role=str(figure.get("pedagogical_role") or ""),
                claim=str(figure.get("claim") or ""),
            )
        )
    return payloads


def build_multi_figure_payloads_impl(
    *,
    default_visual_type: str,
    raw_group: dict[str, Any],
    generate_figure_group_id: Callable[[str], str],
    builders: dict[str, Callable[[dict[str, Any], str], str]],
    logger: Any,
    resolve_renderer_kind: Callable[[str, dict[str, Any], str], str],
    resolve_fallback_html: Callable[[str, dict[str, Any], str, str | None], str | None],
    normalize_visual_payload: Callable[..., Any],
) -> list[Any]:
    figures = raw_group.get("figures")
    if not isinstance(figures, list) or not figures:
        return []

    figure_total = len(figures)
    group_id = str(raw_group.get("figure_group_id") or generate_figure_group_id(default_visual_type))
    payloads: list[Any] = []

    for index, figure in enumerate(figures, start=1):
        if not isinstance(figure, dict):
            continue

        figure_visual_type = str(figure.get("type") or figure.get("visual_type") or default_visual_type or "comparison").strip()
        figure_spec = figure.get("spec") if isinstance(figure.get("spec"), dict) else {}
        if not isinstance(figure_spec, dict):
            figure_spec = {}
        figure_title = str(figure.get("title") or raw_group.get("title") or "")
        builder = builders.get(figure_visual_type)
        builder_html = None
        if builder is not None:
            try:
                builder_html = builder(figure_spec, figure_title)
            except Exception as exc:
                logger.warning("Structured visual fallback HTML failed for grouped type=%s: %s", figure_visual_type, exc)
        resolved_renderer_kind = resolve_renderer_kind(
            figure_visual_type,
            figure_spec,
            str(figure.get("renderer_kind") or raw_group.get("renderer_kind") or ""),
        )
        fallback_html = str(figure.get("fallback_html") or "") or resolve_fallback_html(
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
            normalize_visual_payload(
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
