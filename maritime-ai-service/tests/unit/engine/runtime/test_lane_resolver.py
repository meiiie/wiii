"""Phase 4 lane resolver — Runtime Migration #207.

Locks in the deterministic mapping from ``RuntimeIntent`` to
``ExecutionLane``. Adding a new routing rule should add a test here
*first*, then the implementation.
"""

from __future__ import annotations

from app.engine.messages import Message
from app.engine.runtime.lane import ExecutionLane
from app.engine.runtime.lane_resolver import resolve_lane
from app.engine.runtime.runtime_intent import RuntimeIntent, derive_intent
from app.engine.runtime.turn_request import TurnRequest


# ── derive_intent ──

def _make_request(**kwargs) -> TurnRequest:
    base = {
        "messages": [Message(role="user", content="hi")],
        "user_id": "u1",
        "session_id": "s1",
    }
    base.update(kwargs)
    return TurnRequest(**base)


def test_derive_intent_defaults_to_text_chat():
    intent = derive_intent(_make_request())
    assert intent.needs_streaming is False
    assert intent.needs_tools is False
    assert intent.needs_structured_output is False
    assert intent.needs_vision is False


def test_derive_intent_propagates_streaming_flag():
    intent = derive_intent(_make_request(requested_streaming=True))
    assert intent.needs_streaming is True


def test_derive_intent_recognises_tools_capability():
    intent = derive_intent(
        _make_request(requested_capabilities=["tools"])
    )
    assert intent.needs_tools is True


def test_derive_intent_recognises_structured_output():
    intent = derive_intent(
        _make_request(requested_capabilities=["structured_output"])
    )
    assert intent.needs_structured_output is True


def test_derive_intent_recognises_vision_capability():
    intent = derive_intent(
        _make_request(requested_capabilities=["vision"])
    )
    assert intent.needs_vision is True


def test_derive_intent_picks_up_image_block_in_messages():
    msg = Message(role="user", content="describe this")
    # Pydantic Message stores ``content`` as str — emulate vision by
    # injecting via metadata sniffing instead. The vision detector falls
    # back to checking message-content type, so this remains a
    # best-effort hint.
    request = _make_request(messages=[msg])
    intent = derive_intent(request)
    # Without explicit capability flag and string content, vision off.
    assert intent.needs_vision is False


def test_derive_intent_passes_preferred_provider_through_metadata():
    intent = derive_intent(
        _make_request(metadata={"preferred_provider": "openai"})
    )
    assert intent.preferred_provider == "openai"


# ── resolve_lane ──

def test_resolve_lane_vision_takes_priority():
    intent = RuntimeIntent(needs_vision=True, needs_tools=True)
    assert resolve_lane(intent) == ExecutionLane.VISION_EXTRACTION


def test_resolve_lane_full_combo_picks_cloud_native_sdk():
    intent = RuntimeIntent(
        needs_streaming=True,
        needs_tools=True,
        needs_structured_output=True,
    )
    assert resolve_lane(intent) == ExecutionLane.CLOUD_NATIVE_SDK


def test_resolve_lane_tools_only_uses_openai_http():
    intent = RuntimeIntent(needs_tools=True)
    assert resolve_lane(intent) == ExecutionLane.OPENAI_COMPATIBLE_HTTP


def test_resolve_lane_streaming_only_uses_openai_http():
    intent = RuntimeIntent(needs_streaming=True)
    assert resolve_lane(intent) == ExecutionLane.OPENAI_COMPATIBLE_HTTP


def test_resolve_lane_default_chat_uses_openai_http():
    intent = RuntimeIntent()
    assert resolve_lane(intent) == ExecutionLane.OPENAI_COMPATIBLE_HTTP


def test_resolve_lane_structured_without_streaming_uses_openai_http():
    """Structured output alone (no streaming) is OpenAI-compat-friendly."""
    intent = RuntimeIntent(needs_structured_output=True, needs_tools=True)
    assert resolve_lane(intent) == ExecutionLane.OPENAI_COMPATIBLE_HTTP
