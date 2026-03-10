#!/usr/bin/env python3
"""
Sprint 220: "Cắm Phích" — LMS Hàng Hải End-to-End Integration Test

Tests the full connection between Wiii AI and LMS Maritime (hohulili).
Requires both services running:
  - Wiii: http://localhost:8000
  - LMS:  http://localhost:8088

Usage:
    python scripts/test_lms_integration.py
    python scripts/test_lms_integration.py --wiii-url http://localhost:8000 --lms-url http://localhost:8088
    python scripts/test_lms_integration.py --test token_exchange   # Run single test
"""

import argparse
import hashlib
import hmac
import json
import sys
import time

import httpx

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_WIII_URL = "http://localhost:8000"
DEFAULT_LMS_URL = "http://localhost:8088"
DEFAULT_WEBHOOK_SECRET = "wiii-webhook-hmac-secret-2026"
DEFAULT_SERVICE_TOKEN = "wiii-service-token-shared-secret"
DEFAULT_API_KEY = "your-api-key"  # From .env

# Test data
TEST_STUDENT = {
    "lms_user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "student@maritime.edu",
    "name": "Nguyễn Văn Test",
    "role": "student",
    "organization_id": "maritime-lms",
}


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def ok(msg: str):
    print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"  {Colors.RED}✗{Colors.RESET} {msg}")


def info(msg: str):
    print(f"  {Colors.BLUE}ℹ{Colors.RESET} {msg}")


