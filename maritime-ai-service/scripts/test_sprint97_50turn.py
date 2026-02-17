"""
Sprint 97: 50-Turn Live AGI Test — Wiii Character Tools + Full System
Tests: Routing, Memory, Identity, Character Tools, Response Quality

Scoring:
- Routing: correct agent_type for each message category
- Memory: Wiii remembers personal info across turns
- Identity: Wiii maintains personality (friendly, Vietnamese, no persona reset)
- Character: DB blocks get populated via tool calls
- Quality: Responses are helpful and natural
"""
import io, sys, json, time, subprocess, requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000/api/v1"
USER_ID = "agi-test-s97"
SESSION_ID = "agi-sess-s97"
HEADERS = {
    "X-API-Key": "local-dev-key",
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
    "X-Role": "student",
    "Content-Type": "application/json",
}

# 50 messages covering all categories
MESSAGES = [
    # --- Block 1: Introduction & Personal Info (1-5) ---
    {"msg": "Xin chao! Minh la Khanh, rat vui duoc gap ban!", "cat": "greeting", "expect_route": "memory"},
    {"msg": "Minh 22 tuoi, dang la sinh vien nam 4 nganh Hang hai tai Truong DH Hang Hai Viet Nam", "cat": "personal", "expect_route": "memory"},
    {"msg": "Que minh o Hai Phong, thanh pho bien rat dep", "cat": "personal", "expect_route": "memory"},
    {"msg": "So thich cua minh la doc sach va choi guitar", "cat": "personal", "expect_route": "memory"},
    {"msg": "Minh co mot chu meo ten la Miu, no rat dang yeu", "cat": "personal", "expect_route": "memory"},

    # --- Block 2: Maritime Domain (6-15) ---
    {"msg": "Ban oi, giai thich cho minh ve quy tac COLREG so 5 di", "cat": "maritime", "expect_route": "rag"},
    {"msg": "SOLAS la gi va tai sao no quan trong?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Radar tren tau hoat dong nhu the nao?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "PSC inspection la gi? Tau bi luu giu khi nao?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "ECDIS khac gi so voi hai do giay truyen thong?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Giai thich ve he thong GMDSS tren tau", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Lam sao de tinh tonnage cua tau?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Compass tren tau co may loai? La ban tu va la ban con quay khac gi nhau?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "VHF channel 16 dung de lam gi?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Khi nao can phat tin hieu Mayday?", "cat": "maritime", "expect_route": "rag"},

    # --- Block 3: Memory Recall (16-20) ---
    {"msg": "Ban con nho ten minh khong?", "cat": "memory_recall", "expect_route": "memory"},
    {"msg": "Minh hoc nganh gi nhi?", "cat": "memory_recall", "expect_route": "memory"},
    {"msg": "Minh o dau vay?", "cat": "memory_recall", "expect_route": "memory"},
    {"msg": "So thich cua minh la gi?", "cat": "memory_recall", "expect_route": "memory"},
    {"msg": "Meo cua minh ten la gi?", "cat": "memory_recall", "expect_route": "memory"},

    # --- Block 4: Off-topic / General (21-30) ---
    {"msg": "Cach nau com tam ngon nhat la gi?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Theo ban, AI se thay the con nguoi khong?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Hom nay troi mua qua, minh buon lam", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Ban biet gi ve lich su Viet Nam khong?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Minh dang can hoc tieng Anh, co meo gi khong?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Guitar co kho hoc khong ban?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Mua xuan o Hai Phong dep lam ban oi!", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Ban nghi gi ve du hoc?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Lam the nao de tap trung hoc tot hon?", "cat": "off_topic", "expect_route": "direct"},
    {"msg": "Ban co thich am nhac khong?", "cat": "off_topic", "expect_route": "direct"},

    # --- Block 5: More Maritime (31-40) ---
    {"msg": "Drill abandon ship duoc thuc hien nhu the nao?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "AIS la gi va no giup gi cho an toan hang hai?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "DWT va GT khac nhau nhu the nao?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Quy tac COLREG so 7 ve danh gia nguy co va chong?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "MARPOL Annex I noi ve van de gi?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Cach su dung phan hoi radar de tranh va?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Nguyen tac hoat dong cua gyro compass?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "He thong cuu hoa tren tau gom nhung gi?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "ISM Code la gi? Tai sao can co SMS?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Khi tau gap bao, thuyen truong can lam gi?", "cat": "maritime", "expect_route": "rag"},

    # --- Block 6: Personal sharing + Farewell (41-50) ---
    {"msg": "Minh vua dat diem cao mon Luat Hang hai, vui qua!", "cat": "personal", "expect_route": "memory"},
    {"msg": "Thang toi minh se di thuc tap tren tau", "cat": "personal", "expect_route": "memory"},
    {"msg": "Minh muon tro thanh thuyen truong trong tuong lai", "cat": "personal", "expect_route": "memory"},
    {"msg": "Ban day minh nhieu dieu huu ich lam, cam on ban nhe!", "cat": "feedback", "expect_route": "direct"},
    {"msg": "Minh rat thich noi chuyen voi ban, ban la nguoi ban tot!", "cat": "feedback", "expect_route": "direct"},
    {"msg": "Ngay mai minh co bai kiem tra COLREG, chuc minh may man nhe!", "cat": "personal", "expect_route": "memory"},
    {"msg": "Gio minh phai di hoc roi, hen gap lai ban nhe!", "cat": "farewell", "expect_route": "direct"},
    {"msg": "A quen, truoc khi di, cho minh hoi: quy tac COLREG so 13 la gi?", "cat": "maritime", "expect_route": "rag"},
    {"msg": "Ok cam on ban! Minh ghi chu lai de hoc. Bye bye!", "cat": "farewell", "expect_route": "direct"},
    {"msg": "Lan sau minh se hoi them ve SOLAS Chapter III nhe. Tam biet!", "cat": "farewell", "expect_route": "direct"},
]

# --- Scoring ---
scores = {
    "routing_correct": 0,
    "routing_total": 0,
    "memory_recall_pass": 0,
    "memory_recall_total": 0,
    "identity_ok": 0,
    "identity_total": 0,
    "response_ok": 0,
    "response_total": 0,
}

MEMORY_FACTS = {
    "Khánh": ["Khanh", "Khánh"],
    "Hàng hải": ["hang hai", "Hàng hải", "hàng hải", "Hang hai"],
    "Hải Phòng": ["Hai Phong", "Hải Phòng", "hải phòng"],
    "guitar": ["guitar", "Guitar", "ghi-ta", "ghita"],
    "Miu": ["Miu", "miu", "Míu"],
}

IDENTITY_MARKERS = ["Wiii", "wiii", "mình", "bạn"]
REFUSAL_MARKERS = ["không thể", "xin lỗi, tôi không", "ngoài phạm vi", "tôi là AI"]

print("=" * 70)
print("  Sprint 97: 50-Turn Live AGI Test")
print("  User: Khanh | Session: agi-sess-s97")
print("=" * 70)

results = []
for i, m in enumerate(MESSAGES):
    turn = i + 1
    print(f"\n[{turn:02d}/50] ({m['cat']}) {m['msg'][:60]}...")

    body = {"message": m["msg"], "user_id": USER_ID, "role": "student"}
    try:
        start = time.time()
        r = requests.post(f"{BASE}/chat", headers=HEADERS, json=body, timeout=90)
        elapsed = time.time() - start
        data = r.json()

        if "data" not in data:
            print(f"  ERROR: {json.dumps(data, ensure_ascii=False)[:200]}")
            results.append({"turn": turn, "error": True})
            continue

        d = data["data"]
        meta = d.get("metadata", {})
        agent = meta.get("agent_type", "unknown")
        answer = d.get("answer", "")
        tools = meta.get("tools_used", [])

        results.append({
            "turn": turn,
            "cat": m["cat"],
            "agent": agent,
            "expect": m["expect_route"],
            "answer": answer,
            "tools": tools,
            "time": round(elapsed, 1),
        })

        # Routing score
        scores["routing_total"] += 1
        route_ok = False
        if m["expect_route"] == "rag" and agent in ("rag", "tutor", "rag_agent"):
            route_ok = True
        elif m["expect_route"] == "memory" and agent in ("memory", "memory_agent"):
            route_ok = True
        elif m["expect_route"] == "direct" and agent in ("direct", "direct_response", ""):
            route_ok = True
        elif agent == m["expect_route"]:
            route_ok = True
        if route_ok:
            scores["routing_correct"] += 1

        # Memory recall score
        if m["cat"] == "memory_recall":
            scores["memory_recall_total"] += 1
            for key, variants in MEMORY_FACTS.items():
                if any(v in m["msg"] for v in [key.lower(), key]):
                    if any(v in answer for v in variants):
                        scores["memory_recall_pass"] += 1
                    break

        # Identity score
        scores["identity_total"] += 1
        has_identity = any(mk in answer for mk in IDENTITY_MARKERS)
        no_refusal = not any(rf in answer for rf in REFUSAL_MARKERS)
        if has_identity and no_refusal:
            scores["identity_ok"] += 1

        # Response quality
        scores["response_total"] += 1
        if len(answer) > 20 and no_refusal:
            scores["response_ok"] += 1

        status = "OK" if route_ok else "WRONG"
        route_str = f"[{agent}]" if route_ok else f"[{agent} != {m['expect_route']}]"
        print(f"  {status} {route_str} ({elapsed:.1f}s) {answer[:120]}...")

    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results.append({"turn": turn, "error": True})

    # Small delay to avoid rate limiting
    time.sleep(0.5)

# --- Summary ---
print("\n" + "=" * 70)
print("  RESULTS SUMMARY")
print("=" * 70)

routing_pct = scores["routing_correct"] / max(scores["routing_total"], 1) * 100
memory_pct = scores["memory_recall_pass"] / max(scores["memory_recall_total"], 1) * 100
identity_pct = scores["identity_ok"] / max(scores["identity_total"], 1) * 100
quality_pct = scores["response_ok"] / max(scores["response_total"], 1) * 100

print(f"\n  Routing:   {scores['routing_correct']}/{scores['routing_total']} ({routing_pct:.0f}%)")
print(f"  Memory:    {scores['memory_recall_pass']}/{scores['memory_recall_total']} ({memory_pct:.0f}%)")
print(f"  Identity:  {scores['identity_ok']}/{scores['identity_total']} ({identity_pct:.0f}%)")
print(f"  Quality:   {scores['response_ok']}/{scores['response_total']} ({quality_pct:.0f}%)")

# Routing breakdown
print(f"\n  Routing breakdown:")
for cat in ["greeting", "personal", "maritime", "memory_recall", "off_topic", "feedback", "farewell"]:
    cat_results = [r for r in results if r.get("cat") == cat and not r.get("error")]
    if cat_results:
        correct = sum(1 for r in cat_results if (
            (r["expect"] == "rag" and r["agent"] in ("rag", "tutor", "rag_agent")) or
            (r["expect"] == "memory" and r["agent"] in ("memory", "memory_agent")) or
            (r["expect"] == "direct" and r["agent"] in ("direct", "direct_response", "")) or
            r["agent"] == r["expect"]
        ))
        print(f"    {cat:15s}: {correct}/{len(cat_results)}")

# Wrong routes
wrong = [r for r in results if not r.get("error") and not (
    (r["expect"] == "rag" and r["agent"] in ("rag", "tutor", "rag_agent")) or
    (r["expect"] == "memory" and r["agent"] in ("memory", "memory_agent")) or
    (r["expect"] == "direct" and r["agent"] in ("direct", "direct_response", "")) or
    r["agent"] == r["expect"]
)]
if wrong:
    print(f"\n  Wrong routes:")
    for w in wrong:
        print(f"    Turn {w['turn']:02d}: got [{w['agent']}] expected [{w['expect']}]")

# Average response time
times = [r["time"] for r in results if "time" in r]
if times:
    print(f"\n  Avg response time: {sum(times)/len(times):.1f}s")
    print(f"  Min: {min(times):.1f}s | Max: {max(times):.1f}s")

# --- Character DB Check ---
print(f"\n{'='*70}")
print("  CHARACTER STATE (DB)")
print("=" * 70)

result = subprocess.run(
    ["docker", "exec", "wiii-postgres", "psql", "-U", "wiii", "-d", "wiii_ai",
     "-c", "SELECT label, length(content) as chars, version, content FROM wiii_character_blocks ORDER BY label;"],
    capture_output=True, text=True, encoding="utf-8"
)
print(result.stdout)

result2 = subprocess.run(
    ["docker", "exec", "wiii-postgres", "psql", "-U", "wiii", "-d", "wiii_ai",
     "-c", "SELECT experience_type, left(content, 80) as content, user_id FROM wiii_experiences ORDER BY created_at DESC LIMIT 10;"],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"  Recent experiences:")
print(result2.stdout)

# Final verdict
print("=" * 70)
all_pass = routing_pct >= 70 and memory_pct >= 60 and identity_pct >= 80 and quality_pct >= 90
print(f"  VERDICT: {'PASS' if all_pass else 'NEEDS REVIEW'}")
print(f"  (Routing >= 70%, Memory >= 60%, Identity >= 80%, Quality >= 90%)")
print("=" * 70)
