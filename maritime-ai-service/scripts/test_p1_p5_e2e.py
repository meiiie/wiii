"""E2E test for P1-P5: WiiiRunner with hooks, state overlays, tier config, stream events, guardrails.

Runs the full pipeline with mock LLM to verify all 5 improvements work together.

Usage:
    python scripts/test_p1_p5_e2e.py
"""

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {C_GREEN}PASS{C_RESET} {msg}")


def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  {C_RED}FAIL{C_RESET} {msg}")
    if detail:
        print(f"    {C_RED}>> {detail}{C_RESET}")


def header(msg):
    print(f"\n{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  {msg}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}")


def section(msg):
    print(f"\n{C_YELLOW}> {msg}{C_RESET}")


# ---------------------------------------------------------------------------
# Mock LLM that returns structured output
# ---------------------------------------------------------------------------

def make_mock_llm(response_text: str = "Đây là câu trả lời mẫu."):
    """Create a mock LLM that works with both sync and async invoke."""
    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_text

    async def _ainvoke(*args, **kwargs):
        return mock_response

    mock.ainvoke = _ainvoke
    mock.bind_tools = MagicMock(return_value=mock)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_p1_hooks_fire():
    """P1: Lifecycle hooks fire correctly during pipeline execution."""
    header("P1: Lifecycle Hooks")

    from app.engine.multi_agent.runner import WiiiRunner
    from app.engine.multi_agent.hooks import HookDispatcher, RunHooks

    runner = WiiiRunner()

    # Mock nodes
    async def mock_guardian(state):
        state["guardian_passed"] = True
        return state

    async def mock_supervisor(state):
        state["next_agent"] = "rag_agent"
        state["routing_metadata"] = {"intent": "lookup", "confidence": 0.9}
        return state

    async def mock_rag(state):
        state["rag_output"] = "COLREG là Công ước quốc tế..."
        return state

    async def mock_synthesizer(state):
        state["final_response"] = state.get("rag_output", "OK")
        return state

    runner.register_node("guardian", mock_guardian)
    runner.register_node("supervisor", mock_supervisor)
    runner.register_node("rag_agent", mock_rag)
    runner.register_node("synthesizer", mock_synthesizer)

    # Attach hooks
    dispatcher = HookDispatcher()
    events_log = []

    class TestHooks(RunHooks):
        async def on_run_start(self, state):
            events_log.append(("run_start", state.get("query", "")))

        async def on_run_end(self, state, duration_ms):
            events_log.append(("run_end", duration_ms))

        async def on_step_start(self, step_name, state):
            events_log.append(("step_start", step_name))

        async def on_step_end(self, step_name, state, duration_ms):
            events_log.append(("step_end", step_name))

        async def on_route(self, from_step, to_step, state):
            events_log.append(("route", f"{from_step}->{to_step}"))

    dispatcher.add_run_hooks(TestHooks())
    runner.set_hooks(dispatcher)

    section("Running pipeline with hooks")
    with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
         patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
        result = await runner.run({"query": "COLREG là gì?"})

    # Verify
    section("Checking hook events")
    step_starts = [e for e in events_log if e[0] == "step_start"]
    step_ends = [e for e in events_log if e[0] == "step_end"]
    routes = [e for e in events_log if e[0] == "route"]

    if len(step_starts) == 4:
        ok(f"4 step_start events: {[e[1] for e in step_starts]}")
    else:
        fail(f"Expected 4 step_start, got {len(step_starts)}")

    if len(step_ends) == 4:
        ok(f"4 step_end events")
    else:
        fail(f"Expected 4 step_end, got {len(step_ends)}")

    if routes:
        ok(f"Route events: {[e[1] for e in routes]}")
    else:
        fail("No route events fired")

    run_end_events = [e for e in events_log if e[0] == "run_end"]
    if run_end_events and run_end_events[0][1] > 0:
        ok(f"Pipeline duration: {run_end_events[0][1]:.1f}ms")
    else:
        fail("No run_end event or duration is 0")


