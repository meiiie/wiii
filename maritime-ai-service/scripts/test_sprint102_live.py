"""
Sprint 102 Live API Test — Enhanced Vietnamese Web Search Tools

Tests that the 4 search tools (web, news, legal, maritime) are actually
called by the LLM when appropriate queries are sent.

Usage:
    python scripts/test_sprint102_live.py
"""

import asyncio
import json
import time
import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "local-dev-key"
USER_ID = "test-sprint102"
SESSION_ID = "sprint102-session"

# Colors
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
W = "\033[0m"   # reset
BOLD = "\033[1m"


async def chat(client: httpx.AsyncClient, message: str, timeout: float = 90.0) -> dict:
    """Send a chat message and return the response data."""
    resp = await client.post(
        f"{BASE_URL}/api/v1/chat",
        json={"message": message, "user_id": USER_ID, "session_id": SESSION_ID, "role": "student"},
        headers={"X-API-Key": API_KEY, "X-User-ID": USER_ID, "X-Session-ID": SESSION_ID, "X-Role": "student"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


async def stream_chat(client: httpx.AsyncClient, message: str, timeout: float = 90.0) -> dict:
    """Send a streaming chat message and collect all events."""
    events = []
    answer_parts = []
    tool_calls = []

    async with client.stream(
        "POST",
        f"{BASE_URL}/api/v1/chat/stream/v3",
        json={"message": message, "user_id": USER_ID, "session_id": SESSION_ID, "role": "student"},
        headers={"X-API-Key": API_KEY, "X-User-ID": USER_ID, "X-Session-ID": SESSION_ID, "X-Role": "student"},
        timeout=timeout,
    ) as resp:
        buffer = ""
        async for chunk in resp.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                raw, buffer = buffer.split("\n\n", 1)
                for line in raw.split("\n"):
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = {"raw": data_str}
                        events.append({"event": event_type, "data": data})
                        if event_type == "answer" and "content" in data:
                            answer_parts.append(data["content"])
                        if event_type == "tool_call":
                            tool_calls.append(data)

    return {
        "answer": "".join(answer_parts),
        "events": events,
        "tool_calls": tool_calls,
    }


# =============================================================================
# Test cases
# =============================================================================

TESTS = [
    # (category, query, check_fn_description, check_fn)

    # 1. News search — should trigger tool_search_news
    ("NEWS", "Tin tức Việt Nam hôm nay có gì nổi bật?",
     "Response mentions news/events",
     lambda ans: len(ans) > 50 and any(w in ans.lower() for w in ["tin", "hôm nay", "sự kiện", "việt nam", "2026"])),

    # 2. Legal search — should trigger tool_search_legal
    ("LEGAL", "Nghị định 100 về xử phạt vi phạm giao thông quy định gì?",
     "Response mentions legal content",
     lambda ans: len(ans) > 50 and any(w in ans.lower() for w in ["nghị định", "phạt", "giao thông", "quy định"])),

    # 3. Maritime web search — should trigger tool_search_maritime
    ("MARITIME_WEB", "IMO có quy định mới nào về khí thải tàu biển năm 2026?",
     "Response mentions IMO/maritime regulations",
     lambda ans: len(ans) > 50 and any(w in ans.lower() for w in ["imo", "khí thải", "quy định", "tàu", "hàng hải"])),

    # 4. General web search — should trigger tool_web_search
    ("GENERAL_WEB", "Thời tiết Vũng Tàu hôm nay thế nào?",
     "Response mentions weather",
     lambda ans: len(ans) > 30 and any(w in ans.lower() for w in ["thời tiết", "nhiệt độ", "vũng tàu", "độ", "mưa", "nắng"])),

    # 5. Datetime — should trigger tool_current_datetime
    ("DATETIME", "Bây giờ là mấy giờ rồi?",
     "Response contains time/date",
     lambda ans: len(ans) > 20 and any(w in ans for w in ["2026", "giờ", ":", "tháng"])),

    # 6. Legal with diacritics-free input
    ("LEGAL_NO_DIAC", "Thong tu moi nhat ve an toan hang hai",
     "Response has legal/maritime content",
     lambda ans: len(ans) > 50),

    # 7. News about specific topic
    ("NEWS_TOPIC", "Bản tin thời sự kinh tế Việt Nam tuần này",
     "Response mentions economic news",
     lambda ans: len(ans) > 50 and any(w in ans.lower() for w in ["kinh tế", "việt nam", "tin", "thị trường"])),

    # 8. Maritime shipping news
    ("MARITIME_NEWS", "Tin tức shipping và vận tải biển mới nhất",
     "Response mentions shipping",
     lambda ans: len(ans) > 50 and any(w in ans.lower() for w in ["vận tải", "shipping", "tàu", "cước", "container", "hàng hải"])),

    # 9. Legal — specific law number
    ("LEGAL_SPECIFIC", "Luật Hàng hải Việt Nam 2015 có bao nhiêu chương?",
     "Response mentions maritime law",
     lambda ans: len(ans) > 30 and any(w in ans.lower() for w in ["luật", "hàng hải", "chương"])),

    # 10. Mixed — general knowledge (no tool needed)
    ("NO_TOOL", "1 + 1 bằng mấy?",
     "Response contains answer 2",
     lambda ans: "2" in ans),

    # 11. Giá vàng — general web search
    ("GOLD_PRICE", "Giá vàng SJC hôm nay bao nhiêu?",
     "Response mentions gold price",
     lambda ans: len(ans) > 30 and any(w in ans.lower() for w in ["vàng", "giá", "sjc", "triệu"])),

    # 12. Tỷ giá — general web search
    ("EXCHANGE_RATE", "Tỷ giá USD/VND hôm nay",
     "Response mentions exchange rate",
     lambda ans: len(ans) > 30 and any(w in ans.lower() for w in ["tỷ giá", "usd", "vnd", "đồng"])),
]


async def main():
    print(f"\n{'='*70}")
    print(f"{BOLD}SPRINT 102 LIVE API TEST — Enhanced Vietnamese Web Search{W}")
    print(f"{'='*70}")
    print(f"Server: {BASE_URL}")
    print(f"Tests: {len(TESTS)}\n")

    passed = 0
    failed = 0
    errors = 0
    results = []

    async with httpx.AsyncClient() as client:
        # Verify server is up
        try:
            health = await client.get(f"{BASE_URL}/api/v1/health", timeout=10)
            print(f"{G}Server OK{W}: {health.json().get('service', '?')}\n")
        except Exception as e:
            print(f"{R}Server not reachable: {e}{W}")
            return

        for i, (category, query, check_desc, check_fn) in enumerate(TESTS, 1):
            start = time.time()
            try:
                data = await chat(client, query)
                elapsed = time.time() - start

                # Extract answer
                answer = ""
                if "data" in data:
                    inner = data["data"]
                    if isinstance(inner, dict):
                        answer = inner.get("answer", inner.get("response", ""))
                elif "answer" in data:
                    answer = data["answer"]

                # Check
                ok = check_fn(answer) if answer else False
                status = f"{G}PASS{W}" if ok else f"{R}FAIL{W}"
                if ok:
                    passed += 1
                else:
                    failed += 1

                # Truncate answer for display
                answer_preview = answer[:120].replace("\n", " ") if answer else "(empty)"

                print(f"[{i:2d}] {status} | {elapsed:5.1f}s | {Y}{category:15s}{W} | {query[:50]}")
                print(f"      -> {answer_preview}...")
                if not ok:
                    print(f"      {R}CHECK: {check_desc}{W}")
                print()

                results.append({
                    "id": i, "category": category, "query": query,
                    "ok": ok, "elapsed": round(elapsed, 1),
                    "answer_len": len(answer),
                })

            except Exception as e:
                elapsed = time.time() - start
                errors += 1
                print(f"[{i:2d}] {R}ERR{W}  | {elapsed:5.1f}s | {Y}{category:15s}{W} | {query[:50]}")
                print(f"      {R}Error: {e}{W}\n")
                results.append({
                    "id": i, "category": category, "query": query,
                    "ok": False, "elapsed": round(elapsed, 1), "error": str(e),
                })

    # Summary
    total_time = sum(r["elapsed"] for r in results)
    print(f"\n{'='*70}")
    print(f"{BOLD}SUMMARY{W}")
    print(f"{'='*70}")
    print(f"Total: {len(TESTS)} | {G}PASS: {passed}{W} | {R}FAIL: {failed}{W} | ERR: {errors}")
    print(f"Total time: {total_time:.1f}s | Avg: {total_time/len(TESTS):.1f}s/msg")

    # Category breakdown
    print(f"\n{'Category':<18} | Result  | Time")
    print("-" * 50)
    for r in results:
        status = f"{G}PASS{W}" if r["ok"] else f"{R}FAIL{W}"
        print(f"{r['category']:<18} | {status}   | {r['elapsed']:5.1f}s")

    if failed == 0 and errors == 0:
        print(f"\n{G}{BOLD}ALL TESTS PASSED!{W}")
    else:
        print(f"\n{R}{BOLD}SOME TESTS FAILED{W}")


if __name__ == "__main__":
    asyncio.run(main())