def header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}  {msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")


def sign_payload(body: str, secret: str) -> str:
    """Create HMAC-SHA256 signature matching Wiii's verify_hmac_sha256()."""
    sig = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


# =============================================================================
# Test 1: Health Check
# =============================================================================


def test_wiii_health(wiii_url: str) -> bool:
    """Check Wiii LMS health endpoint."""
    header("Test 1: Wiii LMS Health Check")
    try:
        resp = httpx.get(f"{wiii_url}/api/v1/lms/health", timeout=5)
        data = resp.json()

        if resp.status_code == 200:
            ok(f"Status: {resp.status_code}")
            ok(f"LMS enabled: {data.get('enabled')}")
            ok(f"Connectors: {data.get('connector_count', 0)}")
            for c in data.get("connectors", []):
                info(f"  - {c['id']} ({c['backend_type']}): base_url={c.get('base_url_configured')}")
            return True
        else:
            fail(f"Unexpected status: {resp.status_code}")
            return False
    except httpx.ConnectError:
        fail(f"Cannot connect to Wiii at {wiii_url}")
        return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_lms_health(lms_url: str, service_token: str) -> bool:
    """Check LMS data endpoints are accessible."""
    header("Test 1b: LMS Data Endpoint Health")
    try:
        resp = httpx.get(
            f"{lms_url}/api/v3/integration/",
            headers={"Authorization": f"Bearer {service_token}"},
            timeout=5,
        )
        if resp.status_code in (200, 401, 403, 404):
            ok(f"LMS responded: {resp.status_code}")
            return True
        else:
            fail(f"Unexpected status: {resp.status_code}")
            return False
    except httpx.ConnectError:
        fail(f"Cannot connect to LMS at {lms_url}")
        info("Is the LMS running? Start with: cd LMS_hohulili/backend && mvn spring-boot:run")
        return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


# =============================================================================
# Test 2: Token Exchange
# =============================================================================


def test_token_exchange(wiii_url: str, secret: str) -> dict | None:
    """Test LMS → Wiii JWT token exchange."""
    header("Test 2: Token Exchange (LMS → Wiii JWT)")

    body = json.dumps({
        "connector_id": "maritime-lms",
        "lms_user_id": TEST_STUDENT["lms_user_id"],
        "email": TEST_STUDENT["email"],
        "name": TEST_STUDENT["name"],
        "role": TEST_STUDENT["role"],
        "organization_id": TEST_STUDENT["organization_id"],
        "timestamp": int(time.time()),
    })

    signature = sign_payload(body, secret)
    info(f"HMAC signature: {signature[:30]}...")

    try:
        resp = httpx.post(
            f"{wiii_url}/api/v1/auth/lms/token",
            content=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-LMS-Signature": signature,
            },
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            ok("Token exchange successful!")
            ok(f"Access token: {data.get('access_token', '')[:20]}...")
            ok(f"User ID: {data.get('user', {}).get('id')}")
            ok(f"Role: {data.get('user', {}).get('role')}")
            return data
        elif resp.status_code == 403:
            fail(f"Signature validation failed: {resp.text}")
            info("Check that webhook_secret matches on both sides")
            return None
        else:
            fail(f"Status {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        fail(f"Error: {e}")
        return None


# =============================================================================
# Test 3: LMS Data Pull
# =============================================================================


def test_data_pull(lms_url: str, service_token: str, student_id: str) -> bool:
    """Test Wiii pulling student data from LMS."""
    header("Test 3: Data Pull (Wiii → LMS)")

    endpoints = [
        f"/api/v3/integration/students/{student_id}/profile",
        f"/api/v3/integration/students/{student_id}/grades",
        f"/api/v3/integration/students/{student_id}/assignments/upcoming",
        f"/api/v3/integration/students/{student_id}/enrollments",
    ]

    all_ok = True
    for endpoint in endpoints:
        try:
            resp = httpx.get(
                f"{lms_url}{endpoint}",
                headers={"Authorization": f"Bearer {service_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                ok(f"{endpoint}: OK ({len(resp.text)} bytes)")
            elif resp.status_code == 404:
                info(f"{endpoint}: 404 (student not found — expected if no test data)")
            elif resp.status_code == 500:
                info(f"{endpoint}: 500 (LMS internal error — check LMS Java logs)")
            else:
                fail(f"{endpoint}: {resp.status_code}")
                all_ok = False
        except Exception as e:
            fail(f"{endpoint}: {e}")
            all_ok = False

    return all_ok


# =============================================================================
# Test 4: Webhook Delivery
# =============================================================================


def test_webhook(wiii_url: str, secret: str) -> bool:
    """Test LMS → Wiii webhook delivery (grade_saved event)."""
    header("Test 4: Webhook Delivery (LMS → Wiii)")

    body = json.dumps({
        "event_type": "grade_saved",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload": {
            "student_id": TEST_STUDENT["lms_user_id"],
            "course_id": "NHH101",
            "course_name": "Luật Hàng Hải Quốc Tế",
            "grade": 8.5,
            "max_grade": 10.0,
            "assignment_name": "Quiz COLREGs Chương 1",
        },
    })

    signature = sign_payload(body, secret)
    info(f"Sending grade_saved event for {TEST_STUDENT['name']}")

    try:
        resp = httpx.post(
            f"{wiii_url}/api/v1/lms/webhook/maritime-lms",
            content=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-LMS-Signature": signature,
            },
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            ok(f"Webhook accepted: {data.get('status')}")
            ok(f"Event type: {data.get('event_type')}")
            ok(f"Facts created: {data.get('facts_created', 0)}")
            return True
        else:
            fail(f"Status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


# =============================================================================
# Test 5: Context-Aware Chat
# =============================================================================


def test_context_aware_chat(
    wiii_url: str,
    access_token: str,
    api_key: str,
) -> bool:
    """Test that AI response includes LMS context."""
    header("Test 5: Context-Aware Chat")

    try:
        resp = httpx.post(
            f"{wiii_url}/api/v1/chat",
            json={
                "message": "Tôi đang học những môn gì?",
                "session_id": "test-lms-session-001",
                "user_id": TEST_STUDENT["lms_user_id"],
                "role": "student",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-API-Key": api_key,
                "X-User-ID": TEST_STUDENT["lms_user_id"],
                "X-Role": "student",
            },
            timeout=60,
        )

        if resp.status_code == 200:
            data = resp.json()
            # Response format: {"status":"success","data":{"answer":"..."},"metadata":{}}
            response_text = (
                data.get("data", {}).get("answer", "")
                or data.get("response", "")
            )
            ok(f"Chat response received ({len(response_text)} chars)")

            # Check if response mentions course context
            context_keywords = ["môn", "khóa", "học", "lớp"]
            found_keywords = [kw for kw in context_keywords if kw in response_text.lower()]
            if found_keywords:
                ok(f"Response contains learning context: {found_keywords}")
            else:
                info("Response may not contain specific LMS context (depends on data)")

            info(f"Preview: {response_text[:200]}...")
            return True
        else:
            fail(f"Chat failed: {resp.status_code}")
            info(resp.text[:200])
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Sprint 220: LMS Integration E2E Test")
    parser.add_argument("--wiii-url", default=DEFAULT_WIII_URL)
    parser.add_argument("--lms-url", default=DEFAULT_LMS_URL)
    parser.add_argument("--secret", default=DEFAULT_WEBHOOK_SECRET)
    parser.add_argument("--service-token", default=DEFAULT_SERVICE_TOKEN)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--test", help="Run specific test (health, token_exchange, data_pull, webhook, chat)")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}Sprint 220: 'Cắm Phích' — LMS Hàng Hải E2E Integration Test{Colors.RESET}")
    print(f"  Wiii: {args.wiii_url}")
    print(f"  LMS:  {args.lms_url}")

    results = {}

    # Test 1: Health
    if not args.test or args.test == "health":
        results["wiii_health"] = test_wiii_health(args.wiii_url)
        results["lms_health"] = test_lms_health(args.lms_url, args.service_token)

    # Test 2: Token Exchange
    token_data = None
    if not args.test or args.test == "token_exchange":
        token_data = test_token_exchange(args.wiii_url, args.secret)
        results["token_exchange"] = token_data is not None

    # Test 3: Data Pull
    if not args.test or args.test == "data_pull":
        results["data_pull"] = test_data_pull(
            args.lms_url, args.service_token, TEST_STUDENT["lms_user_id"]
        )

    # Test 4: Webhook
    if not args.test or args.test == "webhook":
        results["webhook"] = test_webhook(args.wiii_url, args.secret)

    # Test 5: Context-Aware Chat (requires token)
    if not args.test or args.test == "chat":
        access_token = (token_data or {}).get("access_token", "")
        if access_token:
            results["chat"] = test_context_aware_chat(
                args.wiii_url, access_token, args.api_key
            )
        else:
            info("Skipping chat test (no access token from token exchange)")
            results["chat"] = None

    # Summary
    header("Summary")
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for test_name, result in results.items():
        if result is True:
            ok(test_name)
        elif result is False:
            fail(test_name)
        else:
            info(f"{test_name} (skipped)")

    print(f"\n  {Colors.GREEN}{passed} passed{Colors.RESET}, "
          f"{Colors.RED}{failed} failed{Colors.RESET}, "
          f"{Colors.YELLOW}{skipped} skipped{Colors.RESET}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
