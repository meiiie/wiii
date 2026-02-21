"""Sprint 164: Parallel Dispatch + Aggregator — Full Integration Test"""
import requests
import json
import time

msg = (
    "Tra cứu thông tin chi tiết về quy tắc COLREGs Phần B "
    "và giải thích cho tôi cách áp dụng trong thực tế hàng hải. "
    "Phân tích các tình huống tránh va chạm quan trọng nhất."
)
session_id = f"test-sprint164-{int(time.time())}"
payload = {
    "message": msg,
    "user_id": "test-user-164",
    "role": "student",
    "session_id": session_id,
}
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-user-164",
    "X-Session-ID": session_id,
    "X-Role": "student",
}

print("=" * 80)
print("  Sprint 164: Parallel Dispatch + Aggregator — LIVE TEST")
print("=" * 80)
print(f"  Query: {msg}")
print(f"  Length: {len(msg)} chars (threshold >= 80)")
print()

resp = requests.post(
    "http://localhost:8000/api/v1/chat/stream/v3",
    json=payload,
    headers=headers,
    stream=True,
    timeout=120,
)

all_events = []
current_event_type = None
answer_text = ""
t0 = time.time()

for line in resp.iter_lines(decode_unicode=True):
    if not line:
        continue
    if line.startswith("event:"):
        current_event_type = line.split(":", 1)[1].strip()
        continue
    if line.startswith("data:"):
        try:
            d = json.loads(line[6:])
        except Exception:
            continue

        elapsed = round(time.time() - t0, 1)
        node = d.get("node", "") or ""
        content = d.get("content", "")
        details = d.get("details")

        if current_event_type == "answer":
            answer_text += str(content)
            continue

        all_events.append({
            "time": elapsed,
            "event": current_event_type,
            "node": node,
            "content": str(content)[:100] if content else "",
            "details": details,
        })

total_time = round(time.time() - t0, 1)

# ── Timeline ──
print("  SSE EVENT TIMELINE")
print("  " + "-" * 76)
print(f"  {'Time':>6} | {'Event':<18} | {'Node':<22} | Content")
print("  " + "-" * 76)
for ev in all_events:
    c = ev["content"][:55]
    det = ""
    if ev["details"]:
        det = " +details"
    print(f"  {ev['time']:>5}s | {ev['event']:<18} | {ev['node']:<22} | {c}{det}")

# ── Analysis ──
print()
print("  PARALLEL DISPATCH ANALYSIS")
print("  " + "-" * 76)

pd_events = [e for e in all_events if e["node"] == "parallel_dispatch"]
rag_events = [e for e in all_events if e["node"] == "rag"]
tutor_events = [e for e in all_events if e["node"] == "tutor"]
agg_events = [e for e in all_events if e["node"] == "aggregator"]
synth_events = [e for e in all_events if e["node"] == "synthesizer"]

# 1. Parallel dispatch
triggered = len(pd_events) > 0
print(f"  1. Parallel Dispatch triggered:  {'YES' if triggered else 'NO'} ({len(pd_events)} event(s))")

# 2. RAG worker
print(f"  2. RAG worker events:            {len(rag_events)}")
for e in rag_events:
    print(f"     - [{e['time']}s] {e['event']}: {e['content'][:55]}")

# 3. Tutor worker
print(f"  3. Tutor worker events:          {len(tutor_events)}")
for e in tutor_events:
    print(f"     - [{e['time']}s] {e['event']}: {e['content'][:55]}")

# 4. Aggregator
print(f"  4. Aggregator events:            {len(agg_events)}")
for e in agg_events:
    det = json.dumps(e["details"], ensure_ascii=False)[:100] if e["details"] else "none"
    print(f"     - [{e['time']}s] {e['event']}: {e['content'][:55]}")
    if e["details"]:
        print(f"       details: {det}")

# 5. Synthesizer
print(f"  5. Synthesizer events:           {len(synth_events)}")

# 6. Answer
print(f"  6. Answer length:                {len(answer_text)} chars")

# 7. Timing
print(f"  7. Total time:                   {total_time}s")

# 8. Parallelism check
if rag_events and tutor_events:
    rag_start = rag_events[0]["time"]
    tutor_start = tutor_events[0]["time"]
    rag_end = rag_events[-1]["time"]
    tutor_end = tutor_events[-1]["time"]
    overlap = min(rag_end, tutor_end) - max(rag_start, tutor_start)
    parallel_ok = overlap > 0
    label = "PARALLEL" if parallel_ok else "SEQUENTIAL"
    print(f"  8. RAG window:   {rag_start}s — {rag_end}s")
    print(f"     Tutor window: {tutor_start}s — {tutor_end}s")
    print(f"     Overlap:      {round(overlap, 1)}s  ({label})")

# ── Verdict ──
print()
print("  " + "=" * 76)
checks = {
    "parallel_dispatch triggered": triggered,
    "RAG worker >= 2 events": len(rag_events) >= 2,
    "Tutor worker >= 2 events": len(tutor_events) >= 2,
    "Aggregator >= 1 event": len(agg_events) >= 1,
    "Aggregator has details": any(e["details"] for e in agg_events),
    "Answer generated (>50 chars)": len(answer_text) > 50,
}
all_pass = True
for name, ok in checks.items():
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] {name}")

print()
if all_pass:
    print("  >>> SPRINT 164 PARALLEL DISPATCH: ALL CHECKS PASSED <<<")
else:
    print("  >>> SOME CHECKS FAILED — see above <<<")
print("  " + "=" * 76)
print()
print(f"  Answer preview ({len(answer_text)} chars):")
print(f"  {answer_text[:300]}...")
