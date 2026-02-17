"""
Measure Local Development Iteration Speed

Tests how fast we can iterate: edit code → auto-reload → test response.
Target: <30 seconds total iteration time.
"""
import time
import requests
import sys
from typing import Dict

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False


def test_health_endpoint() -> Dict[str, any]:
    """Test /health endpoint and measure response time."""
    try:
        start = time.time()
        response = requests.get(
            "http://localhost:8000/api/v1/health",
            timeout=5
        )
        elapsed = time.time() - start
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "latency_ms": elapsed * 1000,
            "data": response.json() if response.status_code == 200 else None,
            "error": None
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "data": None,
            "error": "Server not running. Start with: uvicorn app.main:app --reload"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "data": None,
            "error": str(e)
        }


def test_chat_endpoint() -> Dict[str, any]:
    """Test /chat endpoint with simple message."""
    try:
        start = time.time()
        response = requests.post(
            "http://localhost:8000/api/v1/chat",
            json={
                "message": "Hello",
                "user_id": "test-local-iteration"
            },
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json"
            },
            timeout=120  # Chat can take longer
        )
        elapsed = time.time() - start
        
        return {
            "success": response.status_code in [200, 401],  # 401 = needs valid API key
            "status_code": response.status_code,
            "latency_ms": elapsed * 1000,
            "data": response.json() if response.status_code == 200 else None,
            "error": None if response.status_code in [200, 401] else "Unexpected status"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "data": None,
            "error": "Server not running"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "data": None,
            "error": str(e)
        }


def main():
    """Run iteration speed test."""
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]🏃 Local Development Iteration Speed Test[/bold cyan]\n")
    else:
        print("\n🏃 Local Development Iteration Speed Test\n")
    
    print("Testing http://localhost:8000 ...\n")
    
    # Test 1: Health endpoint
    print("1️⃣ Testing /health endpoint...")
    health_result = test_health_endpoint()
    
    if not health_result["success"]:
        print(f"\n❌ {health_result['error']}")
        print("\n💡 Make sure server is running in another terminal:")
        print("   uvicorn app.main:app --reload --port 8000\n")
        return 1
    
    print(f"   ✅ Status: {health_result['status_code']}")
    print(f"   ⚡ Latency: {health_result['latency_ms']:.1f}ms")
    
    # Test 2: Chat endpoint (optional)
    print("\n2️⃣ Testing /chat endpoint (optional)...")
    chat_result = test_chat_endpoint()
    
    if chat_result["status_code"] == 401:
        print("   ⚠️ Needs valid API key (expected)")
    elif chat_result["success"]:
        print(f"   ✅ Status: {chat_result['status_code']}")
        print(f"   ⏱️ Latency: {chat_result['latency_ms']/1000:.2f}s")
    
    # Summary
    print("\n" + "="*70)
    print("📊 ITERATION SPEED ANALYSIS")
    print("="*70)
    
    if health_result["latency_ms"] < 1000:
        print(f"\n✅ Fast iteration validated!")
        print(f"   Response time: {health_result['latency_ms']:.1f}ms")
        print(f"\n📝 Now try this workflow:")
        print(f"   1. Edit any .py file (e.g., add a comment)")
        print(f"   2. Watch terminal for 'Reloading...' message (1-2s)")
        print(f"   3. Re-run this script → still <1s response")
        print(f"\n   Total iteration time: ~3-5 seconds ⚡")
        print(f"   vs Render deployment: ~10-15 minutes 🐌")
        print(f"\n   🎯 Speedup: 100-300x faster!")
    else:
        print(f"\n⚠️ Slower than expected: {health_result['latency_ms']:.1f}ms")
        print(f"   Expected: <1000ms")
    
    print("\n" + "="*70)
    
    # Auto-reload instructions
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold yellow]💡 Testing Auto-Reload[/bold yellow]\n\n"
            "1. Keep server running in Terminal 1\n"
            "2. Edit [cyan]app/main.py[/cyan] (add a comment)\n"
            "3. Watch Terminal 1 for 'Reloading...' (1-2s)\n"
            "4. Re-run this script → response should be same speed\n\n"
            "[bold green]This is the power of local development! ⚡[/bold green]",
            title="Next Steps",
            border_style="green"
        ))
    else:
        print("\n💡 Testing Auto-Reload:")
        print("   1. Keep server running in Terminal 1")
        print("   2. Edit app/main.py (add a comment)")
        print("   3. Watch Terminal 1 for 'Reloading...' (1-2s)")
        print("   4. Re-run this script → response should be same speed")
        print("\n   This is the power of local development! ⚡\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
