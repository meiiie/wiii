"""Quick raw SSE debug — see what the server actually sends."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import httpx, time

BASE_URL = "http://localhost:8000"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": "local-dev-key",
    "X-User-ID": "test-raw",
    "X-Session-ID": "s-raw-01",
    "X-Role": "student",
}

start = time.time()
with httpx.Client(timeout=120.0) as client:
    with client.stream(
        "POST",
        f"{BASE_URL}/api/v1/chat/stream/v3",
        json={"message": "Xin chào", "domain_id": "maritime"},
        headers=HEADERS,
    ) as resp:
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        print("---")
        chunk_num = 0
        for chunk in resp.iter_text():
            chunk_num += 1
            elapsed = int((time.time() - start) * 1000)
            preview = chunk[:200].replace("\n", "\\n")
            print(f"[{elapsed}ms] chunk#{chunk_num}: {preview}")
            if chunk_num > 20:
                print("... (truncated)")
                break
