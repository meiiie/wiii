"""
Colleague Agent Node — Cross-Soul consultation via SoulBridge.

Sprint 215: "Hỏi Bro" — routes admin questions to a peer soul (Bro)
and returns the response through the Synthesizer.

Defense-in-depth: double-checks admin role even though Supervisor already gated.
Feature-gated: enable_cross_soul_query + enable_soul_bridge.
"""

import logging

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)


async def colleague_agent_process(state: AgentState) -> AgentState:
    """Process a cross-soul consultation request.

    1. Defense-in-depth admin check
    2. Get SoulBridge singleton
    3. ask_peer() with timeout
    4. Parse response → set agent_outputs
    5. Fallback on timeout/error

    Args:
        state: Current agent state with query, context, etc.

    Returns:
        Updated state with colleague response in agent_outputs.
    """
    query = state.get("query", "")
    context = state.get("context", {})
    user_id = state.get("user_id", "")

    # Defense-in-depth: verify admin role (Supervisor already checked, but belt-and-suspenders)
    user_role = context.get("user_role") or context.get("role") or "student"
    if user_role != "admin":
        logger.warning("[COLLEAGUE] Non-admin user '%s' (role=%s) reached colleague node — denying", user_id, user_role)
        state["final_response"] = "Tính năng này chỉ dành cho quản trị viên."
        state["agent_outputs"] = {"colleague": state["final_response"]}
        state["current_agent"] = "colleague_agent"
        return state

    # Get settings
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.enable_cross_soul_query or not settings.enable_soul_bridge:
        logger.info("[COLLEAGUE] Feature disabled, returning fallback")
        state["final_response"] = "Tính năng hỏi Bro hiện chưa được bật."
        state["agent_outputs"] = {"colleague": state["final_response"]}
        state["current_agent"] = "colleague_agent"
        return state

    peer_id = settings.cross_soul_query_peer_id
    timeout = settings.cross_soul_query_timeout

    # Build consultation payload
    payload = {
        "query": query,
        "user_id": user_id,
        "context": {
            "domain_hint": "trading",
            "conversation_phase": context.get("conversation_phase", "engaged"),
        },
        "domain_hint": "trading",
        "timeout_seconds": timeout,
    }

    # Get SoulBridge and ask peer
    try:
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()

        if not bridge.is_initialized:
            logger.warning("[COLLEAGUE] SoulBridge not initialized")
            _set_fallback(state)
            return state

        reply = await bridge.ask_peer(
            peer_id=peer_id,
            event_type="CONSULTATION",
            payload=payload,
            timeout=timeout,
        )

        if reply is None:
            logger.warning("[COLLEAGUE] No reply from peer '%s' (timeout or disconnected)", peer_id)
            _set_fallback(state)
            return state

        # Parse response from reply payload
        reply_payload = reply.payload or {}
        response_text = reply_payload.get("response", "")
        error = reply_payload.get("error", "")

        if error:
            logger.warning("[COLLEAGUE] Peer returned error: %s", error)
            _set_fallback(state)
            return state

        if not response_text:
            logger.warning("[COLLEAGUE] Empty response from peer")
            _set_fallback(state)
            return state

        # Build colleague response with mood/confidence metadata
        mood = reply_payload.get("mood", "")
        confidence = reply_payload.get("confidence", 0.0)
        sources = reply_payload.get("sources", [])

        mood_prefix = f"[Bro mood: {mood}] " if mood else ""
        colleague_output = f"{mood_prefix}{response_text}"

        state["agent_outputs"] = {"colleague": colleague_output}
        state["rag_output"] = colleague_output  # For synthesizer compatibility
        if sources:
            state["sources"] = [{"source": s} for s in sources] if isinstance(sources[0], str) else sources
        state["current_agent"] = "colleague_agent"

        logger.info(
            "[COLLEAGUE] Got response from '%s': %d chars, confidence=%.2f, mood=%s",
            peer_id, len(response_text), confidence, mood,
        )

    except Exception as e:
        logger.warning("[COLLEAGUE] Error during consultation: %s", e)
        _set_fallback(state)

    return state


def _set_fallback(state: AgentState) -> None:
    """Set Vietnamese fallback response when Bro is unreachable."""
    fallback = "Mình không thể kết nối với Bro lúc này. Bạn thử hỏi lại sau nhé!"
    state["final_response"] = fallback
    state["agent_outputs"] = {"colleague": fallback}
    state["current_agent"] = "colleague_agent"
