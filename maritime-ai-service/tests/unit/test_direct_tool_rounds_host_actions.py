import pytest

from app.engine.multi_agent.direct_document_host_action_runtime import (
    DocumentHostActionShortcut,
    execute_document_host_action_shortcut,
    execute_requested_document_host_action_shortcut,
)


@pytest.mark.asyncio
async def test_document_host_action_shortcut_emits_preview_event_contract() -> None:
    pushed_events: list[dict] = []
    tool_call_events: list[dict] = []
    invoke_kwargs: dict = {}
    state: dict = {}

    shortcut = DocumentHostActionShortcut(
        tool_name="tool_preview_lesson_patch",
        tool_call_id="forced_doc_preview_0",
        thinking="Preview only; wait for approval_token before apply.",
        thinking_summary="Preview document lesson",
        thinking_provenance="test_document_preview",
        response="Preview sent.",
        failure_log_message="failed: %s",
    )

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    async def invoke_tool(tool, args, **kwargs):
        invoke_kwargs.update(kwargs)
        return {"host_action": "preview", "approval_required": True}

    async def emit_host_action(**kwargs) -> None:
        pushed_events.append(
            {
                "type": "host_action",
                "content": kwargs["result"],
                "node": kwargs["node"],
            }
        )

    response = await execute_document_host_action_shortcut(
        shortcut=shortcut,
        tool=object(),
        args={"title": "Bản nháp"},
        state=state,
        tool_call_events=tool_call_events,
        push_event=push_event,
        invoke_tool_with_runtime=invoke_tool,
        maybe_emit_host_action_event=emit_host_action,
        summarize_tool_result_for_stream=lambda name, result: "summary",
        runtime_context_base={"request_id": "req-1"},
        query_snippet="Bản nháp",
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert response == "Preview sent."
    assert state["thinking_content"] == shortcut.thinking
    assert invoke_kwargs["tool_name"] == shortcut.tool_name
    assert invoke_kwargs["tool_call_id"] == shortcut.tool_call_id
    assert invoke_kwargs["prefer_async"] is False
    assert invoke_kwargs["run_sync_in_thread"] is True
    assert [event["type"] for event in pushed_events] == [
        "tool_call",
        "tool_result",
        "host_action",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
    ]
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    assert tool_call_events[0]["name"] == shortcut.tool_name
    assert tool_call_events[1]["result"] == str(
        {"host_action": "preview", "approval_required": True}
    )

@pytest.mark.asyncio
async def test_document_host_action_shortcut_redacts_public_tool_args() -> None:
    pushed_events: list[dict] = []
    tool_call_events: list[dict] = []
    invoked_args: dict = {}
    state: dict = {}

    shortcut = DocumentHostActionShortcut(
        tool_name="tool_preview_lesson_patch",
        tool_call_id="forced_doc_preview_sensitive",
        thinking="Preview only.",
        thinking_summary="Preview document lesson",
        thinking_provenance="test_document_preview",
        response="Preview sent.",
        failure_log_message="failed: %s",
    )

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    async def invoke_tool(tool, args, **kwargs):
        invoked_args.update(args)
        return {"host_action": "preview"}

    async def emit_host_action(**kwargs) -> None:
        return None

    await execute_document_host_action_shortcut(
        shortcut=shortcut,
        tool=object(),
        args={
            "title": "Draft",
            "content": "private uploaded document excerpt",
            "source_references": [{"excerpt": "raw source text"}],
            "course_plan": {"chapters": [{"title": "raw chapter"}]},
        },
        state=state,
        tool_call_events=tool_call_events,
        push_event=push_event,
        invoke_tool_with_runtime=invoke_tool,
        maybe_emit_host_action_event=emit_host_action,
        summarize_tool_result_for_stream=lambda name, result: "summary",
        runtime_context_base=None,
        query_snippet="Draft",
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert invoked_args["content"] == "private uploaded document excerpt"
    public_args = pushed_events[0]["content"]["args"]
    assert public_args["title"] == "Draft"
    assert public_args["content"] == "[redacted]"
    assert public_args["source_references"] == "[redacted]"
    assert public_args["course_plan"] == "[redacted]"
    assert tool_call_events[0]["args"] == public_args

@pytest.mark.asyncio
async def test_requested_document_host_action_shortcut_prefers_course_preview() -> None:
    course_tool = object()
    lesson_tool = object()
    pushed_events: list[dict] = []
    tool_call_events: list[dict] = []
    invoked: dict = {}
    lesson_checked = False
    state: dict = {"document_context": {"attachments": [{"id": "doc-1"}]}}

    course_shortcut = DocumentHostActionShortcut(
        tool_name="tool_preview_course_plan",
        tool_call_id="forced_doc_course_preview_0",
        thinking="Course preview only.",
        thinking_summary="Course preview",
        thinking_provenance="test_course_preview",
        response="Course preview sent.",
        failure_log_message="failed: %s",
    )
    lesson_shortcut = DocumentHostActionShortcut(
        tool_name="tool_preview_lesson_patch",
        tool_call_id="forced_doc_preview_0",
        thinking="Lesson preview only.",
        thinking_summary="Lesson preview",
        thinking_provenance="test_lesson_preview",
        response="Lesson preview sent.",
        failure_log_message="failed: %s",
    )

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    async def invoke_tool(tool, args, **kwargs):
        invoked.update({"tool": tool, "args": args, "kwargs": kwargs})
        return {"host_action": "preview-course", "approval_required": True}

    async def emit_host_action(**kwargs) -> None:
        pushed_events.append({"type": "host_action", "content": kwargs["result"]})

    def build_assistant_message(content: str, **kwargs) -> dict:
        return {"content": content, "native_tool_messages": kwargs["native_tool_messages"]}

    def should_request_lesson_preview(**kwargs) -> bool:
        nonlocal lesson_checked
        lesson_checked = True
        return True

    response = await execute_requested_document_host_action_shortcut(
        query="tạo cho mình bài học",
        state=state,
        tools=[course_tool, lesson_tool],
        tool_call_events=tool_call_events,
        push_event=push_event,
        native_tool_messages=True,
        runtime_context_base={"request_id": "req-1"},
        invoke_tool_with_runtime=invoke_tool,
        maybe_emit_host_action_event=emit_host_action,
        summarize_tool_result_for_stream=lambda name, result: "summary",
        should_request_course_preview=lambda **kwargs: True,
        find_course_host_action_tool=lambda tools: course_tool,
        build_course_params=lambda query, state: {
            "title": "Course",
            "source_references": [{"document_id": "doc-1"}],
        },
        course_shortcut=course_shortcut,
        should_request_lesson_preview=should_request_lesson_preview,
        find_lesson_host_action_tool=lambda tools: lesson_tool,
        build_lesson_params=lambda query, state: {"title": "Lesson"},
        lesson_shortcut=lesson_shortcut,
        build_assistant_message=build_assistant_message,
        uploaded_document_attachments_from_state=lambda state: [{"id": "doc-1"}],
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert response == {
        "content": "Course preview sent.",
        "native_tool_messages": True,
    }
    assert lesson_checked is False
    assert invoked["tool"] is course_tool
    assert invoked["kwargs"]["tool_name"] == "tool_preview_course_plan"
    assert invoked["args"]["source_references"] == [{"document_id": "doc-1"}]
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    assert [event["type"] for event in pushed_events] == [
        "tool_call",
        "tool_result",
        "host_action",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
    ]

@pytest.mark.asyncio
async def test_requested_document_host_action_shortcut_uses_lesson_preview() -> None:
    lesson_tool = object()
    invoked: dict = {}
    state: dict = {"document_context": {"attachments": [{"id": "doc-1"}]}}
    shortcut = DocumentHostActionShortcut(
        tool_name="tool_preview_lesson_patch",
        tool_call_id="forced_doc_preview_0",
        thinking="Lesson preview only.",
        thinking_summary="Lesson preview",
        thinking_provenance="test_lesson_preview",
        response="Lesson preview sent.",
        failure_log_message="failed: %s",
    )

    async def push_event(event: dict) -> None:
        return None

    async def invoke_tool(tool, args, **kwargs):
        invoked.update({"tool": tool, "args": args, "kwargs": kwargs})
        return {"host_action": "preview-lesson", "approval_required": True}

    async def emit_host_action(**kwargs) -> None:
        return None

    response = await execute_requested_document_host_action_shortcut(
        query="tạo cho mình bài học",
        state=state,
        tools=[lesson_tool],
        tool_call_events=[],
        push_event=push_event,
        native_tool_messages=False,
        runtime_context_base={"request_id": "req-2"},
        invoke_tool_with_runtime=invoke_tool,
        maybe_emit_host_action_event=emit_host_action,
        summarize_tool_result_for_stream=lambda name, result: "summary",
        should_request_course_preview=lambda **kwargs: False,
        find_course_host_action_tool=lambda tools: None,
        build_course_params=lambda query, state: {"title": "Course"},
        course_shortcut=shortcut,
        should_request_lesson_preview=lambda **kwargs: True,
        find_lesson_host_action_tool=lambda tools: lesson_tool,
        build_lesson_params=lambda query, state: {
            "title": "Lesson",
            "source_references": [{"document_id": "doc-1"}],
        },
        lesson_shortcut=shortcut,
        build_assistant_message=lambda content, **kwargs: {
            "content": content,
            "native_tool_messages": kwargs["native_tool_messages"],
        },
        uploaded_document_attachments_from_state=lambda state: [{"id": "doc-1"}],
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert response == {
        "content": "Lesson preview sent.",
        "native_tool_messages": False,
    }
    assert invoked["tool"] is lesson_tool
    assert invoked["kwargs"]["tool_name"] == "tool_preview_lesson_patch"
    assert invoked["args"]["source_references"] == [{"document_id": "doc-1"}]
