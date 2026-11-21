import asyncio
from types import SimpleNamespace

import pytest


def test_build_direct_final_synthesis_instruction_is_mode_aware_for_market_turn():
    from app.engine.multi_agent.direct_final_synthesis_runtime import (
        build_direct_final_synthesis_instruction as _build_direct_final_synthesis_instruction,
    )

    instruction = _build_direct_final_synthesis_instruction(
        "phan tich gia dau",
        {},
        ["tool_web_search"],
    ).lower()

    assert "khong goi them cong cu" in instruction
    assert "mot cau thesis ve mat bang thi truong hien tai" in instruction
    assert "khong dung heading markdown nhu #, ##, ###" in instruction
    assert "khong dung bullet/bold kieu ban tin tong hop" in instruction
    assert "opec+" in instruction or "ton kho" in instruction

def test_build_direct_final_synthesis_instruction_blocks_live_lookup_memory_bleed():
    from app.engine.multi_agent.direct_final_synthesis_runtime import (
        build_direct_live_lookup_system_guard,
        build_direct_final_synthesis_instruction as _build_direct_final_synthesis_instruction,
    )

    instruction = _build_direct_final_synthesis_instruction(
        "thoi tiet Hai Phong hom nay",
        {},
        ["tool_web_search", "tool_current_datetime", "tool_fetch_url"],
    ).lower()

    assert "chi tra loi tu bang chung cong cu" in instruction
    assert "khong chen ky uc" in instruction
    assert "cam xuc" in instruction
    assert "hang hai" in instruction
    assert "ui da co the nguon" in instruction
    for tool_name in [
        "tool_web_search",
        "TOOL_SEARCH_LEGAL",
        "search_maritime",
        "tool_search_news",
    ]:
        guard = build_direct_live_lookup_system_guard([tool_name])
        assert "Do not use stored memory" in guard
        assert "interested in ports" in guard
    assert build_direct_live_lookup_system_guard(["tool_generate_visual"]) == ""

def test_direct_public_thinking_dedupe_detects_identical_blocks():
    from app.engine.multi_agent.direct_public_thinking_runtime import (
        remember_direct_public_thinking_chunks,
        should_emit_direct_public_thinking_chunks,
    )

    state = {}
    opening_chunks = [
        "Cau nay can mot nhip dap cham va that hon la mot loi giai thich voi.",
        "Minh muon mo loi vua du diu de neu ban muon ke tiep thi van con cho cho nhip do di ra.",
    ]
    remember_direct_public_thinking_chunks(state, opening_chunks)

    assert should_emit_direct_public_thinking_chunks(state, list(opening_chunks)) is False

def test_direct_public_thinking_dedupe_allows_changed_blocks():
    from app.engine.multi_agent.direct_public_thinking_runtime import (
        remember_direct_public_thinking_chunks,
        should_emit_direct_public_thinking_chunks,
    )

    state = {}
    remember_direct_public_thinking_chunks(
        state,
        [
            "Cau nay can mot nhip dap cham va that hon la mot loi giai thich voi.",
            "Minh muon mo loi vua du diu de neu ban muon ke tiep thi van con cho cho nhip do di ra.",
        ],
    )

    assert should_emit_direct_public_thinking_chunks(
        state,
        [
            "Gio minh da co them du kien nen co the noi cu the hon.",
            "Minh se giu nhip diu nhung neo cau tra loi vao dieu vua kiem chung.",
        ],
    ) is True

def test_build_direct_final_synthesis_instruction_is_mode_aware_for_math_turn():
    from app.engine.multi_agent.direct_final_synthesis_runtime import (
        build_direct_final_synthesis_instruction as _build_direct_final_synthesis_instruction,
    )

    instruction = _build_direct_final_synthesis_instruction(
        "Phan tich ve toan hoc con lac don",
        {},
        [],
    ).lower()

    assert "khong goi them cong cu" in instruction
    assert "mot cau thesis ve mo hinh dang dung" in instruction
    assert "mo hinh/gia dinh -> phuong trinh hoac suy dan -> y nghia vat ly" in instruction
    assert "khong dung heading markdown nhu #, ##, ###" in instruction

