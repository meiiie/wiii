import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_explicit_web_search_returns_template_after_fetch_evidence():
    from app.engine.multi_agent.direct_web_search_policy import (
        _prefer_official_query_for_known_docs,
        _should_return_search_template_after_tool_round,
        _should_use_search_template_for_empty_response,
    )

    events = [
        {
            "type": "result",
            "name": "tool_web_search",
            "result": "**OpenAI Responses API**\nURL: https://developers.openai.com/api/reference/responses",
            "id": "search_1",
        },
        {
            "type": "result",
            "name": "tool_fetch_url",
            "result": "The Responses API exposes POST /v1/responses.",
            "id": "fetch_1",
        },
    ]

    assert _should_return_search_template_after_tool_round(
        query="Tìm trên web giúp mình: OpenAI Responses API endpoint nào?",
        state={"routing_metadata": {"intent": "unknown"}},
        tool_call_events=events,
        tool_round=1,
    ) is True
    assert _should_return_search_template_after_tool_round(
        query="Phân tích nội bộ từ dữ liệu đã có",
        state={"routing_metadata": {"intent": "general"}},
        tool_call_events=events,
        tool_round=1,
    ) is False
    assert _should_return_search_template_after_tool_round(
        query="Tìm trên web giúp mình: OpenAI Responses API endpoint nào?",
        state={"routing_metadata": {"intent": "unknown"}},
        tool_call_events=events[:1],
        tool_round=0,
    ) is False
    rich_search_events = [
        {
            "type": "result",
            "name": "tool_web_search",
            "result": (
                "**OpenAI Responses API**\n"
                "URL: https://developers.openai.com/api/reference/responses/overview\n"
                "POST /v1/responses creates a model response. "
                "GET /v1/responses/{response_id} retrieves a response. "
            )
            * 35,
            "id": "search_1",
        },
    ]
    assert _should_return_search_template_after_tool_round(
        query="Tìm trên web giúp mình: OpenAI Responses API endpoint nào?",
        state={"routing_metadata": {"intent": "unknown"}},
        tool_call_events=rich_search_events,
        tool_round=0,
    ) is True
    assert _prefer_official_query_for_known_docs(
        {"query": "OpenAI Responses API endpoints 2025"},
        "Tìm trên web giúp mình: OpenAI Responses API hiện tại có endpoint nào?",
    ) == {
        "query": "OpenAI API Reference Responses POST /v1/responses platform.openai.com"
    }
    assert _should_use_search_template_for_empty_response(
        query="Tìm web từ nguồn chính thức OpenAI: Responses API endpoint là gì?",
        state={"routing_metadata": {"intent": "web_search"}},
        tool_call_events=events[:1],
    ) is True
    assert _should_use_search_template_for_empty_response(
        query="Không dùng web, chỉ nhắc lại trong phiên.",
        state={"routing_metadata": {"intent": "personal"}},
        tool_call_events=events[:1],
    ) is False

def test_auto_routed_web_search_does_not_use_explicit_search_template():
    from app.engine.multi_agent.direct_web_search_policy import (
        _should_return_search_template_after_tool_round,
        _should_use_search_template_for_empty_response,
    )

    events = [
        {
            "type": "result",
            "name": "tool_web_search",
            "result": ("URL: https://example.test/news\nCurrent event evidence.\n") * 80,
            "id": "search_1",
        },
    ]

    assert (
        _should_return_search_template_after_tool_round(
            query="hom nay co gi hot",
            state={"routing_metadata": {"intent": "web_search"}},
            tool_call_events=events,
            tool_round=1,
        )
        is False
    )
    assert (
        _should_use_search_template_for_empty_response(
            query="hom nay co gi hot",
            state={"routing_metadata": {"intent": "web_search"}},
            tool_call_events=events,
        )
        is False
    )

