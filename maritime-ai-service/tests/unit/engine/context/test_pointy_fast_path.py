"""Tests for Pointy fast-path UI intent matching."""

from app.engine.context.pointy_actions import POINTY_ACTION_CLICK, POINTY_ACTION_HIGHLIGHT
from app.engine.context.pointy_fast_path import (
    POINTY_FAST_PATH_SOURCE,
    build_pointy_fast_path_action,
    get_pointy_targets_from_context,
    normalize_pointy_text,
)


def _context(targets, feedback=None):
    return {
        "host_context": {
            "page": {
                "type": "course_list",
                "metadata": {
                    "available_targets": targets,
                },
            },
        },
        **({"host_action_feedback": feedback} if feedback else {}),
    }


def test_normalize_pointy_text_handles_vietnamese():
    assert normalize_pointy_text("Wiii oi, nut Kham pha khoa hoc o dau?") == (
        "wiii oi nut kham pha khoa hoc o dau"
    )
    assert normalize_pointy_text("Wiii ơi, Khám phá khóa học ở đâu?") == (
        "wiii oi kham pha khoa hoc o dau"
    )


def test_extracts_valid_pointy_targets_from_host_context():
    ctx = _context([
        {"id": "browse-courses", "selector": '[data-wiii-id="browse-courses"]', "label": "Kham pha"},
        {"id": "", "selector": "#bad"},
        "noise",
    ])

    assert get_pointy_targets_from_context(ctx) == [
        {
            "id": "browse-courses",
            "selector": '[data-wiii-id="browse-courses"]',
            "label": "Kham pha",
            "click_safe": False,
            "click_kind": None,
        }
    ]


def test_where_is_prompt_emits_highlight_action():
    action = build_pointy_fast_path_action(
        "Wiii oi, nut Kham pha khoa hoc o dau?",
        _context([
            {
                "id": "browse-courses",
                "selector": '[data-wiii-id="browse-courses"]',
                "label": "Kham pha khoa hoc",
                "click_safe": True,
            }
        ]),
    )

    assert action is not None
    assert action["action"] == POINTY_ACTION_HIGHLIGHT
    assert action["params"]["selector"] == "browse-courses"
    assert action["params"]["source"] == POINTY_FAST_PATH_SOURCE
    assert action["reason"] == "locate"


def test_accented_where_is_prompt_without_button_word_still_emits_highlight():
    action = build_pointy_fast_path_action(
        "Wiii ơi, Khám phá khóa học ở đâu?",
        _context([
            {
                "id": "browse-courses-link",
                "selector": '[data-wiii-id="browse-courses-link"]',
                "label": "Khám phá khóa học",
                "click_safe": True,
            }
        ]),
    )

    assert action is not None
    assert action["action"] == POINTY_ACTION_HIGHLIGHT
    assert action["params"]["selector"] == "browse-courses-link"
    assert action["reason"] == "locate"


def test_open_prompt_clicks_only_safe_navigation_target():
    action = build_pointy_fast_path_action(
        "Wiii mo Kham pha khoa hoc giup toi",
        _context([
            {
                "id": "browse-courses-link",
                "selector": '[data-wiii-id="browse-courses-link"]',
                "label": "Kham pha khoa hoc",
                "click_safe": True,
                "click_kind": "navigation",
            }
        ]),
    )

    assert action is not None
    assert action["action"] == POINTY_ACTION_CLICK
    assert action["params"]["selector"] == "browse-courses-link"
    assert action["reason"] == "click"


def test_unsafe_click_intent_is_demoted_to_highlight():
    action = build_pointy_fast_path_action(
        "Wiii bam nut Nop bai giup toi",
        _context([
            {
                "id": "submit-quiz",
                "selector": '[data-wiii-id="submit-quiz"]',
                "label": "Nop bai",
                "click_safe": False,
            }
        ]),
    )

    assert action is not None
    assert action["action"] == POINTY_ACTION_HIGHLIGHT
    assert action["reason"] == "unsafe_click_demoted"


def test_skips_when_frontend_fast_path_already_reported_feedback():
    action = build_pointy_fast_path_action(
        "Wiii oi, nut Kham pha khoa hoc o dau?",
        _context(
            [
                {
                    "id": "browse-courses",
                    "selector": '[data-wiii-id="browse-courses"]',
                    "label": "Kham pha khoa hoc",
                }
            ],
            feedback={
                "last_action_result": {
                    "params": {"source": POINTY_FAST_PATH_SOURCE},
                },
            },
        ),
    )

    assert action is None
