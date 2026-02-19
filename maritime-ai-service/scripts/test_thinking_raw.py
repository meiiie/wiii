#!/usr/bin/env python3
"""
Sprint 140b: Raw SSE event debugger — see exactly what thinking events come through.

Usage:
    python scripts/test_thinking_raw.py
"""
import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8000"
API_KEY = "local-dev-key"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "X-User-ID": "test-user",
    "X-Role": "student",
}

PAYLOAD = {
    "user_id": "test-user",
    "message": "Quy tắc 15 COLREG là gì? Giải thích ngắn gọn.",
    "role": "student",
    "domain_id": "maritime",
    "session_id": f"test-thinking-{int(time.time())}",
}


def main():
    print("=" * 70)
    print("Sprint 140b: Raw SSE Event Debugger")
    print("=" * 70)
    print(f"Message: {PAYLOAD['message']}")
    print(f"Session: {PAYLOAD['session_id']}")
    print("-" * 70)

    # Counters
    event_counts: dict[str, int] = {}
    thinking_events: list[dict] = []
    status_events: list[dict] = []
    answer_chunks: list[str] = []
    all_raw_lines: list[str] = []

    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            headers=HEADERS,
            json=PAYLOAD,
        ) as response:
            if response.status_code != 200:
                print(f"ERROR: HTTP {response.status_code}")
                print(response.read().decode())
                return

            buffer = ""
            current_event = "message"

            for chunk in response.iter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        current_event = "message"
                        continue

                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        all_raw_lines.append(f"event:{current_event} data:{data_str[:200]}")
                        event_counts[current_event] = event_counts.get(current_event, 0) + 1

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = data_str

                        # Print raw event
                        if current_event == "thinking":
                            content = data.get("content", "") if isinstance(data, dict) else str(data)
                            step = data.get("step", "") if isinstance(data, dict) else ""
                            node = data.get("node", "") if isinstance(data, dict) else ""
                            preview = content[:150].replace("\n", "\\n") if content else "(empty)"
                            print(f"\n[THINKING] node={node} step={step}")
                            print(f"  content ({len(content)} chars): {preview}")
                            thinking_events.append(data if isinstance(data, dict) else {"content": data_str})

                        elif current_event == "thinking_start":
                            print(f"\n[THINKING_START] {json.dumps(data, ensure_ascii=False)}")

                        elif current_event == "thinking_end":
                            print(f"[THINKING_END] {json.dumps(data, ensure_ascii=False)}")

                        elif current_event == "thinking_delta":
                            content = data.get("content", "") if isinstance(data, dict) else str(data)
                            sys.stdout.write(f".")  # dot for each delta
                            sys.stdout.flush()

                        elif current_event == "status":
                            content = data.get("content", "") if isinstance(data, dict) else str(data)
                            node = data.get("node", "") if isinstance(data, dict) else ""
                            step = data.get("step", "") if isinstance(data, dict) else ""
                            print(f"\n[STATUS] node={node} step={step} content={content}")
                            status_events.append(data if isinstance(data, dict) else {"content": data_str})

                        elif current_event == "answer":
                            content = data.get("content", "") if isinstance(data, dict) else str(data)
                            answer_chunks.append(content)
                            sys.stdout.write(content)
                            sys.stdout.flush()

                        elif current_event == "tool_call":
                            tc = data.get("content", data) if isinstance(data, dict) else data
                            print(f"\n[TOOL_CALL] {json.dumps(tc, ensure_ascii=False)[:200]}")

                        elif current_event == "tool_result":
                            tc = data.get("content", data) if isinstance(data, dict) else data
                            print(f"[TOOL_RESULT] {json.dumps(tc, ensure_ascii=False)[:200]}")

                        elif current_event == "sources":
                            src_count = len(data.get("sources", [])) if isinstance(data, dict) else 0
                            print(f"\n[SOURCES] {src_count} source(s)")

                        elif current_event == "metadata":
                            print(f"\n[METADATA] {json.dumps(data, ensure_ascii=False)[:300]}")

                        elif current_event == "emotion":
                            print(f"\n[EMOTION] {json.dumps(data, ensure_ascii=False)[:200]}")

                        elif current_event == "domain_notice":
                            print(f"\n[DOMAIN_NOTICE] {json.dumps(data, ensure_ascii=False)[:200]}")

                        elif current_event == "done":
                            print(f"\n[DONE]")

                        elif current_event == "error":
                            print(f"\n[ERROR] {json.dumps(data, ensure_ascii=False)}")

                        else:
                            print(f"\n[{current_event.upper()}] {data_str[:200]}")

    # Summary
    print("\n")
    print("=" * 70)
    print("EVENT SUMMARY")
    print("=" * 70)
    for evt_type, count in sorted(event_counts.items()):
        print(f"  {evt_type}: {count}")

    print(f"\n  Total answer length: {sum(len(c) for c in answer_chunks)} chars")

    print(f"\n--- ALL RAW SSE LINES ({len(all_raw_lines)}) ---")
    for rl in all_raw_lines:
        print(f"  {rl}")

    if thinking_events:
        print(f"\n--- THINKING EVENTS (full content) ---")
        for i, te in enumerate(thinking_events):
            content = te.get("content", "")
            print(f"\n  [{i+1}] node={te.get('node', '?')} ({len(content)} chars):")
            # Show first 500 chars
            print(f"  {content[:500]}")
            if len(content) > 500:
                print(f"  ... ({len(content) - 500} more chars)")

            # Check for pipeline dump indicators
            if "Quá trình suy nghĩ" in content[:300]:
                print("  ⚠️  PIPELINE DUMP DETECTED — this should NOT appear!")
            if content.lstrip().startswith("[RAG Analysis]"):
                print("  ℹ️  [RAG Analysis] prefix — check if genuine thinking follows")
    else:
        print("\n  No thinking events received (expected when no native Gemini thinking)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