def test_weather_web_search_does_not_return_raw_search_template_after_tool_round():
    from app.engine.multi_agent.direct_web_search_policy import (
        _should_return_search_template_after_tool_round,
        _should_use_search_template_for_empty_response,
    )

    events = [
        {
            "type": "result",
            "name": "tool_web_search",
            "result": (
                "**AccuWeather Hai Phong**\n"
                "RealFeel 39C, humidity 64%, cloudy.\n"
                "URL: https://example.test/weather\n"
            )
            * 80,
            "id": "search_1",
        },
    ]

    assert (
        _should_return_search_template_after_tool_round(
            query="thời tiết Hải Phòng hôm nay cho mình nhé",
            state={"routing_metadata": {"intent": "web_search"}},
            tool_call_events=events,
            tool_round=0,
        )
        is False
    )
    assert (
        _should_use_search_template_for_empty_response(
            query="thời tiết Hải Phòng hôm nay cho mình nhé",
            state={"routing_metadata": {"intent": "web_search"}},
            tool_call_events=events,
        )
        is False
    )

def test_weather_web_search_query_contract_enriches_thin_location_args():
    from app.engine.multi_agent.direct_web_search_policy import (
        _enrich_current_weather_search_query,
    )

    assert (
        _enrich_current_weather_search_query(
            candidate_query="Hai Phong",
            user_query="thoi tiet Hai Phong hom nay the nao",
            today="2026-06-05",
            default_city="Ho Chi Minh City",
        )
        == "thoi tiet Hai Phong hom nay 2026-06-05"
    )

def test_weather_web_search_query_contract_uses_default_city_for_generic_turn():
    from app.engine.multi_agent.direct_web_search_policy import (
        _enrich_current_weather_search_query,
    )

    assert (
        _enrich_current_weather_search_query(
            candidate_query="",
            user_query="ua thoi tiet hom nay the nao",
            today="2026-06-05",
            default_city="Ho Chi Minh City",
        )
        == "thoi tiet Ho Chi Minh City hom nay 2026-06-05"
    )
    assert (
        _enrich_current_weather_search_query(
            candidate_query="",
            user_query="thoi tiet hom nay bao nhieu do",
            today="2026-06-05",
            default_city="Ho Chi Minh City",
        )
        == "thoi tiet Ho Chi Minh City hom nay 2026-06-05"
    )

def test_weather_web_search_query_contract_preserves_existing_date():
    from app.engine.multi_agent.direct_web_search_policy import (
        _enrich_current_weather_search_query,
    )

    assert (
        _enrich_current_weather_search_query(
            candidate_query="Ha Noi weather today 2026-06-01",
            user_query="weather now",
            today="2026-06-05",
            default_city="Ho Chi Minh City",
        )
        == "Ha Noi weather today 2026-06-01"
    )

def test_weather_web_search_query_contract_preserves_future_anchor():
    from app.engine.multi_agent.direct_web_search_policy import (
        _enrich_current_weather_search_query,
    )

    assert (
        _enrich_current_weather_search_query(
            candidate_query="Hai Phong",
            user_query="thoi tiet Hai Phong ngay mai the nao",
            today="2026-06-05",
            default_city="Ho Chi Minh City",
        )
        == "thoi tiet Hai Phong ngay mai"
    )

def test_prefer_official_query_rewrites_weather_search_args(monkeypatch):
    from app.engine.multi_agent import direct_web_search_policy as policy

    monkeypatch.setattr(policy, "_today_vietnam", lambda: "2026-06-05")

    assert policy._prefer_official_query_for_known_docs(
        {"q": "Hai Phong"},
        "thoi tiet Hai Phong hom nay the nao",
    ) == {"query": "thoi tiet Hai Phong hom nay 2026-06-05"}

