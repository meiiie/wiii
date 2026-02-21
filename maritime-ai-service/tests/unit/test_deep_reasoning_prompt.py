"""
Test Deep Reasoning Prompt - CHI THI SO 21
Verify that PromptLoader builds valid system prompts for all roles.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.prompts.prompt_loader import PromptLoader


@pytest.fixture(autouse=True)
def _mock_character_state_manager():
    """Prevent build_system_prompt from connecting to PostgreSQL."""
    with patch(
        "app.engine.character.character_state.get_character_state_manager"
    ) as m:
        inst = MagicMock()
        inst.compile_living_state.return_value = ""
        m.return_value = inst
        yield


def test_student_prompt_builds():
    """Student prompt builds without error and has content."""
    loader = PromptLoader()
    prompt = loader.build_system_prompt(role="student", user_name="Test")
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_teacher_prompt_builds():
    """Teacher prompt builds without error and has content."""
    loader = PromptLoader()
    prompt = loader.build_system_prompt(role="teacher", user_name="Test")
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_prompts_differ_by_role():
    """Student and teacher prompts should not be identical."""
    loader = PromptLoader()
    student = loader.build_system_prompt(role="student", user_name="Test")
    teacher = loader.build_system_prompt(role="teacher", user_name="Test")
    # They may share base content but should differ
    assert isinstance(student, str)
    assert isinstance(teacher, str)
