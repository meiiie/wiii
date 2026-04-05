from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_golden_eval_manifest_can_be_loaded_and_core_selection_is_stable():
    module = _load_module(
        "probe_wiii_golden_eval_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    manifest = module.load_manifest(SCRIPTS_DIR / "data" / "wiii_golden_eval_manifest.json")
    sessions = manifest["sessions"]

    assert len(sessions) >= 8
    assert any(session["profile"] == "core" for session in sessions)
    assert any(session["profile"] == "extended" for session in sessions)

    core_sessions = module.select_sessions(manifest, profiles=["core"])
    extended_sessions = module.select_sessions(manifest, profiles=["extended"])

    assert core_sessions
    assert extended_sessions
    assert all(session["profile"] == "core" for session in core_sessions)
    assert all(session["profile"] == "extended" for session in extended_sessions)


def test_golden_eval_summary_counts_transport_results():
    module = _load_module(
        "probe_wiii_golden_eval_summary_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    report = {
        "sessions": [
            {
                "turns": [
                    {
                        "sync": {
                            "evaluation": {"passed": True},
                            "processing_time": 10.0,
                            "metadata": {
                                "provider": "zhipu",
                                "model": "glm-5",
                                "failover": {
                                    "switched": True,
                                    "last_reason_code": "rate_limit",
                                    "route": [{"from_provider": "google", "to_provider": "zhipu"}],
                                },
                            },
                        },
                        "stream": {
                            "evaluation": {"passed": False},
                            "duplicate_answer_tail": True,
                            "thinking": "visible",
                            "tool_trace": [{"kind": "call", "title": "tool", "body": "{}"}],
                            "processing_time": 8.0,
                            "metadata": {"provider": "zhipu", "model": "glm-4.5-air"},
                        },
                    },
                    {
                        "sync": {
                            "evaluation": {"passed": True},
                            "processing_time": 6.0,
                            "metadata": {"provider": "zhipu", "model": "glm-4.5-air"},
                        },
                        "stream": {
                            "evaluation": {"passed": True},
                            "duplicate_answer_tail": False,
                            "thinking": "",
                            "tool_trace": [],
                            "processing_time": 5.0,
                            "metadata": {"provider": "zhipu", "model": "glm-4.5-air"},
                        },
                    },
                ]
            }
        ]
    }

    summary = module.summarize_report(report)

    assert summary["session_count"] == 1
    assert summary["turn_count"] == 2
    assert summary["transport_count"] == 4
    assert summary["passed_transport_count"] == 3
    assert summary["failed_transport_count"] == 1
    assert summary["stream_duplicate_answer_count"] == 1
    assert summary["stream_visible_thinking_turns"] == 1
    assert summary["stream_tool_trace_turns"] == 1
    assert summary["transport_avg_processing_time"]["sync"] == 8.0
    assert summary["transport_avg_processing_time"]["stream"] == 6.5
    assert summary["provider_counts"]["sync"]["zhipu"] == 2
    assert summary["model_counts"]["stream"]["glm-4.5-air"] == 2
    assert summary["failover_switch_transports"] == 1
    assert summary["failover_reason_counts"]["rate_limit"] == 1
    assert summary["failover_route_counts"]["google->zhipu"] == 1


def test_golden_eval_can_filter_selected_turn_ids():
    module = _load_module(
        "probe_wiii_golden_eval_turn_filter_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    sessions = [
        {
            "id": "direct_origin_bong",
            "turns": [
                {"id": "origin", "prompt": "Wiii duoc sinh ra nhu the nao?"},
                {"id": "bong_followup", "prompt": "Con Bong thi sao?"},
            ],
        },
        {
            "id": "memory_name_roundtrip",
            "turns": [
                {"id": "store_name", "prompt": "Minh ten Nam"},
            ],
        },
    ]

    filtered = module.filter_session_turns(sessions, turn_ids=["origin"])

    assert len(filtered) == 1
    assert filtered[0]["id"] == "direct_origin_bong"
    assert [turn["id"] for turn in filtered[0]["turns"]] == ["origin"]


def test_golden_eval_evaluation_normalizes_agent_aliases():
    module = _load_module(
        "probe_wiii_golden_eval_eval_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    turn_def = {
        "expect": {
            "common": {
                "should_have_answer": True,
                "agent_any_of": ["tutor"],
            }
        }
    }
    result = {
        "answer": "Rule 15 nói về tình huống cắt hướng.",
        "thinking": "Mình chốt chỗ dễ nhầm trước.",
        "agent_type": "tutor_agent",
        "tool_trace": [],
    }

    evaluation = module._evaluate_turn(result=result, turn_def=turn_def, transport="stream")

    assert evaluation["passed"] is True
    assert evaluation["checks"]["agent_matches"] is True
    assert evaluation["failures"] == []


def test_golden_eval_builds_isolated_user_ids_per_session():
    module = _load_module(
        "probe_wiii_golden_eval_isolated_user_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    user_a = module._build_session_user_id(
        base_user_id="codex-wiii-golden",
        stamp="2026-04-01-101500",
        session_key="direct_origin_bong",
    )
    user_b = module._build_session_user_id(
        base_user_id="codex-wiii-golden",
        stamp="2026-04-01-101500",
        session_key="memory_name_roundtrip",
    )

    assert user_a != user_b
    assert user_a.startswith("codex-wiii-golden-2026-04-01-101500-")
    assert user_b.endswith("memory_name_roundtrip")


def test_golden_eval_write_report_snapshot(tmp_path):
    module = _load_module(
        "probe_wiii_golden_eval_snapshot_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    output = tmp_path / "golden.json"
    payload = {
        "schema": "wiii_golden_eval_v1",
        "sessions": [{"id": "origin"}],
        "progress": {"completed_session_count": 1, "selected_session_count": 3, "is_complete": False},
    }

    module._write_report_snapshot(output, payload)

    loaded = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert loaded["schema"] == "wiii_golden_eval_v1"
    assert loaded["progress"]["is_complete"] is False
    assert loaded["sessions"][0]["id"] == "origin"


def test_render_html_supports_golden_eval_schema():
    module = _load_module(
        "render_thinking_probe_html_module",
        SCRIPTS_DIR / "render_thinking_probe_html.py",
    )

    report = {
        "selected_profiles": ["core"],
        "summary": {
            "session_count": 1,
            "turn_count": 1,
            "transport_count": 2,
            "passed_transport_count": 2,
            "failed_transport_count": 0,
            "stream_visible_thinking_turns": 1,
            "stream_tool_trace_turns": 1,
        },
        "sessions": [
            {
                "id": "origin",
                "label": "Direct Selfhood + Bong",
                "goal": "Check living selfhood continuity.",
                "coverage": ["direct", "selfhood"],
                "turns": [
                    {
                        "prompt": "Wiii được sinh ra như thế nào?",
                        "sync": {
                            "transport": "sync",
                            "prompt": "Wiii được sinh ra như thế nào?",
                            "answer": "Wiii ra đời từ The Wiii Lab.",
                            "thinking": "Mình muốn kể về nguồn gốc của mình.",
                            "agent_type": "direct",
                            "status_code": 200,
                            "processing_time": 9.1,
                            "tool_trace": [],
                            "runtime": {"provider": "zhipu", "model": "glm-5", "status_code": 200},
                            "evaluation": {"passed": True, "checks": {"has_answer": True}, "failures": []},
                        },
                        "stream": {
                            "transport": "stream",
                            "prompt": "Wiii được sinh ra như thế nào?",
                            "answer": "Wiii ra đời từ The Wiii Lab.",
                            "thinking": "Mình đang ngẫm nghĩ về cội nguồn của mình.",
                            "agent_type": "direct",
                            "status_code": 200,
                            "processing_time": 7.4,
                            "tool_trace": [{"kind": "call", "title": "memory", "body": "{}"}],
                            "runtime": {
                                "provider": "zhipu",
                                "model": "glm-4.5-air",
                                "status_code": 200,
                                "failover_reason_code": "rate_limit",
                                "failover_route": ["google->zhipu"],
                            },
                            "evaluation": {"passed": True, "checks": {"has_visible_thinking": True}, "failures": []},
                        },
                    }
                ],
            }
        ],
    }

    html = module.render_html(report, Path("golden.json"))

    assert "Regression Review" in html
    assert "Session 1" in html
    assert "Direct Selfhood + Bong" in html
    assert "Wiii được sinh ra như thế nào?" in html
    assert "PASS" in html
    assert "Research Trace" in html
    assert "glm-4.5-air" in html
    assert "google-&gt;zhipu" in html


def test_golden_eval_prefers_lifecycle_final_text_over_raw_stream_blob():
    module = _load_module(
        "probe_wiii_golden_eval_lifecycle_module",
        SCRIPTS_DIR / "probe_wiii_golden_eval.py",
    )

    metadata = {
        "thinking_content": "RAW thinker blob that should not win",
        "thinking_lifecycle": {
            "final_text": "Lifecycle final text should be the authority.",
            "final_length": 43,
        },
    }

    assert module._thinking_from_metadata(metadata) == "Lifecycle final text should be the authority."


def test_render_html_prefers_lifecycle_final_text_over_transport_thinking():
    module = _load_module(
        "render_thinking_probe_html_lifecycle_module",
        SCRIPTS_DIR / "render_thinking_probe_html.py",
    )

    report = {
        "selected_profiles": ["core"],
        "summary": {
            "session_count": 1,
            "turn_count": 1,
            "transport_count": 2,
            "passed_transport_count": 2,
            "failed_transport_count": 0,
            "stream_visible_thinking_turns": 1,
            "stream_tool_trace_turns": 0,
        },
        "sessions": [
            {
                "id": "direct_origin_bong",
                "label": "Direct Selfhood + Bong",
                "goal": "Check lifecycle authority.",
                "coverage": ["direct", "selfhood"],
                "turns": [
                    {
                        "prompt": "Con Bong thi sao?",
                        "sync": {
                            "transport": "sync",
                            "prompt": "Con Bong thi sao?",
                            "answer": "Bong la con meo ao.",
                            "thinking": "RAW sync blob",
                            "agent_type": "direct",
                            "tool_trace": [],
                            "metadata": {
                                "thinking_lifecycle": {
                                    "final_text": "Sync lifecycle thought ve Bong.",
                                    "final_length": 28,
                                    "live_length": 28,
                                    "segment_count": 1,
                                    "phases": ["final_snapshot"],
                                    "provenance_mix": ["final_snapshot"],
                                }
                            },
                            "evaluation": {"passed": True, "checks": {}, "failures": []},
                        },
                        "stream": {
                            "transport": "stream",
                            "prompt": "Con Bong thi sao?",
                            "answer": "Bong la con meo ao.",
                            "thinking": "RAW stream blob that should stay hidden",
                            "agent_type": "direct",
                            "tool_trace": [],
                            "metadata": {
                                "thinking_lifecycle": {
                                    "final_text": "Stream lifecycle thought ve Bong.",
                                    "final_length": 30,
                                    "live_length": 30,
                                    "segment_count": 1,
                                    "phases": ["final_snapshot"],
                                    "provenance_mix": ["final_snapshot"],
                                }
                            },
                            "evaluation": {"passed": True, "checks": {}, "failures": []},
                        },
                    }
                ],
            }
        ],
    }

    html = module.render_html(report, Path("golden.json"))

    assert "Sync lifecycle thought ve Bong." in html
    assert "Stream lifecycle thought ve Bong." in html
    assert "RAW stream blob that should stay hidden" not in html


def test_render_html_keeps_legacy_probe_support():
    module = _load_module(
        "render_thinking_probe_html_legacy_module",
        SCRIPTS_DIR / "render_thinking_probe_html.py",
    )

    report = {
        "session_id": "legacy-session",
        "sync_rule15": {
            "prompt": "Giải thích Quy tắc 15 COLREGs",
            "json": {
                "data": {"answer": "Rule 15 nói về tình huống cắt hướng."},
                "metadata": {"agent_type": "tutor", "thinking_content": "Mình chốt chỗ dễ nhầm trước."},
            },
        },
        "stream_rule15": {
            "prompt": "Giải thích Quy tắc 15 COLREGs",
            "answer": "Rule 15 nói về tình huống cắt hướng.",
            "thinking": "Mình chốt chỗ dễ nhầm trước.",
            "metadata": {"agent_type": "tutor"},
        },
    }

    html = module.render_html(report, Path("legacy.json"))

    assert "Raw Thinking Viewer" in html
    assert "legacy-session" in html
    assert "Giải thích Quy tắc 15 COLREGs" in html
