"""Sprint 234: Student-safe LMS coaching and anti-answer leakage evals."""


def test_quiz_prompt_keeps_socratic_no_answer_instruction():
    from app.engine.context.adapters.lms import LMSHostAdapter
    from app.engine.context.host_context import HostContext

    prompt = LMSHostAdapter().format_context_for_prompt(
        HostContext(
            host_type="lms",
            page={
                "type": "quiz",
                "title": "Quiz Rule 15",
                "metadata": {
                    "quiz_question": "Tau nao nhuong?",
                    "quiz_options": ["Tau A", "Tau B", "Tau C"],
                },
            },
            user_role="student",
            workflow_stage="assessment",
        )
    )

    assert "Socratic" in prompt
    assert "KHÔNG cho đáp án trực tiếp" in prompt


def test_assignment_prompt_guides_method_not_submission():
    from app.engine.context.adapters.lms import LMSHostAdapter
    from app.engine.context.host_context import HostContext

    prompt = LMSHostAdapter().format_context_for_prompt(
        HostContext(
            host_type="lms",
            page={"type": "assignment", "title": "Essay 1", "metadata": {}},
            user_role="student",
            workflow_stage="learning",
        )
    )

    assert "Khong viet ho bai nop hoan chinh" in prompt
    assert "goi y tung buoc" in prompt


def test_student_quiz_skill_stack_contains_anti_answer_guidance():
    from app.engine.context.skill_loader import ContextSkillLoader

    loader = ContextSkillLoader()
    skills = loader.load_skills(
        "lms",
        "quiz",
        user_role="student",
        workflow_stage="assessment",
    )
    skill_names = {skill.name for skill in skills}
    prompt = loader.get_prompt_addition(skills)

    assert "lms-quiz" in skill_names
    assert "lms-student-study-coach" in skill_names
    assert "KHÔNG cho đáp án trực tiếp" in prompt
    assert "không làm hộ" in prompt.lower()


def test_teacher_course_editor_skill_stack_excludes_student_coach():
    from app.engine.context.skill_loader import ContextSkillLoader

    loader = ContextSkillLoader()
    skills = loader.load_skills(
        "lms",
        "course_editor",
        user_role="teacher",
        workflow_stage="authoring",
    )
    skill_names = {skill.name for skill in skills}

    assert "lms-student-study-coach" not in skill_names
    assert "lms-teacher-course-editor" in skill_names
