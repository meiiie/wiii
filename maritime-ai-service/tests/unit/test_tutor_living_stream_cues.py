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


def test_build_tutor_system_prompt_adds_thin_living_stream_cues():
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
            "mood_hint": "Nguoi dung dang hoi tiep sau mot luot hoc dai",
            "personality_mode": "professional",
            "response_language": "vi",
            "living_context_block": {
                "current_state": [
                    "Trang thai song: Wiii dang giu nhip on dinh va tap trung de go roi.",
                ],
                "relationship_memory": [
                    "User hien tai: Nam",
                    "Day la mot turn noi tiep, uu tien giu nhip va nho dung ngu canh truoc do.",
                ],
                "narrative_state": [
                    "Nen noi tam hien tai: kha on, giu nhip vua phai.",
                ],
            },
        },
        query="Giai thich tiep di",
        logger=logging.getLogger(__name__),
    )

    assert "## LIVING CONTINUITY CUES" in prompt
    assert "one_self: Day van la Wiii." in prompt
    assert "relationship: User hien tai: Nam" in prompt
    assert "narrative: Nen noi tam hien tai: kha on, giu nhip vua phai." in prompt
    assert "current_state: Trang thai song: Wiii dang giu nhip on dinh va tap trung de go roi." in prompt
