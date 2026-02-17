"""
Sprint 97: Test MCP Server + Web Search Tools
1. MCP Server endpoint health check
2. MCP tools listing via JSON-RPC
3. Web Search via direct API call
4. Web Search via Wiii agent (asks question needing web)
"""
import io, sys, json, requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://localhost:8000"
HEADERS = {
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-mcp",
    "X-Session-ID": "test-mcp-sess",
    "X-Role": "student",
    "Content-Type": "application/json",
}

print("=" * 60)
print("  Test 1: MCP Server Endpoint")
print("=" * 60)

# MCP uses JSON-RPC over SSE — test with proper Accept header
try:
    # Initialize MCP session
    r = requests.post(
        f"{BASE}/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
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
        stream=True,
    )
    print(f"  Status: {r.status_code}")
    # Read SSE response
    content = ""
    for line in r.iter_lines(decode_unicode=True):
        if line:
            content += line + "\n"
        if len(content) > 500:
            break
    print(f"  Response (first 500 chars):\n  {content[:500]}")

    # Try to extract JSON from SSE data
    for line in content.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                print(f"\n  MCP Server Info:")
                if "result" in data:
                    res = data["result"]
                    print(f"    Protocol: {res.get('protocolVersion', '?')}")
                    print(f"    Server: {res.get('serverInfo', {}).get('name', '?')}")
                    caps = res.get('capabilities', {})
                    print(f"    Capabilities: {list(caps.keys())}")
            except json.JSONDecodeError:
                pass
except Exception as e:
    print(f"  Error: {e}")

print(f"\n{'=' * 60}")
print("  Test 2: MCP Tools Listing")
print("=" * 60)

try:
    r = requests.post(
        f"{BASE}/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2,
        },
        timeout=10,
        stream=True,
    )
    content = ""
    for line in r.iter_lines(decode_unicode=True):
        if line:
            content += line + "\n"
        if len(content) > 2000:
            break

    for line in content.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "result" in data:
                    tools = data["result"].get("tools", [])
                    print(f"  Found {len(tools)} MCP tools:")
                    for t in tools:
                        print(f"    - {t.get('name', '?')}: {t.get('description', '?')[:60]}")
            except json.JSONDecodeError:
                pass
    if not content.strip():
        print("  (empty response — may need initialized session)")
except Exception as e:
    print(f"  Error: {e}")

print(f"\n{'=' * 60}")
print("  Test 3: Direct Web Search Tool Test")
print("=" * 60)

try:
    # Call web search directly via Python
    sys.path.insert(0, ".")
    from app.engine.tools.web_search_tools import _search_sync
    results = _search_sync("COLREG 2024 amendments maritime", max_results=3)
    print(f"  DuckDuckGo returned {len(results)} results:")
    for r in results:
        print(f"    - {r['title'][:70]}")
        print(f"      {r['href']}")
    print(f"  Web search: WORKING")
except ImportError as e:
    print(f"  Import error: {e}")
    print(f"  Trying via Docker...")
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "wiii-app", "python", "-c",
         "from duckduckgo_search import DDGS; r=DDGS().text('COLREG 2024 maritime',max_results=3); [print(x['title'][:70]) for x in r]"],
        capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    if result.stdout.strip():
        print(f"  DuckDuckGo results (via Docker):")
        print(f"  {result.stdout}")
        print(f"  Web search: WORKING")
    else:
        print(f"  Error: {result.stderr[:200]}")
except Exception as e:
    print(f"  Error: {e}")

print(f"\n{'=' * 60}")
print("  Test 4: Wiii Uses Web Search (via API)")
print("=" * 60)

# Ask a question that REQUIRES current information (forces web search)
web_queries = [
    "Tin tuc hang hai Viet Nam moi nhat hom nay la gi?",
    "Gia dau Brent hom nay la bao nhieu?",
]

for q in web_queries:
    print(f"\n  Query: {q}")
    try:
        r = requests.post(
            f"{BASE}/api/v1/chat",
            headers=HEADERS,
            json={"message": q, "user_id": "test-mcp", "role": "student"},
            timeout=90,
        )
        data = r.json()
        if "data" in data:
            d = data["data"]
            answer = d.get("answer", "")
            meta = d.get("metadata", {})
            tools = meta.get("tools_used", [])
            print(f"  tools_used: {tools}")
            print(f"  answer: {answer[:300]}")

            # Check if answer contains current info or web results
            if any(kw in answer.lower() for kw in ["http", "url", "2026", "2025", "hôm nay", "mới nhất"]):
                print(f"  >>> Likely used web search!")
            else:
                print(f"  >>> May have used general knowledge only")
        else:
            print(f"  ERROR: {json.dumps(data, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'=' * 60}")
print("  Summary")
print("=" * 60)
