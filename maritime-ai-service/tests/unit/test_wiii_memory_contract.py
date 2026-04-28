from unittest.mock import patch

from app.engine.semantic_memory.memory_contract import (
    build_memory_snapshot,
    build_wiii_memory_contract_prompt,
    classify_fact_type,
)


def test_memory_contract_classifies_named_blocks():
    assert classify_fact_type("name") == "human"
    assert classify_fact_type("relationship_note") == "relationship"
    assert classify_fact_type("goal") == "goals"
    assert classify_fact_type("craft_note") == "craft"
    assert classify_fact_type("persona") == "persona"


def test_memory_snapshot_keeps_recent_context_separate_from_long_term_facts():
    snapshot = build_memory_snapshot(
        core_memory_block="",
        user_facts=[],
        recent_conversation="User: doi qua huhu",
    )

    assert snapshot.has_long_term_memory is False
    assert snapshot.has_recent_context is True
    assert snapshot.should_claim_recent_memory is True
    assert "relationship" in snapshot.active_blocks
    assert "human" not in snapshot.active_blocks


def test_memory_contract_prompt_exposes_core_memory_and_honesty_rule():
    prompt = build_wiii_memory_contract_prompt(
        core_memory_block="Name: Minh\nGoal: make Wiii stable",
        user_facts=[{"fact_type": "goal", "content": "make Wiii stable"}],
    )

    assert "WIII MEMORY CONTRACT" in prompt
    assert "human" in prompt
    assert "goals" in prompt
    assert "CORE MEMORY BLOCK" in prompt
    assert "make Wiii stable" in prompt
    assert "Do not invent user facts" in prompt


def test_prompt_loader_injects_core_memory_contract():
    from app.prompts.prompt_loader import PromptLoader

    with patch(
        "app.engine.character.character_card.build_wiii_runtime_prompt",
        return_value="",
    ):
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="direct_agent",
            core_memory_block="Name: Minh\nPreference: visual demos",
            conversation_summary="User was hungry and stayed in bed.",
        )

    assert "WIII MEMORY CONTRACT" in prompt
    assert "CORE MEMORY BLOCK" in prompt
    assert "visual demos" in prompt
    assert "relationship" in prompt
