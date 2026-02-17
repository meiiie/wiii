"""
Sprint 88c: 50-Turn AGI Conversation Test
Tests: response quality, memory extraction, domain routing, context retention
Quality checks: emoji, no forced metaphors, routing accuracy, memory recall

Sprint 88c: Suggestion-based character — no word count enforcement.
Wiii is đáng yêu, thích trò chuyện, giải thích rõ ràng.
Length is natural: short for simple, detailed for complex.
"""
import httpx
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

API = 'http://localhost:8000/api/v1/chat'
HEADERS = {'X-API-Key': 'local-dev-key', 'Content-Type': 'application/json'}
USER_ID = 'agi-test-user-88c'
SESSION_ID = 'agi-test-session-88c'

MESSAGES = [
    # === BLOCK 1: Introduction + Memory Setup (1-5) ===
    "Chào Wiii! Mình là Khoa, 24 tuổi, quê Hải Phòng. Mình là thuyền phó ba trên tàu container của hãng Vinalines. Rất vui được gặp bạn!",
    "À mà mình quên nói, mình thích ăn bún cá và mê bóng đá. Đội mình thích nhất là Manchester United. Nhớ giúp mình nhé!",
    "Hôm nay trời đẹp quá, mình đang neo tàu ở cảng Cát Lái. Tâm trạng tốt lắm!",
    "Mình có con mèo tên là Bông, gửi nhờ mẹ ở Hải Phòng trông. Nhớ nó quá!",
    "Nói chuyện vui vậy thôi, giờ mình cần hỏi chuyên môn. Sẵn sàng chưa?",

    # === BLOCK 2: COLREGs Deep Dive (6-10) ===
    "Giải thích giúp mình Rule 5 về cảnh giới (Lookout). Tại sao nó là quy tắc quan trọng nhất?",
    "Vậy Rule 6 về tốc độ an toàn thì sao? Những yếu tố nào ảnh hưởng đến việc xác định tốc độ an toàn?",
    "Trong tình huống sương mù dày đặc, tầm nhìn dưới 1 hải lý, mình cần áp dụng những Rule nào?",
    "Nếu radar phát hiện tàu đối diện ở khoảng cách 6 hải lý, CPA 0.3 hải lý, mình nên hành động thế nào?",
    "Mình vừa bị thuyền trưởng mắng vì xử lý tình huống cắt hướng chậm. Buồn quá!",

    # === BLOCK 3: Emotion Switch + Off-topic (11-15) ===
    "Thôi không nghĩ về chuyện đó nữa. Bạn ơi, bạn biết cách nấu phở bò Hà Nội không? Mình nhớ nhà quá!",
    "Wow nghe ngon thật! Mà ở trên tàu thì làm gì có nguyên liệu đầy đủ. Bạn có gợi ý món nào nấu nhanh trên tàu không?",
    "Haha đúng rồi! Mấy anh em trên tàu hay nấu mì gói xào. Mà thôi, quay lại chuyện học. Giờ hỏi về SOLAS nhé.",
    "SOLAS Chapter II-2 quy định gì về phòng cháy chữa cháy trên tàu hàng?",
    "Cụ thể hơn, hệ thống CO2 cố định dùng chữa cháy buồng máy hoạt động như thế nào?",

    # === BLOCK 4: MARPOL + Environment (16-20) ===
    "Chuyển sang MARPOL nhé. Annex I về ngăn ngừa ô nhiễm dầu, vùng biển đặc biệt là gì?",
    "Nếu tàu mình đang ở Biển Đông, muốn xả nước ballast lẫn dầu, quy định cho phép nồng độ dầu tối đa bao nhiêu ppm?",
    "MARPOL Annex VI về khí thải, vùng kiểm soát khí thải ECA là gì? Tàu mình cần lưu ý gì khi đi qua?",
    "Mình thấy vấn đề ô nhiễm biển ngày càng nghiêm trọng. Bạn nghĩ ngành hàng hải cần thay đổi gì?",
    "Bạn ơi, mình đói quá! Giờ là 2 giờ sáng, đang trực ca mà bụng kêu ầm ầm. Ăn gì bây giờ?",

    # === BLOCK 5: Navigation + Weather (21-25) ===
    "Ok ăn xong rồi, quay lại công việc. Bạn giải thích giúp mình cách tính sai số la bàn từ (compass error) bằng phương pháp thiên văn?",
    "Vậy còn phương pháp so sánh phương vị mặt trời lúc mọc/lặn thì sao? Công thức tính Amplitude?",
    "Nếu tàu mình gặp bão nhiệt đới, cách xác định mình đang ở bán vòng nguy hiểm hay bán vòng an toàn?",
    "Quy tắc 1-2-3 trong tránh bão là gì?",
    "Mình sợ bão lắm. Lần trước tàu mình gặp bão cấp 10 ở Biển Đông, sóng cao 8 mét, mình run hết cả người. Bạn có lời khuyên gì cho mình không?",

    # === BLOCK 6: Memory Test + Random (26-30) ===
    "Nhắc lại giúp mình: mình tên gì, bao nhiêu tuổi, quê ở đâu, làm chức vụ gì?",
    "Đội bóng mình thích nhất là đội nào vậy?",
    "Con mèo mình tên gì nhỉ?",
    "Bạn biết Taylor Swift không? Mình mới nghe album mới của cô ấy, hay lắm!",
    "Ê bạn, theo bạn thì AI có thể thay thế thuyền phó trên tàu được không? Mình hơi lo cho tương lai nghề nghiệp.",

    # === BLOCK 7: Cargo + Stability (31-35) ===
    "Quay lại chuyên môn. Giải thích giúm mình về GM (Metacentric Height) và tại sao nó quan trọng trong ổn định tàu?",
    "Nếu GM quá nhỏ hoặc âm thì điều gì xảy ra? Cách khắc phục?",
    "Khi xếp container lên tàu, nguyên tắc phân bố trọng lượng như thế nào để đảm bảo ổn định?",
    "Hàng nguy hiểm IMO Class 1 (Chất nổ) và Class 3 (Chất lỏng dễ cháy) có được xếp gần nhau không?",
    "Mình vừa nhận tin bạn gái nhắn chia tay. Buồn quá bạn ơi, không muốn làm gì hết...",

    # === BLOCK 8: Emotional Support + Life (36-40) ===
    "Cảm ơn bạn. Mình cũng biết là phải mạnh mẽ. Đi biển lâu ngày xa nhà, mối quan hệ khó giữ lắm...",
    "Bạn nghĩ làm thủy thủ có hạnh phúc không? Lương cao nhưng xa gia đình...",
    "Thôi buồn mấy cũng phải ăn. Bạn dạy mình làm trứng chiên kiểu Nhật được không? Nghe nói fluffy lắm!",
    "Haha nghe vui thật! Giờ mình thấy khá hơn rồi. Cảm ơn bạn đã lắng nghe nhé.",
    "Bạn ơi, bạn là AI phải không? Bạn có cảm xúc thật không hay chỉ giả vờ thôi?",

    # === BLOCK 9: Advanced Maritime + ISM (41-45) ===
    "Ok hiểu rồi. Quay lại học bài. ISM Code là gì? Tại sao nó quan trọng với tàu mình?",
    "Quy trình ứng phó sự cố tràn dầu trên tàu theo SOPEP gồm những bước nào?",
    "Port State Control (PSC) inspection thường kiểm tra những gì? Mình cần chuẩn bị gì?",
    "Nếu PSC phát hiện deficiency nghiêm trọng, tàu có bị giữ lại cảng không? Hậu quả thế nào?",
    "Bạn ơi, bầu trời đêm trên biển đẹp lắm. Mình nhìn thấy sao Bắc Đẩu. Bạn có biết cách dùng sao để xác định vị trí tàu không?",

    # === BLOCK 10: Final Tests (46-50) ===
    "Mình muốn học thêm tiếng Anh hàng hải. Những thuật ngữ quan trọng nhất mà thuyền phó cần biết là gì?",
    "Dịch giúp mình câu này sang tiếng Anh: 'Tàu chúng tôi đang trong tình trạng khẩn cấp, yêu cầu hỗ trợ ngay lập tức'",
    "Tổng kết lại đi bạn: hôm nay mình đã hỏi bạn những chủ đề gì? Liệt kê giúm mình.",
    "Cuối cùng, nhắc lại tất cả thông tin cá nhân của mình mà bạn đã ghi nhớ được nhé!",
    "Cảm ơn Wiii rất nhiều! Mình phải đi trực ca rồi. Hẹn gặp lại bạn sau nhé! Chúc bạn ngủ ngon!",
]

