import json
from pathlib import Path

from scripts.analyze_wiii_sync_stream_parity import (
    _analyze_report,
    _classify_thinking_gap,
    _merge_reports,
    _sse_event_counts,
)


def test_classify_thinking_gap_marks_stream_missing():
    assert (
        _classify_thinking_gap(
            {"thinking": "abc" * 50},
            {"thinking": ""},
        )
        == "stream_missing_visible_thinking"
    )


def test_merge_reports_overlays_newer_session_turn_data():
    base = {
        "sessions": [
            {
                "id": "direct_origin_bong",
                "turns": [
                    {
                        "id": "origin",
                        "sync": {"thinking": ""},
                        "stream": {"thinking": ""},
                    }
                ],
            }
        ]
    }
    overlay = {
        "sessions": [
            {
                "id": "direct_origin_bong",
                "turns": [
                    {
                        "id": "origin",
                        "sync": {"thinking": "sync-thought"},
                        "stream": {"thinking": "stream-thought"},
                    }
                ],
            }
        ]
    }

    merged = _merge_reports(base, [overlay])
    turn = merged["sessions"][0]["turns"][0]
    assert turn["sync"]["thinking"] == "sync-thought"
    assert turn["stream"]["thinking"] == "stream-thought"


def test_sse_event_counts_tracks_thinking_and_tool_events(tmp_path: Path):
    raw_path = tmp_path / "sample.txt"
    raw_path.write_text(
        "\n".join(
            [
                "event: thinking_start",
                'data: {"content":"x"}',
                "",
                "event: thinking_delta",
                'data: {"content":"y"}',
                "",
                "event: tool_call",
                'data: {"content":{"name":"tool_x"}}',
                "",
                "event: tool_result",
                'data: {"content":{"name":"tool_x","result":"ok"}}',
                "",
                "event: answer",
                'data: {"content":"done"}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    counts = _sse_event_counts(str(raw_path))
    assert counts["thinking_events"] == 2
    assert counts["tool_call_events"] == 1
    assert counts["tool_result_events"] == 1
    assert counts["answer_events"] == 1


def test_analyze_report_flags_stream_thinner_than_sync():
    report = {
        "sessions": [
            {
                "id": "memory_name_roundtrip",
                "turns": [
                    {
                        "id": "recall_name",
                        "prompt": "Ten minh la gi?",
                        "sync": {
                            "thinking": "a" * 1000,
                            "evaluation": {"failures": []},
                            "agent_type": "memory",
                            "metadata": {"provider": "zhipu", "model": "glm-5", "processing_time": 9.0},
                        },
                        "stream": {
                            "thinking": "b" * 200,
                            "evaluation": {"failures": []},
                            "agent_type": "memory",
                            "raw_path": "",
                            "metadata": {
                                "provider": "zhipu",
                                "model": "glm-4.5-air",
                                "processing_time": 6.0,
                                "failover": {
                                    "switched": True,
                                    "last_reason_code": "rate_limit",
                                    "route": [{"from_provider": "google", "to_provider": "zhipu"}],
                                },
                            },
                        },
                    }
                ],
            }
        ]
    }

    analysis = _analyze_report(report)
    assert analysis["summary"]["stream_thinner_than_sync"] == 1
    assert analysis["findings"][0]["classification"] == "stream_thinner_than_sync"
    assert analysis["summary"]["avg_processing_time"]["sync"] == 9.0
    assert analysis["summary"]["avg_processing_time"]["stream"] == 6.0
    assert analysis["summary"]["provider_counts"]["stream"]["zhipu"] == 1
    assert analysis["summary"]["failover_reason_counts"]["rate_limit"] == 1
    assert analysis["findings"][0]["stream_failover_route"] == ["google->zhipu"]


def test_analyze_report_prefers_lifecycle_final_lengths_over_raw_stream_blob():
    report = {
        "sessions": [
            {
                "id": "product_search_audio",
                "turns": [
                    {
                        "id": "headphone_search",
                        "prompt": "Tai nghe nao dang duoc nhieu nguoi chu y?",
                        "sync": {
                            "thinking": "x" * 220,
                            "thinking_metrics": {"final_length": 220},
                            "evaluation": {"failures": []},
                            "agent_type": "product_search",
                        },
                        "stream": {
                            "thinking": "y" * 6911,
                            "thinking_metrics": {"final_length": 274},
                            "evaluation": {"failures": []},
                            "agent_type": "product_search",
                            "raw_path": "",
                        },
                    }
                ],
            }
        ]
    }

    analysis = _analyze_report(report)
    finding = analysis["findings"][0]

    assert finding["sync_thinking_len"] == 220
    assert finding["stream_thinking_len"] == 274
    assert finding["classification"] == "parity_close"
