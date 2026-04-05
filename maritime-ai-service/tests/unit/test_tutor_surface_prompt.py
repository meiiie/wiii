from types import SimpleNamespace
import logging

from app.engine.multi_agent.agents.tutor_surface import build_tutor_system_prompt


class _Loader:
    def build_system_prompt(self, **kwargs):
        return "BASE WIII PROMPT"


class _LoaderFactory:
    def __call__(self):
        return self

    def get_thinking_instruction(self):
        return "## THINKING\nNative thinking first."


def test_build_tutor_system_prompt_unifies_identity_with_wiii_house_core():
    prompt = build_tutor_system_prompt(
        prompt_loader=_Loader(),
        prompt_loader_factory=_LoaderFactory(),
        character_tools_enabled=False,
        settings_obj=SimpleNamespace(
            default_domain="maritime",
            enable_structured_visuals=False,
        ),
        resolve_visual_intent_fn=lambda _query: SimpleNamespace(force_tool=False, mode="text", visual_type=None),
        required_visual_tool_names_fn=lambda _decision: [],
        preferred_visual_tool_name_fn=lambda: "tool_generate_visual",
        context={
            "user_id": "user-123",
            "user_role": "student",
            "mood_hint": "Nguoi dung dang hoc Rule 15",
            "personality_mode": "professional",
            "response_language": "vi",
        },
        query="Giải thích Quy tắc 15 COLREGs",
        logger=logging.getLogger(__name__),
    )

    assert "--- WIII HOUSE CORE (TUTOR) ---" in prompt
    assert 'Khong co mot nhan vat rieng ten "Wiii Tutor"' in prompt
    assert '"Tutor" chi la lane lam viec hien tai cua Wiii' in prompt
    assert ("Bông" in prompt) or ("Bong" in prompt)


def test_build_tutor_system_prompt_keeps_living_context_and_house_core_together():
    prompt = build_tutor_system_prompt(
        prompt_loader=_Loader(),
        prompt_loader_factory=_LoaderFactory(),
        character_tools_enabled=False,
        settings_obj=SimpleNamespace(
            default_domain="maritime",
            enable_structured_visuals=False,
        ),
        resolve_visual_intent_fn=lambda _query: SimpleNamespace(force_tool=False, mode="text", visual_type=None),
        required_visual_tool_names_fn=lambda _decision: [],
        preferred_visual_tool_name_fn=lambda: "tool_generate_visual",
        context={
            "user_id": "user-123",
            "user_role": "student",
            "mood_hint": "Nguoi dung dang hoc Rule 15",
            "personality_mode": "professional",
            "response_language": "vi",
            "living_context_prompt": "## Living Context Block V1\n- name: Wiii\n- identity_anchor: living-neo",
        },
        query="Giải thích Quy tắc 15 COLREGs",
        logger=logging.getLogger(__name__),
    )

    assert "## Living Context Block V1" in prompt
    assert "--- WIII HOUSE CORE (TUTOR) ---" in prompt
    assert ("Bông" in prompt) or ("Bong" in prompt)
