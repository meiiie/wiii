"""Thinking lifecycle authority for visible Wiii thought.

This module keeps a single backend truth for visible thinking so both sync and
stream can converge on the same trajectory instead of stitching together
multiple ad-hoc sources.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import time
import uuid

from app.engine.reasoning.reasoning_narrator import sanitize_visible_reasoning_text


_SEGMENT_PHASES = {"pre_tool", "tool_continuation", "post_tool", "final_snapshot"}
_SEGMENT_PROVENANCE = {
    "live_native",
    "tool_continuation",
    "final_snapshot",
    "aligned_cleanup",
}
_SEGMENT_STATUS = {"live", "completed"}
_THINKING_EVENT_TYPES = {
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "tool_call",
    "tool_result",
}
_DEFAULT_SEGMENT_PHASE = "pre_tool"


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _default_turn_id(state: dict[str, Any]) -> str:
    context = state.get("context") or {}
    request_id = str(context.get("request_id") or "").strip()
    if request_id:
        return request_id
    session_id = str(state.get("session_id") or "session").strip() or "session"
    return f"{session_id}:{uuid.uuid4().hex[:12]}"


def _default_node(state: dict[str, Any], *, fallback: str = "unknown") -> str:
    for candidate in (
        state.get("current_agent"),
        state.get("next_agent"),
        (state.get("routing_metadata") or {}).get("final_agent"),
        fallback,
    ):
        node = str(candidate or "").strip()
        if node:
            return node
    return fallback


def _phase_from_hint(value: str | None) -> str | None:
    hint = str(value or "").strip().lower()
    if not hint:
        return None
    if hint in _SEGMENT_PHASES:
        return hint
    if hint in {"ground", "retrieve", "verify", "route", "routing"}:
        return "pre_tool"
    if hint in {"synthesize", "build", "compose", "summary", "answer"}:
        return "post_tool"
    if "tool" in hint or hint in {"lookup", "search"}:
        return "tool_continuation"
    return None


def _normalize_segment_phase(
    hint: str | None,
    *,
    node: str,
    trajectory: dict[str, Any],
) -> str:
    explicit = _phase_from_hint(hint)
    if explicit:
        return explicit

    if trajectory.get("last_tool_result_by_node", {}).get(node):
        return "tool_continuation"

    if trajectory.get("tool_seen_by_node", {}).get(node):
        return "post_tool"

    return _DEFAULT_SEGMENT_PHASE


def _build_segment(
    *,
    trajectory: dict[str, Any],
    node: str,
    phase: str,
    provenance: str,
    status: str,
    step_id: str | None,
    sequence_id: int | None,
    display_role: str | None,
    presentation: str | None,
    label: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    trajectory["sequence_counter"] = int(trajectory.get("sequence_counter") or 0) + 1
    next_sequence = int(sequence_id or trajectory["sequence_counter"])
    return {
        "segment_id": f"{node}:{next_sequence}:{uuid.uuid4().hex[:6]}",
        "turn_id": trajectory["turn_id"],
        "node": node,
        "step_id": step_id,
        "sequence_id": next_sequence,
        "phase": phase if phase in _SEGMENT_PHASES else _DEFAULT_SEGMENT_PHASE,
        "provenance": provenance if provenance in _SEGMENT_PROVENANCE else "live_native",
        "status": status if status in _SEGMENT_STATUS else "live",
        "display_role": display_role,
        "presentation": presentation,
        "label": str(label or "").strip() or None,
        "summary": str(summary or "").strip() or None,
        "content": "",
        "content_length": 0,
        "started_at": time.time(),
        "ended_at": None,
    }


def ensure_thinking_trajectory(state: dict[str, Any], *, turn_id: str | None = None) -> dict[str, Any]:
    existing = state.get("_thinking_trajectory")
    if isinstance(existing, dict) and existing.get("turn_id"):
        return existing

    trajectory = {
        "version": 1,
        "turn_id": str(turn_id or _default_turn_id(state)),
        "segments": [],
        "sequence_counter": 0,
        "open_segment_ids": {},
        "last_tool_result_by_node": {},
        "tool_seen_by_node": {},
    }
    state["_thinking_trajectory"] = trajectory
    return trajectory


def merge_thinking_trajectory_state(
    target_state: dict[str, Any],
    source_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge trajectory data from one state into another without losing provenance."""
    if not isinstance(source_state, dict):
        return None

    source = source_state.get("_thinking_trajectory")
    if not isinstance(source, dict) or not source.get("segments"):
        return None

    target = ensure_thinking_trajectory(
        target_state,
        turn_id=str(source.get("turn_id") or "").strip() or None,
    )
    target["sequence_counter"] = max(
        int(target.get("sequence_counter") or 0),
        int(source.get("sequence_counter") or 0),
    )

    existing_ids = {
        str(segment.get("segment_id") or "").strip()
        for segment in target.get("segments") or []
        if str(segment.get("segment_id") or "").strip()
    }

    target_segments = target.setdefault("segments", [])
    for segment in source.get("segments") or []:
        segment_id = str(segment.get("segment_id") or "").strip()
        if segment_id and segment_id in existing_ids:
            continue
        copied = deepcopy(segment)
        copied["content"] = sanitize_visible_reasoning_text(
            str(copied.get("content") or "")
        ).strip()
        copied["content_length"] = len(str(copied.get("content") or ""))
        target_segments.append(copied)
        if segment_id:
            existing_ids.add(segment_id)

    target_open = target.setdefault("open_segment_ids", {})
    for node, segment_id in (source.get("open_segment_ids") or {}).items():
        node_name = str(node or "").strip()
        seg_id = str(segment_id or "").strip()
        if node_name and seg_id and node_name not in target_open:
            target_open[node_name] = seg_id

    for key in ("last_tool_result_by_node", "tool_seen_by_node"):
        merged = target.setdefault(key, {})
        for node, value in (source.get(key) or {}).items():
            node_name = str(node or "").strip()
            if not node_name:
                continue
            merged[node_name] = bool(merged.get(node_name) or value)

    target_state.pop("thinking_lifecycle", None)
    return target


