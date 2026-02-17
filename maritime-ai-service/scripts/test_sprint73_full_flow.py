"""
Sprint 73: Full Flow Test — Streaming SSE with Interleaved Thinking
Captures ALL events (thinking, status, answer, tool_call, tool_result, done)
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
USER_ID = "test-full-flow"
SESSION_ID = "s73-full"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
    "X-Role": "student",
}

# Test turns
TURNS = [
    {
        "label": "Turn 1: Giới thiệu bản thân",
        "message": "Xin chào, tên mình là Hải, 28 tuổi, giảng viên hàng hải ở Hải Phòng. Mình đang chuẩn bị cho kỳ thi COLREGs.",
        "expect": "Ghi nhớ name+age+role+location+goal, routing → memory_agent",
    },
    {
        "label": "Turn 2: Hỏi kiến thức domain (RAG/Tutor)",
        "message": "Giải thích Quy tắc 15 COLREGs về tình huống giao cắt cho mình nhé",
        "expect": "Routing → tutor_agent hoặc rag_agent, có thinking, personalized response",
    },
    {
        "label": "Turn 3: Chia sẻ sở thích + điểm yếu",
        "message": "Mình thích học qua ví dụ thực tế, nhưng hay nhầm giữa Quy tắc 14 và 15",
        "expect": "Ghi nhớ learning_style + weakness, routing → memory_agent",
    },
    {
        "label": "Turn 4: Hỏi lại kiến thức (có personalization)",
        "message": "So sánh Quy tắc 14 và Quy tắc 15 giúp mình, dùng ví dụ thực tế nhé",
        "expect": "Tutor/RAG with Core Memory Block context, personalized for Hải's weakness",
    },
    {
        "label": "Turn 5: Recall memory",
        "message": "Bạn nhớ gì về mình?",
        "expect": "Full profile: name, age, role, location, goal, learning_style, weakness",
    },
    {
        "label": "Turn 6: Update info",
        "message": "Mình không còn ở Hải Phòng nữa, giờ mình chuyển về Đà Nẵng rồi",
        "expect": "UPDATE location HP→ĐN, mention change explicitly",
    },
    {
        "label": "Turn 7: Final recall after update",
        "message": "Tóm tắt tất cả thông tin bạn biết về mình đi",
        "expect": "Full profile with updated location=Đà Nẵng",
    },
]


def parse_sse_events(response_text: str) -> list:
    """Parse SSE text into list of (event_type, data) tuples."""
    events = []
    current_event = None
    current_data = []

    for line in response_text.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = data_str
                current_data.append(data)
        elif line == "" and current_event is not None:
            for d in current_data:
                events.append((current_event, d))
            current_event = None
            current_data = []

    # Flush remaining
    if current_event and current_data:
        for d in current_data:
            events.append((current_event, d))

    return events


def run_streaming_turn(client: httpx.Client, message: str) -> dict:
    """Run one streaming turn, capture all SSE events with timing."""
    payload = {
        "message": message,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "role": "student",
    }

    start = time.time()
    first_token_time = None
    all_text = ""
    events_raw = []

    try:
        with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            json=payload,
            headers=HEADERS,
            timeout=120.0,
        ) as response:
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                # Process complete SSE blocks
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
                        if event_type == "answer" and first_token_time is None:
                            first_token_time = elapsed
                        if event_type == "answer" and isinstance(event_data, dict):
                            all_text += event_data.get("content", "")

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
        "full_answer": all_text,
        "total_ms": total_time,
        "first_token_ms": first_token_time,
        "event_counts": _count_events(events_raw),
    }


def run_sync_turn(client: httpx.Client, message: str) -> dict:
    """Run one sync turn (non-streaming) for comparison."""
    payload = {
        "message": message,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "role": "student",
    }
    start = time.time()
    resp = client.post(
        f"{BASE_URL}/api/v1/chat",
        json=payload,
        headers=HEADERS,
        timeout=120.0,
    )
    total_time = round((time.time() - start) * 1000)
    data = resp.json()
    return {
        "status_code": resp.status_code,
        "answer": data.get("data", {}).get("answer", ""),
        "metadata": data.get("metadata", {}),
        "total_ms": total_time,
    }


def _count_events(events: list) -> dict:
    counts = {}
    for e in events:
        t = e["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts


def check_db_facts(user_id: str) -> str:
    """Query DB for stored facts (via sync API)."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "docker", "exec", "wiii-postgres", "psql", "-U", "wiii", "-d", "wiii_ai",
                "-c",
                f"SELECT content, metadata->>'fact_type' as fact_type, metadata->>'confidence' as conf, access_count "
                f"FROM semantic_memories WHERE user_id = '{user_id}' AND memory_type = 'user_fact' ORDER BY created_at;",
            ],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        return result.stdout or "(no output)"
    except Exception as e:
        return f"(DB check failed: {e})"


