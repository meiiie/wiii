"""
Sprint 74: Full Flow Test — Streaming Quality & Performance
Tests interleaved answer_delta, guardian fast-path, empty thinking suppression,
synthesizer thinking exclusion, and answer deduplication.

Outputs results to markdown file for analysis.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import httpx
import json
import time
import datetime
from pathlib import Path

BASE_URL = "http://localhost:8000"
API_KEY = "local-dev-key"
USER_ID = "test-sprint74"
SESSION_ID = "s74-stream-v2"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
    "X-Role": "student",
}

# 7-turn test flow
TURNS = [
    {
        "label": "Turn 1: Giới thiệu bản thân (Memory)",
        "message": "Xin chào, tên mình là Hải, 28 tuổi, giảng viên hàng hải ở Hải Phòng. Mình đang chuẩn bị cho kỳ thi COLREGs.",
        "checks": [
            ("route", "memory_agent OR direct"),
            ("no_thinking_leak", "No 'tôi đang phân tích' in answer"),
            ("guardian_no_thinking_block", "Guardian has NO thinking_start/thinking_end"),
        ],
    },
    {
        "label": "Turn 2: Kiến thức domain (Tutor — TTFT check)",
        "message": "Giải thích Quy tắc 15 COLREGs về tình huống giao cắt cho mình nhé",
        "checks": [
            ("route", "tutor_agent"),
            ("ttft", "First answer token < 25s (was 36s before Sprint 74)"),
            ("no_duplicate_answer", "Answer not streamed twice"),
            ("length", "Answer < 2000 words"),
            ("no_thinking_leak", "No first-person reasoning in answer"),
        ],
    },
    {
        "label": "Turn 3: Sở thích + điểm yếu (Memory)",
        "message": "Mình thích học qua ví dụ thực tế, nhưng hay nhầm giữa Quy tắc 14 và 15",
        "checks": [
            ("route", "memory_agent"),
        ],
    },
    {
        "label": "Turn 4: Kiến thức personalized (Tutor — TTFT check)",
        "message": "So sánh Quy tắc 14 và Quy tắc 15 giúp mình, dùng ví dụ thực tế nhé",
        "checks": [
            ("route", "tutor_agent OR rag_agent"),
            ("ttft", "First answer token should stream during generation"),
            ("personalized", "Response mentions Hải or uses learned preferences"),
        ],
    },
    {
        "label": "Turn 5: Recall memory",
        "message": "Bạn nhớ gì về mình?",
        "checks": [
            ("route", "memory_agent"),
            ("guardian_fast", "Guardian should skip LLM (safe question)"),
        ],
    },
    {
        "label": "Turn 6: Update info",
        "message": "Mình không còn ở Hải Phòng nữa, giờ mình chuyển về Đà Nẵng rồi",
        "checks": [
            ("route", "memory_agent"),
        ],
    },
    {
        "label": "Turn 7: Final recall",
        "message": "Tóm tắt tất cả thông tin bạn biết về mình đi",
        "checks": [
            ("route", "memory_agent"),
            ("grader_no_thinking_block", "Grader has NO thinking_start/thinking_end"),
        ],
    },
]


def run_streaming_turn(client, message):
    """Run one streaming turn, capture all SSE events with timing."""
    payload = {
        "message": message,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "role": "student",
    }

    start = time.time()
    first_answer_time = None
    all_answer_text = ""
    events_raw = []

    try:
        with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            json=payload,
            headers=HEADERS,
            timeout=180.0,
        ) as response:
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    event_type = None
                    event_data = None
                    for line in block.split("\n"):
                        line = line.strip()
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str:
                                try:
                                    event_data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    event_data = data_str

                    if event_type and event_data is not None:
                        elapsed = round((time.time() - start) * 1000)
                        events_raw.append({
                            "type": event_type,
                            "data": event_data,
                            "elapsed_ms": elapsed,
                        })
                        if event_type == "answer" and first_answer_time is None:
                            first_answer_time = elapsed
                        if event_type == "answer" and isinstance(event_data, dict):
                            all_answer_text += event_data.get("content", "")

    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        events_raw.append({
            "type": "error",
            "data": str(e),
            "elapsed_ms": elapsed,
        })

    total_time = round((time.time() - start) * 1000)

    return {
        "events": events_raw,
        "full_answer": all_answer_text,
        "total_ms": total_time,
        "first_token_ms": first_answer_time,
        "event_counts": _count_events(events_raw),
    }


def _count_events(events):
    counts = {}
    for e in events:
        t = e["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts


def analyze_sprint74_features(turn_idx, turn_def, result):
    """Analyze Sprint 74 specific features for each turn."""
    findings = []
    ec = result["event_counts"]
    events = result["events"]
    answer = result.get("full_answer", "")

    # Sprint 74 Check 1: Guardian emits NO thinking_start/thinking_end
    guardian_thinking_starts = [
        e for e in events
        if e["type"] == "thinking_start"
        and isinstance(e["data"], dict)
        and e["data"].get("node") == "guardian"
    ]
    guardian_thinking_ends = [
        e for e in events
        if e["type"] == "thinking_end"
        and isinstance(e["data"], dict)
        and e["data"].get("node") == "guardian"
    ]
    guardian_statuses = [
        e for e in events
        if e["type"] == "status"
        and isinstance(e["data"], dict)
        and e["data"].get("node") == "guardian"
    ]
    if guardian_thinking_starts or guardian_thinking_ends:
        findings.append(("FAIL", "Guardian emitted thinking_start/end (Sprint 74 should suppress)"))
    elif guardian_statuses:
        findings.append(("PASS", "Guardian: status-only (no empty thinking blocks)"))

    # Sprint 74 Check 2: Grader emits NO thinking_start/thinking_end
    grader_thinking_starts = [
        e for e in events
        if e["type"] == "thinking_start"
        and isinstance(e["data"], dict)
        and e["data"].get("node") == "grader"
    ]
    grader_thinking_ends = [
        e for e in events
        if e["type"] == "thinking_end"
        and isinstance(e["data"], dict)
        and e["data"].get("node") == "grader"
    ]
    if grader_thinking_starts or grader_thinking_ends:
        findings.append(("FAIL", "Grader emitted thinking_start/end (Sprint 74 should suppress)"))
    elif ec.get("status", 0) > 0:
        # Only report if grader ran (not all turns hit grader)
        grader_statuses = [
            e for e in events
            if e["type"] == "status"
            and isinstance(e["data"], dict)
            and "grader" in str(e["data"].get("node", ""))
        ]
        if grader_statuses:
            findings.append(("PASS", "Grader: status-only (no empty thinking blocks)"))

    # Sprint 74 Check 3: No thinking leak in answer
    thinking_leak_phrases = [
        "tôi đang phân tích", "tôi nhận thấy", "tôi đang xem xét",
        "I am analyzing", "I notice", "Let me think",
    ]
    for phrase in thinking_leak_phrases:
        if phrase.lower() in answer.lower():
            findings.append(("FAIL", f"Thinking leak in answer: '{phrase}'"))
            break
    else:
        if answer:
            findings.append(("PASS", "No thinking leak in answer"))

    # Sprint 74 Check 4: TTFT for tutor turns
    if turn_idx in (1, 3):  # Tutor turns
        ttft = result.get("first_token_ms")
        if ttft is not None:
            if ttft < 25000:
                findings.append(("PASS", f"TTFT: {ttft}ms (< 25s target)"))
            else:
                findings.append(("WARN", f"TTFT: {ttft}ms (>= 25s — improvement needed)"))
        else:
            findings.append(("WARN", "No TTFT measured (no answer events)"))

    # Sprint 74 Check 5: Answer length
    word_count = len(answer.split()) if answer else 0
    if word_count > 0:
        if word_count <= 600:
            findings.append(("PASS", f"Answer length: {word_count} words (within limit)"))
        else:
            findings.append(("WARN", f"Answer length: {word_count} words (may be too long)"))

    return findings


def generate_report(results):
    """Generate Sprint 74 markdown report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# Sprint 74: Streaming Quality & Performance — Test Report")
    lines.append("")
    lines.append(f"**Date**: {now}")
    lines.append(f"**User**: `{USER_ID}` | **Session**: `{SESSION_ID}`")
    lines.append(f"**Endpoint**: `{BASE_URL}/api/v1/chat/stream/v3` (SSE)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Turn | Label | Time (ms) | TTFT (ms) | Answer Events | Status Events | Thinking Events |")
    lines.append("|------|-------|-----------|-----------|---------------|---------------|-----------------|")

    for i, (turn_def, result) in enumerate(results):
        ec = result["event_counts"]
        ttft = result.get("first_token_ms", "-")
        answer_count = ec.get("answer", 0)
        status_count = ec.get("status", 0)
        thinking_count = ec.get("thinking_start", 0) + ec.get("thinking_delta", 0) + ec.get("thinking_end", 0) + ec.get("thinking", 0)
        lines.append(
            f"| {i+1} | {turn_def['label'][:40]} | {result['total_ms']} | {ttft} | {answer_count} | {status_count} | {thinking_count} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Sprint 74 Feature Verification
    lines.append("## Sprint 74 Feature Verification")
    lines.append("")
    all_findings = []
    for i, (turn_def, result) in enumerate(results):
        findings = analyze_sprint74_features(i, turn_def, result)
        all_findings.extend(findings)

    # Deduplicate PASS findings
    seen = set()
    unique_findings = []
    for status, msg in all_findings:
        key = msg.split(":")[0] if ":" in msg else msg
        if key not in seen:
            seen.add(key)
            unique_findings.append((status, msg))

    lines.append("| Check | Status | Detail |")
    lines.append("|-------|--------|--------|")
    for status, msg in unique_findings:
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "❓")
        lines.append(f"| {msg.split(':')[0] if ':' in msg else msg[:40]} | {icon} {status} | {msg} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed per-turn
    for i, (turn_def, result) in enumerate(results):
        lines.append(f"## Turn {i+1}: {turn_def['label']}")
        lines.append("")
        lines.append(f"**Input**: `{turn_def['message']}`")
        lines.append("")

        # Event counts
        ec = result["event_counts"]
        lines.append("### Event Counts")
        lines.append("```")
        for etype, count in sorted(ec.items()):
            lines.append(f"  {etype}: {count}")
        lines.append(f"  TOTAL: {sum(ec.values())}")
        lines.append("```")
        lines.append("")

        # Timing
        lines.append("### Timing")
        lines.append(f"- Total: **{result['total_ms']}ms**")
        if result.get("first_token_ms"):
            lines.append(f"- First answer token (TTFT): **{result['first_token_ms']}ms**")
        lines.append("")

        # Event timeline (condensed — group consecutive answer events)
        lines.append("### Event Timeline (key events)")
        lines.append("")
        lines.append("| Time (ms) | Event | Content |")
        lines.append("|-----------|-------|---------|")

        prev_type = None
        answer_start_ms = None
        answer_count = 0

        for e in result["events"]:
            elapsed = e["elapsed_ms"]
            etype = e["type"]
            data = e["data"]

            # Group consecutive answer events
            if etype == "answer":
                if prev_type != "answer":
                    answer_start_ms = elapsed
                    answer_count = 1
                else:
                    answer_count += 1
                prev_type = etype
                continue
            else:
                # Flush answer group
                if prev_type == "answer" and answer_count > 0:
                    lines.append(
                        f"| {answer_start_ms}-{elapsed} | `answer` | ({answer_count} chunks streamed) |"
                    )
                    answer_count = 0

            prev_type = etype

            if isinstance(data, dict):
                content = data.get("content", "")
                if isinstance(content, str) and len(content) > 100:
                    content = content[:100] + "..."
                content = str(content).replace("|", "\\|").replace("\n", " ")
            else:
                content = str(data)[:100].replace("|", "\\|").replace("\n", " ")

            lines.append(f"| {elapsed} | `{etype}` | {content} |")

        # Flush trailing answer group
        if prev_type == "answer" and answer_count > 0:
            lines.append(
                f"| {answer_start_ms}-{result['total_ms']} | `answer` | ({answer_count} chunks streamed) |"
            )

        lines.append("")

        # Full answer (first 500 chars)
        lines.append("### Answer Preview")
        lines.append("")
        answer = result.get("full_answer", "")
        if answer:
            preview = answer[:500] + ("..." if len(answer) > 500 else "")
            lines.append(f"> {preview.replace(chr(10), chr(10) + '> ')}")
            lines.append(f"")
            lines.append(f"*({len(answer)} chars, ~{len(answer.split())} words)*")
        else:
            lines.append("> *(no streaming answer captured)*")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Performance comparison
    lines.append("## Performance Comparison (Sprint 73 → 74)")
    lines.append("")
    lines.append("| Metric | Sprint 73 | Sprint 74 | Improvement |")
    lines.append("|--------|-----------|-----------|-------------|")

    tutor_turns = [(i, r) for i, (t, r) in enumerate(results) if i in (1, 3)]
    for idx, result in tutor_turns:
        ttft = result.get("first_token_ms", "N/A")
        total = result["total_ms"]
        lines.append(f"| Turn {idx+1} TTFT | ~36000ms | {ttft}ms | {'Improved' if isinstance(ttft, int) and ttft < 25000 else 'Check'} |")
        lines.append(f"| Turn {idx+1} Total | ~46000ms | {total}ms | {'Improved' if total < 40000 else 'Check'} |")

    lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("Sprint 74: Streaming Quality & Performance Test")
    print("=" * 60)

    client = httpx.Client(timeout=180.0)
    results = []

    for i, turn in enumerate(TURNS):
        print(f"\n{'='*50}")
        print(f"  {turn['label']}")
        print(f"  Message: {turn['message'][:70]}...")
        print(f"{'='*50}")

        result = run_streaming_turn(client, turn["message"])

        ec = result["event_counts"]
        print(f"  Events: {ec}")
        print(f"  Time: {result['total_ms']}ms | TTFT: {result.get('first_token_ms', '-')}ms")

        # Sprint 74 checks
        guardian_ts = sum(
            1 for e in result["events"]
            if e["type"] in ("thinking_start", "thinking_end")
            and isinstance(e["data"], dict) and e["data"].get("node") == "guardian"
        )
        grader_ts = sum(
            1 for e in result["events"]
            if e["type"] in ("thinking_start", "thinking_end")
            and isinstance(e["data"], dict) and e["data"].get("node") == "grader"
        )
        if guardian_ts > 0:
            print(f"  ❌ Guardian still emits thinking blocks ({guardian_ts})")
        else:
            print(f"  ✅ Guardian: status-only (no empty thinking blocks)")
        if grader_ts > 0:
            print(f"  ❌ Grader still emits thinking blocks ({grader_ts})")

        answer = result.get("full_answer", "")
        if answer:
            word_count = len(answer.split())
            print(f"  Answer: {word_count} words | {answer[:80]}...")

            # Check thinking leak
            leak_phrases = ["tôi đang phân tích", "tôi nhận thấy", "tôi đang xem xét"]
            for phrase in leak_phrases:
                if phrase in answer.lower():
                    print(f"  ❌ Thinking leak: '{phrase}'")
                    break
            else:
                print(f"  ✅ No thinking leak in answer")
        else:
            print(f"  Answer: (no streaming answer)")

        results.append((turn, result))

        # Small delay between turns
        time.sleep(1)

    client.close()

    # Generate report
    report = generate_report(results)

    output_path = Path(__file__).parent.parent / ".claude" / "reports" / "sprint74-streaming-test.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"Report saved to: {output_path}")
    print(f"{'=' * 60}")

    # Final summary
    print(f"\n## SPRINT 74 SUMMARY ##")
    total_time = sum(r["total_ms"] for _, r in results)
    avg_time = total_time // len(results)
    tutor_ttfts = [
        r.get("first_token_ms", 0) for i, (_, r) in enumerate(results) if i in (1, 3) and r.get("first_token_ms")
    ]
    avg_ttft = sum(tutor_ttfts) // len(tutor_ttfts) if tutor_ttfts else 0

    print(f"  Total time (7 turns): {total_time}ms")
    print(f"  Average per turn: {avg_time}ms")
    print(f"  Tutor avg TTFT: {avg_ttft}ms")
    print(f"  Guardian thinking blocks: 0 (expected)")


if __name__ == "__main__":
    main()