def _find_segment(trajectory: dict[str, Any], segment_id: str | None) -> dict[str, Any] | None:
    if not segment_id:
        return None
    for segment in trajectory.get("segments") or []:
        if segment.get("segment_id") == segment_id:
            return segment
    return None


def _append_segment_content(segment: dict[str, Any], text: str) -> None:
    clean = sanitize_visible_reasoning_text(str(text or "")).strip()
    if not clean:
        return

    existing = str(segment.get("content") or "").strip()
    if not existing:
        segment["content"] = clean
    else:
        normalized_existing = _normalize_text(existing)
        normalized_clean = _normalize_text(clean)
        if normalized_clean and normalized_clean in normalized_existing:
            return
        joiner = "\n\n" if not existing.endswith(("\n", " ")) else ""
        segment["content"] = f"{existing}{joiner}{clean}".strip()
    segment["content_length"] = len(str(segment.get("content") or ""))


def _open_segment_for_event(
    state: dict[str, Any],
    *,
    node: str,
    step_id: str | None,
    sequence_id: int | None,
    phase_hint: str | None,
    provenance: str,
    display_role: str | None,
    presentation: str | None,
    label: str | None,
    summary: str | None,
) -> dict[str, Any]:
    trajectory = ensure_thinking_trajectory(state)
    phase = _normalize_segment_phase(phase_hint, node=node, trajectory=trajectory)
    segment = _build_segment(
        trajectory=trajectory,
        node=node,
        phase=phase,
        provenance=provenance,
        status="live",
        step_id=step_id,
        sequence_id=sequence_id,
        display_role=display_role,
        presentation=presentation,
        label=label,
        summary=summary,
    )
    trajectory.setdefault("segments", []).append(segment)
    trajectory.setdefault("open_segment_ids", {})[node] = segment["segment_id"]
    if phase in {"tool_continuation", "post_tool"}:
        trajectory.setdefault("tool_seen_by_node", {})[node] = True
    trajectory.setdefault("last_tool_result_by_node", {})[node] = False
    return segment