async def test_p2_state_overlays():
    """P2: Typed state overlays extract correct groups."""
    header("P2: Typed State Overlays")

    from app.engine.multi_agent.state import (
        get_input_context, get_routing_state, get_agent_output,
        get_runtime_meta, get_thinking_state,
    )

    state = {
        "query": "SOLAS là gì?",
        "user_id": "u1",
        "session_id": "s1",
        "current_agent": "rag_agent",
        "next_agent": "rag_agent",
        "routing_metadata": {"intent": "lookup"},
        "rag_output": "SOLAS là...",
        "final_response": "SOLAS là Công ước...",
        "_trace_id": "t1",
        "_execution_tier": "moderate",
        "thinking_effort": "high",
    }

    section("Testing accessor functions")

    ic = get_input_context(state)
    if ic.get("query") == "SOLAS là gì?" and "current_agent" not in ic:
        ok("InputContext: query extracted, no routing fields")
    else:
        fail("InputContext incorrect", str(ic))

    rs = get_routing_state(state)
    if rs.get("current_agent") == "rag_agent" and "query" not in rs:
        ok("RoutingState: current_agent extracted, no input fields")
    else:
        fail("RoutingState incorrect")

    ao = get_agent_output(state)
    if ao.get("final_response") and "_trace_id" not in ao:
        ok("AgentOutput: final_response extracted, no meta fields")
    else:
        fail("AgentOutput incorrect")

    rm = get_runtime_meta(state)
    if rm.get("_execution_tier") == "moderate" and "query" not in rm:
        ok("RuntimeMeta: _execution_tier extracted")
    else:
        fail("RuntimeMeta incorrect")

    ts = get_thinking_state(state)
    if ts.get("thinking_effort") == "high" and "query" not in ts:
        ok("ThinkingState: thinking_effort extracted")
    else:
        fail("ThinkingState incorrect")


async def test_p3_tier_injection():
    """P3: Per-agent tier injection works in runner."""
    header("P3: Per-Agent Tier Configuration")

    from app.engine.multi_agent.runner import WiiiRunner

    runner = WiiiRunner()

    async def mock_agent(state):
        return state

    runner.register_node("rag_agent", mock_agent)
    runner.register_node("supervisor", mock_agent)

    section("Testing tier injection per agent")

    state = {"query": "test"}
    state = await runner._run_step("rag_agent", state)
    if state.get("_execution_tier") == "moderate":
        ok("rag_agent tier: moderate")
    else:
        fail(f"rag_agent tier: {state.get('_execution_tier')}")

    state2 = {"query": "test"}
    state2 = await runner._run_step("supervisor", state2)
    if state2.get("_execution_tier") == "light":
        ok("supervisor tier: light")
    else:
        fail(f"supervisor tier: {state2.get('_execution_tier')}")

    # Guardian should NOT have tier
    runner.register_node("guardian", mock_agent)
    state3 = {"query": "test"}
    state3 = await runner._run_step("guardian", state3)
    if "_execution_tier" not in state3:
        ok("guardian: no tier (infrastructure node)")
    else:
        fail("guardian should not have tier")


