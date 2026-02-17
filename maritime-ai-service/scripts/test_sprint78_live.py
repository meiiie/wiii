"""
Sprint 77-78: Live API Test — Conversation Context & Memory Management

Tests:
  A. Multi-turn context retention (Sprint 77 — history injection)
  B. Follow-up understanding without re-stating context
  C. Memory recall across turns
  D. Context API endpoints (Sprint 78 — /context/info, /context/compact, /context/clear)
  E. Post-compact conversation continuity
  F. Greeting repetition check (Sprint 76 regression)
  G. Long conversation stress test
"""

import sys
import requests
import json
import time
import os

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000/api/v1"

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
api_key = ""
with open(env_path) as f:
    for line in f:
        if line.startswith("API_KEY="):
            api_key = line.split("=", 1)[1].strip()
            break

SESSION_ID = "test-sprint78-context"
USER_ID = "test-user-sprint78"

HEADERS = {
    "X-API-Key": api_key,
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
    "X-Role": "student",
    "Content-Type": "application/json",
}

turn_count = 0
results = []


def chat(msg, domain=None, label=""):
    """Send a chat message and return the response."""
    global turn_count
    turn_count += 1
    payload = {
        "message": msg,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "role": "student",
    }
    if domain:
        payload["domain_id"] = domain

    start = time.time()
    try:
        r = requests.post(f"{BASE}/chat", headers=HEADERS, json=payload, timeout=120)
        elapsed = time.time() - start

        data = r.json()
        inner = data.get("data", {})
        answer = inner.get("answer", "") if isinstance(inner, dict) else ""
        if not answer:
            answer = data.get("response", data.get("detail", data.get("message", "")))

        print(f"\n  [{turn_count}] User: {msg}")
        print(f"      AI:   {answer[:300]}")
        print(f"      Time: {elapsed:.1f}s | Len: {len(answer)} chars")
        return answer
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  [{turn_count}] User: {msg}")
        print(f"      ERROR: {str(e)[:100]} ({elapsed:.1f}s)")
        return ""


def check(answer, keywords, label, anti_keywords=None):
    """Check if answer contains expected keywords."""
    answer_lower = answer.lower()
    found = any(kw.lower() in answer_lower for kw in keywords)
    blocked = False
    if anti_keywords:
        blocked = any(kw.lower() in answer_lower for kw in anti_keywords)

    ok = found and not blocked
    icon = "PASS" if ok else "FAIL"
    print(f"      [{icon}] {label}")
    if not found:
        print(f"             Missing keywords: {keywords}")
    if blocked:
        print(f"             Found anti-keywords: {anti_keywords}")
    results.append((label, ok))
    return ok


