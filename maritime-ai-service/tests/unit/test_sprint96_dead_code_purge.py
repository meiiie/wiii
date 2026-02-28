"""
Tests for Sprint 96: Dead Code Purge — KG Builder Graph Dead-End + Stale YAML.

Verifies that confirmed-dead code has been removed:
1. AgentType.KG_BUILDER enum value (graph routing dead-end)
2. AgentState KG Builder fields (never set/read by graph flow)
3. _shared.yaml empathy section (never read by prompt_loader)
4. assistant.yaml addressing section (wrong key, never read)
"""

import ast
import os

import pytest
import yaml


# ============================================================================
# Paths
# ============================================================================
STATE_FILE = "app/engine/multi_agent/state.py"
SUPERVISOR_FILE = "app/engine/multi_agent/supervisor.py"
SHARED_YAML = "app/prompts/base/_shared.yaml"
ASSISTANT_YAML = "app/prompts/agents/assistant.yaml"


def _get_typed_dict_fields(filepath: str, class_name: str) -> set:
    """Parse a TypedDict class from source and return field names."""
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields = set()
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.add(item.target.id)
            return fields
    return set()


def _load_yaml(filepath: str) -> dict:
    """Load YAML file and return parsed dict."""
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_enum_values(filepath: str, class_name: str) -> set:
    """Parse an Enum class from source and return assigned string values."""
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                            values.add(item.value.value)
    return values


def _get_enum_names(filepath: str, class_name: str) -> set:
    """Parse an Enum class from source and return member names."""
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
    return names


# ============================================================================
# Test AgentType Cleanup
# ============================================================================
class TestAgentTypeCleanup:
    """Verify KG_BUILDER removed from AgentType enum."""

    def test_kg_builder_not_in_agent_type(self):
        """KG_BUILDER enum value must not exist."""
        values = _get_enum_values(SUPERVISOR_FILE, "AgentType")
        assert "kg_builder" not in values

    def test_six_agent_types_remain(self):
        """Exactly 6 agent types: RAG, TUTOR, MEMORY, DIRECT, PRODUCT_SEARCH, COLLEAGUE."""
        values = _get_enum_values(SUPERVISOR_FILE, "AgentType")
        assert values == {"rag_agent", "tutor_agent", "memory_agent", "direct", "product_search_agent", "colleague_agent"}

    def test_kg_builder_name_not_in_enum(self):
        """KG_BUILDER name must not exist in enum members."""
        names = _get_enum_names(SUPERVISOR_FILE, "AgentType")
        assert "KG_BUILDER" not in names
        assert "RAG" in names
        assert "DIRECT" in names


# ============================================================================
# Test AgentState Cleanup
# ============================================================================
class TestAgentStateCleanup:
    """Verify dead KG Builder state fields removed."""

    @pytest.fixture
    def fields(self):
        return _get_typed_dict_fields(STATE_FILE, "AgentState")

    def test_kg_builder_output_not_in_state(self, fields):
        """kg_builder_output field must not exist."""
        assert "kg_builder_output" not in fields

    def test_extracted_entities_not_in_state(self, fields):
        """extracted_entities field must not exist."""
        assert "extracted_entities" not in fields

    def test_extracted_relations_not_in_state(self, fields):
        """extracted_relations field must not exist."""
        assert "extracted_relations" not in fields

    def test_active_output_fields_still_exist(self, fields):
        """Actively-used output fields must remain."""
        assert "rag_output" in fields
        assert "tutor_output" in fields
        assert "memory_output" in fields

    def test_active_context_fields_still_exist(self, fields):
        """Context fields must remain (used by graph nodes)."""
        assert "user_context" in fields
        assert "learning_context" in fields
        assert "domain_id" in fields


# ============================================================================
# Test Shared YAML Cleanup
# ============================================================================
class TestSharedYAMLCleanup:
    """Verify dead empathy section removed from _shared.yaml."""

    @pytest.fixture
    def shared(self):
        return _load_yaml(SHARED_YAML)

    def test_no_empathy_section(self, shared):
        """empathy section must not exist."""
        assert "empathy" not in shared

    def test_common_directives_still_present(self, shared):
        """common_directives section must remain (alive)."""
        assert "common_directives" in shared

    def test_memory_section_still_present(self, shared):
        """memory section must remain (alive)."""
        assert "memory" in shared

    def test_reasoning_section_still_present(self, shared):
        """reasoning section must remain (alive)."""
        assert "reasoning" in shared


# ============================================================================
# Test Assistant YAML Cleanup
# ============================================================================
class TestAssistantYAMLCleanup:
    """Verify dead addressing section removed from assistant.yaml."""

    @pytest.fixture
    def assistant(self):
        return _load_yaml(ASSISTANT_YAML)

    def test_no_addressing_section(self, assistant):
        """addressing section under style must not exist."""
        style = assistant.get("style", {})
        assert "addressing" not in style

    def test_style_tone_still_present(self, assistant):
        """style.tone must remain (alive)."""
        style = assistant.get("style", {})
        assert "tone" in style

    def test_directives_still_present(self, assistant):
        """directives section must remain (alive)."""
        assert "directives" in assistant
        assert "must" in assistant["directives"]
        assert "avoid" in assistant["directives"]