async def test_p4_stream_events():
    """P4: Typed stream events roundtrip correctly."""
    header("P4: Discriminated Union Stream Events")

    from app.engine.multi_agent.stream_events import (
        GraphNodeEvent, BusEvent, GraphDoneEvent,
        make_graph_event, make_bus_event, from_tuple,
    )

    section("Testing factory + parser roundtrip")

    t = make_graph_event("rag_agent", {"query": "test", "final_response": "ok"})
    event = from_tuple(t)
    if isinstance(event, GraphNodeEvent) and event.node_name == "rag_agent":
        ok(f"GraphNodeEvent: node={event.node_name}")
    else:
        fail("GraphNodeEvent roundtrip failed")

    t2 = make_bus_event({"type": "thinking_delta", "content": "Đang suy nghĩ..."})
    event2 = from_tuple(t2)
    if isinstance(event2, BusEvent) and event2.event["type"] == "thinking_delta":
        ok(f"BusEvent: type={event2.event['type']}")
    else:
        fail("BusEvent roundtrip failed")

    from app.engine.multi_agent.stream_events import make_graph_done
    t3 = make_graph_done()
    event3 = from_tuple(t3)
    if isinstance(event3, GraphDoneEvent):
        ok("GraphDoneEvent parsed correctly")
    else:
        fail("GraphDoneEvent parse failed")

    # Test actual queue flow
    section("Testing queue flow with typed events")
    import asyncio
    queue = asyncio.Queue()
    await queue.put(make_graph_event("guardian", {"guardian_passed": True}))
    await queue.put(make_graph_event("supervisor", {"next_agent": "rag_agent"}))
    await queue.put(make_graph_event("rag_agent", {"rag_output": "answer"}))
    await queue.put(make_graph_done())

    events = []
    while not queue.empty():
        item = await queue.get()
        events.append(from_tuple(item))

    types = [type(e).__name__ for e in events]
    if types == ["GraphNodeEvent", "GraphNodeEvent", "GraphNodeEvent", "GraphDoneEvent"]:
        ok(f"Queue flow: {types}")
    else:
        fail(f"Queue flow incorrect: {types}")


async def test_p5_guardrails():
    """P5: Guardrail decorator and execution."""
    header("P5: Guardrail Decorator Extensibility")

    from app.engine.multi_agent.guardrails import (
        GuardrailRegistry, GuardrailContext, GuardrailResult,
        guardrail, run_input_guardrails, run_output_guardrails,
    )

    GuardrailRegistry.reset()

    section("Registering custom guardrails")

    @guardrail(phase="input", name="block_urls", description="Block URL-only queries", run_parallel=False, priority=1)
    async def block_urls(ctx: GuardrailContext) -> GuardrailResult:
        if ctx.query.startswith("http"):
            return GuardrailResult(passed=False, reason="URL-only query blocked.")
        return GuardrailResult(passed=True)

    @guardrail(phase="input", name="block_short", description="Block very short queries", run_parallel=True, priority=2)
    async def block_short(ctx: GuardrailContext) -> GuardrailResult:
        if len(ctx.query.strip()) < 3:
            return GuardrailResult(passed=False, reason="Query too short.")
        return GuardrailResult(passed=True)

    @guardrail(phase="output", name="min_length", description="Ensure minimum response length")
    async def min_length(ctx: GuardrailContext) -> GuardrailResult:
        if len(ctx.response.strip()) < 10:
            return GuardrailResult(passed=False, reason="Response too short.")
        return GuardrailResult(passed=True)

    names = GuardrailRegistry.list_names()
    if "block_urls" in names["input"] and "min_length" in names["output"]:
        ok(f"Registered: {names}")
    else:
        fail(f"Registration failed: {names}")

    # Test input guardrail — URL blocked
    section("Testing input guardrails")
    passed_url, reason_url = await run_input_guardrails({"query": "https://example.com"})
    if not passed_url and "URL" in reason_url:
        ok(f"URL query blocked: {reason_url}")
    else:
        fail(f"URL should be blocked: passed={passed_url}, reason={reason_url}")

    # Normal query passes
    passed_normal, _ = await run_input_guardrails({"query": "COLREG là gì?"})
    if passed_normal:
        ok("Normal query passes input guardrails")
    else:
        fail("Normal query should pass")

    # Test output guardrail — short response blocked
    section("Testing output guardrails")
    passed_short, reason_short = await run_output_guardrails({
        "query": "test", "final_response": "OK"
    })
    if not passed_short:
        ok(f"Short response blocked: {reason_short}")
    else:
        fail("Short response should be blocked")

    # Good response passes
    passed_good, _ = await run_output_guardrails({
        "query": "test", "final_response": "Đây là câu trả lời đầy đủ và chi tiết."
    })
    if passed_good:
        ok("Full response passes output guardrails")
    else:
        fail("Full response should pass")

    GuardrailRegistry.reset()