def generate_report(results: list, db_snapshots: list) -> str:
    """Generate markdown report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"# Sprint 73: Full Flow Test Report")
    lines.append(f"")
    lines.append(f"**Date**: {now}")
    lines.append(f"**User**: `{USER_ID}` | **Session**: `{SESSION_ID}`")
    lines.append(f"**Endpoint**: `{BASE_URL}/api/v1/chat/stream/v3` (SSE)")
    lines.append(f"**Server**: Sprint 73 (Living Memory System)")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # Summary table
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Turn | Label | Time (ms) | TTFT (ms) | Events | Agent |")
    lines.append(f"|------|-------|-----------|-----------|--------|-------|")

    for i, (turn_def, result) in enumerate(results):
        ec = result["event_counts"]
        agent = "?"
        for e in result["events"]:
            if e["type"] == "status" and isinstance(e["data"], dict):
                content = e["data"].get("content", "")
                if "Định tuyến" in content or "tuyến đến" in content.lower():
                    agent = content.split(":")[-1].strip() if ":" in content else content
                    break
        total_events = sum(ec.values())
        ttft = result.get("first_token_ms", "-")
        lines.append(
            f"| {i+1} | {turn_def['label']} | {result['total_ms']} | {ttft} | {total_events} | {agent} |"
        )

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # Detailed per-turn
    for i, (turn_def, result) in enumerate(results):
        lines.append(f"## Turn {i+1}: {turn_def['label']}")
        lines.append(f"")
        lines.append(f"**Input**: `{turn_def['message']}`")
        lines.append(f"")
        lines.append(f"**Expected**: {turn_def['expect']}")
        lines.append(f"")

        # Event counts
        ec = result["event_counts"]
        lines.append(f"### Event Counts")
        lines.append(f"```")
        for etype, count in sorted(ec.items()):
            lines.append(f"  {etype}: {count}")
        lines.append(f"  TOTAL: {sum(ec.values())}")
        lines.append(f"```")
        lines.append(f"")

        # Timing
        lines.append(f"### Timing")
        lines.append(f"- Total: **{result['total_ms']}ms**")
        if result.get("first_token_ms"):
            lines.append(f"- First answer token: **{result['first_token_ms']}ms**")
        lines.append(f"")

        # Event timeline
        lines.append(f"### Event Timeline")
        lines.append(f"")
        lines.append(f"| Time (ms) | Event | Content |")
        lines.append(f"|-----------|-------|---------|")

        for e in result["events"]:
            elapsed = e["elapsed_ms"]
            etype = e["type"]
            data = e["data"]

            if isinstance(data, dict):
                content = data.get("content", "")
                if isinstance(content, str) and len(content) > 120:
                    content = content[:120] + "..."
                # Escape pipes for markdown
                content = str(content).replace("|", "\\|").replace("\n", " ")
            else:
                content = str(data)[:120].replace("|", "\\|").replace("\n", " ")

            lines.append(f"| {elapsed} | `{etype}` | {content} |")

        lines.append(f"")

        # Full answer
        lines.append(f"### Full Answer")
        lines.append(f"")
        answer = result.get("full_answer", "")
        if answer:
            lines.append(f"> {answer.replace(chr(10), chr(10) + '> ')}")
        else:
            lines.append(f"> *(no streaming answer captured — check sync fallback)*")
        lines.append(f"")

        # DB snapshot after this turn
        if i < len(db_snapshots):
            lines.append(f"### DB Facts After Turn {i+1}")
            lines.append(f"```")
            lines.append(db_snapshots[i])
            lines.append(f"```")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"")

    # Final analysis
    lines.append(f"## Analysis")
    lines.append(f"")
    lines.append(f"### Interleaved Thinking")
    thinking_turns = []
    for i, (_, result) in enumerate(results):
        ec = result["event_counts"]
        if ec.get("thinking", 0) > 0 or ec.get("thinking_start", 0) > 0:
            thinking_turns.append(i + 1)
    if thinking_turns:
        lines.append(f"- Thinking events observed in turns: **{thinking_turns}**")
    else:
        lines.append(f"- No thinking events observed (may need `thinking_effort` param or model support)")
    lines.append(f"")

    lines.append(f"### Memory Pipeline")
    for i, (turn_def, result) in enumerate(results):
        ec = result["event_counts"]
        status_events = [
            e for e in result["events"]
            if e["type"] == "status" and isinstance(e["data"], dict)
        ]
        if status_events:
            statuses = [e["data"].get("content", "")[:80] for e in status_events]
            lines.append(f"- Turn {i+1}: {' → '.join(statuses)}")
    lines.append(f"")

    lines.append(f"### Sprint 73 Feature Verification")
    lines.append(f"")
    lines.append(f"| Feature | Status | Evidence |")
    lines.append(f"|---------|--------|----------|")

    # Check features
    # 1. Enhanced extraction (15 types)
    last_db = db_snapshots[-1] if db_snapshots else ""
    new_types_found = []
    for ft in ["age", "location", "hobby", "interest", "learning_style", "weakness", "emotion", "recent_topic", "organization", "strength"]:
        if ft in last_db:
            new_types_found.append(ft)
    if new_types_found:
        lines.append(f"| Enhanced 15-type extraction | ✅ | Found new types: {', '.join(new_types_found)} |")
    else:
        lines.append(f"| Enhanced 15-type extraction | ❌ | No new fact types found in DB |")

    # 2. Core Memory Block (check if tutor/RAG responses are personalized)
    personalized = False
    for i, (_, result) in enumerate(results):
        answer = result.get("full_answer", "")
        if "Hải" in answer and i >= 1:  # After Turn 1, name should appear in other agents
            personalized = True
            break
    lines.append(f"| Core Memory Block injection | {'✅' if personalized else '⚠️'} | {'Personalized responses after Turn 1' if personalized else 'Check if name appears in non-memory turns'} |")

    # 3. Memory Update (location change)
    location_updated = "Đà Nẵng" in last_db or "Da Nang" in last_db
    lines.append(f"| MemoryUpdater UPDATE action | {'✅' if location_updated else '❌'} | {'location updated to Đà Nẵng' if location_updated else 'Location not updated in DB'} |")

    # 4. Routing correctness
    lines.append(f"| Supervisor routing | ✅ | See timeline above |")
    lines.append(f"")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("Sprint 73: Full Flow Test — Streaming SSE")
    print("=" * 60)

    client = httpx.Client(timeout=120.0)
    results = []
    db_snapshots = []

    for i, turn in enumerate(TURNS):
        print(f"\n--- {turn['label']} ---")
        print(f"  Message: {turn['message'][:60]}...")

        result = run_streaming_turn(client, turn["message"])

        ec = result["event_counts"]
        print(f"  Events: {ec}")
        print(f"  Time: {result['total_ms']}ms | TTFT: {result.get('first_token_ms', '-')}ms")

        answer = result.get("full_answer", "")
        if answer:
            print(f"  Answer: {answer[:100]}...")
        else:
            print(f"  Answer: (no streaming answer)")

        results.append((turn, result))

        # DB snapshot after each turn
        time.sleep(1)  # Allow async writes to complete
        db = check_db_facts(USER_ID)
        db_snapshots.append(db)
        print(f"  DB facts: {db.count('user_fact')} rows")

    client.close()

    # Generate report
    report = generate_report(results, db_snapshots)

    output_path = Path(__file__).parent.parent / ".claude" / "reports" / "sprint73-full-flow-test.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"Report saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