def test_clean_forced_web_search_query_strips_vietnamese_discourse_marker():
    from app.engine.multi_agent.direct_web_search_policy import (
        _clean_forced_web_search_query,
    )

    cleaned = _clean_forced_web_search_query(
        "ý là thời tiết nóng đó. Bạn biết nay bao độ không"
    )

    assert cleaned == "thời tiết nóng đó. Bạn biết nay bao độ không"
    assert not cleaned.lower().startswith("ý là")

def test_clean_forced_web_search_query_strips_polite_search_suffix():
    from app.engine.multi_agent.direct_web_search_policy import (
        _clean_forced_web_search_query,
    )

    assert (
        _clean_forced_web_search_query("thời tiết Hải Phòng hôm nay cho mình")
        == "thời tiết Hải Phòng hôm nay"
    )
    assert (
        _clean_forced_web_search_query("@web-search giá vàng hôm nay giúp mình nhé")
        == "giá vàng hôm nay"
    )

def test_weather_lookup_limits_duplicate_web_search_fanout():
    from app.engine.multi_agent.direct_tool_round_execution_runtime import (
        _should_skip_weather_search_fanout,
    )

    state = {"_turn_path_decision": {"path": "web_search"}}
    query = "thời tiết Hải Phòng hôm nay"

    assert (
        _should_skip_weather_search_fanout(
            tool_call={"name": "tool_web_search"},
            query=query,
            state=state,
            executed_web_search_count=0,
        )
        is False
    )
    assert (
        _should_skip_weather_search_fanout(
            tool_call={"name": "tool_web_search"},
            query=query,
            state=state,
            executed_web_search_count=1,
        )
        is True
    )
    assert (
        _should_skip_weather_search_fanout(
            tool_call={"name": "tool_current_datetime"},
            query=query,
            state=state,
            executed_web_search_count=1,
        )
        is False
    )

