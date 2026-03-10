"""
Test Memory Persistence - Kiểm tra xem bot có nhớ thông tin user không.

Test này gửi nhiều tin nhắn liên tiếp để kiểm tra:
1. Bot có nhớ tên user không?
2. Bot có nhớ context cuộc hội thoại không?
3. Suggested questions có context-aware không?
"""
import httpx
import asyncio
import uuid
from datetime import datetime

# Production API
BASE_URL = "https://wiii.holilihu.online"
API_KEY = "test_key"  # Replace with actual key if needed

# Test user - unique per test run
TEST_USER_ID = f"memory_test_{uuid.uuid4().hex[:8]}"
TEST_SESSION_ID = f"session_{uuid.uuid4().hex[:8]}"


async def send_chat(message: str, user_id: str = TEST_USER_ID, session_id: str = TEST_SESSION_ID):
    """Send a chat message and return response."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={
                "user_id": user_id,
                "message": message,
                "role": "student",
                "session_id": session_id
            },
            headers={"X-API-Key": API_KEY}
        )
        return response.json()


async def test_memory_persistence():
    """Test if bot remembers user information across messages."""
    print("=" * 70)
    print("TEST: MEMORY PERSISTENCE")
    print(f"User ID: {TEST_USER_ID}")
    print(f"Session ID: {TEST_SESSION_ID}")
    print("=" * 70)
    
    # Message 1: Introduce yourself
    print("\n[1] Giới thiệu bản thân...")
    msg1 = "Xin chào, tôi là Minh, tôi là sinh viên hàng hải năm 3 tại Đại học Hàng hải Việt Nam."
    resp1 = await send_chat(msg1)
    
    print(f"User: {msg1}")
    print(f"AI: {resp1.get('data', {}).get('answer', 'No answer')[:300]}...")
    print(f"Metadata: {resp1.get('metadata', {})}")
    
    # Check if bot acknowledged the name
    answer1 = resp1.get('data', {}).get('answer', '').lower()
    name_acknowledged = 'minh' in answer1
    print(f"\n✅ Bot nhận ra tên 'Minh': {name_acknowledged}")
    
    await asyncio.sleep(2)  # Wait a bit
    
    # Message 2: Ask about Rule 15
    print("\n" + "-" * 70)
    print("[2] Hỏi về quy tắc 15...")
    msg2 = "Giải thích quy tắc 15 COLREGs về tình huống cắt hướng"
    resp2 = await send_chat(msg2)
    
    print(f"User: {msg2}")
    print(f"AI: {resp2.get('data', {}).get('answer', 'No answer')[:300]}...")
    
    # Check if bot still remembers the name
    answer2 = resp2.get('data', {}).get('answer', '').lower()
    name_remembered = 'minh' in answer2
    print(f"\n✅ Bot vẫn nhớ tên 'Minh': {name_remembered}")
    
    await asyncio.sleep(2)
    
    # Message 3: Follow-up question
    print("\n" + "-" * 70)
    print("[3] Câu hỏi tiếp theo...")
    msg3 = "Vậy tàu nào phải nhường đường?"
    resp3 = await send_chat(msg3)
    
    print(f"User: {msg3}")
    print(f"AI: {resp3.get('data', {}).get('answer', 'No answer')[:300]}...")
    
    # Check if bot understands context (Rule 15)
    answer3 = resp3.get('data', {}).get('answer', '').lower()
    context_understood = any(kw in answer3 for kw in ['quy tắc 15', 'rule 15', 'cắt hướng', 'mạn phải', 'starboard'])
    print(f"\n✅ Bot hiểu context (Rule 15): {context_understood}")
    
    # Check if bot still remembers name
    name_still_remembered = 'minh' in answer3
    print(f"✅ Bot vẫn nhớ tên 'Minh': {name_still_remembered}")
    
    await asyncio.sleep(2)
    
    # Message 4: Ask about something else
    print("\n" + "-" * 70)
    print("[4] Hỏi về chủ đề khác...")
    msg4 = "Còn quy tắc 13 về tàu vượt thì sao?"
    resp4 = await send_chat(msg4)
    
    print(f"User: {msg4}")
    print(f"AI: {resp4.get('data', {}).get('answer', 'No answer')[:300]}...")
    
    # Check suggested questions
    suggestions = resp4.get('data', {}).get('suggested_questions', [])
    print(f"\nSuggested questions: {suggestions}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    tests = [
        ("Bot nhận ra tên lần đầu", name_acknowledged),
        ("Bot nhớ tên ở tin nhắn 2", name_remembered),
        ("Bot hiểu context Rule 15", context_understood),
        ("Bot nhớ tên ở tin nhắn 3", name_still_remembered),
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Memory persistence is working!")
    elif passed >= 2:
        print("\n⚠️ Memory persistence is partially working")
    else:
        print("\n❌ Memory persistence has issues")
    
    return passed, total


async def test_cross_session_memory():
    """Test if bot remembers user across different sessions."""
    print("\n" + "=" * 70)
    print("TEST: CROSS-SESSION MEMORY")
    print("=" * 70)
    
    # Use same user but different session
    new_session = f"session_{uuid.uuid4().hex[:8]}"
    
    print(f"\nUser ID: {TEST_USER_ID} (same as before)")
    print(f"New Session ID: {new_session}")
    
    # Ask if bot remembers
    msg = "Bạn có nhớ tôi là ai không?"
    resp = await send_chat(msg, TEST_USER_ID, new_session)
    
    print(f"\nUser: {msg}")
    print(f"AI: {resp.get('data', {}).get('answer', 'No answer')[:500]}...")
    
    answer = resp.get('data', {}).get('answer', '').lower()
    remembers_name = 'minh' in answer
    remembers_student = any(kw in answer for kw in ['sinh viên', 'student', 'năm 3'])
    
    print(f"\n✅ Bot nhớ tên 'Minh': {remembers_name}")
    print(f"✅ Bot nhớ là sinh viên: {remembers_student}")
    
    if remembers_name or remembers_student:
        print("\n🎉 Cross-session memory is working!")
    else:
        print("\n❌ Cross-session memory is NOT working")
    
    return remembers_name, remembers_student


async def main():
    """Run all memory tests."""
    print(f"\n{'='*70}")
    print(f"MEMORY PERSISTENCE TEST - {datetime.now()}")
    print(f"{'='*70}")
    
    # Test 1: Within-session memory
    passed, total = await test_memory_persistence()
    
    # Test 2: Cross-session memory
    remembers_name, remembers_student = await test_cross_session_memory()
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Within-session memory: {passed}/{total} tests passed")
    print(f"Cross-session memory: Name={remembers_name}, Student={remembers_student}")


if __name__ == "__main__":
    asyncio.run(main())
