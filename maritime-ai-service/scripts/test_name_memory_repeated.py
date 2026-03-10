"""
Test Name Memory - Kiểm tra AI có nhớ tên khi user giới thiệu liên tục không

Kịch bản:
1. User giới thiệu "Tôi là Minh"
2. User hỏi câu hỏi
3. User lại giới thiệu "Tôi là Minh" (lặp lại)
4. Kiểm tra AI có nhận ra đã biết tên chưa
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://wiii.holilihu.online")
API_KEY = os.getenv("API_KEY", "")

def send_message(message: str, user_id: str, session_id: str) -> dict:
    """Send chat message"""
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    payload = {
        "message": message,
        "user_id": user_id,
        "session_id": session_id,
        "role": "student"
    }
    
    response = requests.post(
        f"{PRODUCTION_URL}/api/v1/chat/",
        json=payload,
        headers=headers,
        timeout=120
    )
    
    if response.status_code == 200:
        return response.json()
    return {"error": response.status_code, "detail": response.text[:200]}


def test_repeated_name_introduction():
    """Test if AI remembers name when user introduces repeatedly"""
    print("="*70)
    print("TEST: REPEATED NAME INTRODUCTION")
    print("Kiểm tra AI có nhớ tên khi user giới thiệu liên tục")
    print("="*70)
    
    session_id = f"name-repeat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    user_id = "name-repeat-user"
    
    # Message 1: First introduction
    print("\n📤 Message 1: 'Xin chào, tôi là Minh'")
    r1 = send_message("Xin chào, tôi là Minh", user_id, session_id)
    answer1 = r1.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer1[:500]}...")
    
    # Message 2: Ask a question
    print("\n" + "-"*50)
    print("📤 Message 2: 'Tàu biển là gì?'")
    r2 = send_message("Tàu biển là gì?", user_id, session_id)
    answer2 = r2.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer2[:500]}...")
    
    # Message 3: Introduce again (repeated)
    print("\n" + "-"*50)
    print("📤 Message 3: 'Tôi là Minh' (LẶP LẠI)")
    r3 = send_message("Tôi là Minh", user_id, session_id)
    answer3 = r3.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer3[:500]}...")
    
    # Message 4: Introduce again with different phrasing
    print("\n" + "-"*50)
    print("📤 Message 4: 'Mình tên là Minh nè' (LẶP LẠI KHÁC CÁCH)")
    r4 = send_message("Mình tên là Minh nè", user_id, session_id)
    answer4 = r4.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer4[:500]}...")
    
    # Analysis
    print("\n" + "="*70)
    print("📊 ANALYSIS")
    print("="*70)
    
    # Check if AI recognized repeated introduction
    recognition_phrases = [
        "đã biết", "biết rồi", "nhớ rồi", "đã gặp", 
        "lần trước", "trước đó", "vừa nãy", "mới nói",
        "đã giới thiệu", "biết tên", "nhớ tên"
    ]
    
    recognized_in_3 = any(phrase in answer3.lower() for phrase in recognition_phrases)
    recognized_in_4 = any(phrase in answer4.lower() for phrase in recognition_phrases)
    
    print(f"\n🔍 Message 3 (lặp lại lần 1):")
    print(f"   AI nhận ra đã biết tên: {'✅ CÓ' if recognized_in_3 else '❌ KHÔNG'}")
    
    print(f"\n🔍 Message 4 (lặp lại lần 2):")
    print(f"   AI nhận ra đã biết tên: {'✅ CÓ' if recognized_in_4 else '❌ KHÔNG'}")
    
    # Check if AI uses name appropriately
    name_in_2 = "minh" in answer2.lower()
    name_in_3 = "minh" in answer3.lower()
    name_in_4 = "minh" in answer4.lower()
    
    print(f"\n🔍 AI sử dụng tên 'Minh':")
    print(f"   Message 2: {'✅' if name_in_2 else '❌'}")
    print(f"   Message 3: {'✅' if name_in_3 else '❌'}")
    print(f"   Message 4: {'✅' if name_in_4 else '❌'}")
    
    return recognized_in_3 or recognized_in_4


def test_cross_session_memory():
    """Test if AI remembers name across different sessions (same user_id)"""
    print("\n" + "="*70)
    print("TEST: CROSS-SESSION MEMORY")
    print("Kiểm tra AI có nhớ tên qua các session khác nhau (cùng user_id)")
    print("="*70)
    
    user_id = "cross-session-user-minh"
    
    # Session 1: Introduce name
    session1 = f"session1-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"\n📤 Session 1: 'Tôi là Minh, tôi muốn học về COLREGs'")
    r1 = send_message("Tôi là Minh, tôi muốn học về COLREGs", user_id, session1)
    answer1 = r1.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer1[:400]}...")
    
    # Session 2: New session, same user_id - check if AI remembers
    session2 = f"session2-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"\n📤 Session 2 (NEW): 'Xin chào, bạn còn nhớ tôi không?'")
    r2 = send_message("Xin chào, bạn còn nhớ tôi không?", user_id, session2)
    answer2 = r2.get("data", {}).get("answer", "")
    print(f"📥 Response:\n{answer2[:400]}...")
    
    # Check if AI remembers
    remembers = "minh" in answer2.lower() or "nhớ" in answer2.lower()
    print(f"\n🔍 AI nhớ user từ session trước: {'✅ CÓ' if remembers else '❌ KHÔNG'}")
    
    return remembers


def main():
    print("="*70)
    print("MARITIME AI TUTOR - NAME MEMORY TEST")
    print(f"Server: {PRODUCTION_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*70)
    
    results = []
    
    # Test 1: Repeated name introduction
    results.append(("Repeated Name Introduction", test_repeated_name_introduction()))
    
    # Test 2: Cross-session memory
    results.append(("Cross-Session Memory", test_cross_session_memory()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 MEMORY TEST SUMMARY")
    print("="*70)
    
    for name, result in results:
        icon = "✅" if result else "⚠️"
        print(f"{icon} {name}")
    
    passed = sum(1 for _, r in results if r)
    print(f"\n🎯 Score: {passed}/{len(results)}")


if __name__ == "__main__":
    main()