@pytest.mark.asyncio
async def test_run_direct_final_synthesis_uses_no_tool_binding_and_moderate_timeout():
    from app.engine.multi_agent.direct_final_synthesis_runtime import (
        run_direct_final_synthesis,
    )

    llm_base = object()
    llm_auto = object()
    llm_with_tools = object()
    final_response = SimpleNamespace(
        content="Day la cau tra loi tong hop cuoi cung.",
        tool_calls=[],
    )
    calls: list[dict] = []
    heartbeat_kwargs: list[dict] = []

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(llm, messages, **kwargs):
        await asyncio.sleep(0)
        calls.append(
            {
                "llm": llm,
                "messages": list(messages),
                "kwargs": dict(kwargs),
            }
        )
        return final_response

    async def fake_stream_direct_wait_heartbeats(*_args, **kwargs):
        heartbeat_kwargs.append(dict(kwargs))
        await asyncio.Future()

    def remember_execution_target(candidate_llm, fallback_source=None):
        assert candidate_llm is llm_base
        assert fallback_source is llm_base
        return "qwen", "qwen3-next"

    def runtime_tier_for(candidate_llm, fallback_source=None):
        assert candidate_llm is llm_base
        assert fallback_source is llm_base
        return "base-tier"

    result = await run_direct_final_synthesis(
        messages=[],
        query="phan tich gia dau",
        state={},
        tool_call_events=[
            {"type": "call", "name": "tool_web_search", "id": "tc-1"},
            {"type": "result", "name": "tool_web_search", "id": "tc-1"},
        ],
        push_event=push_event,
        native_tool_messages=False,
        llm_base=llm_base,
        llm_auto=llm_auto,
        llm_with_tools=llm_with_tools,
        provider="auto",
        resolved_provider=None,
        request_failover_mode="auto",
        allowed_fallback_providers=("qwen",),
        ainvoke_with_fallback=fake_ainvoke_with_fallback,
        stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
        remember_execution_target=remember_execution_target,
        runtime_tier_for=runtime_tier_for,
    )

    assert result.llm_response is final_response
    assert result.resolved_provider == "qwen"
    assert len(result.messages) == 2
    assert result.messages[0].role == "system"
    assert "Do not use stored memory" in result.messages[0].content
    assert "Khong goi them cong cu" in result.messages[-1].content
    assert calls[0]["llm"] is llm_base
    assert "tools" not in calls[0]["kwargs"]
    assert calls[0]["kwargs"]["timeout_profile"] == "moderate"
    assert calls[0]["kwargs"]["tier"] == "base-tier"
    assert calls[0]["kwargs"]["allowed_fallback_providers"] == ("qwen",)
    assert heartbeat_kwargs[0]["phase"] == "synthesize"
    assert heartbeat_kwargs[0]["cue"] == "synthesis"
    assert heartbeat_kwargs[0]["tool_names"] == ["tool_web_search"]

@pytest.mark.asyncio
async def test_run_direct_final_synthesis_requires_unbound_base_llm():
    from app.engine.multi_agent.direct_final_synthesis_runtime import (
        run_direct_final_synthesis,
    )

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(*_args, **_kwargs):
        raise AssertionError("synthesis should fail before invoking a tool-bound model")

    async def fake_stream_direct_wait_heartbeats(*_args, **_kwargs):
        raise AssertionError("heartbeat should not start without an unbound model")

    with pytest.raises(RuntimeError, match="requires an unbound LLM"):
        await run_direct_final_synthesis(
            messages=[],
            query="phan tich gia dau",
            state={},
            tool_call_events=[{"type": "call", "name": "tool_web_search"}],
            push_event=push_event,
            native_tool_messages=False,
            llm_base=None,
            llm_auto=object(),
            llm_with_tools=object(),
            provider="auto",
            resolved_provider=None,
            request_failover_mode="auto",
            allowed_fallback_providers=None,
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            remember_execution_target=lambda *_args, **_kwargs: (None, None),
            runtime_tier_for=lambda *_args, **_kwargs: "moderate",
        )

def test_append_direct_tool_convergence_hint_inserts_sparse_self_eval():
    from app.engine.multi_agent.direct_tool_convergence_runtime import (
        append_direct_tool_convergence_hint,
    )

    messages = []
    result = append_direct_tool_convergence_hint(
        messages=messages,
        tool_round=0,
        tool_call_events=[
            {"type": "call", "name": "tool_web_search", "id": "tc-1"},
            {"type": "result", "name": "tool_web_search", "result": "short"},
        ],
        requires_visual_commit=False,
        native_tool_messages=False,
    )

    assert result.inserted is True
    assert result.kind == "sparse_self_eval"
    assert result.total_result_chars == len("short")
    assert len(messages) == 1
    assert "tool_search_news" in messages[0].content
    assert "110.01" in messages[0].content

def test_append_direct_tool_convergence_hint_inserts_rich_stop_hint():
    from app.engine.multi_agent.direct_tool_convergence_runtime import (
        append_direct_tool_convergence_hint,
    )

    messages = []
    result = append_direct_tool_convergence_hint(
        messages=messages,
        tool_round=0,
        tool_call_events=[
            {"type": "call", "name": "tool_fetch_url", "id": "tc-1"},
            {"type": "result", "name": "tool_fetch_url", "result": "x" * 2500},
        ],
        requires_visual_commit=False,
        native_tool_messages=False,
    )

    assert result.inserted is True
    assert result.kind == "rich_stop_hint"
    assert result.total_result_chars == 2500
    assert len(messages) == 1
    assert "110.01" in messages[0].content

@pytest.mark.parametrize(
    ("tool_round", "events", "requires_visual_commit"),
    [
        (1, [{"type": "call", "name": "tool_web_search"}], False),
        (0, [{"type": "call", "name": "tool_demo"}], False),
        (0, [{"type": "call", "name": "tool_web_search"}], True),
    ],
)
def test_append_direct_tool_convergence_hint_skips_non_convergence_cases(
    tool_round,
    events,
    requires_visual_commit,
):
    from app.engine.multi_agent.direct_tool_convergence_runtime import (
        append_direct_tool_convergence_hint,
    )

    messages = []
    result = append_direct_tool_convergence_hint(
        messages=messages,
        tool_round=tool_round,
        tool_call_events=events,
        requires_visual_commit=requires_visual_commit,
        native_tool_messages=False,
    )

    assert result.inserted is False
    assert messages == []

