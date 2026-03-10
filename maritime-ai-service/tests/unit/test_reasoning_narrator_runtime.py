"""Regression tests for the Card + Skill + Narrator runtime."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_reasoning_skill_loader_loads_persona_subagent_and_tool_skills():
    from app.engine.reasoning.skill_loader import ReasoningSkillLoader

    loader = ReasoningSkillLoader()

    persona_ids = {skill.id for skill in loader.get_persona_skills()}
    assert "wiii-living-core" in persona_ids
    assert "wiii-visible-reasoning" in persona_ids

    direct_skill = loader.get_node_skill("direct")
    assert direct_skill is not None
    assert direct_skill.skill_type == "subagent"
    assert direct_skill.phase_labels.get("attune")
    assert direct_skill.phase_focus.get("attune")
    assert direct_skill.delta_guidance.get("synthesize")
    assert direct_skill.action_style
    assert "local direct path" in direct_skill.avoid_phrases

    tool_skill = loader.get_tool_skill()
    assert tool_skill is not None
    assert tool_skill.skill_type in {"tool", "governance", "tool_governance", "subagent"}


def test_reasoning_narrator_prompt_respects_card_persona_subagent_tool_order():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    narrator = ReasoningNarrator()
    request = ReasoningRenderRequest(
        node="direct",
        phase="act",
        user_goal="Tạo landing page cho Wiii",
        tool_context="generate html file",
    )
    node_skill = narrator._resolve_node_skill("direct")

    with patch(
        "app.engine.reasoning.reasoning_narrator.build_wiii_runtime_prompt",
        return_value="CARD_RUNTIME",
    ):
        prompt = narrator._build_system_prompt(request, node_skill)

    assert prompt.startswith("CARD_RUNTIME")
    assert "## Persona Skill:" in prompt
    assert "## Subagent Skill:" in prompt
    assert "## Tool Governance Skill" in prompt
    assert "## Persona Runtime Guardrails" in prompt
    assert "## Subagent Runtime Cues" in prompt
    assert prompt.index("## Persona Skill:") > prompt.index("CARD_RUNTIME")
    assert prompt.index("## Subagent Skill:") > prompt.index("## Persona Skill:")
    assert prompt.index("## Tool Governance Skill") > prompt.index("## Subagent Skill:")


@pytest.mark.asyncio
async def test_reasoning_narrator_fallback_uses_skill_contract_when_llm_unavailable():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    narrator = ReasoningNarrator()
    request = ReasoningRenderRequest(
        node="direct",
        phase="attune",
        user_goal="Chào Wiii",
    )
    skill = narrator._resolve_node_skill("direct")
    assert skill is not None

    with patch(
        "app.engine.reasoning.reasoning_narrator.AgentConfigRegistry.get_llm",
        side_effect=RuntimeError("offline"),
    ):
        result = await narrator.render(request)

    assert result.label == skill.phase_labels["attune"]
    assert result.summary == skill.fallback_summaries["attune"]
    assert result.phase == "attune"
    assert result.delta_chunks


@pytest.mark.asyncio
async def test_reasoning_narrator_degrades_when_llm_returns_raw_trace_language():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    class _FakeStructured:
        async def ainvoke(self, _messages):
            return SimpleNamespace(
                label="Route",
                summary="router pipeline tool_call_id session_id request_id",
                action_text="",
                delta_chunks=["tool_call_id", "router pipeline"],
                style_tags=[],
            )

    class _FakeLLM:
        def with_structured_output(self, _schema):
            return _FakeStructured()

    narrator = ReasoningNarrator()
    request = ReasoningRenderRequest(
        node="supervisor",
        phase="route",
        user_goal="Giải thích Rule 15",
    )
    skill = narrator._resolve_node_skill("supervisor")
    assert skill is not None

    with patch(
        "app.engine.reasoning.reasoning_narrator.AgentConfigRegistry.get_llm",
        return_value=_FakeLLM(),
    ):
        result = await narrator.render(request)

    assert result.label == skill.phase_labels["route"]
    assert result.summary == skill.fallback_summaries["route"]
    assert "router" not in result.summary.lower()
    assert all("tool_" not in chunk for chunk in result.delta_chunks)


@pytest.mark.asyncio
async def test_reasoning_narrator_degrades_when_llm_uses_skill_forbidden_phrase():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    class _FakeStructured:
        async def ainvoke(self, _messages):
            return SimpleNamespace(
                label="Direct",
                summary="Mình đang đi theo local direct path để trả lời nhanh hơn.",
                action_text="",
                delta_chunks=["local direct path", "đã nhận kết quả"],
                style_tags=[],
            )

    class _FakeLLM:
        def with_structured_output(self, _schema):
            return _FakeStructured()

    narrator = ReasoningNarrator()
    request = ReasoningRenderRequest(
        node="direct",
        phase="synthesize",
        user_goal="Chào Wiii",
    )
    skill = narrator._resolve_node_skill("direct")
    assert skill is not None

    with patch(
        "app.engine.reasoning.reasoning_narrator.AgentConfigRegistry.get_llm",
        return_value=_FakeLLM(),
    ):
        result = await narrator.render(request)

    assert result.label == skill.phase_labels["synthesize"]
    assert result.summary == skill.fallback_summaries["synthesize"]
    assert "local direct path" not in result.summary.lower()


@pytest.mark.asyncio
async def test_reasoning_narrator_normalizes_overlong_label_and_summary():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    class _FakeStructured:
        async def ainvoke(self, _messages):
            return SimpleNamespace(
                label="Mình đang nhìn vào yêu cầu vẽ biểu đồ bằng Python của bạn để cân nhắc hướng làm phù hợp nhất.",
                summary=(
                    "Mình đang nhìn vào yêu cầu vẽ biểu đồ bằng Python của bạn và đang cân nhắc khá nhiều khả năng khác nhau "
                    "để biến nó thành một sản phẩm trực quan, dễ mở và thật sự dùng được ngay cho bạn."
                ),
                action_text="Để mình bắt tay vào chuẩn bị một đoạn mã Python thật chỉnh chu để tạo biểu đồ cho bạn nhé.",
                delta_chunks=[
                    "Mình đang cân nhắc giữa việc viết code mẫu và chạy thật để tạo ra một file hình ảnh có thể mở ra ngay."
                ],
                style_tags=[],
            )

    class _FakeLLM:
        def with_structured_output(self, _schema):
            return _FakeStructured()

    narrator = ReasoningNarrator()
    request = ReasoningRenderRequest(
        node="code_studio_agent",
        phase="ground",
        user_goal="Vẽ một biểu đồ bằng Python và gửi file PNG.",
    )
    skill = narrator._resolve_node_skill("code_studio_agent")
    assert skill is not None

    with patch(
        "app.engine.reasoning.reasoning_narrator.AgentConfigRegistry.get_llm",
        return_value=_FakeLLM(),
    ):
        result = await narrator.render(request)

    assert result.label == skill.phase_labels["ground"]
    assert len(result.summary) <= 140
    assert ". " not in result.summary
    assert "cân nhắc khá nhiều khả năng khác nhau" not in result.summary


def test_runtime_no_longer_depends_on_legacy_reasoning_builders():
    repo_root = Path(__file__).resolve().parents[2]

    runtime_targets = [
        repo_root / "app" / "engine" / "multi_agent" / "graph.py",
        repo_root / "app" / "engine" / "multi_agent" / "graph_streaming.py",
        repo_root / "app" / "engine" / "multi_agent" / "agents" / "rag_node.py",
        repo_root / "app" / "engine" / "multi_agent" / "agents" / "tutor_node.py",
        repo_root / "app" / "engine" / "multi_agent" / "agents" / "memory_agent.py",
        repo_root / "app" / "engine" / "multi_agent" / "agents" / "product_search_node.py",
        repo_root / "app" / "engine" / "multi_agent" / "subagents" / "search" / "workers.py",
    ]
    legacy_symbols = (
        "build_supervisor_reasoning_beat",
        "build_supervisor_reasoning_reflection",
        "build_supervisor_action_text",
        "build_rag_reasoning_beat",
        "build_tutor_reasoning_beat",
        "build_direct_reasoning_beat",
        "build_direct_tool_reflection_text",
        "ReasoningBeat",
    )

    for target in runtime_targets:
        source = target.read_text(encoding="utf-8")
        for symbol in legacy_symbols:
            assert symbol not in source, f"{symbol} leaked into {target.name}"

    character_card = (
        repo_root / "app" / "engine" / "character" / "character_card.py"
    ).read_text(encoding="utf-8")
    for symbol in (*legacy_symbols, "infer_tutor_reasoning_phase"):
        assert symbol not in character_card