def capture_thinking_lifecycle_event(
    state: dict[str, Any],
    event: dict[str, Any] | None,
    *,
    default_node: str | None = None,
) -> None:
    if not isinstance(event, dict):
        return

    event_type = str(event.get("type") or "").strip().lower()
    if event_type not in _THINKING_EVENT_TYPES:
        return

    trajectory = ensure_thinking_trajectory(state)
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    node = str(event.get("node") or default_node or _default_node(state)).strip() or "unknown"
    step_id = (
        str(event.get("step_id") or details.get("step_id") or details.get("block_id") or "").strip()
        or None
    )
    sequence_id_raw = event.get("sequence_id")
    try:
        sequence_id = int(sequence_id_raw) if sequence_id_raw is not None else None
    except Exception:
        sequence_id = None
    display_role = str(event.get("display_role") or "").strip() or None
    presentation = str(event.get("presentation") or "").strip() or None

    if event_type == "tool_call":
        trajectory.setdefault("tool_seen_by_node", {})[node] = True
        return
    if event_type == "tool_result":
        trajectory.setdefault("tool_seen_by_node", {})[node] = True
        trajectory.setdefault("last_tool_result_by_node", {})[node] = True
        return

    if event_type == "thinking_start":
        _open_segment_for_event(
            state,
            node=node,
            step_id=step_id,
            sequence_id=sequence_id,
            phase_hint=str(details.get("phase") or event.get("phase") or ""),
            provenance="tool_continuation"
            if trajectory.get("last_tool_result_by_node", {}).get(node)
            else "live_native",
            display_role=display_role,
            presentation=presentation,
            label=str(event.get("content") or "").strip() or None,
            summary=str(event.get("summary") or details.get("summary") or "").strip() or None,
        )
        return

    open_segment = _find_segment(
        trajectory,
        trajectory.get("open_segment_ids", {}).get(node),
    )
    if event_type == "thinking_end" and open_segment is None:
        trajectory.setdefault("last_tool_result_by_node", {})[node] = False
        return
    if open_segment is None:
        open_segment = _open_segment_for_event(
            state,
            node=node,
            step_id=step_id,
            sequence_id=sequence_id,
            phase_hint=str(details.get("phase") or event.get("phase") or ""),
            provenance="tool_continuation"
            if trajectory.get("last_tool_result_by_node", {}).get(node)
            else "live_native",
            display_role=display_role,
            presentation=presentation,
            label=None,
            summary=None,
        )

    if event_type == "thinking_delta":
        _append_segment_content(open_segment, str(event.get("content") or ""))
        return

    if event_type == "thinking_end":
        open_segment["status"] = "completed"
        open_segment["ended_at"] = time.time()
        trajectory.get("open_segment_ids", {}).pop(node, None)
        trajectory.setdefault("last_tool_result_by_node", {})[node] = False


def record_thinking_snapshot(
    state: dict[str, Any],
    text: str | None,
    *,
    node: str | None = None,
    provenance: str = "final_snapshot",
    phase: str = "final_snapshot",
    step_id: str | None = None,
    sequence_id: int | None = None,
) -> dict[str, Any] | None:
    clean = sanitize_visible_reasoning_text(str(text or "")).strip()
    if not clean:
        return None

    trajectory = ensure_thinking_trajectory(state)
    target_node = str(node or _default_node(state)).strip() or "unknown"
    segments = trajectory.setdefault("segments", [])
    existing = None
    for segment in reversed(segments):
        if segment.get("phase") == "final_snapshot" and segment.get("node") == target_node:
            existing = segment
            break

    if existing is None:
        existing = _build_segment(
            trajectory=trajectory,
            node=target_node,
            phase=phase,
            provenance=provenance,
            status="completed",
            step_id=step_id,
            sequence_id=sequence_id,
            display_role="thinking",
            presentation="compact",
        )
        segments.append(existing)

    existing["phase"] = "final_snapshot"
    existing["provenance"] = provenance if provenance in _SEGMENT_PROVENANCE else "final_snapshot"
    existing["status"] = "completed"
    existing["content"] = clean
    existing["content_length"] = len(clean)
    existing["ended_at"] = time.time()
    return existing


