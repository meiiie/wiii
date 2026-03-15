"""Presentation helpers for streaming SSE responses."""

import json
from dataclasses import dataclass, field
from typing import Any


DISPLAY_ROLE_BY_EVENT: dict[str, str] = {
    "thinking": "thinking",
    "thinking_start": "thinking",
    "thinking_end": "thinking",
    "thinking_delta": "thinking",
    "tool_call": "tool",
    "tool_result": "tool",
    "browser_screenshot": "tool",
    "preview": "tool",
    "action_text": "action",
    "answer": "answer",
    "artifact": "artifact",
    "visual": "artifact",
    "visual_open": "artifact",
    "visual_patch": "artifact",
    "visual_commit": "artifact",
    "visual_dispose": "artifact",
}

PRESENTATION_BY_EVENT: dict[str, str] = {
    "thinking": "expanded",
    "thinking_start": "expanded",
    "thinking_end": "compact",
    "thinking_delta": "expanded",
    "tool_call": "technical",
    "tool_result": "technical",
    "browser_screenshot": "technical",
    "preview": "compact",
    "action_text": "compact",
    "status": "compact",
    "answer": "compact",
    "artifact": "compact",
    "visual": "compact",
    "visual_open": "compact",
    "visual_patch": "compact",
    "visual_commit": "compact",
    "visual_dispose": "compact",
    "sources": "compact",
    "metadata": "compact",
    "done": "compact",
    "error": "compact",
}


@dataclass
class StreamPresentationState:
    """Track active reasoning step ids for interleaved streaming UI."""

    active_step_by_node: dict[str, str] = field(default_factory=dict)
    last_step_id: str | None = None

    @staticmethod
    def _node_key(node: str | None) -> str:
        return node or "__default__"

    def resolve_step_id(
        self,
        *,
        event_type: str,
        event_counter: int,
        node: str | None,
        details: dict[str, Any] | None,
    ) -> str | None:
        explicit_step_id = None
        if details:
            explicit_step_id = (
                details.get("step_id")
                or details.get("block_id")
            )

        node_key = self._node_key(node)

        if event_type == "thinking_start":
            step_id = explicit_step_id or f"{node_key}-step-{event_counter}"
            self.active_step_by_node[node_key] = step_id
            self.last_step_id = step_id
            return step_id

        if event_type == "thinking_end":
            step_id = (
                explicit_step_id
                or self.active_step_by_node.get(node_key)
                or self.last_step_id
            )
            self.active_step_by_node.pop(node_key, None)
            if step_id:
                self.last_step_id = step_id
            return step_id

        step_id = (
            explicit_step_id
            or self.active_step_by_node.get(node_key)
            or self.last_step_id
        )
        if step_id:
            self.last_step_id = step_id
        return step_id


def _step_state_for_event(event_type: str) -> str | None:
    if event_type == "thinking_end":
        return "completed"
    if event_type in {
        "thinking_start",
        "thinking",
        "thinking_delta",
        "tool_call",
        "tool_result",
        "action_text",
        "browser_screenshot",
        "preview",
        "visual",
        "visual_open",
        "visual_patch",
    }:
        return "live"
    if event_type in {"answer", "artifact", "visual", "visual_commit", "visual_dispose", "sources", "metadata", "done", "error"}:
        return "completed"
    return None


def _apply_presentation_metadata(
    *,
    payload: dict[str, Any],
    event_type: str,
    event_counter: int,
    event,
    presentation_state: StreamPresentationState | None,
) -> dict[str, Any]:
    if presentation_state is None:
        presentation_state = StreamPresentationState()

    details = getattr(event, "details", None)
    step_id = presentation_state.resolve_step_id(
        event_type=event_type,
        event_counter=event_counter,
        node=getattr(event, "node", None),
        details=details,
    )

    display_role = DISPLAY_ROLE_BY_EVENT.get(event_type)
    if display_role:
        payload["display_role"] = display_role

    payload["sequence_id"] = event_counter

    if step_id:
        payload["step_id"] = step_id

    step_state = _step_state_for_event(event_type)
    if step_state:
        payload["step_state"] = step_state

    presentation = PRESENTATION_BY_EVENT.get(event_type)
    if presentation:
        payload["presentation"] = presentation

    return payload


def format_sse(event: str, data: dict, event_id: int | None = None) -> str:
    """Format data as a Server-Sent Event with optional event id."""
    parts = []
    if event_id is not None:
        parts.append(f"id: {event_id}")
    parts.append(f"event: {event}")
    parts.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


def emit_blocked_sse_events(
    *,
    blocked_response,
    session_id: str,
    processing_time: float,
    event_counter: int,
) -> tuple[list[str], int]:
    """Emit the standard blocked-response SSE sequence."""
    chunks = []

    event_counter += 1
    chunks.append(
        format_sse(
            "answer",
            {"content": blocked_response.message},
            event_id=event_counter,
        )
    )
    event_counter += 1
    chunks.append(
        format_sse(
            "metadata",
            {
                **(blocked_response.metadata or {}),
                "session_id": session_id,
            },
            event_id=event_counter,
        )
    )
    event_counter += 1
    chunks.append(
        format_sse(
            "done",
            {"processing_time": processing_time},
            event_id=event_counter,
        )
    )
    return chunks, event_counter


