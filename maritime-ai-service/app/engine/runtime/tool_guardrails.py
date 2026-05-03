"""Tool-boundary guardrails — distinct from request-level Guardian.

Phase 26 of the runtime migration epic (issue #207). Wiii's existing
``Guardian Agent`` runs at the **request boundary** (entry point of a
chat turn) doing content safety + relevance filtering. That's the
right surface for "is this question allowed at all?" questions.

It is the **wrong surface** for "is this *tool call* allowed in the
current context?" questions. Examples:

- A Living-Agent skill calls ``filesystem.write_file``; the parent
  agent only consented to read access this turn.
- A subagent invokes ``http.fetch`` against an internal URL; the
  request-level Guardian saw the user's natural-language prompt, not
  the tool-call args.
- A model emits a tool call with malformed JSON arguments; we want a
  fast 4xx-style rejection, not a runtime crash inside the executor.

These need a different primitive: applied AT the tool boundary, with
the structured tool call in hand, before dispatch. Reference SDK
(openai-agents-python) calls these ``tool_guardrails`` to keep them
distinct from request-level guardrails.

Design points:
- **Sync, fast, side-effect-free**. Guardrails run synchronously in
  the dispatch hot path; they cannot do I/O. If a guardrail needs to
  fetch data, it precomputes during turn setup, not at call time.
- **Composable**. ``compose()`` runs a list in order, short-circuiting
  on the first deny. Order matters — cheap rejects (schema validation)
  run before expensive ones (semantic checks).
- **Decision is explicit**: ``ALLOW`` lets the call through, ``DENY``
  blocks with a reason, ``MODIFY`` rewrites the args. ``MODIFY`` is
  rare but useful (sanitising paths, redacting secrets).

Out of scope today:
- Per-org / per-role policy registries — guardrails today are static
  Python objects. Hot-loadable policy YAML lives in a follow-up phase.
- Async guardrails — the contract is sync. If a future guardrail
  needs to look up state, it gets a sync snapshot at turn start.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from app.engine.messages import ToolCall

logger = logging.getLogger(__name__)


class GuardrailDecision(StrEnum):
    """What a guardrail returns for a tool call."""

    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


@dataclass(slots=True)
class GuardrailResult:
    """Outcome of evaluating one guardrail (or a composed chain).

    ``MODIFY`` results carry the rewritten ``tool_call``; ``ALLOW`` and
    ``DENY`` carry the original (DENY's tool_call is informational
    only — the dispatcher must not run it).
    """

    decision: GuardrailDecision
    tool_call: ToolCall
    reason: Optional[str] = None
    """Human-readable explanation, especially required for DENY."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Free-form diagnostic fields — the guardrail name, rule id, etc."""


class ToolGuardrail(ABC):
    """Single guardrail rule applied at the tool boundary.

    Subclasses implement ``check``. Keep it cheap; guardrails sit on
    every tool call's hot path.
    """

    name: str = "ToolGuardrail"

    @abstractmethod
    def check(self, tool_call: ToolCall, *, context: dict) -> GuardrailResult:
        """Evaluate the call. Return the verdict.

        ``context`` carries turn-scoped fields the guardrail can read:
        org_id, user_id, role, granted capabilities. Treat it as read-
        only; mutating it leaks state across guardrails.
        """


# ── built-in guardrails ──


class RequiredArgsGuardrail(ToolGuardrail):
    """Reject calls missing one of the declared required-argument names.

    Cheap schema-shape check that catches the most common model
    misbehaviour: tool call emitted with wrong-shaped arguments.
    """

    name = "RequiredArgsGuardrail"

    def __init__(self, required_args_by_tool: dict[str, set[str]]):
        self._required = {
            tool: frozenset(args)
            for tool, args in required_args_by_tool.items()
        }

    def check(self, tool_call: ToolCall, *, context: dict) -> GuardrailResult:
        required = self._required.get(tool_call.name)
        if not required:
            # No declared requirement → not our business.
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        present = set(tool_call.arguments.keys())
        missing = required - present
        if not missing:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        return GuardrailResult(
            decision=GuardrailDecision.DENY,
            tool_call=tool_call,
            reason=f"missing required args: {sorted(missing)}",
            metadata={"guardrail": self.name, "tool": tool_call.name},
        )


