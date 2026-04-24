from app.prompts.prompt_context_utils import (
    build_response_language_instruction,
    resolve_response_language,
)
from app.prompts.prompt_loader import get_prompt_loader
from app.prompts.prompt_runtime_tail import get_thinking_instruction_from_shared_config


def test_resolve_response_language_defaults_vietnamese_for_vietnamese_short_chat():
    assert resolve_response_language("oke, hẹ hẹ") == "vi"


def test_resolve_response_language_keeps_session_language_for_ambiguous_follow_up():
    assert resolve_response_language("ok", session_language="en") == "en"


def test_resolve_response_language_keeps_vietnamese_for_code_mixed_follow_up():
    assert (
        resolve_response_language(
            "tao visual cho minh xem duoc chu?",
            session_language="vi",
        )
        == "vi"
    )


def test_resolve_response_language_prefers_vietnamese_for_visual_request_with_diacritics():
    assert resolve_response_language("tạo visual cho mình xem được chứ?") == "vi"


def test_build_response_language_instruction_for_english_turn():
    instruction = build_response_language_instruction("en")

    assert "response_language=en" in instruction
    assert "Think in the same language the user is using for this turn." in instruction
    assert "Use English" in instruction


def test_prompt_loader_injects_turn_level_response_language_contract():
    loader = get_prompt_loader()

    prompt = loader.build_system_prompt(
        role="student",
        response_language="en",
    )

    assert "response_language=en" in prompt
    assert "Think in the same language the user is using for this turn." in prompt
    assert "Use English for the final answer, visible thinking, and the underlying native inner monologue for this turn." in prompt


def test_default_thinking_instruction_fallback_stays_native_first():
    instruction = get_thinking_instruction_from_shared_config({})

    assert "native thinking" in instruction.lower()
    assert "KHÔNG lập dàn ý câu trả lời" in instruction
    assert "KHÔNG viết nháp câu trả lời cho user" in instruction


def test_shared_yaml_thinking_instruction_restores_old_shared_prompt_language():
    loader = get_prompt_loader()

    shared_config = loader._load_shared_config()
    instruction = get_thinking_instruction_from_shared_config(shared_config)

    assert "người bạn thân" in instruction
    assert "persona_label" in instruction


def test_shared_yaml_reasoning_rules_restore_self_correction_example():
    loader = get_prompt_loader()

    shared_config = loader._load_shared_config()
    rules = shared_config["reasoning"]["rules"]
    joined = "\n".join(rules)

    assert "Khoan đã" in joined
    assert "Câu này cần trích dẫn Rule nào?" in joined
