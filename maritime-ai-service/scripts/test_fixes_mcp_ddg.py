"""Test MCP auth fix + DuckDuckGo region fix."""
import io, sys, json, requests, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000"

# =====================================================================
# Test 1: DuckDuckGo region=vn-vi
# =====================================================================
print("=" * 60)
print("  Test 1: DuckDuckGo region=vn-vi")
print("=" * 60)

result = subprocess.run(
    ["docker", "exec", "wiii-app", "python", "-c", """
import json, warnings
warnings.filterwarnings('ignore')
from duckduckgo_search import DDGS
results = DDGS().text('IMO 2026 maritime quy dinh moi', max_results=5, region='vn-vi', safesearch='moderate', backend='auto')
for r in results:
    print(json.dumps({'title': r['title'][:80], 'url': r['href'][:120], 'body': r['body'][:100]}, ensure_ascii=False))
"""],
    capture_output=True, text=True, encoding="utf-8", timeout=30
)

if result.stdout.strip():
    print("  Results:")
    for line in result.stdout.strip().split("\n"):
        try:
            r = json.loads(line)
            print(f"    - {r['title']}")
            print(f"      {r['body'][:80]}")
            print(f"      {r['url']}")
        except:
            print(f"    {line}")

    # Check if results are in Vietnamese or English (not Chinese/Japanese)
    all_text = result.stdout
    has_vn = any(c in all_text for c in "àáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ")
    has_en = any(w in all_text.lower() for w in ["maritime", "imo", "the", "and", "for"])
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in all_text)  # Chinese
    has_jp = any('\u3040' <= c <= '\u30ff' for c in all_text)  # Japanese

    print(f"\n  Language check:")
    print(f"    Vietnamese: {'YES' if has_vn else 'no'}")
    print(f"    English: {'YES' if has_en else 'no'}")
    print(f"    Chinese: {'YES (bad)' if has_cjk else 'no (good)'}")
    print(f"    Japanese: {'YES (bad)' if has_jp else 'no (good)'}")
    print(f"  Region fix: {'PASS' if (has_vn or has_en) and not has_cjk and not has_jp else 'CHECK'}")
else:
    print(f"  stderr: {result.stderr[:300]}")

# =====================================================================
# Test 2: MCP auth header forwarding
# =====================================================================
print(f"\n{'=' * 60}")
print("  Test 2: MCP Tool Call with Auth Headers")
print("=" * 60)

session = requests.Session()

def parse_mcp(r):
    body = r.text.strip()
    for line in body.split("\n"):
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except:
                pass
    try:
        return json.loads(body)
    except:
        return None

# Step 1: Initialize
r = session.post(f"{BASE}/mcp", headers={
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}, json={
    "jsonrpc": "2.0", "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-auth", "version": "1.0"},
    },
    "id": 1,
}, timeout=10)

data = parse_mcp(r)
mcp_session = r.headers.get("Mcp-Session-Id", "")
print(f"  Init: {'OK' if data and 'result' in data else 'FAIL'}")

# Step 2: Notify initialized
mcp_h = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    # Auth headers that should be forwarded to tool calls
    "X-API-Key": "local-dev-key",
    "X-User-ID": "mcp-test-user",
    "X-Session-ID": "mcp-test-sess",
    "X-Role": "student",
}
if mcp_session:
    mcp_h["Mcp-Session-Id"] = mcp_session

session.post(f"{BASE}/mcp", headers=mcp_h, json={
    "jsonrpc": "2.0", "method": "notifications/initialized",
}, timeout=5)

# Step 3: Call chat tool WITH auth headers
print(f"  Calling chat tool with X-API-Key header...")
r = session.post(f"{BASE}/mcp", headers=mcp_h, json={
    "jsonrpc": "2.0", "method": "tools/call",
    "params": {
        "name": "chat_completion_api_v1_chat_post",
        "arguments": {
            "message": "Xin chao Wiii! Ban co khoe khong?",
            "user_id": "mcp-test-user",
            "role": "student",
        },
    },
    "id": 3,
}, timeout=60)

data = parse_mcp(r)
if data and "result" in data:
    content = data["result"].get("content", [])
    for c in content[:1]:
        text = c.get("text", "")
        # Try to parse as JSON to get answer
        try:
            resp = json.loads(text)
            answer = resp.get("data", {}).get("answer", text[:200])
            print(f"  Answer: {answer[:300]}")
            print(f"  MCP Auth: PASS (tool call succeeded)")
        except:
            print(f"  Raw: {text[:300]}")
            if "401" in text or "Authentication" in text:
                print(f"  MCP Auth: FAIL (still 401)")
            else:
                print(f"  MCP Auth: PASS (got response)")
elif data and "error" in data:
    err = data["error"]
    msg = err.get("message", "")
    if "401" in msg or "Authentication" in msg:
        print(f"  Error: {msg[:200]}")
        print(f"  MCP Auth: FAIL (401 — headers not forwarded)")
    else:
        print(f"  Error: {msg[:200]}")
else:
    print(f"  Raw: {r.text[:300]}")

# =====================================================================
# Test 3: Knowledge stats via MCP (no auth needed for GET)
# =====================================================================
print(f"\n{'=' * 60}")
print("  Test 3: MCP Tool — Knowledge Stats")
print("=" * 60)

r = session.post(f"{BASE}/mcp", headers=mcp_h, json={
    "jsonrpc": "2.0", "method": "tools/call",
    "params": {
        "name": "get_statistics_api_v1_knowledge_stats_get",
        "arguments": {},
    },
    "id": 4,
}, timeout=15)

data = parse_mcp(r)
if data and "result" in data:
    content = data["result"].get("content", [])
    for c in content[:1]:
        text = c.get("text", "")[:300]
        print(f"  Response: {text}")
    print(f"  Stats tool: PASS")
elif data:
    print(f"  Response: {json.dumps(data, ensure_ascii=False)[:300]}")
else:
    print(f"  Raw: {r.text[:300]}")

print(f"\n{'=' * 60}")
print("  DONE")
print("=" * 60)
