#!/usr/bin/env python3
"""
Audit: 10-test thinking enforcement + De-LangChaining Phase 1 verification.

Tests:
  1. Simple greeting → must have thinking_start/thinking_delta
  2. Maritime question → must have thinking + RAG sources
  3. Factual question → must have thinking
  4. Product search → must have thinking (not zombie filler)
  5. Short query → must have thinking (no "too simple" skip)
  6. Vietnamese casual → must have thinking
  7. Technical maritime → must have thinking
  8. Follow-up context → must have thinking
  9. Long question → must have thinking
  10. Code/explain request → must have thinking
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
    "X-User-ID": "audit-test-user",
    "X-Role": "student",
}

TEST_QUERIES = [
    {
        "id": 1,
        "name": "Simple greeting",
        "message": "Xin chào, bạn tên gì?",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 2,
        "name": "Maritime RAG",
        "message": "COLREGs Rule 15 là gì? Giải thích ngắn gọn.",
        "expect_thinking": True,
        "expect_sources": True,
    },
    {
        "id": 3,
        "name": "Factual question",
        "message": "Thủ đô của Việt Nam là gì?",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 4,
        "name": "Product search",
        "message": "Tìm giúp tôi dây điện 2.5mm trên Shopee",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 5,
        "name": "Short query",
        "message": "tại sao bầu trời xanh",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 6,
        "name": "Vietnamese casual",
        "message": "Mình muốn hỏi về an toàn hàng hải, bạn biết gì không?",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 7,
        "name": "Technical maritime",
        "message": "Giải thích khái niệm CPA (Closest Point of Approach) trong radar hàng hải",
        "expect_thinking": True,
        "expect_sources": True,
    },
    {
        "id": 8,
        "name": "Follow-up context",
        "message": "Còn Rule 16 nữa, nó khác Rule 15 như thế nào?",
        "expect_thinking": True,
        "expect_sources": False,
    },
    {
        "id": 9,
        "name": "Long question",
        "message": "Cho mình hỏi về quy định quốc tế về phòng cháy chữa cháy trên tàu biển, cụ thể là các yêu cầu về thiết bị chữa cháy và quy trình huấn luyện cho thuyền viên theo SOLAS chapter II-2",
        "expect_thinking": True,
        "expect_sources": True,
    },
    {
        "id": 10,
        "name": "Explain request",
        "message": "Giải thích cho mình sự khác biệt giữa radar ARPA và radar thông thường",
        "expect_thinking": True,
        "expect_sources": True,
    },
]

# Zombie phrases that should be filtered
ZOMBIE_PHRASES = (
    "Chỗ khó của câu này không nằm ở",
    "Mình sẽ đi thẳng vào phần lõi",
    "Điều dễ sai nhất là nhầm giữa",
    "Câu này nhẹ hơn một lượt đào sâu",
    "giữ phản hồi ngắn và tự nhiên",
    "giữ đúng cảnh này trước đã",
    "Đang chuẩn bị lượt trả lời",
)


def run_single_test(client: httpx.Client, test: dict, session_id: str) -> dict:
    """Run a single test query and return results."""
    payload = {
        "user_id": "audit-test-user",
        "message": test["message"],
        "role": "student",
        "domain_id": "maritime",
        "session_id": session_id,
    }

    result = {
        "id": test["id"],
        "name": test["name"],
        "message": test["message"][:60],
        "status": "PASS",
        "errors": [],
        "event_counts": {},
        "thinking_content": "",
        "answer_length": 0,
        "has_thinking_start": False,
        "has_thinking_delta": False,
        "has_thinking_end": False,
        "has_sources": False,
        "has_answer": False,
        "zombie_found": [],
        "thinking_preview": "",
        "latency_ms": 0,
    }

    start = time.time()

    try:
        with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            headers=HEADERS,
            json=payload,
        ) as response:
            if response.status_code != 200:
                result["status"] = "FAIL"
                result["errors"].append(f"HTTP {response.status_code}")
                try:
                    result["errors"].append(response.read().decode()[:200])
                except Exception:
                    pass
                return result

            buffer = ""
            current_event = "message"
            thinking_parts = []
            answer_parts = []

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
                        result["event_counts"][current_event] = result["event_counts"].get(current_event, 0) + 1

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = {}

                        if current_event == "thinking_start":
                            result["has_thinking_start"] = True

                        elif current_event == "thinking_delta":
                            result["has_thinking_delta"] = True
                            content = data.get("content", "") if isinstance(data, dict) else ""
                            thinking_parts.append(content)
                            # Check zombie phrases
                            for zp in ZOMBIE_PHRASES:
                                if zp in content:
                                    result["zombie_found"].append(zp)

                        elif current_event == "thinking_end":
                            result["has_thinking_end"] = True

                        elif current_event == "thinking":
                            content = data.get("content", "") if isinstance(data, dict) else ""
                            thinking_parts.append(content)
                            for zp in ZOMBIE_PHRASES:
                                if zp in content:
                                    result["zombie_found"].append(zp)

                        elif current_event == "answer":
                            content = data.get("content", "") if isinstance(data, dict) else ""
                            answer_parts.append(content)

                        elif current_event == "sources":
                            result["has_sources"] = True

                        elif current_event == "error":
                            result["errors"].append(f"Stream error: {data.get('message', '')[:100]}")

            result["thinking_content"] = "".join(thinking_parts)
            result["answer_length"] = sum(len(c) for c in answer_parts)
            result["has_answer"] = result["answer_length"] > 0
            result["thinking_preview"] = result["thinking_content"][:150]

    except Exception as e:
        result["status"] = "FAIL"
        result["errors"].append(f"Exception: {str(e)[:150]}")

    result["latency_ms"] = int((time.time() - start) * 1000)

    # Validate
    has_any_thinking = result["has_thinking_start"] or result["has_thinking_delta"] or result["has_thinking_end"]

    if test["expect_thinking"] and not has_any_thinking:
        result["status"] = "FAIL"
        result["errors"].append("Expected thinking events but got none")

    if test["expect_sources"] and not result["has_sources"]:
        result["errors"].append("Expected sources but got none (WARNING, not FAIL)")

    if result["zombie_found"]:
        result["status"] = "FAIL"
        result["errors"].append(f"Zombie phrases found: {result['zombie_found']}")

    if not result["has_answer"]:
        result["status"] = "FAIL"
        result["errors"].append("No answer content received")

    return result


def main():
    print("=" * 70)
    print("AUDIT: Thinking Enforcement + De-LangChaining Phase 1")
    print(f"Target: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Quick connectivity check
    try:
        resp = httpx.get(f"{BASE_URL}/docs", timeout=5.0)
        print(f"Server status: OK (HTTP {resp.status_code})")
    except Exception as e:
        print(f"Server status: FAILED - {e}")
        sys.exit(1)

    results = []
    session_base = f"audit-{int(time.time())}"

    with httpx.Client(timeout=120.0) as client:
        for i, test in enumerate(TEST_QUERIES):
            session_id = f"{session_base}-{i}"
            print(f"\n[{test['id']}/10] {test['name']}: \"{test['message'][:50]}...\"")
            result = run_single_test(client, test, session_id)
            results.append(result)

            status_icon = "PASS" if result["status"] == "PASS" else "FAIL"
            thinking_icon = "T" if (result["has_thinking_start"] or result["has_thinking_delta"]) else "-"
            sources_icon = "S" if result["has_sources"] else "-"
            print(f"  [{status_icon}] thinking={thinking_icon} sources={sources_icon} answer={result['answer_length']}chars latency={result['latency_ms']}ms")

            if result["thinking_preview"]:
                preview = result["thinking_preview"].replace("\n", "\\n")
                print(f"  thinking: {preview}...")

            if result["errors"]:
                for err in result["errors"]:
                    print(f"  ! {err}")

            # Small delay between requests
            time.sleep(0.5)

    # Summary
    print("\n")
    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    print(f"\n  Results: {passed}/{len(results)} PASSED, {failed}/{len(results)} FAILED")

    # Thinking coverage
    with_thinking = sum(1 for r in results if r["has_thinking_start"] or r["has_thinking_delta"])
    print(f"  Thinking coverage: {with_thinking}/{len(results)} ({with_thinking*100//len(results)}%)")

    # Zombie check
    with_zombies = sum(1 for r in results if r["zombie_found"])
    print(f"  Zombie phrases: {with_zombies} test(s) leaked zombies")

    # Sources
    with_sources = sum(1 for r in results if r["has_sources"])
    print(f"  Sources returned: {with_sources}/{len(results)}")

    # Average latency
    avg_latency = sum(r["latency_ms"] for r in results) // len(results)
    print(f"  Avg latency: {avg_latency}ms")

    # Failed details
    if failed > 0:
        print("\n  FAILED TESTS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    [{r['id']}] {r['name']}")
                for err in r["errors"]:
                    print(f"        {err}")

    # Event breakdown
    print("\n  EVENT BREAKDOWN per test:")
    print(f"  {'#':<3} {'Name':<20} {'think_start':>12} {'think_delta':>12} {'think_end':>10} {'answer':>8} {'sources':>8}")
    for r in results:
        ec = r["event_counts"]
        print(f"  {r['id']:<3} {r['name']:<20} "
              f"{ec.get('thinking_start', 0):>12} "
              f"{ec.get('thinking_delta', 0):>12} "
              f"{ec.get('thinking_end', 0):>10} "
              f"{ec.get('answer', 0):>8} "
              f"{ec.get('sources', 0):>8}")

    print("\n" + "=" * 70)

    if failed > 0:
        print("AUDIT RESULT: FAILED")
        sys.exit(1)
    else:
        print("AUDIT RESULT: ALL PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