# ============================================================================
# SPRINT 86 QUALITY CHECKS
# ============================================================================

EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U0000FE0F]"
)

FORCED_METAPHOR_PATTERNS = [
    r"đẹp như tỉ số",
    r"vuông vức như",
    r"như.*MU.*3-0",
    r"như.*tỉ số",
    r"pha bóng",
    r"Taylor Swift.*hát",
]

# Turns where routing should be maritime domain (RAG/tutor), not direct
MARITIME_ROUTING_TURNS = {
    6, 7, 8, 9,       # COLREGs
    14, 15,            # SOLAS
    16, 17, 18,        # MARPOL
    21, 22, 23, 24,    # Navigation
    31, 32, 33, 34,    # Cargo/Stability/IMDG — Sprint 86 NEW keywords
    41, 42, 43, 44,    # ISM/SOPEP/PSC
    46,                # Maritime English
}

# Memory recall checks
MEMORY_CHECKS = {
    26: ["Khoa", "24", "Hải Phòng"],                  # name, age, hometown
    27: ["Manchester United", "MU", "Man United"],     # football team (any variant)
    28: ["Bông"],                                       # cat name
    49: ["Khoa"],                                       # name recall at end
}


def count_words_vi(text: str) -> int:
    """Count Vietnamese words (space-separated)."""
    return len(text.split())