@pytest.mark.asyncio
async def test_execute_direct_tool_round_emits_skipped_weather_fanout_events():
    from app.engine.multi_agent.direct_tool_round_execution_runtime import (
        _WEATHER_SEARCH_FANOUT_SKIP_RESULT,
        execute_direct_tool_round,
    )

    events: list[dict] = []
    tool_call_events: list[dict] = []
    messages: list[object] = []
    dispatch_calls: list[str] = []
    llm_response = SimpleNamespace(
        tool_calls=[
            {
                "id": "search_1",
                "name": "tool_web_search",
                "args": {"query": "thời tiết Hải Phòng hôm nay"},
            },
            {
                "id": "search_2",
                "name": "tool_web_search",
                "args": {"q": "Hai Phong"},
            },
        ]
    )

    async def push_event(event):
        events.append(event)

    async def dispatch_direct_tool_call(**kwargs):
        dispatch_calls.append(kwargs["tool_call"]["id"])
        return SimpleNamespace(
            tool_call_id=kwargs["tool_call"]["id"],
            tool_name="tool_web_search",
            tool_args=kwargs["tool_call"]["args"],
            result="URL: https://example.test/weather\nRealFeel 39C.",
            matched=True,
        )

    async def process_direct_tool_post_dispatch(**_kwargs):
        return SimpleNamespace(
            active_visual_session_ids=[],
            visual_emitted_any=False,
        )

    async def emit_visual_commit_events(**_kwargs):
        return None

    result = await execute_direct_tool_round(
        llm_response=llm_response,
        tool_round=0,
        tools=[],
        query="thời tiết Hải Phòng hôm nay",
        state={"_turn_path_decision": {"path": "web_search"}},
        messages=messages,
        tool_call_events=tool_call_events,
        push_event=push_event,
        native_tool_messages=False,
        visual_emitted_any=False,
        runtime_context_base=None,
        handoffs_enabled=False,
        get_tool_by_name=lambda *_args, **_kwargs: None,
        invoke_tool_with_runtime=lambda *_args, **_kwargs: None,
        is_search_tool_name=lambda name: name == "tool_web_search",
        prefer_official_query_for_known_docs=lambda _args, _query: {
            "query": "thoi tiet Hai Phong hom nay 2026-06-05"
        },
        summarize_tool_result_for_stream=lambda _name, value: f"summary:{value}",
        maybe_emit_host_action_event=lambda **_kwargs: None,
        maybe_emit_visual_event=lambda **_kwargs: None,
        emit_visual_commit_events=emit_visual_commit_events,
        build_direct_tool_reflection=lambda *_args, **_kwargs: "",
        push_status_only_progress=lambda *_args, **_kwargs: None,
        build_tool_result_message=lambda content, **_kwargs: SimpleNamespace(
            content=content
        ),
        normalize_tool_call=lambda tool_call: tool_call,
        infer_direct_reasoning_cue=lambda *_args, **_kwargs: "cue",
        collect_active_visual_session_ids=lambda _state: [],
        dispatch_direct_tool_call=dispatch_direct_tool_call,
        process_direct_tool_post_dispatch=process_direct_tool_post_dispatch,
        logger_obj=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        ),
    )

    assert result.round_tool_names == ["tool_web_search", "tool_web_search"]
    assert dispatch_calls == ["search_1"]
    assert [event["type"] for event in events] == ["tool_call", "tool_result"]
    assert events[0]["content"]["id"] == "search_2"
    assert events[0]["content"]["args"] == {
        "query": "thoi tiet Hai Phong hom nay 2026-06-05"
    }
    assert events[1]["content"]["id"] == "search_2"
    assert events[1]["content"]["metadata"]["status"] == "skipped"
    assert (
        events[1]["content"]["metadata"]["reason_code"]
        == "weather_search_fanout_limited"
    )
    assert tool_call_events[0]["type"] == "call"
    assert tool_call_events[0]["args"] == {
        "query": "thoi tiet Hai Phong hom nay 2026-06-05"
    }
    assert tool_call_events[0]["metadata"]["status"] == "skipped"
    assert tool_call_events[1]["type"] == "result"
    assert tool_call_events[1]["args"] == {
        "query": "thoi tiet Hai Phong hom nay 2026-06-05"
    }
    assert tool_call_events[1]["result"] == _WEATHER_SEARCH_FANOUT_SKIP_RESULT
    assert messages[-1].content == _WEATHER_SEARCH_FANOUT_SKIP_RESULT

@pytest.mark.asyncio
async def test_execute_direct_tool_round_keeps_weather_fanout_after_no_source_search():
    from app.engine.multi_agent.direct_tool_round_execution_runtime import (
        execute_direct_tool_round,
    )

    events: list[dict] = []
    tool_call_events: list[dict] = []
    messages: list[object] = []
    dispatch_calls: list[str] = []
    llm_response = SimpleNamespace(
        tool_calls=[
            {
                "id": "search_1",
                "name": "tool_web_search",
                "args": {"query": "thời tiết Hải Phòng hôm nay"},
            },
            {
                "id": "search_2",
                "name": "tool_web_search",
                "args": {"query": "weather Hai Phong today"},
            },
        ]
    )

    async def push_event(event):
        events.append(event)

    async def dispatch_direct_tool_call(**kwargs):
        dispatch_calls.append(kwargs["tool_call"]["id"])
        return SimpleNamespace(
            tool_call_id=kwargs["tool_call"]["id"],
            tool_name="tool_web_search",
            tool_args=kwargs["tool_call"]["args"],
            result="No web results found for this query.",
            matched=True,
        )

    async def process_direct_tool_post_dispatch(**_kwargs):
        return SimpleNamespace(
            active_visual_session_ids=[],
            visual_emitted_any=False,
        )

    async def emit_visual_commit_events(**_kwargs):
        return None

    await execute_direct_tool_round(
        llm_response=llm_response,
        tool_round=0,
        tools=[],
        query="thời tiết Hải Phòng hôm nay",
        state={"_turn_path_decision": {"path": "web_search"}},
        messages=messages,
        tool_call_events=tool_call_events,
        push_event=push_event,
        native_tool_messages=False,
        visual_emitted_any=False,
        runtime_context_base=None,
        handoffs_enabled=False,
        get_tool_by_name=lambda *_args, **_kwargs: None,
        invoke_tool_with_runtime=lambda *_args, **_kwargs: None,
        is_search_tool_name=lambda name: name == "tool_web_search",
        prefer_official_query_for_known_docs=lambda args, _query: args,
        summarize_tool_result_for_stream=lambda _name, value: f"summary:{value}",
        maybe_emit_host_action_event=lambda **_kwargs: None,
        maybe_emit_visual_event=lambda **_kwargs: None,
        emit_visual_commit_events=emit_visual_commit_events,
        build_direct_tool_reflection=lambda *_args, **_kwargs: "",
        push_status_only_progress=lambda *_args, **_kwargs: None,
        build_tool_result_message=lambda content, **_kwargs: SimpleNamespace(
            content=content
        ),
        normalize_tool_call=lambda tool_call: tool_call,
        infer_direct_reasoning_cue=lambda *_args, **_kwargs: "cue",
        collect_active_visual_session_ids=lambda _state: [],
        dispatch_direct_tool_call=dispatch_direct_tool_call,
        process_direct_tool_post_dispatch=process_direct_tool_post_dispatch,
        logger_obj=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        ),
    )

    assert dispatch_calls == ["search_1", "search_2"]
    assert events == []

