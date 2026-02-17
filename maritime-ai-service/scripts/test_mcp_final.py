"""Final MCP + Web Search test."""
import io, sys, json, requests, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000"

# =====================================================================
# Test 1: MCP Full Protocol Flow
# =====================================================================
print("=" * 60)
print("  MCP Server — Full Protocol Test")
print("=" * 60)

session = requests.Session()
mcp_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def parse_mcp_response(r):
    body = r.text.strip()
    if body.startswith("event:") or body.startswith("data:"):
        for line in body.split("\n"):
            if line.startswith("data: "):
                try:
                    return json.loads(line[6:])
                except:
                    pass
    else:
        try:
            return json.loads(body)
        except:
            pass
    return None

# Step 1: Initialize
r = session.post(f"{BASE}/mcp", headers=mcp_headers, json={
    "jsonrpc": "2.0", "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "wiii-test", "version": "1.0"},
    },
    "id": 1,
}, timeout=10)

data = parse_mcp_response(r)
mcp_session = r.headers.get("Mcp-Session-Id", "")
if data and "result" in data:
    res = data["result"]
    print(f"  Server: {res.get('serverInfo', {}).get('name', '?')}")
    print(f"  Protocol: {res.get('protocolVersion', '?')}")
    print(f"  Capabilities: {list(res.get('capabilities', {}).keys())}")
    print(f"  Session: {mcp_session[:20]}...")
else:
    print(f"  Init failed: {r.text[:200]}")

# Step 2: Initialized notification
if mcp_session:
    mcp_headers["Mcp-Session-Id"] = mcp_session

session.post(f"{BASE}/mcp", headers=mcp_headers, json={
    "jsonrpc": "2.0", "method": "notifications/initialized",
}, timeout=5)

# Step 3: List tools
r = session.post(f"{BASE}/mcp", headers=mcp_headers, json={
    "jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2,
}, timeout=10)

data = parse_mcp_response(r)
if data and "result" in data:
    tools = data["result"].get("tools", [])
    print(f"\n  MCP Tools ({len(tools)}):")
    for t in tools:
        name = t.get("name", "?")
        desc = t.get("description", "")[:80]
        print(f"    {name}: {desc}")

    if tools:
        print(f"\n  MCP Server: FULLY WORKING ({len(tools)} tools exposed)")
    else:
        print(f"\n  MCP Server: Running but 0 tools (operation ID mismatch?)")
elif data:
    print(f"  Error: {json.dumps(data, ensure_ascii=False)[:300]}")
else:
    print(f"  Raw: {r.text[:300]}")

# Step 4: Call a tool if available
if data and "result" in data:
    tools = data["result"].get("tools", [])
    # Find chat tool
    chat_tool = next((t for t in tools if "chat" in t.get("name", "").lower()), None)
    if chat_tool:
        print(f"\n  Calling MCP tool: {chat_tool['name']}...")
        r = session.post(f"{BASE}/mcp", headers=mcp_headers, json={
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {
                "name": chat_tool["name"],
                "arguments": {
                    "message": "Xin chao Wiii!",
                    "user_id": "mcp-user",
                    "role": "student",
                },
            },
            "id": 3,
        }, timeout=60)
        result = parse_mcp_response(r)
        if result and "result" in result:
            content = result["result"].get("content", [])
            for c in content[:1]:
                text = c.get("text", "")[:200]
                print(f"    Response: {text}")
        elif result:
            print(f"    Result: {json.dumps(result, ensure_ascii=False)[:300]}")

# =====================================================================
# Test 2: Web Search via Docker
# =====================================================================
print(f"\n{'=' * 60}")
print("  Web Search — DuckDuckGo Direct Test")
print("=" * 60)

result = subprocess.run(
    ["docker", "exec", "wiii-app", "python", "-c", """
import json, warnings, os
warnings.filterwarnings('ignore')
os.environ['DUCKDUCKGO_PROXY'] = ''
from duckduckgo_search import DDGS
results = DDGS().text('IMO 2026 maritime news', max_results=3, region='wt-wt')
for r in results:
    print(json.dumps({'title': r['title'][:80], 'url': r['href'][:100]}, ensure_ascii=False))
"""],
    capture_output=True, text=True, encoding="utf-8", timeout=30
)
if result.stdout.strip():
    print("  Results:")
    for line in result.stdout.strip().split("\n"):
        try:
            r = json.loads(line)
            print(f"    - {r['title']}")
            print(f"      {r['url']}")
        except:
            print(f"    {line}")
    print("  Status: WORKING")
else:
    print(f"  stderr: {result.stderr[:200]}")

# =====================================================================
# Test 3: Wiii with web-needing question
# =====================================================================
print(f"\n{'=' * 60}")
print("  Wiii Chat — Questions Needing Web Search")
print("=" * 60)

CHAT_HEADERS = {
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-web-final",
    "X-Session-ID": "test-web-final-sess",
    "X-Role": "student",
    "Content-Type": "application/json",
}

q = "IMO vua thong qua quy dinh gi moi nhat nam 2026?"
print(f"  Q: {q}")
r = requests.post(f"{BASE}/api/v1/chat", headers=CHAT_HEADERS,
    json={"message": q, "user_id": "test-web-final", "role": "student"}, timeout=90)
data = r.json()
if "data" in data:
    answer = data["data"].get("answer", "")
    print(f"  A: {answer[:400]}")
else:
    print(f"  Error: {json.dumps(data, ensure_ascii=False)[:200]}")

print(f"\n{'=' * 60}")
print("  ALL TESTS DONE")
print("=" * 60)
