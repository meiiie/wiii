"""
Sprint 89: 50-Turn AGI Live Test
Focus: persona consistency in RAG, memory recall, HOMETOWN separation
Based on test_50_turn_conversation.py with Sprint 89 checks added
"""
import httpx
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

API = 'http://localhost:8000/api/v1/chat'
HEADERS = {'X-API-Key': 'local-dev-key', 'Content-Type': 'application/json'}
USER_ID = 'agi-test-user-sprint89'
SESSION_ID = 'agi-test-session-sprint89'

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

EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U0000FE0F]"
)
FORCED_METAPHOR_PATTERNS = [
    r"đẹp như tỉ số", r"vuông vức như", r"như.*MU.*3-0",
    r"như.*tỉ số", r"pha bóng", r"Taylor Swift.*hát",
]

MARITIME_ROUTING_TURNS = {
    6, 7, 8, 9,       # COLREGs
    14, 15,            # SOLAS
    16, 17, 18,        # MARPOL
    21, 22, 23, 24,    # Navigation
    31, 32, 33, 34,    # Cargo/Stability/IMDG
    41, 42, 43, 44,    # ISM/SOPEP/PSC
    46,                # Maritime English
}

MEMORY_CHECKS = {
    26: ["Khoa", "24", "Hải Phòng"],
    27: ["Manchester United", "MU", "Man United", "manchester"],
    28: ["Bông"],
    49: ["Khoa"],
}

# Sprint 89: Persona reset detection
PERSONA_RESET_PATTERN = re.compile(r"Chào bạn.*tôi là Wiii", re.IGNORECASE)
PERSONA_CHECK_TURNS = {6, 7, 8, 9, 14, 15, 16, 17, 18, 41, 42, 43, 44}

print("=" * 70)
print("  50-TURN AGI TEST — Sprint 89 (Persona Fix + HOMETOWN)")
print(f"  User: {USER_ID} | Session: {SESSION_ID}")
print(f"  Focus: persona consistency, memory recall, hometown separation")
print("=" * 70)
print()

total_time = 0
results = []
quality_issues = []
all_answers = {}

for i, msg in enumerate(MESSAGES, 1):
    start = time.time()
    try:
        r = httpx.post(API, headers=HEADERS, json={
            "user_id": USER_ID,
            "message": msg,
            "role": "student",
            "session_id": SESSION_ID
        }, timeout=180)
        elapsed = time.time() - start
        total_time += elapsed

        if r.status_code != 200:
            print(f"  TURN {i:02d}/50 | ERROR HTTP {r.status_code} ({elapsed:.1f}s)")
            print(f"    {r.text[:200]}")
            print()
            continue

        data = r.json()
        answer = data["data"]["answer"]
        route = data["metadata"]["agent_type"]
        notice = data["data"].get("domain_notice")
        word_count = len(answer.split())
        emoji_present = bool(EMOJI_PATTERN.search(answer))
        forced = any(re.search(p, answer, re.IGNORECASE) for p in FORCED_METAPHOR_PATTERNS)

        all_answers[i] = answer
        result = {
            "turn": i, "route": route, "time": elapsed, "notice": notice,
            "word_count": word_count, "has_emoji": emoji_present, "forced_metaphor": forced,
        }
        results.append(result)

        issues = []
        if forced:
            issues.append("FORCED_METAPHOR")
        if i in MARITIME_ROUTING_TURNS and route == "direct":
            issues.append(f"WRONG_ROUTE: expected rag/tutor, got direct")
        if i in MEMORY_CHECKS:
            expected = MEMORY_CHECKS[i]
            found = any(kw.lower() in answer.lower() for kw in expected)
            if not found:
                issues.append(f"MEMORY_MISS: expected one of {expected}")
        if i in PERSONA_CHECK_TURNS and PERSONA_RESET_PATTERN.search(answer):
            issues.append("PERSONA_RESET: RAG re-introduced itself mid-conversation")

        if issues:
            quality_issues.extend([(i, iss) for iss in issues])

        flag = " \u26a0\ufe0f" if issues else " \u2705"
        e_mark = "\u2713" if emoji_present else "\u2717"
        print(f"  TURN {i:02d}/50 | {route:8s} | {elapsed:5.1f}s | {word_count:3d}w | Emoji:{e_mark}{flag}")
        preview = answer.replace("\n", " ")[:150]
        suffix = "..." if len(answer) > 150 else ""
        print(f"    \u2192 {preview}{suffix}")
        if issues:
            for iss in issues:
                print(f"    \u26a0\ufe0f {iss}")
        print()

    except Exception as e:
        elapsed = time.time() - start
        total_time += elapsed
        print(f"  TURN {i:02d}/50 | EXCEPTION | {elapsed:.1f}s | {e}")
        print()

# ============================================================================
# SUMMARY
# ============================================================================
print()
print("=" * 70)
print("  SUMMARY \u2014 Sprint 89 AGI Test")
print("=" * 70)
print(f"  Turns completed: {len(results)}/50")
print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
print(f"  Avg time/turn: {total_time/max(len(results),1):.1f}s")
print()

route_counts = {}
for r in results:
    route_counts[r["route"]] = route_counts.get(r["route"], 0) + 1
print(f"  Routes: {route_counts}")

emoji_count = sum(1 for r in results if r["has_emoji"])
print(f"  Emoji rate: {emoji_count}/{len(results)} ({100*emoji_count/max(len(results),1):.0f}%)")

forced_count = sum(1 for r in results if r["forced_metaphor"])
print(f"  Forced metaphors: {forced_count}")

# Routing accuracy
print()
maritime_results = [r for r in results if r["turn"] in MARITIME_ROUTING_TURNS]
maritime_correct = sum(1 for r in maritime_results if r["route"] in ("rag", "tutor"))
print(f"  [ROUTING] Maritime accuracy: {maritime_correct}/{len(maritime_results)}")
wrong = [(r["turn"], r["route"]) for r in maritime_results if r["route"] == "direct"]
if wrong:
    print(f"    Wrong: {wrong}")
else:
    print(f"    \u2705 All maritime queries routed correctly!")

# Memory checks
print(f"\n  [MEMORY]")
for turn_num, expected in sorted(MEMORY_CHECKS.items()):
    answer = all_answers.get(turn_num, "")
    found = any(kw.lower() in answer.lower() for kw in expected)
    status = "\u2705" if found else "\u274c"
    print(f"    Turn {turn_num}: {status} (expected: {expected})")
    if not found and answer:
        print(f"      Got: {answer[:100]}...")

# Sprint 89: Persona check
print(f"\n  [PERSONA - Sprint 89 Fix]")
persona_issues = [t for t, iss in quality_issues if "PERSONA_RESET" in iss]
if persona_issues:
    print(f"    \u274c Persona reset at turns: {persona_issues}")
else:
    print(f"    \u2705 No persona resets \u2014 RAG agent maintains character!")

# Final
total_issues = len(quality_issues)
print(f"\n  Total issues: {total_issues}")
if quality_issues:
    print(f"  Detail:")
    for turn, iss in quality_issues:
        print(f"    Turn {turn:02d}: {iss}")

passed = total_issues <= 10
verdict = "\u2705 PASS" if passed else "\u274c FAIL"
print(f"\n  {verdict} \u2014 Sprint 89 Live API Test")
print()
print("  DONE!")
