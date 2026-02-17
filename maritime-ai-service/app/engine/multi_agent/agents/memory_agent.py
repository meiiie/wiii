"""
Memory Agent Node — Sprint 73: Retrieve-Extract-Decide-Respond

4-phase pipeline for personal memory management:
  Phase 1: RETRIEVE — Load existing user facts from semantic memory
  Phase 2: EXTRACT — Use FactExtractor with existing facts context (enhanced)
  Phase 3: DECIDE — MemoryUpdater classifies ADD/UPDATE/DELETE/NOOP (NEW)
  Phase 4: RESPOND — LLM generates natural response referencing changes (enhanced)

SOTA Reference (Feb 2026):
  OpenAI ChatGPT: background extraction + explicit acknowledgment
  Letta/MemGPT: core memory (in-context) + archival (DB) + agent self-editing
  Mem0: Two-phase extract→evaluate with ADD/UPDATE/DELETE/NOOP
  LangMem: background thread extraction with semantic dedup
  Our approach: Hybrid — inline extraction + Mem0 classify + LLM response

**Integrated with agents/ framework for config and tracing.**
"""

import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.engine.multi_agent.state import AgentState
from app.engine.agents import MEMORY_AGENT_CONFIG
from app.engine.semantic_memory.memory_updater import MemoryUpdater, MemoryAction

logger = logging.getLogger(__name__)

# Sprint 90: Build memory response prompt from wiii_identity.yaml (single source of truth)
# Removes hardcoded personality — loads via PromptLoader for consistency with all agents
_MEMORY_BEHAVIOR_RULES = (
    "- Dùng thông tin đã biết về user để trả lời tự nhiên\n"
    "- Nếu user chia sẻ thông tin mới, xác nhận đã ghi nhớ CỤ THỂ\n"
    "- Nếu thông tin được CẬP NHẬT, đề cập thay đổi\n"
    "- Nếu user hỏi về thông tin đã lưu, trả lời chính xác và đầy đủ\n"
    "- KHÔNG bắt đầu bằng 'Chào' hay lời chào — đi thẳng vào nội dung\n"
    "- KHÔNG bao gồm quá trình suy nghĩ\n"
    "- Trả lời bằng tiếng Việt"
)


def _build_memory_response_prompt() -> str:
    """Build memory agent prompt from wiii_identity.yaml + behavior rules.

    Sprint 90: Single source of truth for personality/voice.
    Falls back to inline defaults if YAML unavailable.
    """
    try:
        from app.prompts.prompt_loader import get_prompt_loader
        loader = get_prompt_loader()
        identity = loader.get_identity().get("identity", {})
        personality = identity.get("personality", {}).get("summary", "")
        emoji_usage = identity.get("voice", {}).get("emoji_usage", "")
        name = identity.get("name", "Wiii")

        if personality:
            return (
                f"Bạn là {name} — {personality}\n"
                f"- {emoji_usage}\n"
                f"{_MEMORY_BEHAVIOR_RULES}"
            )
    except Exception as e:
        logger.warning("[MEMORY_AGENT] Failed to load identity YAML: %s", e)

    # Fallback if YAML unavailable
    return (
        "Bạn là Wiii — đáng yêu, thích trò chuyện, giải thích rõ ràng.\n"
        "- Dùng emoji tự nhiên như nhắn tin với bạn thân (⚓🌊📚✨💡🎯😄)\n"
        f"{_MEMORY_BEHAVIOR_RULES}"
    )


