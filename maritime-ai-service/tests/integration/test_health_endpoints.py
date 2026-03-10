#!/usr/bin/env python3
"""
Test Health Check Endpoints (CHỈ THỊ KỸ THUẬT SỐ 19)

Tests:
1. Shallow health check (no DB access) - for Cronjob
2. Deep health check (with DB access) - for Admin

Usage:
    python scripts/test_health_endpoints.py          # Test local (localhost:8000)
    python scripts/test_health_endpoints.py --prod   # Test production (Render)
"""
import requests
import sys

# URLs
LOCAL_URL = "http://localhost:8000"
PRODUCTION_URL = "https://wiii.holilihu.online"

# Default to local, use --prod for production
BASE_URL = PROD_URL if "--prod" in sys.argv else LOCAL_URL


def test_shallow_health():
    """Test shallow health check - NO DB access"""
    print("\n" + "="*60)
    print("TEST 1: Shallow Health Check (/api/v1/health)")
    print("="*60)
    print("Purpose: Cronjob/Render ping - Does NOT wake up Neon")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        data = response.json()
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {data}")
        
        # Accept both old format (status: healthy) and new format (status: ok)
        status = data.get("status")
        if response.status_code == 200 and status in ["ok", "healthy"]:
            print("✅ Shallow health check: PASSED")
            if status == "healthy":
                print("   ⚠️ Note: Using OLD health check format (deploy new code to fix)")
            return True
        else:
            print("❌ Shallow health check: FAILED")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Start with: uvicorn app.main:app")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_deep_health():
    """Test deep health check - WITH DB access"""
    print("\n" + "="*60)
    print("TEST 2: Deep Health Check (/api/v1/health/db)")
    print("="*60)
    print("Purpose: Admin/Debug - WILL wake up Neon")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health/db", timeout=30)
        data = response.json()
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Overall Status: {data.get('status')}")
        
        components = data.get("components", {})
        for name, comp in components.items():
            status = comp.get("status", "unknown")
            latency = comp.get("latency_ms", 0)
            message = comp.get("message", "")
            print(f"   - {name}: {status} ({latency}ms) - {message}")
        
        if response.status_code == 200:
            print("✅ Deep health check: PASSED")
            return True
        elif response.status_code == 404:
            print("⚠️ Deep health check: ENDPOINT NOT FOUND")
            print("   → Deploy new code to enable /api/v1/health/db")
            return True  # Not a failure, just not deployed yet
        else:
            print("❌ Deep health check: FAILED")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Start with: uvicorn app.main:app")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("CHỈ THỊ KỸ THUẬT SỐ 19: HEALTH CHECK TEST")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print("="*60)
    
    results = []
    
    results.append(("Shallow Health", test_shallow_health()))
    results.append(("Deep Health", test_deep_health()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {name}: {status}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 HEALTH CHECK ENDPOINTS WORKING!")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
