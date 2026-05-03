"""Phase 26 tool guardrails — Runtime Migration #207.

Locks the contract:
- Three decisions (ALLOW / DENY / MODIFY) with the right tool_call shape.
- Built-ins: RequiredArgs, Capability, StringRedaction.
- compose() short-circuits on DENY, pipes MODIFY forward, fail-closes
  on guardrail exceptions.
"""

from __future__ import annotations

import pytest

from app.engine.messages import ToolCall
from app.engine.runtime.tool_guardrails import (
    CapabilityGuardrail,
    GuardrailDecision,
    GuardrailResult,
    RequiredArgsGuardrail,
    StringRedactionGuardrail,
    ToolGuardrail,
    compose,
)


def _tc(name="search", args=None, tc_id="c1"):
    return ToolCall(id=tc_id, name=name, arguments=args or {})


# ── RequiredArgsGuardrail ──

def test_required_args_allows_when_all_present():
    g = RequiredArgsGuardrail({"search": {"q"}})
    result = g.check(_tc(args={"q": "x"}), context={})
    assert result.decision == GuardrailDecision.ALLOW


def test_required_args_denies_when_missing():
    g = RequiredArgsGuardrail({"search": {"q", "limit"}})
    result = g.check(_tc(args={"q": "x"}), context={})
    assert result.decision == GuardrailDecision.DENY
    assert "limit" in result.reason


def test_required_args_no_rule_for_tool_passes_through():
    g = RequiredArgsGuardrail({"other_tool": {"x"}})
    result = g.check(_tc(name="search", args={}), context={})
    assert result.decision == GuardrailDecision.ALLOW


def test_required_args_denies_with_metadata():
    g = RequiredArgsGuardrail({"search": {"q"}})
    result = g.check(_tc(args={}), context={})
    assert result.metadata["guardrail"] == "RequiredArgsGuardrail"
    assert result.metadata["tool"] == "search"


# ── CapabilityGuardrail ──

def test_capability_allows_when_granted():
    g = CapabilityGuardrail({"fs.write": "filesystem.write"})
    result = g.check(
        _tc(name="fs.write"),
        context={"granted_capabilities": {"filesystem.write"}},
    )
    assert result.decision == GuardrailDecision.ALLOW


def test_capability_denies_when_not_granted():
    g = CapabilityGuardrail({"fs.write": "filesystem.write"})
    result = g.check(
        _tc(name="fs.write"),
        context={"granted_capabilities": {"filesystem.read"}},
    )
    assert result.decision == GuardrailDecision.DENY
    assert "filesystem.write" in result.reason


def test_capability_denies_when_context_has_no_grants():
    g = CapabilityGuardrail({"fs.write": "filesystem.write"})
    result = g.check(_tc(name="fs.write"), context={})
    assert result.decision == GuardrailDecision.DENY


def test_capability_accepts_list_or_set_of_grants():
    g = CapabilityGuardrail({"fs.write": "filesystem.write"})
    list_ctx = {"granted_capabilities": ["filesystem.write"]}
    set_ctx = {"granted_capabilities": {"filesystem.write"}}
    assert (
        g.check(_tc(name="fs.write"), context=list_ctx).decision
        == GuardrailDecision.ALLOW
    )
    assert (
        g.check(_tc(name="fs.write"), context=set_ctx).decision
        == GuardrailDecision.ALLOW
    )


def test_capability_passes_through_when_no_rule():
    g = CapabilityGuardrail({"other": "other.cap"})
    result = g.check(_tc(name="search"), context={})
    assert result.decision == GuardrailDecision.ALLOW


# ── StringRedactionGuardrail ──

def test_redaction_modifies_args_with_match():
    g = StringRedactionGuardrail(["sk-secret"])
    result = g.check(
        _tc(args={"q": "my key is sk-secret-123"}),
        context={},
    )
    assert result.decision == GuardrailDecision.MODIFY
    assert "sk-secret-123" not in result.tool_call.arguments["q"]
    assert "[REDACTED]" in result.tool_call.arguments["q"]


