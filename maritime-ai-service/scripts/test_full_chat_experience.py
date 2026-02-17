"""
Wiii — Full Chat Experience Test

Tests ALL aspects of the chat system:
  1. Greeting & naturalness (không chào liên tục)
  2. Memory (nhớ tên, nhớ context)
  3. Multi-turn conversation (follow-up)
  4. Web search tool
  5. Knowledge RAG (nếu có data)
  6. Vietnamese language quality

Usage:
    python scripts/test_full_chat_experience.py
    python scripts/test_full_chat_experience.py --local    # localhost:8000
    python scripts/test_full_chat_experience.py --verbose   # show full responses
"""

import argparse
import asyncio
import json
import sys
import time
import uuid

import httpx

# =============================================================================
# CONFIG
# =============================================================================

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
API_KEY = "local-dev-key"
TEST_USER_ID = str(uuid.uuid4())
TEST_ROLE = "student"
VERBOSE = False

C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"


def ok(msg):
    print(f"  {C_GREEN}✓{C_RESET} {msg}")


def fail(msg):
    print(f"  {C_RED}✗{C_RESET} {msg}")


def info(msg):
    print(f"  {C_DIM}→ {msg}{C_RESET}")


def header(msg):
    print(f"\n{C_BOLD}{C_CYAN}{'═' * 60}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  {msg}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}{'═' * 60}{C_RESET}")


# =============================================================================
# CHAT HELPER
# =============================================================================

async def chat(
    client: httpx.AsyncClient,
    message: str,
    user_id: str = None,
    thread_id: str = None,
) -> dict:
    """Send a chat message and return parsed response."""
    payload = {
        "message": message,
        "user_id": user_id or TEST_USER_ID,
        "role": TEST_ROLE,
    }
    if thread_id:
        payload["thread_id"] = thread_id

    start = time.time()
    resp = await client.post(
        f"{API_PREFIX}/chat",
        json=payload,
        headers={
            "X-API-Key": API_KEY,
            "X-User-ID": user_id or TEST_USER_ID,
            "X-Role": TEST_ROLE,
        },
        timeout=120.0,
    )
    elapsed = time.time() - start

    if resp.status_code != 200:
        return {
            "ok": False,
            "status": resp.status_code,
            "error": resp.text[:300],
            "elapsed": elapsed,
        }

    data = resp.json()
    answer = data.get("data", {}).get("answer", "")
    metadata = data.get("metadata", {})
    session_id = metadata.get("session_id")
    agent_type = metadata.get("agent_type", "?")
    tools_used = metadata.get("tools_used", [])
    sources = data.get("data", {}).get("sources", [])

    return {
        "ok": True,
        "answer": answer,
        "session_id": session_id,
        "agent_type": agent_type,
        "tools_used": tools_used,
        "sources": sources,
        "elapsed": elapsed,
        "raw": data,
    }


# =============================================================================
# TEST SCENARIOS
# =============================================================================

async def test_health(client):
    """Test 0: Health check."""
    header("TEST 0 — Health Check")
    resp = await client.get(f"{API_PREFIX}/health")
    if resp.status_code == 200:
        data = resp.json()
        ok(f"Server healthy — status={data.get('status', '?')}")
        components = data.get("components", {})
        for name, comp in components.items():
            st = comp.get("status", "?") if isinstance(comp, dict) else comp
            icon = "✓" if st in ("healthy", "available") else "⚠"
            info(f"  {icon} {name}: {st}")
        return True
    else:
        fail(f"Health check failed — HTTP {resp.status_code}")
        return False


