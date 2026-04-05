"""
Memory Agent Node - Sprint 73: Retrieve-Extract-Decide-Respond

4-phase pipeline for personal memory management:
  Phase 1: RETRIEVE - Load existing user facts from semantic memory
  Phase 2: EXTRACT - Use FactExtractor with existing facts context
  Phase 3: DECIDE - MemoryUpdater classifies ADD/UPDATE/DELETE/NOOP
  Phase 4: RESPOND - LLM generates natural response referencing changes

Integrated with the agents/ framework for config and tracing.
"""

import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.engine.agents import MEMORY_AGENT_CONFIG
from app.engine.multi_agent.public_thinking import (
    _append_public_thinking_fragment,
    _resolve_public_thinking_content,
)
from app.engine.multi_agent.state import AgentState
from app.engine.reasoning import (
    ReasoningRenderRequest,
    build_living_thinking_context,
    capture_thinking_lifecycle_event,
    get_reasoning_narrator,
)
from app.engine.semantic_memory.memory_updater import MemoryAction, MemoryUpdater

logger = logging.getLogger(__name__)

_MEMORY_BEHAVIOR_RULES = (
    "- Dung thong tin da biet ve user de tra loi tu nhien\n"
    "- Neu user chia se thong tin moi, xac nhan da ghi nho cu the\n"
    "- Neu thong tin duoc cap nhat, de cap thay doi\n"
    "- Neu user hoi ve thong tin da luu, tra loi chinh xac va day du\n"
    "- KHONG bat dau bang loi chao - di thang vao noi dung\n"
    "- KHONG bao gom qua trinh suy nghi"
)


def _build_memory_response_prompt(response_language: str = "vi") -> str:
    """Build memory agent prompt from wiii_identity.yaml + behavior rules."""
    try:
        from app.prompts.prompt_loader import get_prompt_loader
        from app.prompts.prompt_context_utils import build_response_language_instruction

        loader = get_prompt_loader()
        identity = loader.get_identity().get("identity", {})
        personality = identity.get("personality", {}).get("summary", "")
        emoji_usage = identity.get("voice", {}).get("emoji_usage", "")
        name = identity.get("name", "Wiii")

        if personality:
            return (
                f"Ban la {name} - {personality}\n"
                f"- {emoji_usage}\n"
                f"{_MEMORY_BEHAVIOR_RULES}\n"
                f"{build_response_language_instruction(response_language)}"
            )
    except Exception as exc:
        logger.warning("[MEMORY_AGENT] Failed to load identity YAML: %s", exc)

    return (
        "Ban la Wiii - dang yeu, thich tro chuyen, giai thich ro rang.\n"
        "- Dung emoji tu nhien nhu nhan tin voi ban than (⚓🌊📚✨💡🎯😄)\n"
        f"{_MEMORY_BEHAVIOR_RULES}"
    )