class MemoryAgentNode:
    """
    Memory Agent — Retrieve-Extract-Decide-Respond pipeline.

    Phase 1: Retrieve existing user facts from semantic memory
    Phase 2: Extract new facts with existing facts context
    Phase 3: Classify via MemoryUpdater → ADD/UPDATE/DELETE/NOOP
    Phase 4: Generate natural LLM response referencing specific changes

    Implements agents/ framework integration.
    """

    def __init__(self, semantic_memory=None):
        """
        Initialize Memory Agent.

        Args:
            semantic_memory: SemanticMemoryEngine instance (or None for graceful degradation)
        """
        self._semantic_memory = semantic_memory
        self._config = MEMORY_AGENT_CONFIG
        self._updater = MemoryUpdater()
        logger.info("MemoryAgentNode initialized (Sprint 73: Retrieve-Extract-Decide-Respond)")

    async def process(self, state: AgentState, llm=None) -> AgentState:
        """
        Execute 4-phase memory pipeline.

        Args:
            state: Current agent state
            llm: Optional LangChain LLM for response generation

        Returns:
            Updated state with memory_output and agent_outputs
        """
        user_id = state.get("user_id", "")
        query = state.get("query", "")

        try:
            # Phase 1: RETRIEVE existing facts
            existing_facts_list = await self._retrieve_facts(user_id)
            existing_facts_dict = {f["type"]: f["content"] for f in existing_facts_list}

            # Phase 2: EXTRACT new facts (with existing facts context)
            new_facts = await self._extract_and_store_facts(
                user_id, query, existing_facts_dict,
            )

            # Phase 3: DECIDE — classify changes via MemoryUpdater
            parsed_facts = []
            for f in new_facts:
                if ": " in f:
                    parts = f.split(": ", 1)
                    parsed_facts.append({"fact_type": parts[0], "value": parts[1]})
                elif f.strip():
                    parsed_facts.append({"fact_type": "unknown", "value": f.strip()})
            decisions = self._updater.classify_batch(
                extracted_facts=parsed_facts,
                existing_facts=existing_facts_dict,
            )

            # Execute DELETE actions against DB
            for d in decisions:
                if d.action == MemoryAction.DELETE and self._semantic_memory:
                    try:
                        await self._semantic_memory.delete_memory_by_keyword(
                            user_id=user_id,
                            keyword=d.old_value or d.new_value,
                        )
                        logger.info("[MEMORY_AGENT] Executed DELETE for %s: %s", d.fact_type, d.old_value)
                    except Exception as e:
                        logger.warning("[MEMORY_AGENT] DELETE failed for %s: %s", d.fact_type, e)

            changes_summary = self._updater.summarize_changes(decisions)

            # Phase 4: RESPOND with LLM using all context + changes
            response = await self._generate_response(
                llm, query, existing_facts_list, new_facts, changes_summary, state,
            )

            # Update state
            state["memory_output"] = response
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["memory"] = response
            state["current_agent"] = "memory_agent"

            action_counts = {}
            for d in decisions:
                action_counts[d.action.value] = action_counts.get(d.action.value, 0) + 1

            logger.info(
                "[MEMORY_AGENT] Processed for user %s: %d existing, %d extracted, actions=%s",
                user_id, len(existing_facts_list), len(new_facts), action_counts,
            )

        except Exception as e:
            logger.error("[MEMORY_AGENT] Error: %s", e)
            # Graceful fallback — never return an error to the user
            fallback = self._template_response(query, [], [], "")
            state["memory_output"] = fallback
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["memory"] = fallback
            state["current_agent"] = "memory_agent"

        return state

    # =========================================================================
    # Phase 1: RETRIEVE
    # =========================================================================

    async def _retrieve_facts(self, user_id: str) -> list:
        """
        Retrieve existing user facts from semantic memory.

        Returns:
            List of fact dicts: [{"type": "name", "content": "Minh"}, ...]
        """
        if not self._semantic_memory or not user_id:
            return []

        try:
            facts_dict = await self._semantic_memory.get_user_facts(user_id)
            # Convert dict → list of {type, content} for uniform handling
            result = []
            for fact_type, value in facts_dict.items():
                if value:
                    if isinstance(value, list):
                        for item in value:
                            result.append({"type": fact_type, "content": str(item)})
                    else:
                        result.append({"type": fact_type, "content": str(value)})
            return result
        except Exception as e:
            logger.warning("[MEMORY_AGENT] Failed to retrieve facts: %s", e)
            return []

    # =========================================================================
    # Phase 2: EXTRACT + STORE
    # =========================================================================

    async def _extract_and_store_facts(
        self, user_id: str, message: str, existing_facts: dict,
    ) -> list:
        """
        Extract facts from current message and store via upsert.

        Sprint 73: Passes existing_facts to FactExtractor for
        context-aware extraction (avoids re-extracting known info).

        Returns:
            List of new fact content strings that were stored.
        """
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
            # Return content strings for response generation
            return [f.to_content() for f in stored_facts]
        except Exception as e:
            logger.warning("[MEMORY_AGENT] Failed to extract facts: %s", e)
            return []

    # =========================================================================
    # Phase 4: RESPOND
    # =========================================================================

    async def _generate_response(
        self,
        llm,
        query: str,
        existing_facts: list,
        new_facts: list,
        changes_summary: str,
        state: AgentState,
    ) -> str:
        """
        Generate natural Vietnamese response using LLM with memory context.

        Sprint 73: Includes changes_summary so LLM can reference specific
        ADD/UPDATE/DELETE changes in its response.

        Falls back to template response if LLM is unavailable.
        """
        if not llm:
            return self._template_response(query, existing_facts, new_facts, changes_summary)

        try:
            # Build context block for LLM
            context_parts = []
            if existing_facts:
                facts_str = "\n".join(
                    f"- {f['type']}: {f['content']}" for f in existing_facts
                )
                context_parts.append(f"Thông tin đã biết về user:\n{facts_str}")
            if new_facts:
                new_str = "\n".join(f"- {f}" for f in new_facts)
                context_parts.append(f"Thông tin mới vừa ghi nhớ:\n{new_str}")
            if changes_summary:
                context_parts.append(f"Thay đổi: {changes_summary}")

            context_block = "\n\n".join(context_parts) if context_parts else "Chưa có thông tin nào về user."

            messages = [SystemMessage(content=_build_memory_response_prompt())]
            # Sprint 77: Inject last 5 turns for conversational continuity
            lc_messages = state.get("context", {}).get("langchain_messages", [])
            if lc_messages:
                messages.extend(lc_messages[-5:])
            messages.append(HumanMessage(content=(
                f"Ngữ cảnh bộ nhớ:\n{context_block}\n\n"
                f"Tin nhắn của user: {query}"
            )))

            response = await llm.ainvoke(messages)

            # Handle Gemini content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, thinking = extract_thinking_from_response(response.content)
            result = text_content.strip()

            if thinking:
                state["thinking"] = thinking

            if result:
                return result

            # LLM returned empty — fall back to template
            return self._template_response(query, existing_facts, new_facts, changes_summary)

        except Exception as e:
            logger.warning("[MEMORY_AGENT] LLM response generation failed: %s", e)
            return self._template_response(query, existing_facts, new_facts, changes_summary)

    def _template_response(
        self,
        query: str,
        existing_facts: list,
        new_facts: list,
        changes_summary: str,
    ) -> str:
        """
        Template-based fallback response when LLM is unavailable.

        Never returns a hardcoded error — always a natural acknowledgment.
        Sprint 73: Includes changes_summary in response.
        """
        # Case 1: Changes were made — use summary
        if changes_summary:
            return f"{changes_summary}. Bạn cứ hỏi lại bất cứ lúc nào nhé!"

        # Case 2: New facts were stored — acknowledge
        if new_facts:
            items = ", ".join(new_facts[:3])
            return f"Mình đã ghi nhớ: {items}. Bạn cứ hỏi lại bất cứ lúc nào nhé!"

        # Case 3: User is asking about stored facts
        if existing_facts:
            facts_str = ", ".join(
                f"{f['type']}: {f['content']}" for f in existing_facts[:5]
            )
            return f"Đây là thông tin mình biết về bạn: {facts_str}"

        # Case 4: No facts at all — friendly response
        return "Mình chưa có thông tin gì về bạn. Bạn có thể chia sẻ để mình ghi nhớ nhé!"

    def is_available(self) -> bool:
        """Check if memory services are available."""
        return self._semantic_memory is not None


# Singleton
_memory_node: Optional[MemoryAgentNode] = None


def get_memory_agent_node(semantic_memory=None) -> MemoryAgentNode:
    """Get or create MemoryAgentNode singleton."""
    global _memory_node
    if _memory_node is None:
        _memory_node = MemoryAgentNode(semantic_memory=semantic_memory)
    return _memory_node
