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
    _resolve_public_thinking_content,
)
from app.engine.multi_agent.state import AgentState
from app.engine.reasoning import (
    capture_thinking_lifecycle_event,
    record_thinking_snapshot,
)
from app.engine.semantic_memory.memory_updater import MemoryAction, MemoryUpdater
from app.prompts.prompt_runtime_tail import get_thinking_instruction_from_shared_config

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
    thinking_instruction = get_thinking_instruction_from_shared_config({})
    try:
        from app.prompts.prompt_loader import get_prompt_loader
        from app.prompts.prompt_context_utils import build_response_language_instruction
        from app.engine.reasoning.thinking_enforcement import get_thinking_enforcement

        loader = get_prompt_loader()
        identity = loader.get_identity().get("identity", {})
        personality = identity.get("personality", {}).get("summary", "")
        emoji_usage = identity.get("voice", {}).get("emoji_usage", "")
        name = identity.get("name", "Wiii")
        thinking_instruction = str(loader.get_thinking_instruction() or "").strip() or thinking_instruction
        enforcement = get_thinking_enforcement()

        if personality:
            return "\n".join(
                part
                for part in (
                    enforcement,
                    f"Ban la {name} - {personality}\n- {emoji_usage}\n{_MEMORY_BEHAVIOR_RULES}",
                    build_response_language_instruction(response_language),
                    thinking_instruction,
                )
                if part
            )
    except Exception as exc:
        logger.warning("[MEMORY_AGENT] Failed to load identity YAML: %s", exc)

    try:
        from app.engine.reasoning.thinking_enforcement import get_thinking_enforcement
        enforcement = get_thinking_enforcement()
    except Exception:
        enforcement = ""

    return "\n".join(
        part
        for part in (
            enforcement,
            "Ban la Wiii - dang yeu, thich tro chuyen, giai thich ro rang.\n"
            "- Dung emoji tu nhien nhu nhan tin voi ban than (⚓🌊📚✨💡🎯😄)\n"
            f"{_MEMORY_BEHAVIOR_RULES}",
            thinking_instruction,
        )
        if part
    )


def _thinking_provenance_from_source(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if normalized == "gemini_native":
        return "provider_native"
    if normalized in {"text_tags", "visible_thinking_block"}:
        return "provider_summary"
    return "provider_native"


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
        state["allow_authored_thinking_fallback"] = False

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

        try:
            existing_facts_list = await self._retrieve_facts(user_id)
            existing_facts_dict = {fact["type"]: fact["content"] for fact in existing_facts_list}

            new_facts, decisions = await self._extract_and_store_facts(
                user_id,
                query,
                existing_facts_dict,
            )
            actionable_decisions = [
                decision for decision in decisions if decision.action != MemoryAction.NOOP
            ]
            action_counts = {}
            for decision in actionable_decisions:
                action_counts[decision.action.value] = action_counts.get(decision.action.value, 0) + 1
            changes_summary = self._updater.summarize_changes(actionable_decisions)

            response = await self._generate_response(
                llm,
                query,
                existing_facts_list,
                new_facts,
                changes_summary,
                state,
            )
            native_thinking = str(state.pop("_memory_native_thinking", "") or "").strip()
            thinking_source = str(state.pop("_memory_thinking_source", "") or "").strip()
            if native_thinking:
                provenance = _thinking_provenance_from_source(thinking_source)
                details = {"phase": "post_tool", "provenance": provenance}
                state["thinking_provenance"] = provenance
                await _push(
                    {
                        "type": "thinking_start",
                        "content": "",
                        "node": "memory_agent",
                        "details": details,
                        "provenance": provenance,
                    }
                )
                await _push(
                    {
                        "type": "thinking_delta",
                        "content": native_thinking,
                        "node": "memory_agent",
                        "details": details,
                        "provenance": provenance,
                    }
                )
                await _push(
                    {
                        "type": "thinking_end",
                        "content": "",
                        "node": "memory_agent",
                        "details": details,
                        "provenance": provenance,
                    }
                )
                state["thinking"] = native_thinking
                record_thinking_snapshot(
                    state,
                    native_thinking,
                    node="memory_agent",
                    provenance=provenance,
                )
            else:
                state.pop("thinking", None)
                state.pop("thinking_provenance", None)

            state["memory_output"] = response
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["memory"] = response
            state["current_agent"] = "memory_agent"

            public_memory_thinking = _resolve_public_thinking_content(state)
            if public_memory_thinking:
                state["thinking_content"] = public_memory_thinking
            else:
                state["thinking_content"] = ""

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
            state["thinking_content"] = ""
            state.pop("thinking", None)
            state.pop("thinking_provenance", None)

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
    ) -> tuple[list, list]:
        """Extract facts from the current message and store them via upsert."""
        if not self._semantic_memory or not user_id or not message:
            return [], []

        try:
            fact_extractor = getattr(self._semantic_memory, "_fact_extractor", None)
            if fact_extractor is None:
                logger.warning("[MEMORY_AGENT] No fact extractor available on semantic memory")
                return []

            stored_facts = await fact_extractor.extract_and_store_facts(
                user_id=user_id,
                message=message,
                existing_facts=existing_facts,
                return_decisions=True,
            )
            if (
                isinstance(stored_facts, tuple)
                and len(stored_facts) == 2
            ):
                facts, decisions = stored_facts
            else:
                facts, decisions = stored_facts or [], []
            return [fact.to_content() for fact in facts], list(decisions or [])
        except Exception as exc:
            logger.warning("[MEMORY_AGENT] Failed to extract facts: %s", exc)
            return [], []

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
        state.pop("_memory_native_thinking", None)
        state.pop("_memory_thinking_source", None)
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

            from app.services.thinking_post_processor import get_thinking_processor

            extraction = get_thinking_processor().process_result(response.content)
            result = extraction.text.strip()
            thinking = str(extraction.thinking or "").strip()
            if thinking:
                state["_memory_native_thinking"] = thinking
                state["_memory_thinking_source"] = extraction.source
                state["thinking"] = thinking

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
