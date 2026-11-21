import asyncio
from types import SimpleNamespace

import pytest


def test_select_direct_tool_followup_uses_auto_llm_for_non_visual_turn():
    from app.engine.multi_agent.direct_tool_followup_runtime import (
        select_direct_tool_followup,
    )
    from app.engine.multi_agent.visual_intent_resolver import VisualIntentDecision

    llm_auto = object()
    llm_base = object()
    llm_with_tools = object()
    tools = [SimpleNamespace(name="tool_web_search")]

    selection = select_direct_tool_followup(
        llm_auto=llm_auto,
        llm_base=llm_base,
        llm_with_tools=llm_with_tools,
        tools=tools,
        requires_visual_commit=False,
        visual_emitted_any=False,
        visual_decision=VisualIntentDecision(mode="text"),
        resolved_provider="zhipu",
        provider="auto",
    )

    assert selection.llm is llm_auto
    assert selection.tools is tools
    assert selection.tool_choice is None
    assert selection.fallback_source is llm_base

def test_select_direct_tool_followup_rebinds_visual_only_tools():
    from app.engine.multi_agent.direct_tool_followup_runtime import (
        select_direct_tool_followup,
    )
    from app.engine.multi_agent.visual_intent_resolver import VisualIntentDecision

    bound_llm = object()

    class FakeBaseLLM:
        def __init__(self):
            self.calls: list[dict] = []

        def bind_tools(self, tools, tool_choice=None):
            self.calls.append({"tools": list(tools), "tool_choice": tool_choice})
            return bound_llm

    llm_base = FakeBaseLLM()
    tools = [
        SimpleNamespace(name="tool_web_search"),
        SimpleNamespace(name="tool_generate_visual"),
        SimpleNamespace(name="tool_generate_mermaid"),
    ]

    selection = select_direct_tool_followup(
        llm_auto=object(),
        llm_base=llm_base,
        llm_with_tools=object(),
        tools=tools,
        requires_visual_commit=True,
        visual_emitted_any=False,
        visual_decision=VisualIntentDecision(
            mode="template",
            force_tool=True,
            presentation_intent="article_figure",
        ),
        resolved_provider="zhipu",
        provider="auto",
    )

    assert selection.llm is bound_llm
    assert [tool.name for tool in selection.tools] == ["tool_generate_visual"]
    assert selection.tool_choice == "tool_generate_visual"
    assert selection.fallback_source is llm_base
    assert len(llm_base.calls) == 1
    assert [tool.name for tool in llm_base.calls[0]["tools"]] == ["tool_generate_visual"]
    assert llm_base.calls[0]["tool_choice"] == "tool_generate_visual"

def test_select_direct_tool_followup_skips_non_bindable_base_llm():
    from app.engine.multi_agent.direct_tool_followup_runtime import (
        select_direct_tool_followup,
    )
    from app.engine.multi_agent.visual_intent_resolver import VisualIntentDecision

    bound_llm = object()

    class FakeAutoLLM:
        def __init__(self):
            self.calls: list[dict] = []

        def bind_tools(self, tools, tool_choice=None):
            self.calls.append({"tools": list(tools), "tool_choice": tool_choice})
            return bound_llm

    llm_auto = FakeAutoLLM()
    llm_base = object()
    tools = [
        SimpleNamespace(name="tool_web_search"),
        SimpleNamespace(name="tool_generate_visual"),
    ]

    selection = select_direct_tool_followup(
        llm_auto=llm_auto,
        llm_base=llm_base,
        llm_with_tools=object(),
        tools=tools,
        requires_visual_commit=True,
        visual_emitted_any=False,
        visual_decision=VisualIntentDecision(
            mode="template",
            force_tool=True,
            presentation_intent="article_figure",
        ),
        resolved_provider="zhipu",
        provider="auto",
    )

    assert selection.llm is bound_llm
    assert [tool.name for tool in selection.tools] == ["tool_generate_visual"]
    assert selection.tool_choice == "tool_generate_visual"
    assert selection.fallback_source is llm_auto
    assert len(llm_auto.calls) == 1
    assert [tool.name for tool in llm_auto.calls[0]["tools"]] == ["tool_generate_visual"]
    assert llm_auto.calls[0]["tool_choice"] == "tool_generate_visual"

