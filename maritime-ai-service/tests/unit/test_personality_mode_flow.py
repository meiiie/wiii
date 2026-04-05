from types import SimpleNamespace

import pytest

from app.services.chat_orchestrator_multi_agent import build_multi_agent_context_impl


@pytest.mark.asyncio
async def test_build_multi_agent_context_keeps_personality_mode():
    context = SimpleNamespace(
        user_id="u1",
        user_name="Nam",
        user_role=SimpleNamespace(value="student"),
        lms_course_name=None,
        lms_module_id=None,
        conversation_history="",
        semantic_context="",
        langchain_messages=[],
        conversation_summary="",
        core_memory_block="",
        history_list=[],
        response_language="vi",
        personality_mode="professional",
        mood_hint="Nguoi dung dang hoc Rule 15",
        organization_id=None,
        images=None,
        page_context=None,
        student_state=None,
        available_actions=None,
        host_context=None,
        host_capabilities=None,
        host_action_feedback=None,
        visual_context=None,
        widget_feedback=None,
        code_studio_context=None,
    )
    session = SimpleNamespace(
        state=SimpleNamespace(
            total_responses=0,
            name_usage_count=0,
            recent_phrases=[],
            response_language="vi",
        )
    )

    async def _resolve_lms_identity(_user_id, _organization_id):
        return None, None

    graph_context = await build_multi_agent_context_impl(
        context,
        session,
        resolve_lms_identity_fn=_resolve_lms_identity,
    )

    assert graph_context["personality_mode"] == "professional"
