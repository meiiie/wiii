"""
Tests for Sprint 43: AgentState schema coverage.

Tests the multi-agent shared state TypedDict by parsing the source file.
Uses AST to avoid circular import issues.
"""

import ast
import pytest


STATE_FILE = "app/engine/multi_agent/state.py"


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


class TestAgentState:
    """Test AgentState TypedDict schema."""

    @pytest.fixture
    def fields(self):
        """Get AgentState fields from source."""
        return _get_typed_dict_fields(STATE_FILE, "AgentState")

    def test_agent_state_class_exists(self):
        """AgentState class exists in state.py."""
        fields = _get_typed_dict_fields(STATE_FILE, "AgentState")
        assert len(fields) > 0, "AgentState class not found or has no fields"

    def test_core_input_fields(self, fields):
        """Core input fields exist."""
        assert "query" in fields
        assert "user_id" in fields
        assert "session_id" in fields

    def test_context_fields(self, fields):
        """Context fields exist."""
        assert "context" in fields
        assert "user_context" in fields
        assert "learning_context" in fields

    def test_routing_fields(self, fields):
        """Routing fields exist."""
        assert "current_agent" in fields
        assert "next_agent" in fields

    def test_agent_output_fields(self, fields):
        """Agent output fields exist."""
        assert "rag_output" in fields
        assert "tutor_output" in fields
        assert "memory_output" in fields
        assert "agent_outputs" in fields

    def test_quality_fields(self, fields):
        """Quality control fields exist."""
        assert "grader_score" in fields
        assert "grader_feedback" in fields

    def test_final_output_fields(self, fields):
        """Final output fields exist."""
        assert "final_response" in fields
        assert "sources" in fields
        assert "tools_used" in fields

    def test_metadata_fields(self, fields):
        """Metadata fields exist."""
        assert "iteration" in fields
        assert "max_iterations" in fields
        assert "error" in fields

    def test_reasoning_trace_fields(self, fields):
        """Reasoning trace fields exist (SOTA 2025)."""
        assert "reasoning_trace" in fields
        assert "thinking_content" in fields
        assert "thinking" in fields

    def test_guardian_field(self, fields):
        """Guardian agent field exists."""
        assert "guardian_passed" in fields

    def test_domain_fields(self, fields):
        """Domain plugin fields exist."""
        assert "domain_id" in fields
        assert "domain_config" in fields
        assert "skill_context" in fields

    def test_internal_tracer_field(self, fields):
        """Internal tracer reference exists."""
        assert "_tracer" in fields

    def test_total_field_count(self, fields):
        """State has expected number of fields (catches accidental deletions)."""
        # Sprint 96: 3 KG Builder fields removed → 25 fields minimum
        assert len(fields) >= 22, f"Only {len(fields)} fields, expected >= 22"

    def test_is_typed_dict_subclass(self):
        """Source file declares AgentState as TypedDict subclass."""
        with open(STATE_FILE, encoding="utf-8") as f:
            source = f.read()
        assert "class AgentState(TypedDict" in source

    def test_total_false_in_declaration(self):
        """AgentState declared with total=False."""
        with open(STATE_FILE, encoding="utf-8") as f:
            source = f.read()
        assert "total=False" in source