def _segments_without_final_snapshot(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        segment
        for segment in trajectory.get("segments") or []
        if str(segment.get("phase") or "") != "final_snapshot"
        and str(segment.get("content") or "").strip()
    ]


def _final_snapshot_segments(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        segment
        for segment in trajectory.get("segments") or []
        if str(segment.get("phase") or "") == "final_snapshot"
        and str(segment.get("content") or "").strip()
    ]


def _join_unique_segment_text(segments: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        content = sanitize_visible_reasoning_text(str(segment.get("content") or "")).strip()
        if not content:
            continue
        normalized = _normalize_text(content).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(content)
    return "\n\n".join(parts).strip()


def build_thinking_lifecycle_snapshot(
    state: dict[str, Any],
    *,
    fallback: str = "",
    default_node: str | None = None,
) -> dict[str, Any] | None:
    trajectory = ensure_thinking_trajectory(state)
    fallback_text = sanitize_visible_reasoning_text(
        str(
            state.get("thinking_content")
            or state.get("thinking")
            or fallback
            or ""
        )
    ).strip()

    live_segments = _segments_without_final_snapshot(trajectory)
    live_text = _join_unique_segment_text(live_segments)

    final_segments = _final_snapshot_segments(trajectory)
    final_text = _join_unique_segment_text(final_segments)

    if fallback_text and not final_text:
        provenance = "final_snapshot"
        if live_text and fallback_text != live_text:
            provenance = "aligned_cleanup"
        record_thinking_snapshot(
            state,
            fallback_text,
            node=default_node or _default_node(state),
            provenance=provenance,
        )
        trajectory = ensure_thinking_trajectory(state)
        final_segments = _final_snapshot_segments(trajectory)
        final_text = _join_unique_segment_text(final_segments)

    if not final_text:
        final_text = live_text or fallback_text
    if not final_text and not live_text and not trajectory.get("segments"):
        state["thinking_lifecycle"] = None
        return None

    serialized_segments: list[dict[str, Any]] = []
    for segment in trajectory.get("segments") or []:
        copied = deepcopy(segment)
        copied["content"] = sanitize_visible_reasoning_text(str(copied.get("content") or "")).strip()
        copied["content_length"] = len(str(copied.get("content") or ""))
        if not copied["content"] and copied.get("phase") != "final_snapshot":
            continue
        serialized_segments.append(copied)

    provenance_mix = sorted(
        {
            str(segment.get("provenance") or "").strip()
            for segment in serialized_segments
            if str(segment.get("provenance") or "").strip()
        }
    )
    phase_mix = sorted(
        {
            str(segment.get("phase") or "").strip()
            for segment in serialized_segments
            if str(segment.get("phase") or "").strip()
        }
    )

    snapshot = {
        "version": 1,
        "turn_id": trajectory.get("turn_id"),
        "final_text": final_text,
        "final_length": len(final_text),
        "live_text": live_text,
        "live_length": len(live_text),
        "segment_count": len(serialized_segments),
        "has_tool_continuation": any(
            str(segment.get("phase") or "") == "tool_continuation"
            or str(segment.get("provenance") or "") == "tool_continuation"
            for segment in serialized_segments
        ),
        "phases": phase_mix,
        "provenance_mix": provenance_mix,
        "segments": serialized_segments,
    }
    state["thinking_lifecycle"] = snapshot
    return snapshot


def resolve_visible_thinking_from_lifecycle(
    state: dict[str, Any],
    *,
    fallback: str = "",
    default_node: str | None = None,
) -> str:
    snapshot = build_thinking_lifecycle_snapshot(
        state,
        fallback=fallback,
        default_node=default_node,
    )
    if not snapshot:
        return ""
    return str(snapshot.get("final_text") or "").strip()