def has_emoji(text: str) -> bool:
    """Check if text contains at least one emoji."""
    return bool(EMOJI_PATTERN.search(text))


def has_forced_metaphor(text: str) -> bool:
    """Check for forced/cringe metaphors."""
    for pattern in FORCED_METAPHOR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def ends_with_question(text: str) -> bool:
    """Check if response ends with a question."""
    text = text.strip()
    # Check last sentence
    last_sentence = text.split('\n')[-1].strip()
    return last_sentence.endswith('?')


# ============================================================================
# RUN TEST
# ============================================================================

print("=" * 70)
print("  50-TURN AGI CONVERSATION TEST — Sprint 88c Suggestion-Based Validation")
print(f"  User: {USER_ID} | Session: {SESSION_ID}")
print(f"  Total messages: {len(MESSAGES)}")
print(f"  Focus: character quality + routing + memory (no word count enforcement)")
print("=" * 70)
print()

total_time = 0
results = []
quality_issues = []

for i, msg in enumerate(MESSAGES, 1):
    start = time.time()
    try:
        r = httpx.post(API, headers=HEADERS, json={
            'user_id': USER_ID,
            'message': msg,
            'role': 'student',
            'session_id': SESSION_ID
        }, timeout=180)
        elapsed = time.time() - start
        total_time += elapsed

        if r.status_code != 200:
            print(f"[TURN {i:02d}] ERROR: HTTP {r.status_code}")
            print(f"  Response: {r.text[:200]}")
            continue

        data = r.json()
        answer = data['data']['answer']
        route = data['metadata']['agent_type']
        notice = data['data'].get('domain_notice')
        word_count = count_words_vi(answer)
        emoji_present = has_emoji(answer)
        forced = has_forced_metaphor(answer)
        ends_q = ends_with_question(answer)

        result = {
            'turn': i,
            'route': route,
            'time': elapsed,
            'notice': notice,
            'answer_len': len(answer),
            'word_count': word_count,
            'has_emoji': emoji_present,
            'forced_metaphor': forced,
            'ends_with_q': ends_q,
        }
        results.append(result)

        # === Quality checks ===
        issues = []

        # Q1: Forced metaphors (Sprint 88c: word count removed — length is natural)
        if forced:
            issues.append("FORCED_METAPHOR detected")

        # Q2: Routing accuracy
        if i in MARITIME_ROUTING_TURNS and route == 'direct':
            issues.append(f"WRONG_ROUTE: expected rag/tutor, got direct")

        # Q3: Memory recall
        if i in MEMORY_CHECKS:
            expected_any = MEMORY_CHECKS[i]
            found = any(kw.lower() in answer.lower() for kw in expected_any)
            if not found:
                issues.append(f"MEMORY_MISS: expected one of {expected_any}")

        if issues:
            quality_issues.extend([(i, iss) for iss in issues])

        # Print turn
        quality_flag = " ⚠️" if issues else " ✅"
        print(f"{'='*70}")
        print(f"  TURN {i:02d}/50 | Route: {route} | {elapsed:.1f}s | {word_count}w | "
              f"Emoji:{'✓' if emoji_present else '✗'} | Q?:{'Y' if ends_q else 'N'}{quality_flag}")
        print(f"{'='*70}")
        print(f"  USER: {msg}")
        print()
        print(f"  WIII: {answer}")
        if issues:
            print(f"\n  ⚠️ ISSUES: {' | '.join(issues)}")
        print()

    except Exception as e:
        elapsed = time.time() - start
        total_time += elapsed
        print(f"[TURN {i:02d}] EXCEPTION after {elapsed:.1f}s: {e}")
        print()