def test_redaction_is_case_insensitive():
    g = StringRedactionGuardrail(["secret"])
    result = g.check(_tc(args={"q": "MY SECRET"}), context={})
    assert result.decision == GuardrailDecision.MODIFY
    assert "MY [REDACTED]" in result.tool_call.arguments["q"]


def test_redaction_no_match_passes_through():
    g = StringRedactionGuardrail(["sk-secret"])
    result = g.check(_tc(args={"q": "innocent query"}), context={})
    assert result.decision == GuardrailDecision.ALLOW


def test_redaction_skips_non_string_args():
    g = StringRedactionGuardrail(["secret"])
    result = g.check(_tc(args={"limit": 10, "q": "secret here"}), context={})
    assert result.decision == GuardrailDecision.MODIFY
    assert result.tool_call.arguments["limit"] == 10
    assert "[REDACTED]" in result.tool_call.arguments["q"]


def test_redaction_handles_multiple_occurrences():
    g = StringRedactionGuardrail(["pwd"])
    result = g.check(_tc(args={"q": "pwd1 and pwd2"}), context={})
    assert result.decision == GuardrailDecision.MODIFY
    redacted = result.tool_call.arguments["q"]
    assert "pwd1" not in redacted
    assert "pwd2" not in redacted
    assert redacted.count("[REDACTED]") == 2


def test_redaction_empty_pattern_list_allows():
    g = StringRedactionGuardrail([])
    result = g.check(_tc(args={"q": "anything"}), context={})
    assert result.decision == GuardrailDecision.ALLOW


# ── compose ──

def test_compose_empty_chain_returns_allow():
    result = compose([], _tc())
    assert result.decision == GuardrailDecision.ALLOW


def test_compose_first_deny_short_circuits():
    """Subsequent guardrails should NOT run after a DENY."""
    sentinel = []

    class Tracker(ToolGuardrail):
        name = "Tracker"

        def check(self, tool_call, *, context):
            sentinel.append("ran")
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )

    deny = RequiredArgsGuardrail({"search": {"q"}})
    chain = [deny, Tracker()]
    result = compose(chain, _tc(name="search", args={}))
    assert result.decision == GuardrailDecision.DENY
    assert sentinel == []  # Tracker never ran


def test_compose_modify_pipes_forward():
    """Guardrail B sees the rewritten tool_call from guardrail A."""
    received = []

    class Inspect(ToolGuardrail):
        name = "Inspect"

        def check(self, tool_call, *, context):
            received.append(tool_call.arguments.get("q"))
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )

    redact = StringRedactionGuardrail(["secret"])
    chain = [redact, Inspect()]
    result = compose(chain, _tc(args={"q": "my secret"}))
    # Inspect saw the redacted version.
    assert received == ["my [REDACTED]"]
    # Final result is the latest (Inspect's ALLOW with the modified call).
    assert "[REDACTED]" in result.tool_call.arguments["q"]


def test_compose_guardrail_exception_fails_closed():
    """Faulty guardrail should DENY the call, not let it through."""

    class Boom(ToolGuardrail):
        name = "Boom"

        def check(self, tool_call, *, context):
            raise RuntimeError("guardrail buggy")

    result = compose([Boom()], _tc())
    assert result.decision == GuardrailDecision.DENY
    assert "crashed" in result.reason
    assert "RuntimeError" in result.metadata["error"]


def test_compose_propagates_context_unchanged():
    """compose() doesn't mutate the caller's context dict."""
    seen = []

    class CaptureCtx(ToolGuardrail):
        name = "CaptureCtx"

        def check(self, tool_call, *, context):
            seen.append(dict(context))
            context["mutated"] = True  # try to leak
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW, tool_call=tool_call
            )

    caller_ctx = {"org_id": "A"}
    compose([CaptureCtx(), CaptureCtx()], _tc(), context=caller_ctx)
    # Caller's dict is untouched.
    assert "mutated" not in caller_ctx
    # Each guardrail saw its own snapshot, but mutations within a
    # single compose() call ARE visible to subsequent guardrails — that's
    # by design for chained refinements.
    assert seen[0] == {"org_id": "A"}