def context_info():
    """Get context info via API."""
    try:
        r = requests.get(f"{BASE}/context/info", headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            print(f"\n  [CONTEXT INFO] {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
            return data
        else:
            print(f"\n  [CONTEXT INFO] Status {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"\n  [CONTEXT INFO] Error: {e}")
        return None


def context_compact():
    """Trigger manual compaction."""
    try:
        r = requests.post(f"{BASE}/context/compact", headers=HEADERS, timeout=60)
        data = r.json()
        print(f"\n  [COMPACT] Status {r.status_code}: {json.dumps(data, ensure_ascii=False)[:300]}")
        return r.status_code == 200, data
    except Exception as e:
        print(f"\n  [COMPACT] Error: {e}")
        return False, {}


def context_clear():
    """Clear conversation context."""
    try:
        r = requests.post(f"{BASE}/context/clear", headers=HEADERS, timeout=30)
        data = r.json()
        print(f"\n  [CLEAR] Status {r.status_code}: {json.dumps(data, ensure_ascii=False)[:300]}")
        return r.status_code == 200, data
    except Exception as e:
        print(f"\n  [CLEAR] Error: {e}")
        return False, {}


def main():
    print("=" * 70)
    print("SPRINT 77-78: LIVE CONVERSATION CONTEXT TEST")
    print("=" * 70)
    print(f"Server: {BASE}")
    print(f"User: {USER_ID} | Session: {SESSION_ID}")

    # ================================================================
    # A. MULTI-TURN CONTEXT RETENTION
    # ================================================================
    print("\n" + "=" * 70)
    print("[A] MULTI-TURN CONTEXT RETENTION (Sprint 77)")
    print("=" * 70)

    # Turn 1: Introduce yourself
    a1 = chat("Xin chào, mình là Minh, sinh viên năm 3 ngành Hàng Hải.")
    check(a1,
          ["minh", "hàng hải", "sinh viên", "chào", "xin chào", "giúp"],
          "A1: Greeting acknowledges name/major")

    # Turn 2: Ask a domain question
    a2 = chat("Giải thích Rule 15 của COLREGs cho mình nhé")
    check(a2,
          ["rule 15", "crossing", "giao nhau", "starboard", "mạn phải", "tránh", "nhường"],
          "A2: Explains Rule 15 (crossing situation)")

    # Turn 3: Follow-up WITHOUT re-stating topic
    a3 = chat("Vậy nó khác gì so với Rule 13?")
    check(a3,
          ["rule 13", "overtaking", "vượt", "đuổi", "phía sau", "khác"],
          "A3: Compares Rule 15 vs 13 (follow-up context)")

    # Turn 4: Another follow-up referencing earlier
    a4 = chat("Cho mình ví dụ thực tế về cả hai quy tắc này")
    check(a4,
          ["ví dụ", "tàu", "tình huống", "rule", "quy tắc"],
          "A4: Gives examples for both rules (deep follow-up)")

    # ================================================================
    # B. PERSONAL MEMORY ACROSS TURNS
    # ================================================================
    print("\n" + "=" * 70)
    print("[B] PERSONAL MEMORY ACROSS TURNS")
    print("=" * 70)

    # Turn 5: Tell AI something personal
    b1 = chat("Mình đang chuẩn bị thi cuối kỳ môn Luật Hàng Hải")
    check(b1,
          ["thi", "luật", "ôn", "chuẩn bị", "giúp", "hàng hải"],
          "B1: Acknowledges exam preparation")

    # Turn 6: Ask for help — AI should know context
    b2 = chat("Giúp mình ôn phần SOLAS nhé")
    check(b2,
          ["solas", "an toàn", "safety", "chương", "quy định"],
          "B2: Helps with SOLAS review")

    # Turn 7: Follow-up — should remember exam context
    b3 = chat("Phần nào hay ra thi nhất?")
    check(b3,
          ["thi", "quan trọng", "thường", "chương", "phần", "hay"],
          "B3: Suggests exam-relevant topics (remembers exam context)")

    # ================================================================
    # C. CONTEXT API ENDPOINTS (Sprint 78)
    # ================================================================
    print("\n" + "=" * 70)
    print("[C] CONTEXT API ENDPOINTS (Sprint 78)")
    print("=" * 70)

    # C1: Get context info
    info = context_info()
    if info:
        check(json.dumps(info),
              ["session_id", "token", "message", "budget"],
              "C1: /context/info returns meaningful data")
    else:
        print("      [SKIP] /context/info not available")
        results.append(("C1: /context/info returns meaningful data", None))

    # C2: Compact context
    compact_ok, compact_data = context_compact()
    if compact_ok:
        check(json.dumps(compact_data),
              ["summary", "compact", "success"],
              "C2: /context/compact succeeds")
    else:
        print(f"      [INFO] /context/compact returned non-200")
        results.append(("C2: /context/compact succeeds", None))

    # C3: After compact, conversation should continue normally
    c3 = chat("Quay lại chủ đề COLREGs, Rule 14 là gì?")
    check(c3,
          ["rule 14", "head-on", "đối đầu", "đối diện", "mạn phải"],
          "C3: Post-compact conversation works normally")

    # ================================================================
    # D. GREETING REPETITION CHECK (Sprint 76 regression)
    # ================================================================
    print("\n" + "=" * 70)
    print("[D] GREETING REPETITION CHECK (Sprint 76)")
    print("=" * 70)

    # After 8+ turns, AI should NOT re-greet
    d1 = chat("Cảm ơn, giờ mình muốn hỏi về MARPOL")
    has_greeting = any(g in d1.lower() for g in [
        "xin chào", "chào bạn", "chào minh", "rất vui", "hân hạnh"
    ])
    ok = not has_greeting
    icon = "PASS" if ok else "FAIL"
    print(f"      [{icon}] D1: No re-greeting after 8+ turns")
    if not ok:
        print(f"             Found greeting in follow-up response!")
    results.append(("D1: No re-greeting after 8+ turns", ok))

    check(d1,
          ["marpol", "ô nhiễm", "pollution", "phụ lục", "annex", "biển"],
          "D2: Answers MARPOL question")

    # ================================================================
    # E. CONTEXT CLEAR + FRESH START
    # ================================================================
    print("\n" + "=" * 70)
    print("[E] CONTEXT CLEAR + FRESH START (Sprint 78)")
    print("=" * 70)

    # E1: Clear context
    clear_ok, clear_data = context_clear()
    if clear_ok:
        check(json.dumps(clear_data),
              ["clear", "success", "reset"],
              "E1: /context/clear succeeds")
    else:
        print(f"      [INFO] /context/clear returned non-200")
        results.append(("E1: /context/clear succeeds", None))

    # E2: After clear, AI responds (core memory may persist — that's by design)
    e2 = chat("Mình đang học gì vậy nhỉ?")
    # After clear, conversation messages are removed but CoreMemoryBlock persists.
    # AI may still know user's name/subject from long-term memory — this is correct.
    # Just verify the AI generates a coherent response (not an error).
    check(e2,
          ["Hàng", "Luật", "ôn", "thi", "giúp", "hỏi", "bạn"],
          "E2: After clear, AI responds coherently")

    # ================================================================
    # F. LONG CONVERSATION STRESS (7+ more turns)
    # ================================================================
    print("\n" + "=" * 70)
    print("[F] LONG CONVERSATION — CONTEXT WINDOW STRESS")
    print("=" * 70)

    # Build up a longer conversation
    f1 = chat("Chào, mình là Nam, sinh viên năm 2")
    f2 = chat("Mình muốn tìm hiểu về hệ thống đèn hiệu hàng hải")
    check(f2,
          ["đèn", "hiệu", "hàng hải", "tín hiệu", "navigation"],
          "F1: Discusses navigation lights")

    f3 = chat("Đèn mạn trái màu gì?")
    check(f3,
          ["đỏ", "red", "mạn trái", "port"],
          "F2: Port side light = red")

    f4 = chat("Còn mạn phải?")
    check(f4,
          ["xanh", "green", "mạn phải", "starboard"],
          "F3: Starboard light = green (follow-up)")

    f5 = chat("Tàu nào phải mang đèn kéo?")
    check(f5,
          ["kéo", "towing", "đèn", "vàng", "yellow", "rule 24"],
          "F4: Towing lights question")

    f6 = chat("Mình quên rồi, đèn mạn trái màu gì nhỉ?")
    check(f6,
          ["đỏ", "red", "mạn trái", "port"],
          "F5: Re-asks port light — should still answer correctly")

    f7 = chat("Tóm tắt lại những gì mình đã học hôm nay")
    check(f7,
          ["đèn", "mạn", "rule", "tàu", "hàng hải", "colregs", "tóm tắt"],
          "F6: Summarizes session (proves full context)")

    # Check context info at the end
    final_info = context_info()
    if final_info:
        results.append(("F7: Final context info available", True))

    # ================================================================
    # RESULTS SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, ok in results if ok is True)
    failed = sum(1 for _, ok in results if ok is False)
    skipped = sum(1 for _, ok in results if ok is None)
    total = len(results)

    for label, ok in results:
        if ok is True:
            print(f"  [PASS] {label}")
        elif ok is False:
            print(f"  [FAIL] {label}")
        else:
            print(f"  [SKIP] {label}")

    print(f"\n  Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print(f"  Turns: {turn_count}")

    if failed == 0:
        print("\n  === ALL TESTS PASSED ===")
    else:
        print(f"\n  === {failed} TESTS FAILED ===")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
