"""Test MCP Server + Web Search — v2 with fixes."""
import io, sys, json, requests, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000"

# =====================================================================
# Test 1: MCP Server — proper Streamable HTTP protocol
# =====================================================================
print("=" * 60)
print("  Test 1: MCP Server — Initialize + List Tools")
print("=" * 60)

session = requests.Session()

# Step 1: Initialize
try:
    r = session.post(
        f"{BASE}/mcp",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            "id": 1,
        },
        timeout=10,
    )
    print(f"  Init status: {r.status_code}")
    print(f"  Content-Type: {r.headers.get('Content-Type', '?')}")

    body = r.text.strip()
    # Parse SSE or JSON
    parsed = None
    if body.startswith("event:") or body.startswith("data:"):
        for line in body.split("\n"):
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[6:])
                except:
                    pass
    else:
        try:
            parsed = json.loads(body)
        except:
            pass

    if parsed and "result" in parsed:
        res = parsed["result"]
        print(f"  Server: {res.get('serverInfo', {}).get('name', '?')}")
        print(f"  Protocol: {res.get('protocolVersion', '?')}")
        caps = res.get('capabilities', {})
        print(f"  Capabilities: {list(caps.keys())}")

        # Get session ID from response headers
        mcp_session = r.headers.get("Mcp-Session-Id", "")
        print(f"  Session ID: {mcp_session[:30]}...")

        # Step 2: Send initialized notification
        session.post(
            f"{BASE}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **({"Mcp-Session-Id": mcp_session} if mcp_session else {}),
            },
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=5,
        )

        # Step 3: List tools
        r2 = session.post(
            f"{BASE}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **({"Mcp-Session-Id": mcp_session} if mcp_session else {}),
            },
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
            timeout=10,
        )

        body2 = r2.text.strip()
        parsed2 = None
        if body2.startswith("event:") or body2.startswith("data:"):
            for line in body2.split("\n"):
                if line.startswith("data: "):
                    try:
                        parsed2 = json.loads(line[6:])
                    except:
                        pass
        else:
            try:
                parsed2 = json.loads(body2)
            except:
                pass

        if parsed2 and "result" in parsed2:
            tools = parsed2["result"].get("tools", [])
            print(f"\n  MCP Tools ({len(tools)}):")
            for t in tools:
                desc = t.get('description', '')[:60]
                print(f"    - {t.get('name', '?')}: {desc}")
        elif parsed2:
            print(f"  Tools response: {json.dumps(parsed2, ensure_ascii=False)[:300]}")
        else:
            print(f"  Raw tools response: {body2[:300]}")
    elif parsed:
        print(f"  Response: {json.dumps(parsed, ensure_ascii=False)[:300]}")
    else:
        print(f"  Raw: {body[:300]}")
except Exception as e:
    print(f"  Error: {e}")

# =====================================================================
# Test 2: Web Search — via Docker exec
# =====================================================================
print(f"\n{'=' * 60}")
print("  Test 2: DuckDuckGo Web Search (via Docker)")
print("=" * 60)

result = subprocess.run(
    ["docker", "exec", "wiii-app", "python", "-c", """
import json, warnings
warnings.filterwarnings('ignore')
from duckduckgo_search import DDGS
results = DDGS().text('COLREG 2024 amendments IMO', max_results=3, region='wt-wt', safesearch='moderate', backend='auto')
for r in results:
    print(json.dumps({'title': r['title'][:70], 'url': r['href']}, ensure_ascii=False))
"""],
    capture_output=True, text=True, encoding="utf-8", timeout=30
)
if result.stdout.strip():
    print(f"  DuckDuckGo results:")
    for line in result.stdout.strip().split("\n"):
        try:
            r = json.loads(line)
            print(f"    - {r['title']}")
            print(f"      {r['url']}")
        except:
            print(f"    {line}")
    print(f"  Status: WORKING")
else:
    print(f"  stderr: {result.stderr[:300]}")
    print(f"  Status: FAILED")

# =====================================================================
# Test 3: Wiii answers using web search context
# =====================================================================
print(f"\n{'=' * 60}")
print("  Test 3: Wiii Answers Needing Current Info")
print("=" * 60)

HEADERS = {
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-web",
    "X-Session-ID": "test-web-sess",
    "X-Role": "student",
    "Content-Type": "application/json",
}

queries = [
    ("Tin tuc moi nhat ve IMO nam 2026 la gi?", "current_events"),
    ("Thoi tiet o Ha Noi hom nay the nao?", "weather"),
    ("Viet Nam co bao nhieu cang bien quoc te?", "maritime_fact"),
]

for q, cat in queries:
    print(f"\n  [{cat}] {q}")
    try:
        r = requests.post(
            f"{BASE}/api/v1/chat",
            headers=HEADERS,
            json={"message": q, "user_id": "test-web", "role": "student"},
            timeout=90,
        )
        data = r.json()
        if "data" in data:
            answer = data["data"].get("answer", "")
            print(f"  Answer: {answer[:250]}...")
        else:
            print(f"  Error: {json.dumps(data, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'=' * 60}")
print("  DONE")
print("=" * 60)
