"""
200-message sequential conversation test.
Tests: memory persistence, context compaction, routing, persona consistency.
Single session, single user — simulates real browser usage.
"""
import requests
import json
import time
import sys
import unicodedata

sys.stdout.reconfigure(encoding='utf-8')


def strip_diacritics(text):
    """Remove Vietnamese diacritics for fuzzy matching."""
    # Handle đ/Đ (d with stroke) — not decomposed by NFKD
    text = text.replace('đ', 'd').replace('Đ', 'D')
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

BASE = "http://localhost:8000/api/v1"
SESSION_ID = "memory-stress-test-001"
USER_ID = "hung-test-user"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": "local-dev-key",
    "X-User-ID": USER_ID,
    "X-Session-ID": SESSION_ID,
}

stats = {
    "total": 0, "success": 0, "fail": 0,
    "routes": {}, "total_time": 0,
    "memory_pass": 0, "memory_fail": 0,
    "memory_details": [],
}


def chat(msg):
    try:
        resp = requests.post(f"{BASE}/chat", headers=HEADERS, json={
            "message": msg,
            "user_id": USER_ID,
            "role": "student",
            "session_id": SESSION_ID,
        }, timeout=120)
        stats["total"] += 1
        if resp.status_code != 200:
            stats["fail"] += 1
            return f"ERROR {resp.status_code}", "error", 0
        data = resp.json()
        answer = data.get("data", {}).get("answer", "NO ANSWER")
        meta = data.get("metadata", {})
        proc_time = meta.get("processing_time", 0)
        stats["total_time"] += proc_time
        steps = meta.get("reasoning_trace", {}).get("steps", [])
        route = steps[0].get("details", {}).get("routed_to", "?") if steps else "?"
        stats["routes"][route] = stats["routes"].get(route, 0) + 1
        stats["success"] += 1
        return answer, route, proc_time
    except Exception as e:
        stats["total"] += 1
        stats["fail"] += 1
        return f"EXCEPTION: {e}", "error", 0


def check_memory(answer, keywords, label):
    # Strip Vietnamese diacritics for fuzzy matching
    answer_norm = strip_diacritics(answer.lower())
    found = [kw for kw in keywords if strip_diacritics(kw.lower()) in answer_norm]
    missing = [kw for kw in keywords if strip_diacritics(kw.lower()) not in answer_norm]
    passed = len(found) >= len(keywords) // 2 + 1  # majority match
    if passed:
        stats["memory_pass"] += 1
    else:
        stats["memory_fail"] += 1
    status = "PASS" if passed else "FAIL"
    stats["memory_details"].append({
        "label": label, "status": status,
        "found": found, "missing": missing,
    })
    print(f"    >>> MEMORY [{label}]: {status} (found: {found}, missing: {missing})")
    return passed


# Build 200 messages
PLAN = []

# Phase 1: Introduction (1-5)
PLAN.append(("Xin chao, minh la Hung, sinh vien nam 3 Dai hoc Hang hai Viet Nam", None))
PLAN.append(("Minh que Hai Phong, hien dang o ky tuc xa", None))
PLAN.append(("Mon yeu thich cua minh la Luat Hang hai Quoc te", None))
PLAN.append(("Minh cung thich choi bong da vao cuoi tuan", None))
PLAN.append(("Ban nho duoc gi ve minh?", ["Hung", "Hai Phong", "hang hai"]))

# Phase 2: COLREGs deep dive (6-20)
colregs = [
    "Giai thich Rule 5 ve viec canh gioi",
    "Rule 6 noi ve toc do an toan",
    "Rule 7 la gi? Xac dinh nguy co va cham",
    "Rule 8 quy dinh hanh dong tranh va",
    "Rule 9 ve luong hep",
    "Rule 10 he thong phan luong giao thong",
    "Rule 13 ve tinh huong vuot",
    "Rule 14 tinh huong doi huong",
    "Rule 15 tinh huong cat huong",
    "So sanh Rule 14 va Rule 15",
    "Rule 16 hanh dong tau nhuong duong",
    "Rule 17 hanh dong tau duoc nhuong",
    "Rule 18 trach nhiem giua cac loai tau",
    "Rule 19 tam nhin han che",
    "Tong hop cac Rule quan trong nhat trong COLREGs",
]
for q in colregs:
    PLAN.append((q, None))

# Phase 3: Memory check #1 (21)
PLAN.append(("Ban con nho minh la ai khong? Que o dau?", ["Hung", "Hai Phong"]))

