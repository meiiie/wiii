from typing import Any

from app.engine.tools.visual_runtime_metadata import (
    _runtime_living_expression_mode_impl,
    _runtime_metadata_text_impl,
    _runtime_preferred_render_surface_impl,
)
from app.engine.tools.runtime_context import get_current_tool_runtime_context


def _default_visual_title(visual_type: str) -> str:
    return visual_type.replace("_", " ").title() or "Visual"


def _get_runtime_metadata() -> dict[str, Any]:
    runtime = get_current_tool_runtime_context()
    if runtime and isinstance(runtime.metadata, dict):
        return runtime.metadata
    return {}


def _runtime_metadata_text(key: str, default: str = "") -> str:
    return _runtime_metadata_text_impl(key, default, _get_runtime_metadata)


def build_scene_impl(visual_type: str, spec: dict[str, Any], title: str) -> dict[str, Any]:
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
            nodes.append(
                {
                    "id": node_id,
                    "label": str(item.get("title") or f"Step {index + 1}"),
                    "kind": "step",
                }
            )
            if index > 0:
                links.append({"source": f"step-{index}", "target": node_id})
        return {"kind": "process", "nodes": nodes, "links": links}

    if visual_type == "matrix":
        rows = spec.get("rows", []) if isinstance(spec.get("rows"), list) else []
        cols = spec.get("cols", []) if isinstance(spec.get("cols"), list) else []
        nodes = [{"id": f"row-{i}", "label": str(row), "kind": "row"} for i, row in enumerate(rows)]
        nodes.extend({"id": f"col-{i}", "label": str(col), "kind": "column"} for i, col in enumerate(cols))
        return {
            "kind": "matrix",
            "nodes": nodes,
            "metadata": {"row_count": len(rows), "column_count": len(cols)},
        }

    if visual_type == "architecture":
        layers = spec.get("layers", []) if isinstance(spec.get("layers"), list) else []
        nodes = []
        links = []
        for index, layer in enumerate(layers):
            item = layer if isinstance(layer, dict) else {}
            node_id = f"layer-{index + 1}"
            nodes.append(
                {
                    "id": node_id,
                    "label": str(item.get("name") or f"Layer {index + 1}"),
                    "kind": "layer",
                }
            )
            if index > 0:
                links.append({"source": f"layer-{index}", "target": node_id})
        return {"kind": "architecture", "nodes": nodes, "links": links}

    if visual_type == "concept":
        center = spec.get("center", {}) if isinstance(spec.get("center"), dict) else {}
        branches = spec.get("branches", []) if isinstance(spec.get("branches"), list) else []
        nodes = [{"id": "center", "label": str(center.get("title") or title or "Core concept"), "kind": "center"}]
        links = []
        for index, branch in enumerate(branches):
            item = branch if isinstance(branch, dict) else {}
            node_id = f"branch-{index + 1}"
            nodes.append(
                {
                    "id": node_id,
                    "label": str(item.get("title") or f"Branch {index + 1}"),
                    "kind": "branch",
                }
            )
            links.append({"source": "center", "target": node_id})
        return {"kind": "concept", "nodes": nodes, "links": links}

    if visual_type == "infographic":
        stats = spec.get("stats", []) if isinstance(spec.get("stats"), list) else []
        sections = spec.get("sections", []) if isinstance(spec.get("sections"), list) else []
        nodes = []
        for index, stat in enumerate(stats):
            item = stat if isinstance(stat, dict) else {}
            nodes.append({"id": f"stat-{index + 1}", "label": str(item.get("label") or f"Stat {index + 1}"), "kind": "stat"})
        for index, section in enumerate(sections):
            item = section if isinstance(section, dict) else {}
            nodes.append(
                {
                    "id": f"section-{index + 1}",
                    "label": str(item.get("title") or f"Section {index + 1}"),
                    "kind": "section",
                }
            )
        return {"kind": "infographic", "nodes": nodes}

    if visual_type == "chart":
        labels = spec.get("labels", []) if isinstance(spec.get("labels"), list) else []
        return {
            "kind": "chart",
            "nodes": [
                {"id": f"point-{index + 1}", "label": str(label), "kind": "point"}
                for index, label in enumerate(labels)
            ],
            "scales": {"x": {"kind": "categorical", "domain": labels}},
        }

    if visual_type == "timeline":
        events = spec.get("events", []) if isinstance(spec.get("events"), list) else []
        nodes = []
        links = []
        for index, event in enumerate(events):
            item = event if isinstance(event, dict) else {}
            node_id = f"milestone-{index + 1}"
            nodes.append(
                {
                    "id": node_id,
                    "label": str(item.get("title") or item.get("label") or f"Milestone {index + 1}"),
                    "kind": "milestone",
                }
            )
            if index > 0:
                links.append({"source": f"milestone-{index}", "target": node_id})
        return {"kind": "timeline", "nodes": nodes, "links": links}

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


