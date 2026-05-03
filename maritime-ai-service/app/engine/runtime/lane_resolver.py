"""Map a ``RuntimeIntent`` to an ``ExecutionLane``.

Phase 4 of the runtime migration epic (issue #207). The resolver is the
hinge of the lane-first architecture: every dispatch path goes through
``resolve_lane(intent)`` so the rest of the runtime can reason about
"which lane" instead of "which provider".

Decision priorities (high → low):
1. Vision content → ``VISION_EXTRACTION`` lane.
2. Structured output + tools + streaming combo → ``CLOUD_NATIVE_SDK``
   (only direct SDKs reliably stream typed tool calls).
3. Tools but no streaming → ``OPENAI_COMPATIBLE_HTTP`` (Gemini, Zhipu,
   OpenAI all share this shape and the failover stays cheap).
4. Plain chat completion → ``OPENAI_COMPATIBLE_HTTP``.
5. Local embedding-only flows → ``EMBEDDING``.

The resolver is intentionally pure: same intent always returns the same
lane. Capability detection from real provider metadata happens at lane
*execution* time, not here.
"""

from __future__ import annotations

from .lane import ExecutionLane
from .runtime_intent import RuntimeIntent
from .runtime_metrics import inc_counter


def resolve_lane(intent: RuntimeIntent) -> ExecutionLane:
    """Return the execution lane for a turn given its resolved intent."""
    if intent.needs_vision:
        lane = ExecutionLane.VISION_EXTRACTION
    elif (
        intent.needs_structured_output
        and intent.needs_tools
        and intent.needs_streaming
    ):
        lane = ExecutionLane.CLOUD_NATIVE_SDK
    else:
        # Default chat lane — covers tools-only, streaming-only, plain text.
        lane = ExecutionLane.OPENAI_COMPATIBLE_HTTP

    inc_counter("runtime.lane_resolver.decisions", labels={"lane": lane.value})
    return lane


__all__ = ["resolve_lane"]