def test_build_direct_post_tool_search_template_response_for_forced_web(monkeypatch):
    from app.engine.multi_agent import direct_search_template_runtime as runtime

    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "Tổng hợp từ web có nguồn.",
    )

    monkeypatch.setattr(
        runtime,
        "_force_skills_for_turn",
        lambda _state: {"web-search"},
    )

    response = runtime.build_direct_post_tool_search_template_response(
        query="giá dầu hôm nay",
        state={"routing_metadata": {"intent": "web_search"}},
        tool_call_events=[
            {
                "type": "result",
                "name": "tool_web_search",
                "result": "URL: https://example.test/oil\nGiá dầu tăng.",
            }
        ],
        tool_round=0,
        native_tool_messages=False,
    )

    assert response is not None
    assert response.content == "Tổng hợp từ web có nguồn."

def test_build_direct_post_tool_search_template_response_skips_weather_even_when_forced(
    monkeypatch,
):
    from app.engine.multi_agent import direct_search_template_runtime as runtime

    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "Không nên trả template cho weather tự nhiên.",
    )

    response = runtime.build_direct_post_tool_search_template_response(
        query="thời tiết Hải Phòng hôm nay cho mình nhé",
        state={"force_skills": ["web-search"]},
        tool_call_events=[
            {
                "type": "result",
                "name": "tool_web_search",
                "result": "URL: https://example.test/weather\nRealFeel 39C.",
            }
        ],
        tool_round=0,
        native_tool_messages=False,
    )

    assert response is None

def test_build_direct_post_tool_search_template_response_for_explicit_round(
    monkeypatch,
):
    from app.engine.multi_agent import direct_search_template_runtime as runtime

    monkeypatch.setattr(runtime, "_force_skills_for_turn", lambda _state: set())
    monkeypatch.setattr(
        runtime,
        "_should_return_search_template_after_tool_round",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "Tổng hợp sau vòng công cụ.",
    )

    response = runtime.build_direct_post_tool_search_template_response(
        query="tìm web về responses api",
        state={"routing_metadata": {"intent": "unknown"}},
        tool_call_events=[{"type": "result", "name": "tool_fetch_url", "result": "ok"}],
        tool_round=1,
        native_tool_messages=False,
    )

    assert response is not None
    assert response.content == "Tổng hợp sau vòng công cụ."

