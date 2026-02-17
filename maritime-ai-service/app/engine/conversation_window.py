"""
Conversation Window Manager — Sprint 77 + Sprint 78

Sprint 77: Sliding window with fixed RECENT_WINDOW=15
Sprint 78: Dynamic budget-based windowing via TokenBudgetManager
Sprint 80: Increased RECENT_WINDOW 15→30 (SOTA alignment: 10-30 verbatim messages standard)

Replaces the 300-char truncation in chat_history_repository.format_history_for_prompt()
with proper LangChain message objects for agent nodes.

SOTA Reference (Feb 2026):
  - ChatGPT: 4-layer (facts + summaries + session window)
  - Claude Code: Auto-compact at 65%, pause_after_compaction
  - OpenClawd: Pre-compaction memory flush, chars/4 token estimate
  - Mem0/Letta: Core memory (in-context) + archival memory + conversation buffer
  - LangMem: SummarizationNode, RunningSummary, budget-aware trimming
"""

import logging
from typing import Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

# Sprint 77: Fixed window fallback (used when no budget manager available)
# Sprint 80: Increased 15→30 (SOTA: 10-30 verbatim messages + summary is standard)
RECENT_WINDOW = 30

# Max chars for backward-compatible flat string format
FORMAT_CHAR_LIMIT = 1000

# Max chars per message in summary context
SUMMARY_MSG_LIMIT = 200

# Max total chars for summary of older messages
MAX_SUMMARY_CHARS = 2000


class ConversationWindowManager:
    """Sliding window: last N turns verbatim + older turns as condensed text.

    Sprint 77: Fixed RECENT_WINDOW=15, Sprint 80: RECENT_WINDOW=30
    Sprint 78: Dynamic budget-based windowing when TokenBudgetManager is available
    """

    def build_messages(self, history_list: List[Dict[str, str]]) -> List[BaseMessage]:
        """Convert recent history_list entries to LangChain HumanMessage/AIMessage.

        Takes last RECENT_WINDOW entries from history_list.
        Returns List[HumanMessage | AIMessage] — preserving full content (NO truncation).

        Args:
            history_list: List of dicts with "role" and "content" keys.
                          role is "user" or "assistant".

        Returns:
            List of LangChain BaseMessage objects.
        """
        if not history_list:
            return []

        recent = history_list[-RECENT_WINDOW:]
        messages: List[BaseMessage] = []

        for entry in recent:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if not content:
                continue
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        return messages

    def build_messages_with_budget(
        self,
        history_list: List[Dict[str, str]],
        system_prompt: str = "",
        core_memory: str = "",
        summary: str = "",
    ) -> Tuple[List[BaseMessage], "ContextBudget"]:
        """Build messages that fit within token budget (Sprint 78).

        Uses TokenBudgetManager to compute how many recent messages fit
        in the remaining budget after system prompt, core memory, and summary.
        Falls back to fixed RECENT_WINDOW if budget manager unavailable.

        Args:
            history_list: Full conversation history
            system_prompt: System prompt text for budget calculation
            core_memory: Core memory block text
            summary: Running conversation summary

        Returns:
            Tuple of (messages, budget)
        """
        try:
            from app.engine.context_manager import get_budget_manager

            mgr = get_budget_manager()
            return mgr.build_context_messages(
                history_list=history_list,
                system_prompt=system_prompt,
                core_memory=core_memory,
                summary=summary,
            )
        except Exception as e:
            logger.warning(
                "[WINDOW_MGR] Budget manager unavailable, using fixed window: %s", e
            )
            # Fallback to fixed window
            messages = self.build_messages(history_list)
            return messages, None

    def build_summary_context(
        self, history_list: List[Dict[str, str]], existing_summary: str = ""
    ) -> str:
        """Build text summary of older messages (beyond RECENT_WINDOW).

        If len(history_list) <= RECENT_WINDOW: return existing_summary unchanged.
        Otherwise: format older messages as condensed text for context.

        Args:
            history_list: Full conversation history.
            existing_summary: Previously generated summary (from memory_summarizer).

        Returns:
            Summary string for older messages.
        """
        if not history_list or len(history_list) <= RECENT_WINDOW:
            return existing_summary or ""

        older = history_list[:-RECENT_WINDOW]
        if not older:
            return existing_summary or ""

        # Build condensed summary of older messages
        lines = []
        total_chars = 0
        for entry in older:
            role = "User" if entry.get("role") == "user" else "AI"
            content = entry.get("content", "")
            truncated = content[:SUMMARY_MSG_LIMIT]
            if len(content) > SUMMARY_MSG_LIMIT:
                truncated += "..."
            line = f"{role}: {truncated}"
            if total_chars + len(line) > MAX_SUMMARY_CHARS:
                lines.append("...")
                break
            lines.append(line)
            total_chars += len(line)

        older_text = "\n".join(lines)

        # Combine with existing summary if available
        if existing_summary:
            return f"{existing_summary}\n\n--- Lịch sử cũ ---\n{older_text}"

        return older_text

    def format_for_prompt(self, history_list: List[Dict[str, str]]) -> str:
        """Backward-compatible flat string (for RAG context injection).

        Like chat_history_repository.format_history_for_prompt but with
        1000-char limit per message instead of 300.

        Args:
            history_list: Conversation history entries.

        Returns:
            Formatted string for prompt injection.
        """
        if not history_list:
            return ""

        lines = []
        for entry in history_list:
            role = "User" if entry.get("role") == "user" else "AI"
            content = entry.get("content", "")
            truncated = content[:FORMAT_CHAR_LIMIT]
            if len(content) > FORMAT_CHAR_LIMIT:
                truncated += "..."
            lines.append(f"{role}: {truncated}")

        return "\n".join(lines)