# Phase 4: SOLAS (22-40)
solas = [
    "SOLAS la gi?", "SOLAS Chapter II-1", "SOLAS Chapter II-2 phong chay",
    "SOLAS Chapter III cuu sinh", "GMDSS la gi?", "SOLAS Chapter V an toan",
    "ISM Code la gi?", "ISPS Code la gi?", "So sanh ISM va ISPS",
    "VDR la gi?", "AIS hoat dong the nao?", "ECDIS bat buoc khong?",
    "LRIT system la gi?", "BNWAS la gi?", "Safe Manning la gi?",
    "Damage Stability la gi?", "SOLAS sua doi bao nhieu lan?",
    "Titanic va SOLAS co lien quan gi?", "Certificate theo SOLAS",
]
for q in solas:
    PLAN.append((q, None))

# Phase 5: Memory check #2 (41)
PLAN.append(("Nhac lai giup: minh hoc truong gi, mon thich la gi?", ["hang hai", "luat"]))

# Phase 6: MARPOL (42-60)
marpol = [
    "MARPOL 73/78 la gi?", "Annex I ve dau", "Annex II chat long doc",
    "Annex III hang nguy hiem", "Annex IV nuoc thai", "Annex V rac thai",
    "Annex VI khi thai", "Special Areas la gi?", "SOPEP plan la gi?",
    "Oil Record Book la gi?", "Ballast Water Convention la gi?",
    "Scrubber la gi?", "ECA va SECA la gi?", "IMO 2020 Sulphur Cap",
    "EEDI va EEXI la gi?", "CII rating la gi?",
    "Carbon Intensity Indicator", "Green Shipping la gi?", "PSSA la gi?",
]
for q in marpol:
    PLAN.append((q, None))

# Phase 7: Memory check #3 (61)
PLAN.append(("Minh la ai, que dau, hoc gi? Nhac lai het giup!",
             ["Hung", "Hai Phong", "hang hai"]))

# Phase 8: General maritime (62-100)
general = [
    "IMO la gi?", "Flag State la gi?", "Port State Control la gi?",
    "PSC inspection kiem tra gi?", "Detention la gi?", "Class Society la gi?",
    "IACS la gi?", "Annual Survey la gi?", "Special Survey la gi?",
    "Docking Survey la gi?", "Certificate of Class la gi?",
    "DPA la gi?", "SMS la gi?", "DOC va SMC la gi?",
    "MLC 2006 la gi?", "ILO lien quan gi hang hai?", "STCW la gi?",
    "OOW can chung chi gi?", "Master Mariner can gi?",
    "Pilot la gi?", "VTS la gi?", "TSS la gi?",
    "STS operation la gi?", "Bunkering la gi?", "Bill of Lading la gi?",
    "Charter Party la gi?", "Voyage vs Time Charter?",
    "Demurrage la gi?", "Laytime la gi?", "NOR la gi?",
    "General Average la gi?", "P&I Club la gi?",
    "Hull & Machinery insurance la gi?", "Salvage la gi?",
    "Towage la gi?", "Pilotage la gi?",
    "Dry docking la gi?", "Ship recycling la gi?",
    "Hong Kong Convention la gi?",
]
for q in general:
    PLAN.append((q, None))

# Phase 9: Memory check #4 at msg 101
PLAN.append(("Oi nhac lai di, minh ten gi, que dau, truong nao?",
             ["Hung", "Hai Phong", "hang hai"]))

# Phase 10: Off-topic + personality (102-120)
offtopic = [
    "Hom nay troi dep khong?", "Ban thich mau gi?",
    "Ke chuyen vui di", "Python hay JavaScript?",
    "AI thay the thuy thu duoc khong?", "Tu dong hoa hang hai",
    "MASS la gi?", "E-Navigation la gi?",
    "Starlink tren tau", "Cyber security tren tau",
    "Minh muon lam Captain", "De lam Captain can gi?",
    "Luong Captain bao nhieu?", "Cuoc song tren tau the nao?",
    "Bao nhieu thang di bien?", "Ho nghiep vu hang hai",
    "Thi bang thuyen truong o VN?", "Cuc Hang hai VN la gi?",
    "VINAMARINE la gi?",
]
for q in offtopic:
    PLAN.append((q, None))

# Phase 11: Deep memory check at 121
PLAN.append(("Ban co nho minh thich choi gi cuoi tuan khong?", ["bong da"]))