async def test_full_pipeline_integration():
    """Full pipeline: all P1-P5 working together."""
    header("Integration: Full Pipeline with P1-P5")

    from app.engine.multi_agent.runner import WiiiRunner
    from app.engine.multi_agent.hooks import HookDispatcher, RunHooks
    from app.engine.multi_agent.guardrails import (
        GuardrailRegistry, GuardrailContext, GuardrailResult, guardrail,
    )

    GuardrailRegistry.reset()

    # Register a test guardrail
    @guardrail(phase="input", name="e2e_block_urls", run_parallel=False, priority=1)
    async def e2e_block_urls(ctx: GuardrailContext) -> GuardrailResult:
        if "http://" in ctx.query:
            return GuardrailResult(passed=False, reason="URL không hợp lệ")
        return GuardrailResult(passed=True)

    runner = WiiiRunner()

    async def mock_guardian(state):
        state["guardian_passed"] = True
        return state

    async def mock_supervisor(state):
        state["next_agent"] = "rag_agent"
        state["routing_metadata"] = {"intent": "lookup"}
        return state

    async def mock_rag(state):
        state["rag_output"] = "RAG result"
        return state

    async def mock_synthesizer(state):
        state["final_response"] = state.get("rag_output", "OK")
        return state

    runner.register_node("guardian", mock_guardian)
    runner.register_node("supervisor", mock_supervisor)
    runner.register_node("rag_agent", mock_rag)
    runner.register_node("synthesizer", mock_synthesizer)

    # Attach hooks
    dispatcher = HookDispatcher()
    hook_events = []

    class IntegrationHooks(RunHooks):
        async def on_step_end(self, step_name, state, duration_ms):
            tier = state.get("_execution_tier", "N/A")
            hook_events.append({"step": step_name, "tier": tier, "ms": duration_ms})

    dispatcher.add_run_hooks(IntegrationHooks())
    runner.set_hooks(dispatcher)

    section("Running full pipeline (normal query)")

    with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
         patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
        result = await runner.run({"query": "SOLAS là gì?", "user_id": "u1"})

    if result.get("final_response") == "RAG result":
        ok(f"Final response: {result['final_response'][:50]}")
    else:
        fail(f"Wrong response: {result.get('final_response')}")

    # Check tier was injected for rag_agent
    rag_events = [e for e in hook_events if e["step"] == "rag_agent"]
    if rag_events and rag_events[0]["tier"] == "moderate":
        ok(f"rag_agent tier tracked in hooks: {rag_events[0]['tier']}")
    else:
        fail(f"rag_agent tier not tracked: {rag_events}")

    # Check hooks covered all steps
    steps_covered = {e["step"] for e in hook_events}
    if steps_covered >= {"guardian", "supervisor", "rag_agent", "synthesizer"}:
        ok(f"All steps covered: {steps_covered}")
    else:
        fail(f"Missing steps: {steps_covered}")

    section("Running pipeline with URL query (guardrail blocks)")

    with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
         patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
        result2 = await runner.run({"query": "http://bad-url.com"})

    if not result2.get("guardian_passed", True):
        ok(f"URL query blocked by guardrail: guardian_passed={result2.get('guardian_passed')}")
    else:
        fail("URL query should be blocked")

    GuardrailRegistry.reset()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print(f"\n{C_BOLD}Wiii P1-P5 E2E Test Suite{C_RESET}")
    print(f"Testing lifecycle hooks, state overlays, tier config, stream events, guardrails\n")

    t_start = time.time()

    await test_p1_hooks_fire()
    await test_p2_state_overlays()
    await test_p3_tier_injection()
    await test_p4_stream_events()
    await test_p5_guardrails()
    await test_full_pipeline_integration()

    elapsed = time.time() - t_start

    print(f"\n{C_BOLD}{'=' * 60}{C_RESET}")
    print(f"{C_BOLD}Results: {C_GREEN}{passed} passed{C_RESET}, {C_RED}{failed} failed{C_RESET} ({elapsed:.1f}s)")
    print(f"{C_BOLD}{'=' * 60}{C_RESET}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
