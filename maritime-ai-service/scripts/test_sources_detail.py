"""
Test Sources Detail - Kiểm tra chi tiết sources và evidence images
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://wiii.holilihu.online")
API_KEY = os.getenv("API_KEY", "")

def test_sources_detail():
    """Test sources detail with image_url"""
    print("="*60)
    print("SOURCES & EVIDENCE IMAGES DETAIL TEST")
    print(f"Server: {PRODUCTION_URL}")
    print("="*60)
    
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    payload = {
        "message": "Điều kiện để đăng ký tàu biển Việt Nam là gì?",
        "user_id": "sources-test-user",
        "session_id": f"sources-test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "role": "student"
    }
    
    print(f"\n📤 Query: {payload['message']}")
    
    response = requests.post(
        f"{PRODUCTION_URL}/api/v1/chat/",
        json=payload,
        headers=headers,
        timeout=120
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return
    
    data = response.json()
    
    # Check sources
    sources = data.get("data", {}).get("sources", [])
    print(f"\n📊 Total Sources: {len(sources)}")
    
    with_image = 0
    without_image = 0
    
    for i, src in enumerate(sources):
        has_image = bool(src.get("image_url"))
        icon = "✅" if has_image else "❌"
        
        if has_image:
            with_image += 1
        else:
            without_image += 1
        
        print(f"\n{icon} Source {i+1}:")
        print(f"   Title: {src.get('title', 'N/A')[:60]}...")
        print(f"   Source: {src.get('source', 'N/A')}")
        print(f"   Relevance: {src.get('relevance_score', 'N/A')}")
        print(f"   Image URL: {src.get('image_url', 'None')[:60] if src.get('image_url') else 'None'}...")
        print(f"   Node ID: {src.get('node_id', 'N/A')[:20]}...")
        print(f"   Content: {src.get('content_snippet', 'N/A')[:80]}...")
    
    print(f"\n📊 SUMMARY:")
    print(f"   With image_url: {with_image}/{len(sources)}")
    print(f"   Without image_url: {without_image}/{len(sources)}")
    
    # Check evidence_images in metadata
    metadata = data.get("metadata", {})
    evidence_images = metadata.get("evidence_images", [])
    print(f"\n🖼️ Evidence Images in metadata: {len(evidence_images)}")
    for img in evidence_images:
        print(f"   - Page {img.get('page_number')}: {img.get('url', '')[:50]}...")


if __name__ == "__main__":
    test_sources_detail()