def build_controls_impl(visual_type: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
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


def build_annotations_impl(visual_type: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
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


def infer_interaction_mode_impl(controls: list[dict[str, Any]]) -> str:
    if not controls:
        return "static"
    control_types = {str(control.get("type")) for control in controls}
    if "range" in control_types:
        return "scrubbable"
    if control_types & {"chips", "select", "toggle"}:
        return "filterable"
    return "guided"


def infer_runtime_impl(renderer_kind: str, visual_type: str, spec: dict[str, Any]) -> str:
    if renderer_kind in {"recharts", "template"}:
        return "svg"
    if renderer_kind == "app":
        ui_runtime = str(spec.get("ui_runtime") or "")
        return "sandbox_react" if visual_type == "react_app" or ui_runtime == "react" else "sandbox_html"
    return "sandbox_html"


def infer_shell_variant_impl(renderer_kind: str, requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"editorial", "compact", "immersive"}:
        return candidate
    return "immersive" if renderer_kind == "app" else "editorial"


def infer_patch_strategy_impl(renderer_kind: str, requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"spec_merge", "replace_html", "app_state"}:
        return candidate
    if renderer_kind == "template":
        return "spec_merge"
    if renderer_kind == "app":
        return "app_state"
    return "replace_html"


def infer_scene_render_surface_impl(renderer_kind: str, visual_type: str) -> str:
    preferred = _runtime_preferred_render_surface_impl(_runtime_metadata_text)
    if preferred in {"svg", "canvas", "html", "video"}:
        return preferred
    if visual_type == "simulation":
        return "canvas"
    if renderer_kind == "template":
        return "svg"
    if renderer_kind == "app":
        return "canvas" if visual_type == "simulation" else "html"
    return "html"


def infer_scene_motion_profile_impl(*, visual_type: str, presentation_intent: str, render_surface: str) -> str:
    if render_surface == "canvas":
        return "continuous_simulation" if visual_type == "simulation" else "continuous_canvas"
    if presentation_intent == "chart_runtime":
        return "guided_focus"
    if visual_type in {"process", "timeline"}:
        return "stepwise_reveal"
    if visual_type in {"comparison", "architecture", "concept", "infographic", "chart"}:
        return "guided_focus"
    return "static"


def infer_scene_pedagogy_arc_impl(*, presentation_intent: str, visual_type: str, summary: str, claim: str) -> dict[str, str]:
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


def infer_scene_state_model_impl(*, presentation_intent: str, visual_type: str, render_surface: str) -> dict[str, Any]:
    if visual_type == "simulation" or render_surface == "canvas":
        return {"kind": "continuous_state", "driver": "animation_loop", "patchable": True}
    if presentation_intent == "chart_runtime":
        return {"kind": "declarative_chart", "driver": "chart_spec", "patchable": True}
    if presentation_intent == "article_figure":
        return {"kind": "semantic_svg_scene", "driver": "figure_spec", "patchable": True}
    return {"kind": "artifact_state", "driver": "html_runtime", "patchable": True}


def infer_scene_narrative_voice_impl(presentation_intent: str) -> dict[str, Any]:
    mode = _runtime_living_expression_mode_impl(_runtime_metadata_text) or (
        "expressive" if presentation_intent == "article_figure" else "subtle"
    )
    return {
        "mode": mode,
        "stance": "guide",
        "character_forward": True,
        "tone": "clear_vivid" if mode == "expressive" else "clear_precise",
    }


def enrich_scene_contract_impl(
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
    render_surface = infer_scene_render_surface_impl(renderer_kind, visual_type)
    enriched["render_surface"] = enriched.get("render_surface") or render_surface
    enriched["motion_profile"] = enriched.get("motion_profile") or infer_scene_motion_profile_impl(
        visual_type=visual_type,
        presentation_intent=presentation_intent,
        render_surface=render_surface,
    )
    enriched["pedagogy_arc"] = enriched.get("pedagogy_arc") or infer_scene_pedagogy_arc_impl(
        presentation_intent=presentation_intent,
        visual_type=visual_type,
        summary=summary,
        claim=claim,
    )
    enriched["state_model"] = enriched.get("state_model") or infer_scene_state_model_impl(
        presentation_intent=presentation_intent,
        visual_type=visual_type,
        render_surface=render_surface,
    )
    enriched["narrative_voice"] = enriched.get("narrative_voice") or infer_scene_narrative_voice_impl(presentation_intent)
    if "focus_states" not in enriched:
        enriched["focus_states"] = [{
            "id": "default",
            "claim": claim or summary,
            "pedagogical_role": pedagogical_role or "overview",
        }]
    return enriched


def build_runtime_manifest_impl(
    *,
    renderer_kind: str,
    visual_type: str,
    spec: dict[str, Any],
    provided: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if renderer_kind != "app":
        return None
    return {
        "ui_runtime": str((provided or {}).get("ui_runtime") or spec.get("ui_runtime") or ("react" if visual_type == "react_app" else "html")),
        "storage": bool((provided or {}).get("storage", spec.get("storage", False))),
        "mcp_access": bool((provided or {}).get("mcp_access", spec.get("mcp_access", False))),
        "file_export": bool((provided or {}).get("file_export", spec.get("file_export", False))),
        "shareability": str((provided or {}).get("shareability") or spec.get("shareability") or "session"),
    }