async def test_greeting_and_naturalness(client):
    """Test 1: Greeting — should NOT repeat greetings every turn."""
    header("TEST 1 — Greeting & Naturalness")

    passed = True
    session_id = None

    # Turn 1: Chào lần đầu — nên có lời chào
    r1 = await chat(client, "Xin chào!")
    if not r1["ok"]:
        fail(f"Turn 1 failed: {r1.get('error', r1.get('status'))}")
        return False

    session_id = r1["session_id"]
    answer1 = r1["answer"]
    info(f"Turn 1 ({r1['elapsed']:.1f}s): {answer1[:150]}...")

    has_greeting = any(w in answer1.lower() for w in ["chào", "hello", "xin chào"])
    if has_greeting:
        ok("Turn 1: Có lời chào → đúng")
    else:
        info("Turn 1: Không có lời chào rõ ràng (có thể OK)")

    # Turn 2: Hỏi câu bình thường — KHÔNG nên lặp lại chào
    r2 = await chat(client, "Bạn có thể giúp gì cho tôi?", thread_id=session_id)
    if not r2["ok"]:
        fail(f"Turn 2 failed: {r2.get('error')}")
        return False

    answer2 = r2["answer"]
    info(f"Turn 2 ({r2['elapsed']:.1f}s): {answer2[:150]}...")

    greeting_words = ["xin chào", "chào bạn", "hello"]
    has_repeat_greeting = any(w in answer2.lower()[:80] for w in greeting_words)
    if not has_repeat_greeting:
        ok("Turn 2: Không lặp lại lời chào → tự nhiên")
    else:
        fail("Turn 2: Lặp lại lời chào → không tự nhiên!")
        passed = False

    # Turn 3: Nói tiếp — kiểm tra fluency
    r3 = await chat(client, "Kể cho tôi nghe về bản thân bạn đi", thread_id=session_id)
    if not r3["ok"]:
        fail(f"Turn 3 failed: {r3.get('error')}")
        return False

    answer3 = r3["answer"]
    info(f"Turn 3 ({r3['elapsed']:.1f}s): {answer3[:150]}...")

    if len(answer3) > 50:
        ok(f"Turn 3: Trả lời có nội dung ({len(answer3)} chars)")
    else:
        fail(f"Turn 3: Trả lời quá ngắn ({len(answer3)} chars)")
        passed = False

    return passed


async def test_memory(client):
    """Test 2: Memory — nhớ tên người dùng, nhớ facts."""
    header("TEST 2 — Memory & Recall")

    passed = True
    user_id = str(uuid.uuid4())  # User mới để test memory riêng

    # Turn 1: Giới thiệu tên
    r1 = await chat(client, "Tôi tên là Minh, tôi là sinh viên năm 3 ngành hàng hải.", user_id=user_id)
    if not r1["ok"]:
        fail(f"Turn 1 failed: {r1.get('error')}")
        return False
    session_id = r1["session_id"]
    info(f"Turn 1 ({r1['elapsed']:.1f}s): {r1['answer'][:150]}...")
    ok("Đã gửi thông tin cá nhân")

    # Turn 2: Hỏi câu khác rồi xem có nhớ tên không
    r2 = await chat(client, "Bạn còn nhớ tên tôi không?", user_id=user_id, thread_id=session_id)
    if not r2["ok"]:
        fail(f"Turn 2 failed: {r2.get('error')}")
        return False

    answer2 = r2["answer"]
    info(f"Turn 2 ({r2['elapsed']:.1f}s): {answer2[:150]}...")

    if "minh" in answer2.lower():
        ok("Nhớ tên 'Minh' → memory hoạt động")
    else:
        fail("Không nhắc lại tên 'Minh' → memory có thể chưa hoạt động")
        passed = False

    # Turn 3: Hỏi thông tin đã cung cấp
    r3 = await chat(
        client,
        "Tôi học ngành gì và năm mấy?",
        user_id=user_id,
        thread_id=session_id,
    )
    if not r3["ok"]:
        fail(f"Turn 3 failed: {r3.get('error')}")
        return False

    answer3 = r3["answer"]
    info(f"Turn 3 ({r3['elapsed']:.1f}s): {answer3[:150]}...")

    has_major = any(w in answer3.lower() for w in ["hàng hải", "maritime"])
    has_year = any(w in answer3.lower() for w in ["năm 3", "năm ba", "third"])
    if has_major or has_year:
        ok(f"Nhớ context: hàng hải={'✓' if has_major else '✗'}, năm 3={'✓' if has_year else '✗'}")
    else:
        fail("Không nhớ ngành/năm học → memory context chưa đầy đủ")
        passed = False

    # Check memories API
    try:
        resp = await client.get(
            f"{API_PREFIX}/memories/{user_id}",
            headers={"X-API-Key": API_KEY},
            timeout=15.0,
        )
        if resp.status_code == 200:
            memories = resp.json()
            if isinstance(memories, list):
                info(f"Memory API: {len(memories)} facts stored")
                for m in memories[:3]:
                    if isinstance(m, dict):
                        info(f"  • {m.get('fact_type', '?')}: {m.get('content', '?')[:60]}")
            elif isinstance(memories, dict):
                facts = memories.get("facts", memories.get("data", []))
                info(f"Memory API: {len(facts)} facts stored")
        else:
            info(f"Memory API: HTTP {resp.status_code}")
    except Exception as e:
        info(f"Memory API check skipped: {e}")

    return passed