@pytest.mark.asyncio
async def test_finalize_direct_tool_response_uses_empty_search_template(monkeypatch):
    from app.engine.multi_agent import direct_tool_response_finalization_runtime as runtime

    messages = [{"role": "user", "content": "gia dau"}]
    tool_events = [{"type": "result", "name": "tool_web_search", "content": "evidence"}]
    inject_call: dict = {}

    monkeypatch.setattr(
        runtime,
        "_should_use_search_template_for_empty_response",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "Bản tổng hợp có nguồn.",
    )

    async def fail_synthesis(**_kwargs):
        raise AssertionError("final synthesis should not run after template fallback")

    def inject_widget_blocks(response, events, **kwargs):
        inject_call["response"] = response
        inject_call["events"] = events
        inject_call.update(kwargs)
        return response

    monkeypatch.setattr(runtime, "run_direct_final_synthesis", fail_synthesis)

    result = await runtime.finalize_direct_tool_response(
        llm_response=SimpleNamespace(content=""),
        messages=messages,
        tools=[SimpleNamespace(name="tool_web_search")],
        tool_call_events=tool_events,
        query="giá dầu hôm nay",
        state={"force_search": True},
        push_event=lambda _event: None,
        native_tool_messages=False,
        llm_base=object(),
        llm_auto=object(),
        llm_with_tools=object(),
        provider="auto",
        resolved_provider="zhipu",
        request_failover_mode="auto",
        allowed_fallback_providers=("zhipu",),
        ainvoke_with_fallback=lambda *_args, **_kwargs: None,
        stream_direct_wait_heartbeats=lambda *_args, **_kwargs: None,
        remember_execution_target=lambda *_args, **_kwargs: (None, None),
        runtime_tier_for=lambda *_args, **_kwargs: "moderate",
        inject_widget_blocks_from_tool_results=inject_widget_blocks,
        structured_visuals_enabled=True,
    )

    assert result.llm_response.content == "Bản tổng hợp có nguồn."
    assert result.messages is messages
    assert result.resolved_provider == "zhipu"
    assert inject_call["response"] is result.llm_response
    assert inject_call["events"] is tool_events
    assert inject_call["query"] == "giá dầu hôm nay"
    assert inject_call["structured_visuals_enabled"] is True

@pytest.mark.asyncio
async def test_finalize_direct_tool_response_forces_no_tool_synthesis(monkeypatch):
    from app.engine.multi_agent import direct_tool_response_finalization_runtime as runtime

    response = SimpleNamespace(content="final")
    messages = [{"role": "user", "content": "hoc hang hai"}]
    synthesized_messages = [*messages, {"role": "assistant", "content": "final"}]
    tool_events = [{"type": "call", "name": "tool_knowledge_search"}]
    synthesis_call: dict = {}

    monkeypatch.setattr(
        runtime,
        "_should_use_search_template_for_empty_response",
        lambda **_kwargs: False,
    )

    async def fake_synthesis(**kwargs):
        synthesis_call.update(kwargs)
        return SimpleNamespace(
            llm_response=response,
            messages=synthesized_messages,
            resolved_provider="qwen",
        )

    def inject_widget_blocks(response_arg, events, **kwargs):
        assert response_arg is response
        assert events is tool_events
        assert kwargs["structured_visuals_enabled"] is False
        return response_arg

    monkeypatch.setattr(runtime, "run_direct_final_synthesis", fake_synthesis)

    result = await runtime.finalize_direct_tool_response(
        llm_response=SimpleNamespace(content="", tool_calls=[{"name": "tool_demo"}]),
        messages=messages,
        tools=[SimpleNamespace(name="tool_demo")],
        tool_call_events=tool_events,
        query="mình muốn học hàng hải",
        state={"request_id": "req-2"},
        push_event=lambda _event: None,
        native_tool_messages=False,
        llm_base="base",
        llm_auto="auto",
        llm_with_tools="with_tools",
        provider="auto",
        resolved_provider="zhipu",
        request_failover_mode="auto",
        allowed_fallback_providers=("zhipu",),
        ainvoke_with_fallback=lambda *_args, **_kwargs: None,
        stream_direct_wait_heartbeats=lambda *_args, **_kwargs: None,
        remember_execution_target=lambda *_args, **_kwargs: (None, None),
        runtime_tier_for=lambda *_args, **_kwargs: "moderate",
        inject_widget_blocks_from_tool_results=inject_widget_blocks,
        structured_visuals_enabled=False,
    )

    assert result.llm_response is response
    assert result.messages is synthesized_messages
    assert result.resolved_provider == "qwen"
    assert synthesis_call["messages"] is messages
    assert synthesis_call["query"] == "mình muốn học hàng hải"
    assert synthesis_call["tool_call_events"] is tool_events
    assert synthesis_call["resolved_provider"] == "zhipu"
