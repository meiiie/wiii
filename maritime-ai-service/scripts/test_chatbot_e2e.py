"""
End-to-End Chatbot Test Script

Test luồng logic nghiệp vụ của Wiii:
1. Chat API hoạt động
2. RAG search trả về kết quả với evidence images
3. Agent xử lý câu hỏi về hàng hải
4. Memory/context được lưu trữ

Usage:
    python scripts/test_chatbot_e2e.py
    python scripts/test_chatbot_e2e.py --local
    python scripts/test_chatbot_e2e.py --render
"""
import os
import sys
import json
import requests
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
RENDER_URL = os.getenv("RENDER_URL", "https://maritime-ai-chatbot.onrender.com")
LOCAL_URL = "http://localhost:8000"
API_KEY = os.getenv("API_KEY", "")  # Get API key from .env

# Test cases - các câu hỏi về hàng hải
TEST_CASES = [
    {
        "name": "Câu hỏi cơ bản về Luật Hàng hải",
        "message": "Luật Hàng hải Việt Nam 2015 quy định những gì về tàu biển?",
        "expected_keywords": ["tàu biển", "luật", "hàng hải"],
        "check_evidence": True
    },
    {
        "name": "Câu hỏi về điều khoản cụ thể",
        "message": "Điều kiện để đăng ký tàu biển Việt Nam là gì?",
        "expected_keywords": ["đăng ký", "tàu"],
        "check_evidence": True
    },
    {
        "name": "Câu hỏi follow-up (test memory)",
        "message": "Còn về thuyền viên thì sao?",
        "expected_keywords": ["thuyền viên"],
        "check_evidence": True
    }
]


def get_base_url(use_local: bool = False) -> str:
    """Get base URL based on environment"""
    return LOCAL_URL if use_local else RENDER_URL