async def test_web_search(client):
    """Test 3: Web search tool."""
    header("TEST 3 — Web Search Tool")

    r = await chat(
        client,
        "Thời tiết hôm nay ở Hà Nội thế nào? Tìm trên web giúp tôi.",
    )
    if not r["ok"]:
        fail(f"Failed: {r.get('error')}")
        return False

    answer = r["answer"]
    tools = r["tools_used"]
    agent_type = r["agent_type"]
    info(f"Agent: {agent_type}, Tools: {tools}")
    info(f"Answer ({r['elapsed']:.1f}s): {answer[:200]}...")

    passed = True

    # Check if web search was used
    has_web_tool = any("web" in str(t).lower() or "search" in str(t).lower() for t in tools)
    web_mentioned = any(w in answer.lower() for w in ["web", "tìm kiếm", "kết quả", "thời tiết"])

    if has_web_tool:
        ok("Web search tool được sử dụng")
    elif web_mentioned:
        ok("Có đề cập đến kết quả tìm kiếm (tool có thể không hiện trong metadata)")
    else:
        fail("Không thấy web search được kích hoạt")
        info("Lưu ý: Agent có thể trả lời trực tiếp nếu cho rằng không cần search")
        passed = False

    if len(answer) > 30:
        ok(f"Có nội dung trả lời ({len(answer)} chars)")
    else:
        fail("Trả lời quá ngắn")
        passed = False

    return passed


async def test_knowledge_rag(client):
    """Test 4: Knowledge RAG (nếu có data trong DB)."""
    header("TEST 4 — Knowledge RAG")

    r = await chat(
        client,
        "Giải thích quy tắc 15 COLREGs về tình huống cắt hướng",
    )
    if not r["ok"]:
        fail(f"Failed: {r.get('error')}")
        return False

    answer = r["answer"]
    sources = r["sources"]
    agent_type = r["agent_type"]
    info(f"Agent: {agent_type}, Sources: {len(sources or [])}")
    info(f"Answer ({r['elapsed']:.1f}s): {answer[:200]}...")

    passed = True

    if sources and len(sources) > 0:
        ok(f"Có {len(sources)} sources → RAG hoạt động")
        for s in sources[:2]:
            title = s.get("title", "?") if isinstance(s, dict) else "?"
            info(f"  📄 {title}")
    else:
        info("Không có sources (có thể chưa ingest data vào DB)")
        info("Điều này bình thường nếu chưa chạy ingest_full_pdf.py")

    if agent_type in ("rag", "rag_agent"):
        ok(f"Agent type = '{agent_type}' → routing đúng")
    else:
        info(f"Agent type = '{agent_type}' (expected 'rag')")

    if len(answer) > 100:
        ok(f"Trả lời chi tiết ({len(answer)} chars)")
    else:
        info(f"Trả lời ngắn ({len(answer)} chars) — có thể do chưa có data")

    return passed


async def test_multi_turn_coherence(client):
    """Test 5: Multi-turn conversation — follow-up coherent."""
    header("TEST 5 — Multi-Turn Coherence")

    passed = True

    # Turn 1: Hỏi về chủ đề cụ thể
    r1 = await chat(client, "MARPOL là gì?")
    if not r1["ok"]:
        fail(f"Turn 1 failed: {r1.get('error')}")
        return False
    session_id = r1["session_id"]
    info(f"Turn 1 ({r1['elapsed']:.1f}s): {r1['answer'][:120]}...")

    # Turn 2: Follow-up ngắn — agent phải hiểu context
    r2 = await chat(client, "Nó gồm mấy phụ lục?", thread_id=session_id)
    if not r2["ok"]:
        fail(f"Turn 2 failed: {r2.get('error')}")
        return False

    answer2 = r2["answer"]
    info(f"Turn 2 ({r2['elapsed']:.1f}s): {answer2[:150]}...")

    # "Nó" = MARPOL, agent phải hiểu
    marpol_context = any(
        w in answer2.lower()
        for w in ["marpol", "phụ lục", "annex", "ô nhiễm", "pollution"]
    )
    if marpol_context:
        ok("Hiểu context 'nó' = MARPOL → multi-turn coherent")
    else:
        fail("Không hiểu follow-up → mất context")
        passed = False

    # Turn 3: Follow-up tiếp
    r3 = await chat(client, "Phụ lục nào quan trọng nhất?", thread_id=session_id)
    if not r3["ok"]:
        fail(f"Turn 3 failed: {r3.get('error')}")
        return False
    info(f"Turn 3 ({r3['elapsed']:.1f}s): {r3['answer'][:120]}...")

    if len(r3["answer"]) > 50:
        ok("Follow-up tiếp vẫn trả lời được")
    else:
        fail("Follow-up turn 3 quá ngắn")
        passed = False

    return passed


