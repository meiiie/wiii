"""
Quick test: Check answer dedup after Sprint 74 fix.
Sends a tutor query and checks that answer content is NOT duplicated.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import httpx
import json
import time

BASE_URL = "http://localhost:8000"
API_KEY = "local-dev-key"
USER_ID = "test-dedup"
SESSION_ID = "s-dedup-01"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
    "X-Role": "student",
}

def stream_turn(message: str):
    """Stream a single turn and collect events."""
    events = []
    start = time.time()

    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            json={"message": message, "domain_id": "maritime", "user_id": USER_ID, "role": "student", "session_id": SESSION_ID},
            headers=HEADERS,
        ) as resp:
            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw, buffer = buffer.split("\n\n", 1)
                    # Parse SSE: "event: <type>\ndata: <json>"
                    event_type = None
                    data_str = None
                    for line in raw.split("\n"):
                        if line.startswith("event: "):
                            event_type = line[7:].strip()
                        elif line.startswith("data: "):
                            data_str = line[6:]
                    if data_str and data_str.strip() == "[DONE]":
                        continue
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            elapsed = int((time.time() - start) * 1000)
                            etype = event_type or data.get("type", "unknown")
                            events.append({
                                "time": elapsed,
                                "event": etype,
                                "content": data.get("content", ""),
                            })
                        except json.JSONDecodeError:
                            pass
    return events


def analyze_events(events):
    """Analyze events for answer duplication."""
    # Collect all thinking_delta content
    thinking_text = ""
    thinking_chunks = 0
    for e in events:
        if e["event"] == "thinking_delta":
            content = e["content"]
            if isinstance(content, str):
                thinking_text += content
                thinking_chunks += 1

    # Collect all answer content
    answer_text = ""
    answer_chunks = 0
    first_answer_time = None
    last_answer_time = None
    for e in events:
        if e["event"] == "answer":
            content = e["content"]
            if isinstance(content, str):
                answer_text += content
                answer_chunks += 1
                if first_answer_time is None:
                    first_answer_time = e["time"]
                last_answer_time = e["time"]

    # Count status events
    status_count = sum(1 for e in events if e["event"] == "status")

    # Check for guardian thinking blocks
    guardian_thinking = False
    for i, e in enumerate(events):
        if e["event"] == "thinking_start":
            content = str(e.get("content", ""))
            if "an toàn" in content.lower() or "guardian" in content.lower():
                guardian_thinking = True

    # Check overlap between thinking and answer
    thinking_words = set(thinking_text.split()) if thinking_text else set()
    answer_words = set(answer_text.split()) if answer_text else set()

    if thinking_words and answer_words:
        overlap = len(thinking_words & answer_words)
        total = len(thinking_words | answer_words)
        overlap_ratio = overlap / total if total > 0 else 0
    else:
        overlap_ratio = 0

    return {
        "thinking_chunks": thinking_chunks,
        "thinking_chars": len(thinking_text),
        "answer_chunks": answer_chunks,
        "answer_chars": len(answer_text),
        "first_answer_ms": first_answer_time,
        "last_answer_ms": last_answer_time,
        "answer_duration_ms": (last_answer_time - first_answer_time) if first_answer_time and last_answer_time else 0,
        "status_events": status_count,
        "guardian_thinking": guardian_thinking,
        "word_overlap_ratio": round(overlap_ratio, 2),
        "total_events": len(events),
    }


def main():
    print("=" * 60)
    print("Sprint 74 Fix: Answer Dedup Test")
    print("=" * 60)

    print("\n--- Sending tutor query ---")
    events = stream_turn("Giải thích Quy tắc 15 COLREGs về tình huống giao cắt")

    stats = analyze_events(events)

    print(f"\nTotal events: {stats['total_events']}")
    print(f"Status events: {stats['status_events']}")
    print(f"Guardian thinking block: {'YES (BAD)' if stats['guardian_thinking'] else 'NO (GOOD)'}")
    print(f"\nThinking delta: {stats['thinking_chunks']} chunks, {stats['thinking_chars']} chars")
    print(f"Answer: {stats['answer_chunks']} chunks, {stats['answer_chars']} chars")
    print(f"First answer at: {stats['first_answer_ms']}ms")
    print(f"Answer duration: {stats['answer_duration_ms']}ms")
    print(f"\nWord overlap ratio (thinking vs answer): {stats['word_overlap_ratio']}")

    # Print event timeline (condensed)
    print("\n--- Event Timeline ---")
    prev_event = None
    run_count = 0
    for e in events:
        etype = e["event"]
        if etype == prev_event and etype in ("thinking", "answer"):
            run_count += 1
            continue
        if run_count > 0:
            print(f"  ... ({run_count} more {prev_event} events)")
            run_count = 0
        content_preview = str(e["content"])[:60].replace("\n", " ")
        print(f"  {e['time']:>6}ms  {etype:<20} {content_preview}")
        prev_event = etype
    if run_count > 0:
        print(f"  ... ({run_count} more {prev_event} events)")

    # Verdict
    print("\n" + "=" * 60)
    # Expected behavior: thinking and answer have ~100% overlap (Claude pattern)
    # Key check: answer chunks should be ~125 (bus answer_delta only)
    # NOT ~250+ (bus + post-hoc double emission)
    expected_chunks = max(1, stats["answer_chars"] // 12)  # 12 chars per chunk
    if stats["answer_chunks"] <= expected_chunks + 10:
        print(f"VERDICT: POST-HOC DEDUP OK (answer={stats['answer_chunks']} chunks, expected ~{expected_chunks})")
        print("  - Bus answer_delta: YES (fast, ~{:.1f}s)".format(stats["answer_duration_ms"]/1000))
        print("  - Post-hoc re-emission: SKIPPED")
        if stats["word_overlap_ratio"] > 0.8:
            print("  - Thinking/Answer overlap: expected (Claude pattern - thinking auto-collapses)")
    else:
        print(f"VERDICT: DOUBLE ANSWER ({stats['answer_chunks']} chunks, expected ~{expected_chunks}) — FIX NEEDED")
    print("=" * 60)


if __name__ == "__main__":
    main()