class CapabilityGuardrail(ToolGuardrail):
    """Reject tool calls whose required capability is not in ``context``.

    Capabilities are turn-scoped strings (e.g. ``filesystem.read``,
    ``filesystem.write``, ``net.fetch.internal``). The dispatcher
    populates ``context["granted_capabilities"]`` at turn start; this
    guardrail just checks membership.
    """

    name = "CapabilityGuardrail"

    def __init__(self, required_capability_by_tool: dict[str, str]):
        self._required = dict(required_capability_by_tool)

    def check(self, tool_call: ToolCall, *, context: dict) -> GuardrailResult:
        required = self._required.get(tool_call.name)
        if required is None:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        granted = context.get("granted_capabilities") or set()
        if isinstance(granted, (list, tuple)):
            granted = set(granted)
        if required in granted:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        return GuardrailResult(
            decision=GuardrailDecision.DENY,
            tool_call=tool_call,
            reason=f"capability '{required}' not granted this turn",
            metadata={
                "guardrail": self.name,
                "tool": tool_call.name,
                "required_capability": required,
            },
        )


class StringRedactionGuardrail(ToolGuardrail):
    """Rewrite tool-call args to redact substrings matching the deny list.

    Conservative ``MODIFY`` example: the model emits a tool call with
    a literal API key in the arguments string; this guardrail strips
    it before dispatch. Match is plain-substring + case-insensitive.
    """

    name = "StringRedactionGuardrail"

    def __init__(self, patterns: list[str], replacement: str = "[REDACTED]"):
        self._patterns = [p for p in patterns if p]
        self._replacement = replacement

    def check(self, tool_call: ToolCall, *, context: dict) -> GuardrailResult:
        if not self._patterns:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        modified = False
        new_args: dict[str, Any] = {}
        for key, value in tool_call.arguments.items():
            if not isinstance(value, str):
                new_args[key] = value
                continue
            redacted = value
            for pattern in self._patterns:
                if pattern.lower() in redacted.lower():
                    redacted = self._case_insensitive_replace(
                        redacted, pattern, self._replacement
                    )
                    modified = True
            new_args[key] = redacted
        if not modified:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )
        new_tool_call = ToolCall(
            id=tool_call.id, name=tool_call.name, arguments=new_args
        )
        return GuardrailResult(
            decision=GuardrailDecision.MODIFY,
            tool_call=new_tool_call,
            reason="redacted matching substrings",
            metadata={"guardrail": self.name},
        )

    @staticmethod
    def _case_insensitive_replace(
        haystack: str, needle: str, replacement: str
    ) -> str:
        """Replace every case-insensitive occurrence of ``needle``."""
        # Avoid an import dance — use lowercase scanning.
        result_parts: list[str] = []
        cursor = 0
        haystack_lower = haystack.lower()
        needle_lower = needle.lower()
        n = len(needle_lower)
        if n == 0:
            return haystack
        while cursor < len(haystack):
            idx = haystack_lower.find(needle_lower, cursor)
            if idx == -1:
                result_parts.append(haystack[cursor:])
                break
            result_parts.append(haystack[cursor:idx])
            result_parts.append(replacement)
            cursor = idx + n
        return "".join(result_parts)


# ── composition ──


def compose(
    guardrails: list[ToolGuardrail],
    tool_call: ToolCall,
    *,
    context: Optional[dict] = None,
) -> GuardrailResult:
    """Run guardrails in order, short-circuit on first DENY.

    MODIFY results pipe forward — the next guardrail sees the rewritten
    tool_call. ALLOW results pass through unchanged. DENY ends the
    chain immediately.
    """
    ctx = dict(context or {})
    current = tool_call
    last_result: GuardrailResult = GuardrailResult(
        decision=GuardrailDecision.ALLOW, tool_call=current
    )
    for guardrail in guardrails:
        try:
            result = guardrail.check(current, context=ctx)
        except Exception as exc:  # noqa: BLE001
            # A faulty guardrail must fail closed — better to deny than
            # to leak a tool call past a broken safety check.
            logger.warning(
                "[tool_guardrails] %s raised during check: %s — failing closed",
                guardrail.name,
                exc,
            )
            return GuardrailResult(
                decision=GuardrailDecision.DENY,
                tool_call=current,
                reason=f"{guardrail.name} crashed; failing closed",
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
        last_result = result
        if result.decision == GuardrailDecision.DENY:
            return result
        if result.decision == GuardrailDecision.MODIFY:
            current = result.tool_call
    return last_result


__all__ = [
    "GuardrailDecision",
    "GuardrailResult",
    "ToolGuardrail",
    "RequiredArgsGuardrail",
    "CapabilityGuardrail",
    "StringRedactionGuardrail",
    "compose",
]
