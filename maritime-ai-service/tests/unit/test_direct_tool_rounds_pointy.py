from types import SimpleNamespace

import pytest

from tests.unit.direct_tool_rounds_helpers import _state_with_targets


def test_pointy_validator_accepts_bare_id_in_inventory():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button", "settings-link")
    assert _validate_pointy_selector("chat-send-button", state) is None

@pytest.mark.asyncio
async def test_direct_pointy_post_dispatch_emits_show_action() -> None:
    from app.engine.multi_agent.direct_pointy_runtime import (
        handle_direct_pointy_post_dispatch,
    )

    pushed_events: list[dict] = []

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    result = await handle_direct_pointy_post_dispatch(
        tool_name="tool_pointy_show",
        tool_args={
            "selector": "chat-send-button",
            "caption": "Nút gửi",
            "duration_ms": 3000,
        },
        result="[POINTY:highlight]",
        state=_state_with_targets("chat-send-button"),
        push_event=push_event,
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert result.result == "[POINTY:highlight]"
    assert result.pointy_action_emitted is True
    assert result.inventory_served is False
    assert [event["type"] for event in pushed_events] == ["pointy_action"]
    assert pushed_events[0]["content"]["action"] == "ui.highlight"
    assert pushed_events[0]["content"]["params"]["selector"] == "chat-send-button"

@pytest.mark.asyncio
async def test_direct_pointy_post_dispatch_rewrites_invalid_selector_result() -> None:
    from app.engine.multi_agent.direct_pointy_runtime import (
        handle_direct_pointy_post_dispatch,
    )

    pushed_events: list[dict] = []

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    result = await handle_direct_pointy_post_dispatch(
        tool_name="tool_pointy_show",
        tool_args={"selector": ".send-button"},
        result="[POINTY:highlight]",
        state=_state_with_targets("chat-send-button"),
        push_event=push_event,
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert "NOT a valid Wiii Pointy id" in result.result
    assert result.pointy_action_emitted is False
    assert pushed_events == []

@pytest.mark.asyncio
async def test_direct_pointy_post_dispatch_rewrites_inventory_result() -> None:
    from app.engine.multi_agent.direct_pointy_runtime import (
        handle_direct_pointy_post_dispatch,
    )

    async def push_event(event: dict) -> None:
        return None

    result = await handle_direct_pointy_post_dispatch(
        tool_name="tool_pointy_inventory",
        tool_args={},
        result="[POINTY:inventory]",
        state=_state_with_targets("chat-send-button"),
        push_event=push_event,
        logger_obj=__import__("logging").getLogger(__name__),
    )

    assert result.inventory_served is True
    assert "Pointable elements" in result.result
    assert 'tool_pointy_show(selector="chat-send-button"' in result.result

def test_pointy_validator_accepts_auto_id_in_inventory():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("auto:button:gui-tin-nhan", "settings-link")
    assert _validate_pointy_selector("auto:button:gui-tin-nhan", state) is None

def test_pointy_validator_accepts_data_wiii_id_verbose_form():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    assert (
        _validate_pointy_selector('[data-wiii-id="chat-send-button"]', state)
        is None
    )

def test_pointy_validator_rejects_compound_css_selector():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector(
        'button[type="submit"], .send-button, [aria-label="Gửi"], button:has(svg)',
        state,
    )
    assert err is not None
    assert "ERROR" in err
    assert "NOT a valid Wiii Pointy id" in err
    assert "chat-send-button" in err  # available ids surfaced for self-correction

def test_pointy_validator_rejects_class_selector():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector(".send-button", state)
    assert err is not None
    assert "DO NOT generate CSS selectors" in err

def test_pointy_validator_rejects_aria_label_selector():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector('[aria-label="Gửi"]', state)
    assert err is not None
    assert "ERROR" in err

def test_pointy_validator_rejects_pseudo_class_selector():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector("button:has(svg)", state)
    assert err is not None

def test_pointy_validator_rejects_id_with_hash_prefix():
    """The `#chat-send-button` form is a CSS id selector, not a bare id."""
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector("#chat-send-button", state)
    assert err is not None

def test_pointy_validator_rejects_empty_selector():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button")
    err = _validate_pointy_selector("", state)
    assert err is not None
    assert "Empty selector" in err

def test_pointy_validator_rejects_unknown_bare_id_with_inventory_hint():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("chat-send-button", "settings-link")
    err = _validate_pointy_selector("nonexistent-button", state)
    assert err is not None
    assert "không có trong available_targets" in err
    assert "chat-send-button" in err

def test_pointy_validator_rejects_unknown_auto_id_with_inventory_hint():
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = _state_with_targets("auto:button:gui-tin-nhan")
    err = _validate_pointy_selector("auto:button:cai-dat", state)
    assert err is not None
    assert "available_targets" in err
    assert "auto:button:gui-tin-nhan" in err

def test_pointy_validator_passes_bare_id_when_inventory_empty():
    """Without inventory we can't verify — fall through to permissive."""
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = SimpleNamespace(host_context=None)
    assert _validate_pointy_selector("chat-send-button", state) is None

def test_pointy_validator_passes_auto_id_when_inventory_empty():
    """Without inventory, allow Wiii synthetic id syntax and let frontend resolve."""
    from app.engine.multi_agent.direct_pointy_runtime import (
        _validate_pointy_selector,
    )

    state = SimpleNamespace(host_context=None)
    assert _validate_pointy_selector("auto:button:gui-tin-nhan", state) is None

def test_build_force_skill_directive_pointy_inlines_inventory():
    """v3.0 F5: when @-mention force-binds wiii-pointy, system prompt
    directive must inline the available_targets so LLM picks right id
    without round-tripping tool_pointy_inventory."""
    from app.engine.multi_agent.direct_prompt_turn_contracts import _build_force_skill_directive

    state = {
        'context': {
            'force_skills': ['wiii-pointy'],
            'host_context': {
                'page': {
                    'metadata': {
                        'available_targets': [
                            {'id': 'chat-send-button', 'role': 'button', 'label': 'Gửi tin nhắn'},
                            {'id': 'auto:button:dinh-kem-file', 'role': 'button', 'label': 'Đính kèm file'},
                            {'id': 'settings-link', 'role': 'link', 'label': 'Cài đặt'},
                        ]
                    }
                }
            }
        }
    }
    result = _build_force_skill_directive(state)
    # Imperative phrasing — Anthropic Computer Use 2026.
    assert 'PHẢI gọi' in result
    assert 'tool_pointy_show' in result
    # Inventory inline với prescriptive directive.
    assert 'chat-send-button' in result
    assert 'Gửi tin nhắn' in result
    # Anti-hallucination — exact inventory id contract, including auto ids.
    assert 'auto:button:dinh-kem-file' in result
    assert 'Synthetic ids' in result
    assert 'KHÔNG generate CSS' in result

def test_build_force_skill_directive_empty_when_no_force_skills():
    from app.engine.multi_agent.direct_prompt_turn_contracts import _build_force_skill_directive

    assert _build_force_skill_directive({'context': {}}) == ''
    assert _build_force_skill_directive({}) == ''

def test_build_force_skill_directive_web_search_branch():
    from app.engine.multi_agent.direct_prompt_turn_contracts import _build_force_skill_directive

    state = {'context': {'force_skills': ['web-search']}}
    result = _build_force_skill_directive(state)
    assert 'web-search' in result.lower() or 'tool_web_search' in result
    assert 'PHẢI gọi' in result

def test_make_pointy_show_with_enum_constrains_selector():
    """v9.0 F18: enum-bound tool's selector must accept inventory ids only.

    SeeAct (ICML'24) Textual Choices grounding pattern — JSON schema
    enum constraint at OpenAI tool-call layer.
    """
    from app.engine.tools.pointy_tools import make_pointy_show_with_enum

    inventory = ["chat-send-button", "auto:button:dinh-kem-file", "domain-selector"]
    enum_tool = make_pointy_show_with_enum(inventory)
    schema = enum_tool.input_model.model_json_schema()
    selector_field = schema.get("properties", {}).get("selector", {})
    # Pydantic produces enum constraint via Literal[...].
    enum_values = selector_field.get("enum")
    assert enum_values is not None
    assert set(enum_values) == set(inventory)

def test_make_pointy_show_with_enum_empty_falls_back_to_static():
    from app.engine.tools.pointy_tools import (
        make_pointy_show_with_enum,
        tool_pointy_show,
    )

    enum_tool = make_pointy_show_with_enum([])
    # No inventory → return static unchanged.
    assert enum_tool is tool_pointy_show

def test_make_pointy_show_with_enum_caps_at_64_for_token_budget():
    from app.engine.tools.pointy_tools import make_pointy_show_with_enum

    huge_inventory = [f"item-{i:03d}" for i in range(200)]
    enum_tool = make_pointy_show_with_enum(huge_inventory)
    schema = enum_tool.input_model.model_json_schema()
    enum_values = schema["properties"]["selector"].get("enum", [])
    # Cap to 64 to avoid prompt bloat.
    assert len(enum_values) == 64
    assert enum_values[0] == "item-000"

def test_validate_pointy_target_accepts_inventory_id():
    from app.engine.tools.pointy_tools import validate_pointy_target

    inv = ["chat-send-button", "attach-file-button"]
    assert validate_pointy_target("chat-send-button", inv) is None
    err = validate_pointy_target("nonexistent", inv)
    assert err is not None
    assert "not in current inventory" in err
    err = validate_pointy_target("", inv)
    assert err is not None

def test_extract_inventory_ids_from_state_dict_form():
    from app.engine.tools.pointy_tools import extract_inventory_ids_from_state

    state = {
        "host_context": {
            "page": {
                "metadata": {
                    "available_targets": [
                        {"id": "btn-a"},
                        {"id": "btn-b"},
                        {"id": ""},  # filtered
                    ]
                }
            }
        }
    }
    ids = extract_inventory_ids_from_state(state)
    assert ids == ["btn-a", "btn-b"]

def test_extract_inventory_ids_from_state_nested_context():
    from app.engine.tools.pointy_tools import extract_inventory_ids_from_state

    # Some flows set host_context inside state["context"] not top-level.
    state = {
        "context": {
            "host_context": {
                "page": {
                    "metadata": {
                        "available_targets": [{"id": "btn-x"}]
                    }
                }
            }
        }
    }
    ids = extract_inventory_ids_from_state(state)
    assert ids == ["btn-x"]
