"""
Test Memory Behavior - 2 câu hỏi liên tiếp để verify:
1. Câu hỏi thường: AI có nhận biết câu hỏi lại không?
2. Câu hỏi yêu cầu dùng tool: AI có chịu truy vấn lại không?
"""
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('API_KEY', '')
BASE_URL = "https://wiii.holilihu.online"

# Dùng cùng user_id và session_id để test memory
USER_ID = "test-memory-user-456"
SESSION_ID = "test-memory-session-456"

def send_message(message: str, request_num: int):
    """Send message and analyze response"""
    headers = {'X-API-Key': API_KEY} if API_KEY else {}
    payload = {
        'message': message,
        'user_id': USER_ID,
        'session_id': SESSION_ID,
        'role': 'student'
    }
    
    print(f"\n{'='*60}")
    print(f"📝 Request {request_num}: {message[:80]}...")
    print('='*60)
    
    resp = requests.post(f'{BASE_URL}/api/v1/chat/', json=payload, headers=headers, timeout=120)
    data = resp.json()
    
    sources = data.get('data', {}).get('sources', [])
    answer = data.get('data', {}).get('answer', '')
    
    print(f"✅ Status: {resp.status_code}")
    print(f"📊 Sources returned: {len(sources)}")
    print(f"📄 Answer preview ({len(answer)} chars):")
    print("-" * 40)
    print(answer[:600])
    print("-" * 40)
    
    if sources:
        print("\n📚 Sources details:")
        for i, src in enumerate(sources[:3], 1):
            print(f"  {i}. {src.get('title', 'N/A')[:50]}")
            print(f"     page={src.get('page_number')}, doc={src.get('document_id')}, has_bbox={bool(src.get('bounding_boxes'))}")
    
    return len(sources), answer

def main():
    print("\n" + "="*70)
    print("🧪 TEST MEMORY BEHAVIOR - 2 CÂU HỎI LIÊN TIẾP")
    print(f"User ID: {USER_ID}")
    print(f"Session ID: {SESSION_ID}")
    print("="*70)
    
    # Câu hỏi 1: Hỏi thường (không yêu cầu nguồn)
    q1 = "Điều 15 Luật Hàng hải Việt Nam 2015 quy định gì về chủ tàu?"
    sources1, answer1 = send_message(q1, 1)
    
    print("\n⏳ Chờ 3 giây trước câu hỏi tiếp...")
    time.sleep(3)
    
    # Câu hỏi 2: Hỏi lại CÙNG NỘI DUNG nhưng YÊU CẦU TRA CỨU LẠI
    q2 = "Hãy TRA CỨU LẠI Điều 15 Luật Hàng hải 2015 về chủ tàu và cho tôi xem NGUỒN GỐC thông tin từ database."
    sources2, answer2 = send_message(q2, 2)
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"Câu hỏi 1 (thường): {sources1} sources")
    print(f"Câu hỏi 2 (yêu cầu tra cứu): {sources2} sources")
    
    if sources1 == 0 and sources2 > 0:
        print("✅ AI nhận biết câu hỏi lại và chỉ tra cứu khi user yêu cầu")
    elif sources1 > 0 and sources2 > 0:
        print("✅ AI luôn tra cứu (tốt cho accuracy)")
    elif sources1 == 0 and sources2 == 0:
        print("❌ AI KHÔNG TRA CỨU dù user yêu cầu - ĐÂY LÀ VẤN ĐỀ!")
    else:
        print("⚠️ Behavior không mong đợi")

if __name__ == "__main__":
    main()
