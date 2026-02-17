"""Quick test script for off-topic detection (Sprint 80)."""
import requests
import json
import sys
import io
import uuid

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "local-dev-key", "Content-Type": "application/json"}

tests = [
    ("OFF-TOPIC: tren tau doi qua", "trên tàu đói quá thì làm gì"),
    ("OFF-TOPIC: nau com tren tau", "nấu cơm trên tàu như thế nào"),
    ("OFF-TOPIC: programming", "Python là ngôn ngữ lập trình gì?"),
    ("OFF-TOPIC: weather", "hôm nay thời tiết Hà Nội thế nào?"),
    ("ON-TOPIC: COLREGs", "Điều 15 COLREGs nói gì?"),
    ("ON-TOPIC: tau thuy ao phao", "tàu thủy phải mang bao nhiêu áo phao?"),
    ("ON-TOPIC: hang hai", "quy tắc hàng hải phòng ngừa va chạm trên biển"),
]

passed = 0
failed = 0

for label, query in tests:
    is_off_topic = label.startswith("OFF-TOPIC")
    # Unique session per test to avoid contamination
    session_id = str(uuid.uuid4())
    user_id = f"test-offtopic-{uuid.uuid4().hex[:8]}"

    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"Query: {query}")
    print("-" * 60)
    try:
        body = json.dumps({
            "message": query,
            "user_id": user_id,
            "session_id": session_id,
            "role": "student",
        }, ensure_ascii=False)
        r = requests.post(
            f"{BASE}/chat",
            headers=HEADERS,
            data=body.encode("utf-8"),
            timeout=60,
        )
        if r.status_code == 200:
            raw = r.json()
            # API wraps in {"status": "success", "data": {...}}
            data = raw.get("data", raw)
            response = data.get("answer", data.get("response", ""))[:400]
            metadata = data.get("metadata", {})
            routing = metadata.get("routing_metadata", {})
            method = routing.get("method", "?")
            agent = metadata.get("agent", "?")
            intent = routing.get("intent", "?")
            conf = routing.get("confidence", "?")

            print(f"Route: {method} -> {agent}")
            print(f"Intent: {intent}, Conf: {conf}")
            print(f"Response: {response}")
            if not response:
                print(f"RAW: {json.dumps(raw, ensure_ascii=False)[:500]}")

            # Check correctness
            if is_off_topic:
                # Off-topic should route to direct and contain redirection
                if agent == "direct" or "chuyên" in response.lower() or "hàng hải" in response.lower():
                    print("RESULT: PASS (correctly handled off-topic)")
                    passed += 1
                else:
                    print("RESULT: FAIL (off-topic query got domain answer!)")
                    failed += 1
            else:
                # On-topic should get a substantive answer
                if len(response) > 50:
                    print("RESULT: PASS (on-topic got substantive answer)")
                    passed += 1
                else:
                    print("RESULT: FAIL (on-topic got too short answer)")
                    failed += 1
        else:
            print(f"ERROR {r.status_code}: {r.text[:200]}")
            failed += 1
    except Exception as e:
        print(f"FAILED: {e}")
        failed += 1

print(f"\n{'='*60}")
print(f"Results: {passed} PASSED, {failed} FAILED out of {len(tests)} tests")
print("Done!")