def test_build_direct_post_tool_search_template_response_skips_empty_template(
    monkeypatch,
):
    from app.engine.multi_agent import direct_search_template_runtime as runtime

    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "",
    )

    response = runtime.build_direct_post_tool_search_template_response(
        query="giá dầu hôm nay",
        state={"force_skills": ["web-search"]},
        tool_call_events=[
            {"type": "result", "name": "tool_web_search", "result": "source"}
        ],
        tool_round=0,
        native_tool_messages=False,
    )

    assert response is None

def test_build_direct_post_tool_search_template_response_returns_no_source_template():
    from app.engine.multi_agent import direct_search_template_runtime as runtime

    response = runtime.build_direct_post_tool_search_template_response(
        query="@web-search một chủ đề rất hẹp",
        state={"force_skills": ["web-search"]},
        tool_call_events=[
            {
                "type": "result",
                "name": "tool_web_search",
                "result": "",
                "metadata": {
                    "schema_version": "tool_result_metadata.v1",
                    "status": "unavailable",
                    "result_kind": "web_sources",
                    "reason_code": "no_sources",
                    "source_count": 0,
                    "domains": [],
                },
            }
        ],
        tool_round=0,
        native_tool_messages=False,
    )

    assert response is not None
    assert "chưa tìm được kết quả phù hợp" in response.content

@pytest.mark.asyncio
async def test_execute_forced_web_search_shortcut_emits_events(monkeypatch):
    from app.engine.multi_agent import direct_forced_web_search_runtime as runtime

    tool = object()
    emitted: list[dict] = []
    tool_events: list[dict] = []
    invoke_call: dict = {}

    monkeypatch.setattr(
        runtime,
        "build_search_template_fallback",
        lambda **_kwargs: "Tổng hợp nhanh có nguồn.",
    )

    async def push_event(event):
        emitted.append(event)

    def get_tool_by_name(tools, name):
        assert tools == [tool]
        return tool if name == "tool_web_search" else None

    async def invoke_tool_with_runtime(tool_arg, args, **kwargs):
        invoke_call["tool"] = tool_arg
        invoke_call["args"] = args
        invoke_call.update(kwargs)
        return (
            "URL: https://example.test\n"
            "Tin mới.\n"
            "access_token=raw-forced-token-123456 page_id=page-secret-123456"
        )

    response = await runtime.execute_forced_web_search_shortcut(
        query="@web-search giá dầu hôm nay",
        state={"force_skills": ["web-search"]},
        tools=[tool],
        messages=[],
        tool_call_events=tool_events,
        push_event=push_event,
        native_tool_messages=False,
        runtime_context_base={"tenant": "demo"},
        get_tool_by_name=get_tool_by_name,
        invoke_tool_with_runtime=invoke_tool_with_runtime,
        summarize_tool_result_for_stream=lambda _name, result: f"summary:{result}",
    )

    assert response is not None
    assert response.content == "Tổng hợp nhanh có nguồn."
    assert [event["type"] for event in emitted] == [
        "tool_call",
        "tool_result",
        "sources",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
    ]
    assert emitted[2]["content"][0]["url"] == "https://example.test"
    assert emitted[2]["details"] == {
        "tool_call_id": "forced_web_search_0",
        "tool_name": "tool_web_search",
    }
    thinking_text = " ".join(
        str(event.get("content", ""))
        for event in emitted
        if event.get("type") == "thinking_delta"
    )
    assert "@web-search" not in thinking_text
    assert "tool_web_search" not in thinking_text
    assert "synthesizer" not in thinking_text.lower()
    assert tool_events[0]["type"] == "call"
    assert tool_events[0]["name"] == "tool_web_search"
    assert tool_events[1]["type"] == "result"
    assert "URL: https://example.test" in tool_events[1]["result"]
    assert "raw-forced-token" not in tool_events[1]["result"]
    assert "page-secret-123456" not in tool_events[1]["result"]
    assert invoke_call["tool"] is tool
    assert invoke_call["args"]["query"] == "giá dầu hôm nay"
    assert invoke_call["tool_name"] == "tool_web_search"
    assert invoke_call["runtime_context_base"] == {"tenant": "demo"}
    assert invoke_call["tool_call_id"] == "forced_web_search_0"
    assert invoke_call["prefer_async"] is False
    assert invoke_call["run_sync_in_thread"] is True