def test_select_direct_tool_followup_keeps_auto_llm_after_visual_emits():
    from app.engine.multi_agent.direct_tool_followup_runtime import (
        select_direct_tool_followup,
    )
    from app.engine.multi_agent.visual_intent_resolver import VisualIntentDecision

    llm_auto = object()
    llm_base = object()
    tools = [SimpleNamespace(name="tool_generate_visual")]

    selection = select_direct_tool_followup(
        llm_auto=llm_auto,
        llm_base=llm_base,
        llm_with_tools=object(),
        tools=tools,
        requires_visual_commit=True,
        visual_emitted_any=True,
        visual_decision=VisualIntentDecision(
            mode="template",
            force_tool=True,
            presentation_intent="article_figure",
        ),
        resolved_provider="zhipu",
        provider="auto",
    )

    assert selection.llm is llm_auto
    assert selection.tools is tools
    assert selection.tool_choice is None
    assert selection.fallback_source is llm_base

@pytest.mark.asyncio
async def test_invoke_direct_tool_followup_cancels_heartbeat_and_updates_provider():
    from app.engine.multi_agent.direct_tool_followup_runtime import (
        invoke_direct_tool_followup,
    )
    from app.engine.multi_agent.visual_intent_resolver import VisualIntentDecision

    llm_auto = object()
    llm_base = object()
    response = SimpleNamespace(content="done")
    messages = [{"role": "user", "content": "xin chao"}]
    tools = [SimpleNamespace(name="tool_web_search")]
    state: dict = {"request_id": "req-1"}
    heartbeat_started = asyncio.Event()
    heartbeat_cancelled = False
    heartbeat_call: dict = {}
    invoke_call: dict = {}

    async def push_event(event):
        return event

    async def fake_heartbeats(push_event_arg, **kwargs):
        nonlocal heartbeat_cancelled
        heartbeat_call["push_event"] = push_event_arg
        heartbeat_call.update(kwargs)
        heartbeat_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            heartbeat_cancelled = True
            raise

    async def fake_ainvoke(llm, messages_arg, **kwargs):
        await heartbeat_started.wait()
        invoke_call["llm"] = llm
        invoke_call["messages"] = messages_arg
        invoke_call.update(kwargs)
        return response

    def remember_execution_target(candidate_llm, fallback_source=None):
        assert candidate_llm is llm_auto
        assert fallback_source is llm_base
        return "qwen", "qwen3-next"

    def runtime_tier_for(candidate_llm, fallback_source=None):
        assert candidate_llm is llm_auto
        assert fallback_source is llm_base
        return "balanced"

    result = await invoke_direct_tool_followup(
        llm_auto=llm_auto,
        llm_base=llm_base,
        llm_with_tools=object(),
        tools=tools,
        messages=messages,
        query="xin chao",
        push_event=push_event,
        requires_visual_commit=False,
        visual_emitted_any=False,
        visual_decision=VisualIntentDecision(mode="text"),
        resolved_provider="zhipu",
        provider="auto",
        request_failover_mode="auto",
        followup_timeout_profile="structured",
        state=state,
        allowed_fallback_providers=("zhipu",),
        ainvoke_with_fallback=fake_ainvoke,
        stream_direct_wait_heartbeats=fake_heartbeats,
        remember_execution_target=remember_execution_target,
        runtime_tier_for=runtime_tier_for,
        round_cue="tool-cue",
        round_tool_names=["tool_web_search"],
    )

    assert result.llm_response is response
    assert result.resolved_provider == "qwen"
    assert heartbeat_cancelled is True
    assert heartbeat_call["push_event"] is push_event
    assert heartbeat_call["query"] == "xin chao"
    assert heartbeat_call["phase"] == "ground"
    assert heartbeat_call["cue"] == "tool-cue"
    assert heartbeat_call["tool_names"] == ["tool_web_search"]
    assert invoke_call["llm"] is llm_auto
    assert invoke_call["messages"] is messages
    assert invoke_call["tools"] is tools
    assert invoke_call["tool_choice"] is None
    assert invoke_call["tier"] == "balanced"
    assert invoke_call["provider"] == "auto"
    assert invoke_call["resolved_provider"] == "qwen"
    assert invoke_call["failover_mode"] == "auto"
    assert invoke_call["push_event"] is push_event
    assert invoke_call["timeout_profile"] == "structured"
    assert invoke_call["state"] is state
    assert invoke_call["allowed_fallback_providers"] == ("zhipu",)