async def test_vietnamese_quality(client):
    """Test 6: Vietnamese language quality."""
    header("TEST 6 — Vietnamese Language Quality")

    r = await chat(client, "Hãy giải thích cho tôi về an toàn hàng hải bằng tiếng Việt thật dễ hiểu")
    if not r["ok"]:
        fail(f"Failed: {r.get('error')}")
        return False

    answer = r["answer"]
    info(f"Answer ({r['elapsed']:.1f}s): {answer[:200]}...")

    passed = True

    # Check Vietnamese content
    vn_chars = sum(1 for c in answer if ord(c) > 127)
    vn_ratio = vn_chars / max(len(answer), 1)
    if vn_ratio > 0.05:
        ok(f"Tiếng Việt: {vn_ratio:.0%} ký tự Unicode → có dấu")
    else:
        fail(f"Ít ký tự tiếng Việt ({vn_ratio:.0%}) → có thể trả lời bằng tiếng Anh")
        passed = False

    # Check not robotic
    robotic_phrases = [
        "tôi là ai",
        "i am an ai",
        "as an ai",
        "i don't have",
    ]
    is_robotic = any(p in answer.lower() for p in robotic_phrases)
    if not is_robotic:
        ok("Không có cụm từ robotic → tự nhiên")
    else:
        info("Có thể hơi robotic nhưng chấp nhận được")

    if len(answer) > 200:
        ok(f"Nội dung đầy đủ ({len(answer)} chars)")
    else:
        info(f"Trả lời hơi ngắn ({len(answer)} chars)")

    return passed


# =============================================================================
# MAIN
# =============================================================================

async def main():
    global BASE_URL, VERBOSE

    parser = argparse.ArgumentParser(description="Wiii Full Chat Experience Test")
    parser.add_argument("--local", action="store_true", help="Use localhost:8000")
    parser.add_argument("--url", type=str, help="Custom base URL")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full responses")
    args = parser.parse_args()

    if args.local:
        BASE_URL = "http://localhost:8000"
    if args.url:
        BASE_URL = args.url
    VERBOSE = args.verbose

    print(f"\n{C_BOLD}🧪 Wiii — Full Chat Experience Test{C_RESET}")
    print(f"{C_DIM}   Server: {BASE_URL}")
    print(f"   User:   {TEST_USER_ID}")
    print(f"   Role:   {TEST_ROLE}{C_RESET}\n")

    results = {}

    async with httpx.AsyncClient(base_url=BASE_URL) as client:

        # Test 0: Health
        if not await test_health(client):
            print(f"\n{C_RED}Server không healthy — dừng test.{C_RESET}")
            print(f"{C_YELLOW}Hãy chắc chắn:")
            print(f"  1. Docker services đang chạy (docker-compose up -d)")
            print(f"  2. Server đang chạy (uvicorn app.main:app --reload)")
            print(f"  3. URL đúng: {BASE_URL}{C_RESET}")
            return

        tests = [
            ("Greeting & Naturalness", test_greeting_and_naturalness),
            ("Memory & Recall", test_memory),
            ("Web Search Tool", test_web_search),
            ("Knowledge RAG", test_knowledge_rag),
            ("Multi-Turn Coherence", test_multi_turn_coherence),
            ("Vietnamese Quality", test_vietnamese_quality),
        ]

        for name, test_fn in tests:
            try:
                results[name] = await test_fn(client)
            except Exception as e:
                fail(f"Exception in {name}: {e}")
                results[name] = False

    # Summary
    header("SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for name, result in results.items():
        icon = f"{C_GREEN}✓{C_RESET}" if result else f"{C_RED}✗{C_RESET}"
        print(f"  {icon} {name}")

    color = C_GREEN if passed == total else C_YELLOW if passed > total // 2 else C_RED
    print(f"\n  {color}{C_BOLD}{passed}/{total} tests passed{C_RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