@pytest.mark.asyncio
async def test_execute_forced_web_search_shortcut_skips_natural_weather_auto_route():
    from app.engine.multi_agent import direct_forced_web_search_runtime as runtime

    emitted: list[dict] = []

    async def push_event(event):
        emitted.append(event)

    async def invoke_tool_with_runtime(*_args, **_kwargs):
        raise AssertionError("Natural weather routing should use the planner loop")

    response = await runtime.execute_forced_web_search_shortcut(
        query="thời tiết Hải Phòng hôm nay cho mình nhé",
        state={"routing_metadata": {"intent": "web_search"}},
        tools=[object()],
        messages=[],
        tool_call_events=[],
        push_event=push_event,
        native_tool_messages=False,
        runtime_context_base={},
        get_tool_by_name=lambda _tools, _name: object(),
        invoke_tool_with_runtime=invoke_tool_with_runtime,
        summarize_tool_result_for_stream=lambda _name, result: result,
    )

    assert response is None
    assert emitted == []

@pytest.mark.asyncio
async def test_execute_forced_web_search_shortcut_skips_when_not_forced():
    from app.engine.multi_agent.direct_forced_web_search_runtime import (
        execute_forced_web_search_shortcut,
    )

    response = await execute_forced_web_search_shortcut(
        query="giá dầu hôm nay",
        state={},
        tools=[object()],
        messages=[],
        tool_call_events=[],
        push_event=lambda _event: None,
        native_tool_messages=False,
        runtime_context_base=None,
        get_tool_by_name=lambda _tools, _name: object(),
        invoke_tool_with_runtime=lambda *_args, **_kwargs: None,
        summarize_tool_result_for_stream=lambda _name, result: result,
    )

    assert response is None

@pytest.mark.asyncio
async def test_forced_web_search_runs_tool_without_planner_or_synthesis_llm():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    class FakeTool:
        name = "tool_web_search"

        def invoke(self, args):
            return (
                "**Introducing GPT-5.5 - OpenAI**\n"
                "Apr 23, 2026 · OpenAI is releasing GPT-5.5.\n"
                "URL: https://openai.com/index/introducing-gpt-5-5/"
            )

        async def ainvoke(self, args):
            return (
                "**Introducing GPT-5.5 - OpenAI**\n"
                "Apr 23, 2026 · OpenAI is releasing GPT-5.5.\n"
                "URL: https://openai.com/index/introducing-gpt-5-5/"
            )

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(_llm, _messages, **_kwargs):
        fake_ainvoke_with_fallback.calls += 1
        raise AssertionError("forced @web-search should not depend on planner LLM")

    fake_ainvoke_with_fallback.calls = 0

    async def fake_stream_direct_answer_with_fallback(*args, **kwargs):
        raise AssertionError("tool-bound turn should not use no-tool streaming path")

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        llm_response, _messages, tool_call_events = await execute_direct_tool_rounds_impl(
            llm_with_tools=object(),
            llm_auto=object(),
            messages=[],
            tools=[FakeTool()],
            push_event=push_event,
            query="OpenAI latest model announcement 2026",
            state={"context": {"force_skills": ["web-search"]}},
            forced_tool_choice="tool_web_search",
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert fake_ainvoke_with_fallback.calls == 0
    assert "Introducing GPT-5.5" in llm_response.content
    assert "https://openai.com/index/introducing-gpt-5-5/" in llm_response.content
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    assert tool_call_events[0]["args"]["query"] == "OpenAI latest model announcement 2026"
