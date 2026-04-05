import uuid
from typing import Any, Callable


def build_artifact_handoff_impl(
    *,
    presentation_intent: str,
    visual_type: str,
    title: str,
    summary: str,
    default_visual_title: Callable[[str], str],
    clean_summary_text: Callable[[Any], str],
) -> dict[str, Any]:
    if presentation_intent == "artifact":
        return {
            "available": False,
            "mode": "none",
            "label": None,
            "prompt": None,
        }

    clean_title = clean_summary_text(title) or default_visual_title(visual_type)
    clean_summary = clean_summary_text(summary)

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


def normalize_visual_payload_impl(
    *,
    payload_class: type,
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
    default_visual_title: Callable[[str], str] = None,
    sanitize_summary_candidate: Callable[[str, str, str], str] = None,
    default_visual_summary: Callable[[str, str, dict[str, Any] | None], str] = None,
    resolve_renderer_kind: Callable[[str, dict[str, Any], str], str] = None,
    infer_runtime: Callable[[str, str, dict[str, Any]], str] = None,
    infer_shell_variant: Callable[[str, str], str] = None,
    infer_patch_strategy: Callable[[str, str], str] = None,
    infer_pedagogical_role: Callable[[str, dict[str, Any], str], str] = None,
    infer_chrome_mode: Callable[[str, str, str], str] = None,
    clean_summary_text: Callable[[Any], str] = None,
    default_visual_claim: Callable[[str, str, str, dict[str, Any]], str] = None,
    build_controls: Callable[[str, dict[str, Any]], list[dict[str, Any]]] = None,
    build_scene: Callable[[str, dict[str, Any], str], dict[str, Any]] = None,
    build_annotations: Callable[[str, dict[str, Any]], list[dict[str, Any]]] = None,
    metadata_text: Callable[[dict[str, Any] | None, str, str], str] = None,
    runtime_presentation_intent: Callable[[], str] = None,
    runtime_renderer_contract: Callable[[], str] = None,
    runtime_quality_profile: Callable[[], str] = None,
    runtime_studio_lane: Callable[[], str] = None,
    runtime_artifact_kind: Callable[[], str] = None,
    runtime_preferred_render_surface: Callable[[], str] = None,
    infer_scene_render_surface: Callable[[str, str], str] = None,
    runtime_planning_profile: Callable[[], str] = None,
    runtime_thinking_floor: Callable[[], str] = None,
    runtime_critic_policy: Callable[[], str] = None,
    runtime_living_expression_mode: Callable[[], str] = None,
    get_runtime_visual_metadata: Callable[[], dict[str, Any]] = None,
    build_artifact_handoff: Callable[..., dict[str, Any]] = None,
    enrich_scene_contract: Callable[..., dict[str, Any]] = None,
    generate_visual_session_id: Callable[[str], str] = None,
    generate_figure_group_id: Callable[[str], str] = None,
    infer_interaction_mode: Callable[[list[dict[str, Any]]], str] = None,
    build_runtime_manifest: Callable[..., dict[str, Any] | None] = None,
) -> Any:
    resolved_title = title.strip() or default_visual_title(visual_type)
    resolved_summary = sanitize_summary_candidate(summary, visual_type, resolved_title) or default_visual_summary(
        visual_type,
        resolved_title,
        spec,
    )
    resolved_subtitle = subtitle.strip() or None
    resolved_renderer_kind = resolve_renderer_kind(visual_type, spec, renderer_kind)
    resolved_runtime = runtime.strip() or infer_runtime(resolved_renderer_kind, visual_type, spec)
    resolved_shell_variant = infer_shell_variant(resolved_renderer_kind, shell_variant)
    resolved_patch_strategy = infer_patch_strategy(resolved_renderer_kind, patch_strategy)
    resolved_pedagogical_role = infer_pedagogical_role(visual_type, spec, pedagogical_role)
    resolved_chrome_mode = infer_chrome_mode(
        resolved_renderer_kind,
        resolved_shell_variant,
        chrome_mode,
    )
    resolved_claim = clean_summary_text(claim) or default_visual_claim(
        visual_type,
        resolved_title,
        resolved_summary,
        spec,
    )
    resolved_controls = build_controls(visual_type, spec)
    resolved_scene = build_scene(visual_type, spec, resolved_title)
    resolved_annotations = build_annotations(visual_type, spec)
    if not resolved_annotations:
        resolved_annotations = [{
            "id": "takeaway",
            "title": "Điểm chốt",
            "body": resolved_summary,
            "tone": "accent",
        }]
    lifecycle_event = "visual_patch" if operation == "patch" else "visual_open"
    metadata = metadata or {}
    metadata_presentation_intent = metadata_text(metadata, "presentation_intent", "")
    resolved_presentation_intent = runtime_presentation_intent() or metadata_presentation_intent
    if not resolved_presentation_intent or resolved_presentation_intent == "text":
        if resolved_renderer_kind == "app":
            resolved_presentation_intent = "code_studio_app"
        elif visual_type == "chart":
            resolved_presentation_intent = "chart_runtime"
        else:
            resolved_presentation_intent = "article_figure"
    resolved_renderer_contract = runtime_renderer_contract() or metadata_text(metadata, "renderer_contract", "")
    if not resolved_renderer_contract:
        resolved_renderer_contract = "host_shell" if resolved_renderer_kind == "app" else (
            "chart_runtime" if resolved_presentation_intent == "chart_runtime" else "article_figure"
        )
    resolved_quality_profile = metadata_text(metadata, "quality_profile", runtime_quality_profile()) or "standard"
    resolved_studio_lane = runtime_studio_lane() or metadata_text(metadata, "studio_lane", "") or None
    resolved_artifact_kind = runtime_artifact_kind() or metadata_text(metadata, "artifact_kind", "") or None
    resolved_preferred_render_surface = metadata_text(
        metadata,
        "preferred_render_surface",
        runtime_preferred_render_surface(),
    ) or infer_scene_render_surface(resolved_renderer_kind, visual_type)
    resolved_planning_profile = metadata_text(
        metadata,
        "planning_profile",
        runtime_planning_profile(),
    ) or ("simulation_canvas" if visual_type == "simulation" else "article_svg")
    resolved_thinking_floor = metadata_text(
        metadata,
        "thinking_floor",
        runtime_thinking_floor(),
    ) or "medium"
    resolved_critic_policy = metadata_text(
        metadata,
        "critic_policy",
        runtime_critic_policy(),
    ) or "standard"
    resolved_living_expression_mode = metadata_text(
        metadata,
        "living_expression_mode",
        runtime_living_expression_mode(),
    ) or ("expressive" if resolved_presentation_intent == "article_figure" else "subtle")
    runtime_metadata = get_runtime_visual_metadata()
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
    artifact_handoff = build_artifact_handoff(
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
    resolved_scene = enrich_scene_contract(
        scene=resolved_scene,
        visual_type=visual_type,
        renderer_kind=resolved_renderer_kind,
        presentation_intent=resolved_presentation_intent,
        pedagogical_role=resolved_pedagogical_role,
        summary=resolved_summary,
        claim=resolved_claim,
    )
    return payload_class(
        id=f"visual-{uuid.uuid4().hex[:12]}",
        visual_session_id=visual_session_id.strip() or generate_visual_session_id(visual_type),
        type=visual_type,
        renderer_kind=resolved_renderer_kind,
        shell_variant=resolved_shell_variant,
        patch_strategy=resolved_patch_strategy,
        figure_group_id=figure_group_id.strip() or str(spec.get("figure_group_id") or generate_figure_group_id(visual_type)),
        figure_index=max(1, int(figure_index or 1)),
        figure_total=max(1, int(figure_total or 1)),
        pedagogical_role=resolved_pedagogical_role,
        chrome_mode=resolved_chrome_mode,
        claim=resolved_claim,
        presentation_intent=resolved_presentation_intent,
        figure_budget=resolved_figure_budget,
        quality_profile=resolved_quality_profile,
        renderer_contract=resolved_renderer_contract,
        studio_lane=resolved_studio_lane,
        artifact_kind=resolved_artifact_kind,
        narrative_anchor=narrative_anchor.strip() or str(spec.get("narrative_anchor") or "after-lead"),
        preferred_render_surface=resolved_preferred_render_surface,
        planning_profile=resolved_planning_profile,
        thinking_floor=resolved_thinking_floor,
        critic_policy=resolved_critic_policy,
        living_expression_mode=resolved_living_expression_mode,
        runtime=resolved_runtime,
        title=resolved_title,
        summary=resolved_summary,
        spec=spec,
        scene=resolved_scene,
        controls=resolved_controls,
        annotations=resolved_annotations,
        interaction_mode=infer_interaction_mode(resolved_controls),
        ephemeral=True,
        lifecycle_event=lifecycle_event,
        subtitle=resolved_subtitle,
        fallback_html=fallback_html,
        runtime_manifest=build_runtime_manifest(
            renderer_kind=resolved_renderer_kind,
            visual_type=visual_type,
            spec=spec,
            provided=runtime_manifest,
        ),
        artifact_handoff_available=artifact_handoff["available"],
        artifact_handoff_mode=artifact_handoff["mode"],
        artifact_handoff_label=artifact_handoff["label"],
        artifact_handoff_prompt=artifact_handoff["prompt"],
        metadata=resolved_metadata,
    )


def coerce_visual_payload_data_impl(
    data: dict[str, Any],
    *,
    build_controls: Callable[[str, dict[str, Any]], list[dict[str, Any]]],
    generate_visual_session_id: Callable[[str], str],
    resolve_renderer_kind: Callable[[str, dict[str, Any], str], str],
    infer_shell_variant: Callable[[str, str], str],
    infer_patch_strategy: Callable[[str, str], str],
    generate_figure_group_id: Callable[[str], str],
    infer_pedagogical_role: Callable[[str, dict[str, Any], str], str],
    infer_chrome_mode: Callable[[str, str, str], str],
    clean_summary_text: Callable[[Any], str],
    default_visual_claim: Callable[[str, str, str, dict[str, Any]], str],
    default_visual_title: Callable[[str], str],
    infer_runtime: Callable[[str, str, dict[str, Any]], str],
    build_scene: Callable[[str, dict[str, Any], str], dict[str, Any]],
    build_annotations: Callable[[str, dict[str, Any]], list[dict[str, Any]]],
    infer_interaction_mode: Callable[[list[dict[str, Any]]], str],
    build_runtime_manifest: Callable[..., dict[str, Any] | None],
) -> dict[str, Any]:
    visual_type = str(data.get("type") or "comparison")
    spec = data.get("spec") if isinstance(data.get("spec"), dict) else {}
    controls = data.get("controls")
    if not isinstance(controls, list):
        controls = build_controls(visual_type, spec)

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    metadata = {
        "contract_version": metadata.get("contract_version") or "visual_payload_v3",
        **metadata,
    }

    coerced = dict(data)
    coerced["visual_session_id"] = str(
        data.get("visual_session_id") or generate_visual_session_id(visual_type)
    )
    coerced["renderer_kind"] = resolve_renderer_kind(
        visual_type,
        spec,
        str(data.get("renderer_kind") or ""),
    )
    coerced["shell_variant"] = infer_shell_variant(
        str(coerced["renderer_kind"]),
        str(data.get("shell_variant") or ""),
    )
    coerced["patch_strategy"] = infer_patch_strategy(
        str(coerced["renderer_kind"]),
        str(data.get("patch_strategy") or ""),
    )
    coerced["figure_group_id"] = str(
        data.get("figure_group_id")
        or metadata.get("figure_group_id")
        or spec.get("figure_group_id")
        or generate_figure_group_id(visual_type)
    )
    coerced["figure_index"] = max(1, int(data.get("figure_index") or 1))
    coerced["figure_total"] = max(
        coerced["figure_index"],
        int(data.get("figure_total") or 1),
    )
    coerced["pedagogical_role"] = infer_pedagogical_role(
        visual_type,
        spec,
        str(data.get("pedagogical_role") or metadata.get("pedagogical_role") or ""),
    )
    coerced["chrome_mode"] = infer_chrome_mode(
        str(coerced["renderer_kind"]),
        str(coerced["shell_variant"]),
        str(data.get("chrome_mode") or ""),
    )
    coerced["claim"] = clean_summary_text(str(data.get("claim") or "")) or default_visual_claim(
        visual_type,
        str(data.get("title") or default_visual_title(visual_type)),
        str(data.get("summary") or ""),
        spec,
    )
    coerced["narrative_anchor"] = str(data.get("narrative_anchor") or "after-lead")
    coerced["runtime"] = str(
        data.get("runtime")
        or infer_runtime(str(coerced["renderer_kind"]), visual_type, spec)
    )
    coerced["scene"] = data.get("scene") if isinstance(data.get("scene"), dict) else build_scene(
        visual_type,
        spec,
        str(data.get("title") or ""),
    )
    coerced["controls"] = controls
    coerced["annotations"] = (
        data.get("annotations")
        if isinstance(data.get("annotations"), list)
        else build_annotations(visual_type, spec)
    )
    coerced["interaction_mode"] = str(
        data.get("interaction_mode") or infer_interaction_mode(controls)
    )
    coerced["ephemeral"] = bool(data.get("ephemeral", True))
    coerced["lifecycle_event"] = str(data.get("lifecycle_event") or "visual_open")
    coerced["runtime_manifest"] = build_runtime_manifest(
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