# Phase 12: Navigation tech (122-180)
tech = [
    "Radar ARPA la gi?", "True vs Relative motion?",
    "CPA va TCPA la gi?", "EBL va VRM la gi?",
    "Trial manoeuvre la gi?", "Parallel indexing la gi?",
    "GPS hoat dong the nao?", "DGPS la gi?",
    "GLONASS la gi?", "Galileo la gi?", "BeiDou la gi?",
    "ECDIS hoat dong the nao?", "Route planning tren ECDIS",
    "ENC va RNC la gi?", "Gyro compass hoat dong the nao?",
    "Compass error la gi?", "Deviation va Variation?",
    "Echo sounder la gi?", "Speed log la gi?",
    "Doppler log vs EM log?", "Navtex la gi?",
    "EPIRB la gi?", "SART la gi?", "DSC la gi?",
    "VHF Channel 16 la gi?", "Inmarsat la gi?",
    "SSAS la gi?", "AIS chi tiet?", "MMSI la gi?",
    "VDR chi tiet?", "BNWAS chi tiet?",
    "Weather routing la gi?", "Beaufort Scale la gi?",
    "Tropical Cyclone la gi?", "Monsoon la gi?",
    "Ocean current la gi?", "Tide la gi?",
    "Chart datum la gi?", "UKC la gi?",
    "Squat effect la gi?", "Bank effect la gi?",
    "Shallow water effect?", "Turning circle la gi?",
    "Pivot point la gi?", "Stopping distance la gi?",
    "Crash stop la gi?", "Williamson turn la gi?",
    "MOB procedure?", "Abandon ship procedure?",
    "Fire drill procedure?", "Enclosed space entry?",
    "Hot work permit la gi?", "Permit to work system?",
    "Risk assessment tren tau?", "Toolbox meeting la gi?",
    "Near miss reporting la gi?", "Safety culture la gi?",
    "BBS (Behavior Based Safety)?", "Root cause analysis?",
]
for q in tech:
    PLAN.append((q, None))

# Phase 13: Final memory check at ~181
PLAN.append(("Tong ket: minh la ai, que dau, truong gi, mon thich, so thich cuoi tuan?",
             ["Hung", "Hai Phong", "hang hai", "luat", "bong da"]))

# Phase 14: Fill to 200 (182-200)
final = [
    "Ship stability la gi?", "GM la gi?", "Free surface effect?",
    "Metacentric height?", "GZ curve la gi?", "Inclining test la gi?",
    "Loadline Convention?", "Plimsoll Mark la gi?",
    "TPC la gi?", "FWA la gi?",
    "DWT vs Displacement?", "Hydrostatic curves?",
    "Trim la gi?", "Shear force va bending moment?",
    "Still water vs wave bending moment?",
    "Hull stress monitoring?",
    "Cam on Wiii nhieu lam! Hoc duoc rat nhieu!",
    "Hen gap lai nhe!",
    "Tam biet Wiii!",
]
for q in final:
    PLAN.append((q, None))


print(f"=== 200-MESSAGE CONVERSATION MEMORY TEST ===")
print(f"Session: {SESSION_ID} | User: {USER_ID}")
print(f"Total planned: {len(PLAN)} messages")
print(f"Memory checkpoints: 6 (at msg 5, 21, 41, 61, 101, 121, 181)")
print("=" * 70)

start = time.time()

for i, (msg, keywords) in enumerate(PLAN):
    n = i + 1
    print(f"\n[{n:3d}/{len(PLAN)}] USER: {msg[:80]}")
    answer, route, pt = chat(msg)
    print(f"         WIII ({route}, {pt:.1f}s): {answer[:200]}...")

    if keywords:
        check_memory(answer, keywords, f"msg_{n}")

    # Progress every 20
    if n % 20 == 0:
        elapsed = time.time() - start
        avg = stats["total_time"] / max(stats["success"], 1)
        print(f"\n{'='*70}")
        print(f"  PROGRESS {n}/{len(PLAN)} | OK:{stats['success']} FAIL:{stats['fail']} | "
              f"Avg:{avg:.1f}s | Elapsed:{elapsed:.0f}s")
        print(f"  Routes: {stats['routes']}")
        print(f"  Memory: {stats['memory_pass']}P/{stats['memory_fail']}F")
        print(f"{'='*70}")

    time.sleep(0.3)

# Final report
elapsed = time.time() - start
avg = stats["total_time"] / max(stats["success"], 1)

print(f"\n\n{'='*70}")
print("FINAL REPORT")
print(f"{'='*70}")
print(f"Total:        {stats['total']} messages")
print(f"Success:      {stats['success']}")
print(f"Failed:       {stats['fail']}")
print(f"Avg latency:  {avg:.2f}s")
print(f"Total time:   {elapsed:.0f}s ({elapsed/60:.1f} min)")
print(f"Routes:       {json.dumps(stats['routes'], indent=2)}")
print(f"\nMEMORY CHECKS:")
print(f"  Passed: {stats['memory_pass']}")
print(f"  Failed: {stats['memory_fail']}")
for d in stats["memory_details"]:
    print(f"  [{d['status']}] {d['label']}: found={d['found']}, missing={d['missing']}")
print(f"{'='*70}")

# Save results
with open("scripts/test_conversation_memory_results.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)
print("Results saved to scripts/test_conversation_memory_results.json")
