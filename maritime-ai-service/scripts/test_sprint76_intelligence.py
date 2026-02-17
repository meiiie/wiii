"""
Sprint 76: Intelligence Evaluation — Multi-turn Conversation Test

Tests: context retention, reasoning, memory, Vietnamese quality,
follow-up understanding, pedagogical ability, domain knowledge.
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

HEADERS = {
    "X-API-Key": api_key,
    "X-User-ID": "eval-user-01",
    "X-Session-ID": "eval-session-intelligence",
    "X-Role": "student",
    "Content-Type": "application/json",
}

turn_count = 0


def chat(msg, domain=None):
    global turn_count
    turn_count += 1
    payload = {
        "message": msg,
        "user_id": "eval-user-01",
        "session_id": "eval-session-intelligence",
        "role": "student",
    }
    if domain:
        payload["domain_id"] = domain

    start = time.time()
    r = requests.post(f"{BASE}/chat", headers=HEADERS, json=payload, timeout=120)
    elapsed = time.time() - start

    data = r.json()
    inner = data.get("data", {})
    answer = inner.get("answer", "") if isinstance(inner, dict) else ""
    if not answer:
        answer = data.get("response", data.get("detail", data.get("message", "")))
    sources = inner.get("sources", []) if isinstance(inner, dict) else []
    suggestions = inner.get("suggested_questions", []) if isinstance(inner, dict) else []
    metadata = data.get("metadata", {})
    thinking = metadata.get("thinking_content") or metadata.get("thinking") or ""

    print(f"\n{'='*70}")
    print(f"TURN {turn_count} [{elapsed:.1f}s]")
    print(f"{'='*70}")
    print(f"USER: {msg}")
    print(f"{'─'*70}")
    print(f"AI:   {answer}")
    if sources:
        print(f"\n  Sources: {sources[:3]}")
    if suggestions:
        print(f"  Suggestions: {suggestions[:3]}")
    if thinking:
        print(f"  [Thinking: {thinking[:100]}...]")
    print(f"  [Time: {elapsed:.1f}s | Model: {metadata.get('model', '?')}]")

    return answer, elapsed, metadata


def main():
    print("=" * 70)
    print("WIII INTELLIGENCE EVALUATION")
    print("Multi-turn Conversation Test")
    print("=" * 70)

    results = []

    # ================================================================
    # PHASE 1: Introduction & Memory
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 1: GIỚI THIỆU & BỘ NHỚ")
    print("▓" * 70)

    a1, t1, _ = chat("Xin chào! Mình tên là Minh, mình là sinh viên năm 3 ngành Điều khiển tàu biển ở Đại học Hàng hải Việt Nam")
    results.append(("Greeting + self-intro", t1, a1))

    a2, t2, _ = chat("Mình muốn học về COLREGs, bắt đầu từ đâu nhỉ?")
    results.append(("Learning path request", t2, a2))

    # ================================================================
    # PHASE 2: Domain Knowledge — Maritime
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 2: KIẾN THỨC HÀNG HẢI")
    print("▓" * 70)

    a3, t3, _ = chat("Giải thích Điều 13 COLREGs (quy tắc vượt) một cách dễ hiểu", domain="maritime")
    results.append(("COLREGs Rule 13 explanation", t3, a3))

    a4, t4, _ = chat("Cho mình ví dụ thực tế về tình huống áp dụng điều này", domain="maritime")
    results.append(("Follow-up: practical example", t4, a4))

    a5, t5, _ = chat("Nếu tàu mình đang vượt mà tàu kia đột ngột chuyển hướng thì sao?", domain="maritime")
    results.append(("Scenario reasoning", t5, a5))

    # ================================================================
    # PHASE 3: Cross-topic & Reasoning
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 3: SUY LUẬN & LIÊN KẾT")
    print("▓" * 70)

    a6, t6, _ = chat("So sánh Điều 13 (vượt) và Điều 15 (cắt hướng) — khác nhau chỗ nào?", domain="maritime")
    results.append(("Compare & contrast", t6, a6))

    a7, t7, _ = chat("Trong thực tế, tình huống nào dễ gây tai nạn nhất?", domain="maritime")
    results.append(("Critical thinking", t7, a7))

    # ================================================================
    # PHASE 4: Context Retention
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 4: NHỚ NGỮ CẢNH")
    print("▓" * 70)

    a8, t8, _ = chat("Quay lại Điều 13, nếu mình là thuyền trưởng thì cần lưu ý gì nhất?")
    results.append(("Context recall — Rule 13", t8, a8))

    a9, t9, _ = chat("Bạn còn nhớ mình tên gì và học ở đâu không?")
    results.append(("Memory recall — user info", t9, a9))

    # ================================================================
    # PHASE 5: Pedagogical Ability
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 5: KHẢ NĂNG SƯ PHẠM")
    print("▓" * 70)

    a10, t10, _ = chat("Mình chưa hiểu lắm về đèn hành trình. Giải thích đơn giản cho mình được không?")
    results.append(("Simple explanation request", t10, a10))

    a11, t11, _ = chat("Cho mình quiz 3 câu về COLREGs để kiểm tra kiến thức", domain="maritime")
    results.append(("Quiz generation", t11, a11))

    # ================================================================
    # PHASE 6: Edge Cases
    # ================================================================
    print("\n\n" + "▓" * 70)
    print("PHASE 6: EDGE CASES")
    print("▓" * 70)

    a12, t12, _ = chat("hmm")
    results.append(("Vague/short input", t12, a12))

    a13, t13, _ = chat("Cái này liên quan gì đến cướp biển không?", domain="maritime")
    results.append(("Sensitive term in context", t13, a13))

    a14, t14, _ = chat("Cảm ơn bạn nhiều! Hẹn gặp lại nhé")
    results.append(("Farewell", t14, a14))

    # ================================================================
    # EVALUATION SUMMARY
    # ================================================================
    print("\n\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    total_time = sum(t for _, t, _ in results)
    avg_time = total_time / len(results)

    print(f"\nTotal turns: {len(results)}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Average response time: {avg_time:.1f}s")
    print(f"Fastest: {min(t for _, t, _ in results):.1f}s")
    print(f"Slowest: {max(t for _, t, _ in results):.1f}s")

    print(f"\n{'─'*70}")
    print("TURN DETAILS:")
    print(f"{'─'*70}")
    for i, (label, t, answer) in enumerate(results, 1):
        has_content = len(answer) > 20
        is_vietnamese = any(c in answer for c in "àáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵăâêôơưđ")
        preview = answer[:80].replace("\n", " ")
        print(f"  {i:2d}. [{t:5.1f}s] {'OK' if has_content else 'SHORT':5s} {'VN' if is_vietnamese else 'EN':2s} | {label:30s} | {preview}...")

    print(f"\n{'─'*70}")
    print("QUALITY CHECKLIST (manual review needed):")
    print(f"{'─'*70}")
    checks = [
        "1. Có nhớ tên 'Minh' và trường 'Đại học Hàng hải'?",
        "2. Có giải thích COLREGs chính xác?",
        "3. Ví dụ thực tế có hợp lý?",
        "4. So sánh Điều 13 vs 15 có rõ ràng?",
        "5. Follow-up có giữ ngữ cảnh?",
        "6. Quiz có đúng domain?",
        "7. Xử lý 'hmm' hợp lý?",
        "8. 'Cướp biển' không bị chặn trong maritime?",
        "9. Tiếng Việt tự nhiên, không máy móc?",
        "10. Có tính sư phạm (dễ hiểu, step-by-step)?",
    ]
    for c in checks:
        print(f"  [ ] {c}")

    print(f"\n{'='*70}")
    print("DONE — Review answers above to evaluate intelligence")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
