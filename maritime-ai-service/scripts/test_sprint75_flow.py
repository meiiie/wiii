"""
Sprint 75: Comprehensive Flow Test — Real API with Interleaved Thinking Analysis.

Tests 5 diverse turns:
1. Memory (personal info) — should route to memory agent
2. Tutor (complex learning) — should route to tutor, show interleaved thinking
3. RAG (factual lookup) — should route to RAG
4. Follow-up (tutor) — complex comparison question
5. Social (greeting) — should route to direct

For each turn, analyzes:
- Event timeline (what events appear and when)
- Interleaved thinking quality (thinking_delta count, content)
- Answer quality (length, Vietnamese)
- Pipeline stages visible to user
- Latency breakdown
"""
import httpx
import json
import time
import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"

API_URL = "http://localhost:8000/api/v1/chat/stream/v3"
API_KEY = "local-dev-key"
USER_ID = "flow-test-user"
SESSION_ID = "flow-test-sess-75"

QUESTIONS = [
    {
        "label": "Q1: Memory",
        "message": "Toi ten la Minh, toi la sinh vien nam 3 nganh hang hai",
        "expect_agent": "memory",
    },
    {
        "label": "Q2: Tutor (complex)",
        "message": "Hay giang day chi tiet ve quy tac 5 cua COLREGs, giai thich y nghia thuc te va cho vi du cu the khi ap dung tren bien",
        "expect_agent": "tutor",
    },
    {
        "label": "Q3: RAG (factual)",
        "message": "Noi dung chinh cua quy tac 8 COLREGs la gi?",
        "expect_agent": "rag",
    },
    {
        "label": "Q4: Tutor (comparison)",
        "message": "So sanh chi tiet quy tac 14 va quy tac 15 COLREGs, khi nao ap dung tung quy tac va cho vi du cu the",
        "expect_agent": "tutor",
    },
    {
        "label": "Q5: Social",
        "message": "Cam on ban nhieu nhe!",
        "expect_agent": "direct",
    },
]


def _safe_print(text):
    """Print with UTF-8 encoding for Windows."""
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


async def run_turn(client, question, turn_num):
    """Run a single turn and analyze the response."""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "X-User-ID": USER_ID,
        "X-Session-ID": SESSION_ID,
        "X-Role": "student",
    }
    body = {
        "message": question["message"],
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "role": "student",
    }

    # Tracking
    events = {}
    timeline = []
    thinking_delta_chars = 0
    thinking_delta_count = 0
    answer_chars = 0
    answer_count = 0
    answer_text = ""
    thinking_text = ""
    current_event = None
    first_thinking_delta_time = None
    first_answer_time = None
    tool_calls = []
    statuses = []

    start = time.time()

    try:
        async with client.stream("POST", API_URL, json=body, headers=headers) as resp:
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    events[current_event] = events.get(current_event, 0) + 1
                    elapsed = time.time() - start
                    timeline.append((elapsed, current_event))
                elif line.startswith("data:") and current_event:
                    raw_data = line[5:].strip()
                    try:
                        data = json.loads(raw_data)
                        content = data.get("content", "")

                        if current_event == "thinking_delta":
                            thinking_delta_chars += len(content)
                            thinking_delta_count += 1
                            thinking_text += content
                            if first_thinking_delta_time is None:
                                first_thinking_delta_time = time.time() - start
                        elif current_event == "answer":
                            answer_chars += len(content)
                            answer_count += 1
                            answer_text += content
                            if first_answer_time is None:
                                first_answer_time = time.time() - start
                        elif current_event == "status":
                            statuses.append(content)
                        elif current_event == "tool_call":
                            tool_calls.append(content if isinstance(content, dict) else {"name": str(content)})
                        elif current_event == "thinking":
                            thinking_text += content
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        _safe_print(f"  ERROR: {e}")
        return None

    total_time = time.time() - start

    # Analysis
    _safe_print(f"\n{'='*70}")
    _safe_print(f"  {question['label']} (expected: {question['expect_agent']})")
    _safe_print(f"{'='*70}")
    _safe_print(f"  Message: {question['message'][:80]}...")
    _safe_print(f"  Total time: {total_time:.1f}s")

    # Timing
    _safe_print(f"\n  TIMING:")
    if first_thinking_delta_time:
        _safe_print(f"    First thinking_delta: {first_thinking_delta_time:.1f}s (Time-to-First-Think)")
    if first_answer_time:
        _safe_print(f"    First answer:         {first_answer_time:.1f}s (Time-to-First-Answer)")

    # Event counts
    _safe_print(f"\n  EVENTS:")
    for k in sorted(events.keys()):
        _safe_print(f"    {k}: {events[k]}")

    # Pipeline stages (statuses)
    _safe_print(f"\n  PIPELINE STAGES:")
    for s in statuses:
        _safe_print(f"    > {s}")

    # Tool calls
    if tool_calls:
        _safe_print(f"\n  TOOL CALLS:")
        for tc in tool_calls:
            name = tc.get("name", "unknown") if isinstance(tc, dict) else str(tc)
            _safe_print(f"    > {name}")

    # Interleaved thinking analysis
    _safe_print(f"\n  INTERLEAVED THINKING:")
    thinking_starts = events.get("thinking_start", 0)
    thinking_ends = events.get("thinking_end", 0)
    _safe_print(f"    thinking_start/end pairs: {thinking_starts}/{thinking_ends}")
    _safe_print(f"    thinking_delta events: {thinking_delta_count}")
    _safe_print(f"    thinking_delta chars: {thinking_delta_chars}")
    if thinking_delta_count > 0:
        _safe_print(f"    thinking preview: {thinking_text[:150]}...")
        _safe_print(f"    VERDICT: INTERLEAVED THINKING WORKING")
    elif events.get("thinking", 0) > 0:
        _safe_print(f"    thinking (bulk) chars: {len(thinking_text)}")
        _safe_print(f"    VERDICT: BULK THINKING (not interleaved)")
    else:
        _safe_print(f"    VERDICT: NO THINKING CONTENT")

    # Answer analysis
    _safe_print(f"\n  ANSWER:")
    _safe_print(f"    answer events: {answer_count}")
    _safe_print(f"    answer chars: {answer_chars}")
    if answer_text:
        _safe_print(f"    preview: {answer_text[:200]}...")

    # Grader check (Sprint 75: should NOT appear for tutor)
    has_grader = any("grader" in s.lower() or "chat luong" in s.lower() for s in statuses)
    if question["expect_agent"] == "tutor":
        if has_grader:
            _safe_print(f"\n  WARNING: Grader ran for tutor turn! Sprint 75 skip may not be working")
        else:
            _safe_print(f"\n  SPRINT 75: Tutor skip grader CONFIRMED (no grader status)")

    # Professional quality check
    _safe_print(f"\n  QUALITY CHECK:")
    issues = []
    if total_time > 30 and question["expect_agent"] in ("tutor", "rag"):
        issues.append(f"Slow response ({total_time:.0f}s)")
    if answer_chars < 50 and question["expect_agent"] in ("tutor", "rag"):
        issues.append(f"Short answer ({answer_chars} chars)")
    if thinking_starts != thinking_ends:
        issues.append(f"Unmatched thinking blocks ({thinking_starts} starts, {thinking_ends} ends)")
    if events.get("done", 0) != 1:
        issues.append(f"Missing or duplicate done event ({events.get('done', 0)})")
    if not events.get("metadata"):
        issues.append("Missing metadata event")

    if issues:
        for issue in issues:
            _safe_print(f"    ISSUE: {issue}")
    else:
        _safe_print(f"    ALL CHECKS PASSED")

    return {
        "label": question["label"],
        "total_time": total_time,
        "first_think": first_thinking_delta_time,
        "first_answer": first_answer_time,
        "thinking_delta_count": thinking_delta_count,
        "thinking_delta_chars": thinking_delta_chars,
        "answer_chars": answer_chars,
        "has_grader": has_grader,
        "events": events,
    }


