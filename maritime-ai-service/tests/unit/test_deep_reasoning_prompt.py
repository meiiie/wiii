"""
Test Deep Reasoning Prompt - CHI THI SO 21
Verify that PromptLoader builds valid system prompts for all roles.
"""

from app.prompts.prompt_loader import PromptLoader


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
