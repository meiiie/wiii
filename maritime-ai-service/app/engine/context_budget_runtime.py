"""Token budgeting contracts and heuristics for conversation context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from langchain_core.messages import BaseMessage


DEFAULT_EFFECTIVE_WINDOW = 32_000
MAX_OUTPUT_TOKENS = 8_192
SAFETY_MARGIN_RATIO = 0.10
COMPACTION_THRESHOLD = 0.75
SYSTEM_PROMPT_RATIO = 0.15
CORE_MEMORY_RATIO = 0.05
SUMMARY_RATIO = 0.10
MAX_SUMMARY_TOKENS = 1500
MIN_MESSAGES_FOR_SUMMARY = 6
CHARS_PER_TOKEN = 4


@dataclass
class ContextBudget:
    """Token budget allocation across context layers."""

    effective_window: int = DEFAULT_EFFECTIVE_WINDOW
    max_output: int = MAX_OUTPUT_TOKENS
    safety_margin: int = 0
    system_prompt_budget: int = 0
    core_memory_budget: int = 0
    summary_budget: int = 0
    recent_messages_budget: int = 0
    system_prompt_used: int = 0
    core_memory_used: int = 0
    summary_used: int = 0
    recent_messages_used: int = 0
    total_budget: int = 0
    total_used: int = 0
    utilization: float = 0.0
    needs_compaction: bool = False
    messages_included: int = 0
    messages_dropped: int = 0
    has_summary: bool = False

    def to_dict(self) -> Dict:
        """Serialize for API response / logging."""
        return {
            "effective_window": self.effective_window,
            "max_output": self.max_output,
            "total_budget": self.total_budget,
            "total_used": self.total_used,
            "utilization": round(self.utilization, 3),
            "needs_compaction": self.needs_compaction,
            "layers": {
                "system_prompt": {
                    "budget": self.system_prompt_budget,
                    "used": self.system_prompt_used,
                },
                "core_memory": {
                    "budget": self.core_memory_budget,
                    "used": self.core_memory_used,
                },
                "summary": {
                    "budget": self.summary_budget,
                    "used": self.summary_used,
                },
                "recent_messages": {
                    "budget": self.recent_messages_budget,
                    "used": self.recent_messages_used,
                },
            },
            "messages_included": self.messages_included,
            "messages_dropped": self.messages_dropped,
            "has_summary": self.has_summary,
        }


class TokenBudgetManager:
    """
    SOTA token budget management for 4-layer context architecture.

    Estimates token usage using chars/4 heuristic (fast, no API call),
    allocates budget across layers, and detects when compaction is needed.
    """

    def __init__(
        self,
        effective_window: int = DEFAULT_EFFECTIVE_WINDOW,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        compaction_threshold: float = COMPACTION_THRESHOLD,
    ):
        self.effective_window = effective_window
        self.max_output_tokens = max_output_tokens
        self.compaction_threshold = compaction_threshold

    def estimate_tokens(self, text: str) -> int:
        """Fast token estimation using chars/4 heuristic."""
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    def estimate_messages_tokens(self, messages: list[BaseMessage]) -> int:
        """Estimate total tokens for a list of LangChain messages."""
        total = 0
        for msg in messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            total += self.estimate_tokens(content)
            total += 4
        return total

    def estimate_history_tokens(self, history_list: list[Dict[str, str]]) -> int:
        """Estimate tokens for raw history list (before conversion to messages)."""
        total = 0
        for entry in history_list:
            content = entry.get("content", "")
            total += self.estimate_tokens(content)
            total += 4
        return total

    def allocate(
        self,
        system_prompt: str = "",
        core_memory: str = "",
        summary: str = "",
        history_list: Optional[list[Dict[str, str]]] = None,
    ) -> ContextBudget:
        """Allocate token budget across 4 layers."""
        history_list = history_list or []

        budget = ContextBudget(
            effective_window=self.effective_window,
            max_output=self.max_output_tokens,
        )

        total_available = self.effective_window - self.max_output_tokens
        budget.safety_margin = int(total_available * SAFETY_MARGIN_RATIO)
        total_available -= budget.safety_margin
        budget.total_budget = max(0, total_available)

        budget.system_prompt_budget = int(total_available * SYSTEM_PROMPT_RATIO)
        budget.core_memory_budget = int(total_available * CORE_MEMORY_RATIO)
        budget.summary_budget = int(total_available * SUMMARY_RATIO)
        budget.recent_messages_budget = (
            total_available
            - budget.system_prompt_budget
            - budget.core_memory_budget
            - budget.summary_budget
        )

        budget.system_prompt_used = self.estimate_tokens(system_prompt)
        budget.core_memory_used = self.estimate_tokens(core_memory)
        budget.summary_used = self.estimate_tokens(summary)
        budget.has_summary = bool(summary)

        fixed_used = (
            budget.system_prompt_used
            + budget.core_memory_used
            + budget.summary_used
        )
        remaining_for_messages = max(0, total_available - fixed_used)

        messages_tokens = 0
        included = 0
        for entry in reversed(history_list):
            entry_tokens = self.estimate_tokens(entry.get("content", "")) + 4
            if messages_tokens + entry_tokens > remaining_for_messages:
                break
            messages_tokens += entry_tokens
            included += 1

        budget.recent_messages_used = messages_tokens
        budget.messages_included = included
        budget.messages_dropped = max(0, len(history_list) - included)
        budget.total_used = fixed_used + messages_tokens
        budget.utilization = (
            budget.total_used / budget.total_budget if budget.total_budget > 0 else 1.0
        )
        budget.needs_compaction = (
            budget.messages_dropped > MIN_MESSAGES_FOR_SUMMARY
            and budget.utilization >= self.compaction_threshold
        )
        return budget

    def compute_dynamic_window(
        self,
        system_prompt: str = "",
        core_memory: str = "",
        summary: str = "",
        history_list: Optional[list[Dict[str, str]]] = None,
    ) -> tuple[int, int]:
        """Compute how many recent messages fit vs. need compaction."""
        budget = self.allocate(system_prompt, core_memory, summary, history_list)
        return budget.messages_included, budget.messages_dropped

    def build_context_messages(
        self,
        history_list: list[Dict[str, str]],
        system_prompt: str = "",
        core_memory: str = "",
        summary: str = "",
    ) -> tuple[list[BaseMessage], ContextBudget]:
        """Build LangChain messages that fit within the allocated context budget."""
        budget = self.allocate(
            system_prompt=system_prompt,
            core_memory=core_memory,
            summary=summary,
            history_list=history_list,
        )

        messages: list[BaseMessage] = []
        if system_prompt:
            from langchain_core.messages import SystemMessage

            messages.append(SystemMessage(content=system_prompt))

        if core_memory:
            from langchain_core.messages import SystemMessage

            messages.append(SystemMessage(content=core_memory))

        if summary:
            from langchain_core.messages import SystemMessage

            messages.append(SystemMessage(content=summary))

        included_history = history_list[-budget.messages_included :] if budget.messages_included else []
        for entry in included_history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role == "user":
                from langchain_core.messages import HumanMessage

                messages.append(HumanMessage(content=content))
            else:
                from langchain_core.messages import AIMessage

                messages.append(AIMessage(content=content))

        return messages, budget