def check_health(base_url: str) -> dict:
    """Check server health and get system info"""
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=30)
        if response.status_code == 200:
            return {"healthy": True, "data": response.json()}
        return {"healthy": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_knowledge_stats(base_url: str) -> dict:
    """Get knowledge base statistics"""
    try:
        response = requests.get(f"{base_url}/api/v1/knowledge/stats", timeout=30)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def send_chat_message(base_url: str, message: str, user_id: str = "test-user", session_id: str = None) -> dict:
    """Send a chat message and get response"""
    try:
        payload = {
            "message": message,
            "user_id": user_id,
            "session_id": session_id or f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "role": "student"  # Use student role for tutor-style responses
        }
        
        headers = {}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        
        response = requests.post(
            f"{base_url}/api/v1/chat/",
            json=payload,
            headers=headers,
            timeout=120  # 2 minutes for complex queries
        )
        
        if response.status_code == 200:
            data = response.json()
            # Debug: print raw response structure
            print(f"   🔍 Raw response keys: {list(data.keys())}")
            if "data" in data:
                print(f"   🔍 data keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else type(data['data'])}")
                if isinstance(data['data'], dict) and 'answer' in data['data']:
                    print(f"   🔍 answer length: {len(data['data']['answer'])}")
            return {"success": True, "data": data}
        else:
            return {
                "success": False, 
                "error": f"Status {response.status_code}",
                "detail": response.text[:500]
            }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out (120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_response(response_data: dict, test_case: dict) -> dict:
    """Analyze chat response against expected criteria"""
    analysis = {
        "has_response": False,
        "has_expected_keywords": False,
        "has_evidence_images": False,
        "response_length": 0,
        "evidence_count": 0,
        "issues": []
    }
    
    if not response_data.get("success"):
        analysis["issues"].append(f"Request failed: {response_data.get('error')}")
        return analysis
    
    # API response structure: {"status": "success", "data": {"answer": "...", "sources": [...], ...}}
    api_response = response_data.get("data", {})
    inner_data = api_response.get("data", {})
    
    # Get answer from nested data structure
    response_text = inner_data.get("answer", "") or inner_data.get("response", "") or api_response.get("answer", "")
    
    # Check response exists
    analysis["has_response"] = bool(response_text)
    analysis["response_length"] = len(response_text)
    
    if not analysis["has_response"]:
        analysis["issues"].append("No response text received")
        return analysis
    
    # Check expected keywords
    response_lower = response_text.lower()
    found_keywords = []
    missing_keywords = []
    
    for keyword in test_case.get("expected_keywords", []):
        if keyword.lower() in response_lower:
            found_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    
    analysis["has_expected_keywords"] = len(found_keywords) > 0
    analysis["found_keywords"] = found_keywords
    analysis["missing_keywords"] = missing_keywords
    
    if missing_keywords:
        analysis["issues"].append(f"Missing keywords: {missing_keywords}")
    
    # Check evidence images/sources
    if test_case.get("check_evidence"):
        # Sources are in inner_data.sources
        evidence = inner_data.get("sources", []) or api_response.get("sources", [])
        analysis["evidence_count"] = len(evidence) if evidence else 0
        analysis["has_evidence_images"] = analysis["evidence_count"] > 0
        
        # Check if sources have image_url
        if evidence:
            sources_with_images = [s for s in evidence if s.get("image_url")]
            analysis["sources_with_images"] = len(sources_with_images)
        
        if not analysis["has_evidence_images"]:
            analysis["issues"].append("No sources returned (may be expected for some queries)")
    
    return analysis


def run_tests(base_url: str, verbose: bool = True) -> dict:
    """Run all test cases"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "base_url": base_url,
        "health_check": None,
        "knowledge_stats": None,
        "test_results": [],
        "summary": {
            "total": len(TEST_CASES),
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    }
    
    print("=" * 60)
    print("MARITIME AI TUTOR - END-TO-END TEST")
    print(f"Server: {base_url}")
    print(f"Time: {results['timestamp']}")
    print("=" * 60)
    
    # Health check
    print("\n🔍 Checking server health...")
    health = check_health(base_url)
    results["health_check"] = health
    
    if not health.get("healthy"):
        print(f"❌ Server not healthy: {health.get('error')}")
        return results
    print("✅ Server is healthy")
    
    # Knowledge stats
    print("\n📊 Checking knowledge base...")
    stats = check_knowledge_stats(base_url)
    results["knowledge_stats"] = stats
    
    if "error" not in stats:
        total_docs = stats.get("total_documents", 0) or stats.get("total_chunks", 0)
        print(f"✅ Knowledge base: {total_docs} documents/chunks")
    else:
        print(f"⚠️ Could not get stats: {stats.get('error')}")
    
    # Run test cases
    print("\n" + "-" * 60)
    print("RUNNING TEST CASES")
    print("-" * 60)
    
    session_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Check API key
    if not API_KEY:
        print("\n⚠️ Warning: No API_KEY found in .env - requests may fail with 401")
    else:
        print(f"\n🔑 Using API key: {API_KEY[:8]}...")
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n📝 Test {i}/{len(TEST_CASES)}: {test_case['name']}")
        print(f"   Message: {test_case['message'][:50]}...")
        
        # Send message with same session_id for follow-up tests
        response = send_chat_message(base_url, test_case["message"], "test-user", session_id)
        
        # Analyze response
        analysis = analyze_response(response, test_case)
        
        # Determine result
        test_result = {
            "name": test_case["name"],
            "message": test_case["message"],
            "response": response,
            "analysis": analysis,
            "status": "PASSED"
        }
        
        if not analysis["has_response"]:
            test_result["status"] = "FAILED"
            results["summary"]["failed"] += 1
        elif analysis["issues"]:
            test_result["status"] = "WARNING"
            results["summary"]["warnings"] += 1
        else:
            results["summary"]["passed"] += 1
        
        results["test_results"].append(test_result)
        
        # Print result
        status_icon = {"PASSED": "✅", "FAILED": "❌", "WARNING": "⚠️"}[test_result["status"]]
        print(f"   {status_icon} Status: {test_result['status']}")
        print(f"   📏 Response length: {analysis['response_length']} chars")
        print(f"   🖼️ Evidence images: {analysis['evidence_count']}")
        
        if analysis["issues"] and verbose:
            for issue in analysis["issues"]:
                print(f"   ⚠️ {issue}")
        
        if verbose and analysis["has_response"]:
            # Get actual response text
            api_data = response.get("data", {})
            inner_data = api_data.get("data", {})
            response_text = inner_data.get("answer", "")[:300]
            print(f"   📄 Response preview: {response_text}...")
            
            # Show sources with images
            sources = inner_data.get("sources", [])
            if sources:
                sources_with_img = sum(1 for s in sources if s.get("image_url"))
                print(f"   🖼️ Sources with image_url: {sources_with_img}/{len(sources)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Total: {results['summary']['total']}")
    print(f"✅ Passed: {results['summary']['passed']}")
    print(f"⚠️ Warnings: {results['summary']['warnings']}")
    print(f"❌ Failed: {results['summary']['failed']}")
    
    success_rate = (results['summary']['passed'] / results['summary']['total']) * 100
    print(f"\n🎯 Success Rate: {success_rate:.1f}%")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Test Wiii chatbot')
    parser.add_argument('--local', action='store_true', help='Use local server')
    parser.add_argument('--render', action='store_true', help='Use Render server (default)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--save', action='store_true', help='Save results to file')
    args = parser.parse_args()
    
    base_url = LOCAL_URL if args.local else RENDER_URL
    
    results = run_tests(base_url, verbose=args.verbose or True)
    
    if args.save:
        filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Results saved to: {filename}")
    
    # Exit code based on results
    if results["summary"]["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