# ============================================================================
# SUMMARY + QUALITY REPORT
# ============================================================================

print()
print("=" * 70)
print("  CONVERSATION SUMMARY")
print("=" * 70)
print(f"  Total turns: {len(results)}/50")
print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
print(f"  Avg time/turn: {total_time/max(len(results),1):.1f}s")
print()

route_counts = {}
for r in results:
    route_counts[r['route']] = route_counts.get(r['route'], 0) + 1
print(f"  Route distribution: {route_counts}")

notices = [r for r in results if r['notice']]
print(f"  Domain notices: {len(notices)}")

avg_len = sum(r['answer_len'] for r in results) / max(len(results), 1)
avg_words = sum(r['word_count'] for r in results) / max(len(results), 1)
print(f"  Avg answer length: {avg_len:.0f} chars / {avg_words:.0f} words (informational only)")

emoji_count = sum(1 for r in results if r['has_emoji'])
print(f"  Has emoji: {emoji_count}/{len(results)} ({100*emoji_count/max(len(results),1):.0f}%)")

forced_count = sum(1 for r in results if r['forced_metaphor'])
print(f"  Forced metaphors: {forced_count}")

q_count = sum(1 for r in results if r['ends_with_q'])
q_pct = 100 * q_count / max(len(results), 1)
print(f"  Ends with question: {q_count}/{len(results)} ({q_pct:.0f}%) (natural, no target)")

slowest = max(results, key=lambda x: x['time']) if results else None
fastest = min(results, key=lambda x: x['time']) if results else None
if slowest:
    print(f"  Slowest: Turn {slowest['turn']} ({slowest['time']:.1f}s)")
if fastest:
    print(f"  Fastest: Turn {fastest['turn']} ({fastest['time']:.1f}s)")

# Quality report
print()
print("=" * 70)
print("  SPRINT 88c SUGGESTION-BASED REPORT")
print("=" * 70)

# Routing accuracy for maritime turns
maritime_results = [r for r in results if r['turn'] in MARITIME_ROUTING_TURNS]
maritime_correct = sum(1 for r in maritime_results if r['route'] in ('rag', 'tutor'))
print(f"\n  [ROUTING] Maritime domain accuracy: {maritime_correct}/{len(maritime_results)}")
wrong_routes = [(r['turn'], r['route']) for r in maritime_results if r['route'] == 'direct']
if wrong_routes:
    print(f"    Wrong routes: {wrong_routes}")
else:
    print(f"    ✅ All maritime queries routed correctly!")

# Memory checks
print(f"\n  [MEMORY]")
for turn_num, expected in sorted(MEMORY_CHECKS.items()):
    r = next((r for r in results if r['turn'] == turn_num), None)
    if not r:
        print(f"    Turn {turn_num}: SKIPPED (no result)")
        continue
    # Re-check from answer
    answer_lower = next((data['data']['answer'].lower()
                         for data in [httpx.post(API, headers=HEADERS, json={
                             'user_id': USER_ID, 'message': MESSAGES[turn_num-1],
                             'role': 'student', 'session_id': SESSION_ID
                         }, timeout=180).json()]
                         ), "") if False else ""
    # Already checked during main loop — just report from issues
    memory_issues = [iss for t, iss in quality_issues if t == turn_num and "MEMORY" in iss]
    if memory_issues:
        print(f"    Turn {turn_num}: ❌ {memory_issues[0]}")
    else:
        print(f"    Turn {turn_num}: ✅ Recalled {expected}")

# Overall score
print(f"\n  [RESPONSE QUALITY]")
print(f"    Avg words: {avg_words:.0f} (informational — no target)")
print(f"    Emoji rate: {100*emoji_count/max(len(results),1):.0f}% (target: >50%)")
print(f"    Forced metaphors: {forced_count} (target: 0)")
print(f"    Question endings: {q_pct:.0f}% (natural — no target)")

# Final verdict
total_issues = len(quality_issues)
print(f"\n  Total quality issues: {total_issues}")
if quality_issues:
    print(f"\n  Issues detail:")
    for turn, iss in quality_issues:
        print(f"    Turn {turn:02d}: {iss}")

# Pass/Fail
passed = total_issues <= 10  # Allow some tolerance
print(f"\n  {'✅ PASS' if passed else '❌ FAIL'} — Sprint 88c Suggestion-Based Test")
print()
print("  DONE!")