class MemoryAgentNode:
    """
    Memory Agent - Retrieve-Extract-Decide-Respond pipeline.

    Phase 1: Retrieve existing user facts from semantic memory
    Phase 2: Extract new facts with existing facts context
    Phase 3: Classify via MemoryUpdater -> ADD/UPDATE/DELETE/NOOP
    Phase 4: Generate natural LLM response referencing specific changes
    """

    def __init__(self, semantic_memory=None):
        self._semantic_memory = semantic_memory
        self._config = MEMORY_AGENT_CONFIG
        self._updater = MemoryUpdater()
        logger.info("MemoryAgentNode initialized (Sprint 73: Retrieve-Extract-Decide-Respond)")

    async def process(self, state: AgentState, llm=None) -> AgentState:
        """Execute the 4-phase memory pipeline."""
        user_id = state.get("user_id", "")
        query = state.get("query", "")
        context = state.get("context") or {}
        living_thinking_context = build_living_thinking_context(
            user_id=user_id or "__global__",
            organization_id=state.get("organization_id") or context.get("organization_id"),
            mood_hint=context.get("mood_hint"),
            personality_mode=context.get("personality_mode"),
            lane="memory",
            intent="personal",
        )

        event_queue = None
        bus_id = state.get("_event_bus_id")
        if bus_id:
            from app.engine.multi_agent.graph_event_bus import _get_event_queue

            event_queue = _get_event_queue(bus_id)

        async def _push(event: dict):
            capture_thinking_lifecycle_event(state, event)
            if event_queue:
                try:
                    event_queue.put_nowait(event)
                except Exception:
                    pass

        narrator_state = {
            "current_state": list(living_thinking_context.runtime_notes),
            "narrative_state": [
                item
                for item in (
                    living_thinking_context.identity_anchor,
                    *living_thinking_context.reasoning_style,
                )
                if item
            ],
            "relationship_memory": list(living_thinking_context.relationship_style),
        }

        async def _emit_narration(narration, *, include_header: bool = False):
            if include_header and (narration.label or narration.summary):
                await _push(
                    {
                        "type": "thinking_start",
                        "content": narration.label,
                        "node": "memory_agent",
                        "summary": narration.summary,
                        "details": {
                            "phase": getattr(narration, "phase", ""),
                            "style_tags": list(getattr(narration, "style_tags", []) or []),
                        },
                    }
                )

            fragments = [str(chunk).strip() for chunk in (getattr(narration, "delta_chunks", []) or []) if str(chunk).strip()]
            if not fragments and str(getattr(narration, "summary", "") or "").strip():
                fragments = [str(narration.summary).strip()]

            for fragment in fragments:
                await _push(
                    {
                        "type": "thinking_delta",
                        "content": fragment,
                        "node": "memory_agent",
                    }
                )
                _append_public_thinking_fragment(
                    state,
                    fragment,
                    node="memory_agent",
                    capture=False,
                )

        try:
            retrieve_narration = await get_reasoning_narrator().render(
                ReasoningRenderRequest(
                    node="memory_agent",
                    phase="retrieve",
                    user_goal=query,
                    conversation_context=str((state.get("context") or {}).get("conversation_summary", "")),
                    next_action="Luc lai nhung manh ngu canh rieng co the do cau tra loi nay.",
                    user_id=user_id or "__global__",
                    organization_id=state.get("organization_id"),
                    personality_mode=(state.get("context") or {}).get("personality_mode"),
                    mood_hint=(state.get("context") or {}).get("mood_hint"),
                    visibility_mode="rich",
                    style_tags=["memory", "retrieve"],
                    **narrator_state,
                )
            )
            await _emit_narration(retrieve_narration, include_header=True)

            existing_facts_list = await self._retrieve_facts(user_id)
            existing_facts_dict = {fact["type"]: fact["content"] for fact in existing_facts_list}

            if existing_facts_list:
                existing_narration = await get_reasoning_narrator().render(
                    ReasoningRenderRequest(
                        node="memory_agent",
                        phase="verify",
                        user_goal=query,
                        memory_context=f"{len(existing_facts_list)} manh ky uc dang con lien quan.",
                        next_action="Xem manh nao con dang giu va manh nao can noi vao cau hoi luc nay.",
                        observations=[f"existing_facts={len(existing_facts_list)}"],
                        user_id=user_id or "__global__",
                        organization_id=state.get("organization_id"),
                        personality_mode=(state.get("context") or {}).get("personality_mode"),
                        mood_hint=(state.get("context") or {}).get("mood_hint"),
                        visibility_mode="rich",
                        style_tags=["memory", "verify"],
                        **narrator_state,
                    )
                )
                await _emit_narration(existing_narration)

            extract_narration = await get_reasoning_narrator().render(
                ReasoningRenderRequest(
                    node="memory_agent",
                    phase="verify",
                    user_goal=query,
                    memory_context=f"{len(existing_facts_list)} manh ky uc dang duoc doi chieu voi tin nhan moi.",
                    next_action="Soi xem trong tin nhan nay co dieu gi moi that su dang giu lai.",
                    user_id=user_id or "__global__",
                    organization_id=state.get("organization_id"),
                    personality_mode=(state.get("context") or {}).get("personality_mode"),
                    mood_hint=(state.get("context") or {}).get("mood_hint"),
                    visibility_mode="rich",
                    style_tags=["memory", "extract"],
                    **narrator_state,
                )
            )
            await _emit_narration(extract_narration)

            new_facts = await self._extract_and_store_facts(user_id, query, existing_facts_dict)
            if new_facts:
                new_fact_narration = await get_reasoning_narrator().render(
                    ReasoningRenderRequest(
                        node="memory_agent",
                        phase="verify",
                        user_goal=query,
                        memory_context=f"{len(new_facts)} chi tiet moi vua noi len.",
                        next_action="Gan lai xem chi tiet moi nao nen duoc giu that lau hon.",
                        observations=[f"new_facts={len(new_facts)}"],
                        user_id=user_id or "__global__",
                        organization_id=state.get("organization_id"),
                        personality_mode=(state.get("context") or {}).get("personality_mode"),
                        mood_hint=(state.get("context") or {}).get("mood_hint"),
                        visibility_mode="rich",
                        style_tags=["memory", "new_facts"],
                        **narrator_state,
                    )
                )
                await _emit_narration(new_fact_narration)

            parsed_facts = []
            for fact in new_facts:
                if ": " in fact:
                    fact_type, value = fact.split(": ", 1)
                    parsed_facts.append({"fact_type": fact_type, "value": value})
                elif fact.strip():
                    parsed_facts.append({"fact_type": "unknown", "value": fact.strip()})

            decisions = self._updater.classify_batch(
                extracted_facts=parsed_facts,
                existing_facts=existing_facts_dict,
            )

            for decision in decisions:
                if decision.action == MemoryAction.DELETE and self._semantic_memory:
                    try:
                        await self._semantic_memory.delete_memory_by_keyword(
                            user_id=user_id,
                            keyword=decision.old_value or decision.new_value,
                        )
                        logger.info(
                            "[MEMORY_AGENT] Executed DELETE for %s: %s",
                            decision.fact_type,
                            decision.old_value,
                        )
                    except Exception as exc:
                        logger.warning(
                            "[MEMORY_AGENT] DELETE failed for %s: %s",
                            decision.fact_type,
                            exc,
                        )

            action_counts = {}
            for decision in decisions:
                action_counts[decision.action.value] = action_counts.get(decision.action.value, 0) + 1

            changes_summary = self._updater.summarize_changes(decisions)
            await _push({"type": "thinking_end", "content": "", "node": "memory_agent"})

            synthesis_narration = await get_reasoning_narrator().render(
                ReasoningRenderRequest(
                    node="memory_agent",
                    phase="synthesize",
                    user_goal=query,
                    memory_context=(
                        f"{sum(action_counts.values())} thay doi can khau lai."
                        if action_counts
                        else "Khong co thay doi lon, chi can tra loi that tu nhien."
                    ),
                    next_action="Khau dieu cu va dieu moi thanh mot cau tra loi gan nguoi dung.",
                    user_id=user_id or "__global__",
                    organization_id=state.get("organization_id"),
                    personality_mode=(state.get("context") or {}).get("personality_mode"),
                    mood_hint=(state.get("context") or {}).get("mood_hint"),
                    visibility_mode="rich",
                    style_tags=["memory", "synthesis"],
                    **narrator_state,
                )
            )
            await _emit_narration(synthesis_narration, include_header=True)

            response = await self._generate_response(
                llm,
                query,
                existing_facts_list,
                new_facts,
                changes_summary,
                state,
            )
            await _push({"type": "thinking_end", "content": "", "node": "memory_agent"})

            state["memory_output"] = response
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["memory"] = response
            state["current_agent"] = "memory_agent"
            state.pop("thinking", None)

            public_memory_thinking = _resolve_public_thinking_content(state)
            if public_memory_thinking:
                state["thinking_content"] = public_memory_thinking

            logger.info(
                "[MEMORY_AGENT] Processed for user %s: %d existing, %d extracted, actions=%s",
                user_id,
                len(existing_facts_list),
                len(new_facts),
                action_counts,
            )

        except Exception as exc:
            logger.error("[MEMORY_AGENT] Error: %s", exc)
            fallback = self._template_response(query, [], [], "")
            state["memory_output"] = fallback
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["memory"] = fallback
            state["current_agent"] = "memory_agent"

        return state

    async def _retrieve_facts(self, user_id: str) -> list:
        """Retrieve existing user facts from semantic memory."""
        if not self._semantic_memory or not user_id:
            return []

        try:
            facts_dict = await self._semantic_memory.get_user_facts(user_id)
            result = []
            for fact_type, value in facts_dict.items():
                if value:
                    if isinstance(value, list):
                        for item in value:
                            result.append({"type": fact_type, "content": str(item)})
                    else:
                        result.append({"type": fact_type, "content": str(value)})
            return result
        except Exception as exc:
            logger.warning("[MEMORY_AGENT] Failed to retrieve facts: %s", exc)
            return []

    async def _extract_and_store_facts(
        self,
        user_id: str,
        message: str,
        existing_facts: dict,
    ) -> list:
        """Extract facts from the current message and store them via upsert."""
        if not self._semantic_memory or not user_id or not message:
            return []

        try:
            fact_extractor = getattr(self._semantic_memory, "_fact_extractor", None)
            if fact_extractor is None:
                logger.warning("[MEMORY_AGENT] No fact extractor available on semantic memory")
                return []

            stored_facts = await fact_extractor.extract_and_store_facts(
                user_id=user_id,
                message=message,
                existing_facts=existing_facts,
            )
            return [fact.to_content() for fact in stored_facts]
        except Exception as exc:
            logger.warning("[MEMORY_AGENT] Failed to extract facts: %s", exc)
            return []

    async def _generate_response(
        self,
        llm,
        query: str,
        existing_facts: list,
        new_facts: list,
        changes_summary: str,
        state: AgentState,
    ) -> str:
        """Generate a natural Vietnamese response using LLM memory context."""
        if not llm:
            return self._template_response(query, existing_facts, new_facts, changes_summary)

        try:
            context_parts = []
            if existing_facts:
                facts_str = "\n".join(f"- {fact['type']}: {fact['content']}" for fact in existing_facts)
                context_parts.append(f"Thong tin da biet ve user:\n{facts_str}")
            if new_facts:
                new_str = "\n".join(f"- {fact}" for fact in new_facts)
                context_parts.append(f"Thong tin moi vua ghi nho:\n{new_str}")
            if changes_summary:
                context_parts.append(f"Thay doi: {changes_summary}")

            ctx = state.get("context", {})
            lms_external_id = ctx.get("lms_external_id")
            lms_connector_id = ctx.get("lms_connector_id")
            if lms_external_id and lms_connector_id:
                try:
                    from app.core.config import settings as cfg

                    if getattr(cfg, "enable_lms_integration", False):
                        from app.integrations.lms.context_loader import get_lms_context_loader

                        loader = get_lms_context_loader()
                        lms_ctx = loader.load_student_context(
                            lms_external_id,
                            connector_id=lms_connector_id,
                        )
                        if lms_ctx:
                            context_parts.append(loader.format_for_prompt(lms_ctx))
                except Exception:
                    pass

            for key in (
                "host_context_prompt",
                "host_capabilities_prompt",
                "operator_context_prompt",
                "living_context_prompt",
                "widget_feedback_prompt",
            ):
                prompt = state.get(key, "")
                if prompt:
                    context_parts.append(prompt)

            context_block = (
                "\n\n".join(context_parts)
                if context_parts
                else "Chua co thong tin nao ve user."
            )

            messages = [SystemMessage(content=_build_memory_response_prompt(ctx.get("response_language", "vi")))]
            langchain_messages = state.get("context", {}).get("langchain_messages", [])
            if langchain_messages:
                messages.extend(langchain_messages[-5:])
            messages.append(
                HumanMessage(
                    content=(
                        f"Ngu canh bo nho:\n{context_block}\n\n"
                        f"Tin nhan cua user: {query}"
                    )
                )
            )

            response = await llm.ainvoke(messages)

            from app.services.output_processor import extract_thinking_from_response

            text_content, _thinking = extract_thinking_from_response(response.content)
            result = text_content.strip()

            if result:
                return result

            return self._template_response(query, existing_facts, new_facts, changes_summary)

        except Exception as exc:
            logger.warning("[MEMORY_AGENT] LLM response generation failed: %s", exc)
            return self._template_response(query, existing_facts, new_facts, changes_summary)

    def _template_response(
        self,
        query: str,
        existing_facts: list,
        new_facts: list,
        changes_summary: str,
    ) -> str:
        """Template fallback response when LLM is unavailable."""
        if changes_summary:
            return f"{changes_summary}. Bạn cứ hỏi lại bất cứ lúc nào nhé!"

        if new_facts:
            items = ", ".join(new_facts[:3])
            return f"Mình đã ghi nhớ: {items}. Bạn cứ hỏi lại bất cứ lúc nào nhé!"

        if existing_facts:
            facts_str = ", ".join(
                f"{fact['type']}: {fact['content']}" for fact in existing_facts[:5]
            )
            return f"Đây là thông tin mình biết về bạn: {facts_str}"

        return "Mình chưa có thông tin gì về bạn. Bạn có thể chia sẻ để mình ghi nhớ nhé!"

    def is_available(self) -> bool:
        """Check if memory services are available."""
        return self._semantic_memory is not None


_memory_node: Optional[MemoryAgentNode] = None


def get_memory_agent_node(semantic_memory=None) -> MemoryAgentNode:
    """Get or create MemoryAgentNode singleton."""
    global _memory_node
    if _memory_node is None:
        _memory_node = MemoryAgentNode(semantic_memory=semantic_memory)
    return _memory_node