def emit_internal_error_sse_events(
    *,
    processing_time: float | None = None,
    event_counter: int | None = None,
) -> tuple[list[str], int | None]:
    """Emit the standard internal-error SSE sequence."""
    chunks: list[str] = []

    next_event_id = None
    if event_counter is not None:
        event_counter += 1
        next_event_id = event_counter

    chunks.append(
        format_sse(
            "error",
            {
                "message": "Internal processing error",
                "type": "internal_error",
            },
            event_id=next_event_id,
        )
    )

    if processing_time is not None:
        next_event_id = None
        if event_counter is not None:
            event_counter += 1
            next_event_id = event_counter
        chunks.append(
            format_sse(
                "done",
                {"processing_time": processing_time},
                event_id=next_event_id,
            )
        )

    return chunks, event_counter


def serialize_stream_event(
    *,
    event,
    event_counter: int,
    enable_artifacts: bool,
    presentation_state: StreamPresentationState | None = None,
) -> tuple[list[str], int, bool]:
    """Serialize a StreamEvent into one or more SSE chunks."""
    event_type = event.type

    if event_type == "artifact" and not enable_artifacts:
        return [], event_counter, False

    event_counter += 1

    if event_type == "status":
        data: dict[str, Any] = {
            "content": event.content,
            "step": event.step,
            "node": event.node,
        }
        if event.details:
            data["details"] = event.details
        data = _apply_presentation_metadata(
            payload=data,
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("status", data, event_id=event_counter)
        ], event_counter, False

    if event_type == "thinking":
        data = _apply_presentation_metadata(
            payload={
                "content": event.content,
                "step": event.step,
                "confidence": event.confidence,
                "details": event.details,
            },
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("thinking", data, event_id=event_counter)], event_counter, False

    if event_type == "answer":
        data = _apply_presentation_metadata(
            payload={"content": event.content},
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("answer", data, event_id=event_counter)], event_counter, False

    if event_type in {"tool_call", "tool_result"}:
        data = _apply_presentation_metadata(
            payload={
                "content": event.content,
                "node": event.node,
                "step": event.step,
            },
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse(event_type, data, event_id=event_counter)], event_counter, False

    if event_type in {"action_text", "browser_screenshot", "preview"}:
        data = _apply_presentation_metadata(
            payload={
                "content": event.content,
                "node": event.node,
            },
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse(event_type, data, event_id=event_counter)], event_counter, False

    if event_type in {"artifact", "visual", "visual_open", "visual_patch", "visual_commit", "visual_dispose"}:
        data = _apply_presentation_metadata(
            payload={
                "content": event.content,
                "node": event.node,
            },
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse(event_type, data, event_id=event_counter)], event_counter, False

    if event_type == "thinking_start":
        data = {
            "type": "thinking_start",
            "content": event.content,
            "node": event.node,
        }
        if event.details:
            data.update(event.details)
        if event.details and event.details.get("summary"):
            data["summary"] = event.details["summary"]
        data = _apply_presentation_metadata(
            payload=data,
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("thinking_start", data, event_id=event_counter)
        ], event_counter, False

    if event_type == "thinking_end":
        data = {
            "type": "thinking_end",
            "node": event.node,
        }
        if event.details:
            data.update(event.details)
        data = _apply_presentation_metadata(
            payload=data,
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("thinking_end", data, event_id=event_counter)
        ], event_counter, False

    if event_type == "thinking_delta":
        data = _apply_presentation_metadata(
            payload={"content": event.content, "node": event.node},
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("thinking_delta", data, event_id=event_counter)], event_counter, False

    if event_type == "domain_notice":
        data = _apply_presentation_metadata(
            payload={"content": event.content},
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("domain_notice", data, event_id=event_counter)], event_counter, False

    if event_type == "emotion":
        data = _apply_presentation_metadata(
            payload=dict(event.content),
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("emotion", data, event_id=event_counter)
        ], event_counter, False

    if event_type == "sources":
        data = _apply_presentation_metadata(
            payload={"sources": event.content},
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("sources", data, event_id=event_counter)], event_counter, False

    if event_type == "metadata":
        metadata = dict(event.content)
        metadata.setdefault("streaming_version", "v3-graph")
        metadata = _apply_presentation_metadata(
            payload=metadata,
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("metadata", metadata, event_id=event_counter)
        ], event_counter, False

    if event_type == "done":
        data = _apply_presentation_metadata(
            payload=dict(event.content),
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [
            format_sse("done", data, event_id=event_counter)
        ], event_counter, False

    if event_type == "error":
        data = _apply_presentation_metadata(
            payload={
                "message": event.content.get("message", str(event.content)),
                "type": "stream_error",
            },
            event_type=event_type,
            event_counter=event_counter,
            event=event,
            presentation_state=presentation_state,
        )
        return [format_sse("error", data, event_id=event_counter)], event_counter, True

    return [], event_counter, False