async def main():
    _safe_print("=" * 70)
    _safe_print("  Sprint 75: Comprehensive Flow Test")
    _safe_print("  API: " + API_URL)
    _safe_print("  User: " + USER_ID)
    _safe_print("=" * 70)

    results = []
    async with httpx.AsyncClient(timeout=180) as client:
        for i, q in enumerate(QUESTIONS):
            result = await run_turn(client, q, i + 1)
            if result:
                results.append(result)
            # Small gap between turns
            await asyncio.sleep(1)

    # Summary table
    _safe_print(f"\n{'='*70}")
    _safe_print(f"  SUMMARY")
    _safe_print(f"{'='*70}")
    _safe_print(f"  {'Turn':<25} {'Time':>6} {'TTFT':>6} {'TTFA':>6} {'Think':>6} {'Answer':>7} {'Grader':>7}")
    _safe_print(f"  {'-'*25} {'-----':>6} {'-----':>6} {'-----':>6} {'-----':>6} {'------':>7} {'------':>7}")

    for r in results:
        ttft = f"{r['first_think']:.1f}s" if r['first_think'] else "—"
        ttfa = f"{r['first_answer']:.1f}s" if r['first_answer'] else "—"
        think = f"{r['thinking_delta_chars']}" if r['thinking_delta_chars'] > 0 else "—"
        grader = "YES" if r['has_grader'] else "NO"
        _safe_print(
            f"  {r['label']:<25} {r['total_time']:>5.1f}s {ttft:>6} {ttfa:>6} {think:>6} {r['answer_chars']:>6}c {grader:>7}"
        )

    total = sum(r['total_time'] for r in results)
    _safe_print(f"\n  Total flow time: {total:.1f}s")

    # Professional verdict
    _safe_print(f"\n  PROFESSIONAL FLOW VERDICT:")
    all_done = all(r['events'].get('done', 0) == 1 for r in results)
    all_metadata = all(r['events'].get('metadata', 0) >= 1 for r in results)
    tutor_results = [r for r in results if "Tutor" in r['label']]
    tutor_has_thinking = all(r['thinking_delta_chars'] > 0 for r in tutor_results) if tutor_results else True
    tutor_no_grader = all(not r['has_grader'] for r in tutor_results) if tutor_results else True

    checks = [
        ("All turns complete (done event)", all_done),
        ("All turns have metadata", all_metadata),
        ("Tutor turns have interleaved thinking", tutor_has_thinking),
        ("Tutor turns skip grader (Sprint 75)", tutor_no_grader),
    ]

    for label, passed in checks:
        icon = "PASS" if passed else "FAIL"
        _safe_print(f"    [{icon}] {label}")


if __name__ == "__main__":
    asyncio.run(main())
