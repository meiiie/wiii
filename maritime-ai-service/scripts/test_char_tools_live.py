"""Sprint 97 Live Test: Check if Wiii uses character tools in DIRECT node."""
import io, sys, json, requests, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000/api/v1"
HEADERS = {
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-char-97",
    "X-Role": "student",
    "Content-Type": "application/json",
}

tests = [
    {
        "label": "Test 1: Personal sharing (DIRECT - should trigger character note)",
        "session": "test-direct-char-1",
        "message": "Minh rat thich hoc ve thien van hoc va vu tru, minh mo uoc duoc lam viec o NASA",
    },
    {
        "label": "Test 2: Funny moment (DIRECT - should trigger log_experience)",
        "session": "test-direct-char-2",
        "message": "Haha hom qua minh thi truot mon ly, buon qua! Nhung hom nay lai vui vi duoc noi chuyen voi ban",
    },
    {
        "label": "Test 3: General knowledge (DIRECT - unlikely to trigger tools)",
        "session": "test-direct-char-3",
        "message": "Theo ban, mau nao la mau dep nhat?",
    },
]

print("=" * 60)
print("Sprint 97 Live Test: Character Tools Activation")
print("DB tables: wiii_character_blocks + wiii_experiences")
print("=" * 60)

for t in tests:
    print(f"\n{'─'*60}")
    print(f"  {t['label']}")
    print(f"  Query: {t['message']}")
    print(f"{'─'*60}")

    headers = {**HEADERS, "X-Session-ID": t["session"]}
    body = {
        "message": t["message"],
        "user_id": "test-char-97",
        "role": "student",
    }

    try:
        r = requests.post(f"{BASE}/chat", headers=headers, json=body, timeout=90)
        data = r.json()

        if "data" in data:
            d = data["data"]
            meta = d.get("metadata", {})
            print(f"  agent_type: {meta.get('agent_type', '?')}")
            print(f"  tools_used: {meta.get('tools_used', [])}")
            answer = d.get("answer", "")
            print(f"  answer: {answer[:400]}")
        else:
            print(f"  ERROR: {json.dumps(data, ensure_ascii=False)[:500]}")

    except Exception as e:
        print(f"  EXCEPTION: {e}")

    time.sleep(1)

# Check DB for any character data written
print(f"\n{'='*60}")
print("Checking DB for character data...")
print("=" * 60)

import subprocess
result = subprocess.run(
    ["docker", "exec", "wiii-postgres", "psql", "-U", "wiii", "-d", "wiii_ai",
     "-c", "SELECT label, length(content) as content_len, content FROM wiii_character_blocks WHERE content != '';"],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"  Character blocks with content:\n{result.stdout}")

result2 = subprocess.run(
    ["docker", "exec", "wiii-postgres", "psql", "-U", "wiii", "-d", "wiii_ai",
     "-c", "SELECT experience_type, content, user_id, created_at FROM wiii_experiences ORDER BY created_at DESC LIMIT 5;"],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"  Recent experiences:\n{result2.stdout}")
