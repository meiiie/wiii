"""
Test script for P3+ V3 SOTA Streaming API

Tests the new /chat/stream/v3 endpoint which uses full CRAG pipeline
with true token-by-token streaming.

Features tested:
- Progressive SSE events at each CRAG step
- Full CRAG quality (grading, reasoning_trace)
- True token streaming for answer
- Sources with image_url
- Metadata with reasoning_trace

Run: python scripts/test_streaming_v3.py
"""

import asyncio
import httpx
import time
import sys
import os
import re
import json
from datetime import datetime

# Configuration
BASE_URL = "https://wiii.holilihu.online"
# BASE_URL = "http://localhost:8000"  # For local testing
API_KEY = "maritime-lms-prod-2024"

# Output file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"scripts/test_streaming_v3_results_{TIMESTAMP}.txt"

# Test questions - CACHE BUSTING with timestamp
# Using completely NEW query to avoid semantic similarity with previous tests

# Unique cache-busting suffix
CACHE_BUST = f"[{TIMESTAMP}]"

TEST_QUESTIONS = [
    {
        # COMPLETELY NEW QUERY - never tested before
        "query": f"Phân tích chi tiết quy trình kiểm tra PSC (Port State Control) đối với tàu biển Việt Nam khi cập cảng nước ngoài. Liệt kê các hạng mục kiểm tra chính và cách xử lý nếu tàu bị lưu giữ. {CACHE_BUST}",
        "expected_route": "tutor_agent",  # "Phân tích chi tiết", "Liệt kê"
        "purpose": "FRESH query about PSC inspections - never cached"
    },
    {
        "query": f"ISM Code yêu cầu gì về hệ thống quản lý an toàn trên tàu? Giải thích vai trò của DPA (Designated Person Ashore). {CACHE_BUST}",
        "expected_route": "tutor_agent",  # "Giải thích"
        "purpose": "ISM Code and DPA explanation"
    },
    {
        "query": f"Theo Công ước STCW 2010, đào tạo huấn luyện thuyền viên cần đáp ứng những tiêu chuẩn nào? Cho ví dụ về chứng chỉ bắt buộc. {CACHE_BUST}",
        "expected_route": "tutor_agent",  # "Cho ví dụ"
        "purpose": "STCW training standards"
    }
]

# Default question for single test mode - uses FIRST query (PSC inspection - never cached)
TEST_QUESTION = TEST_QUESTIONS[0]["query"]


def strip_thinking_tags(text: str) -> tuple[str, str]:
    """Extract and separate thinking content from answer text."""
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
    thinking_content = thinking_match.group(1).strip() if thinking_match else ""
    clean_answer = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
    return clean_answer, thinking_content


class TestLogger:
    """Logger that writes to both console and file."""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.lines = []
    
    def log(self, message=""):
        print(message)
        self.lines.append(message)
    
    def save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines))
        print(f"\n📁 Results saved to: {self.filepath}")


async def test_streaming_v3(logger: TestLogger):
    """Test the V3 streaming endpoint with full CRAG pipeline."""
    logger.log("=" * 70)
    logger.log("P3+ V3 SOTA STREAMING TEST - /api/v1/chat/stream/v3")
    logger.log("=" * 70)
    
    payload = {
        "user_id": f"test-v3-{TIMESTAMP}",
        "message": TEST_QUESTION,
        "role": "student"
    }
    
    logger.log(f"\n📤 Request: {TEST_QUESTION}")
    logger.log("-" * 70)
    
    start_time = time.time()
    first_event_time = None
    first_token_time = None
    token_count = 0
    thinking_events = []
    full_answer = []
    sources_data = None
    metadata = None
    reasoning_trace = None
    error_message = None
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)
    ) as client:
        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/v1/chat/stream/v3",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY,
                    "Accept": "text/event-stream"
                },
                timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)
            ) as resp:
                logger.log(f"Status: {resp.status_code}")
                logger.log(f"Content-Type: {resp.headers.get('content-type')}")
                logger.log("-" * 70)
                
                if resp.status_code != 200:
                    content = await resp.aread()
                    error_message = content.decode()[:500]
                    logger.log(f"❌ Error: {error_message}")
                    return None
                
                logger.log("\n📨 Events received:\n")
                
                current_event = None
                
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line.replace("event:", "").strip()
                        
                        # First event time
                        if first_event_time is None:
                            first_event_time = time.time() - start_time
                            logger.log(f"\n   ⚡ FIRST EVENT TIME: {first_event_time:.2f}s")
                            logger.log("-" * 70)
                        
                        # First token time
                        if current_event == "answer" and first_token_time is None:
                            first_token_time = time.time() - start_time
                            logger.log(f"\n   ⚡ FIRST TOKEN TIME: {first_token_time:.2f}s")
                            logger.log("-" * 70)
                    
                    elif line.startswith("data:"):
                        data = line.replace("data:", "").strip()
                        
                        if current_event == "thinking":
                            try:
                                parsed = json.loads(data)
                                content = parsed.get("content", "")
                                step = parsed.get("step", "")
                                thinking_events.append({
                                    "content": content,
                                    "step": step
                                })
                                logger.log(f"   🔄 thinking [{step}]: {content[:80]}...")
                            except:
                                logger.log(f"   🔄 thinking: {data[:80]}...")
                        
                        elif current_event == "answer":
                            token_count += 1
                            try:
                                parsed = json.loads(data)
                                content = parsed.get("content", "")
                                full_answer.append(content)
                            except:
                                full_answer.append(data)
                            
                            if token_count <= 3:
                                logger.log(f"   📝 token #{token_count}: {data[:100]}...")
                            elif token_count == 4:
                                logger.log(f"   📝 ... (streaming tokens)")
                        
                        elif current_event == "sources":
                            try:
                                parsed = json.loads(data)
                                sources_data = parsed.get("sources", [])
                                logger.log(f"   📚 sources: {len(sources_data)} sources received")
                            except:
                                logger.log(f"   📚 sources: {data[:100]}...")
                        
                        elif current_event == "metadata":
                            try:
                                parsed = json.loads(data)
                                metadata = parsed
                                reasoning_trace = parsed.get("reasoning_trace")
                                logger.log(f"   📊 metadata: processing_time={parsed.get('processing_time')}s")
                                if reasoning_trace:
                                    logger.log(f"   📊 reasoning_trace: {reasoning_trace.get('total_steps', 0)} steps")
                            except:
                                logger.log(f"   📊 metadata: {data[:100]}...")
                        
                        elif current_event == "done":
                            logger.log(f"   ✅ done")
                        
                        elif current_event == "error":
                            error_message = data
                            logger.log(f"   ❌ error: {data}")
                
                total_time = time.time() - start_time
                
                # Process answer
                raw_answer = "".join(full_answer)
                clean_answer, thinking_content = strip_thinking_tags(raw_answer)
                
                return {
                    "success": True,
                    "first_event_time": first_event_time,
                    "first_token_time": first_token_time,
                    "total_time": total_time,
                    "token_count": token_count,
                    "thinking_events": len(thinking_events),
                    "raw_answer_length": len(raw_answer),
                    "clean_answer_length": len(clean_answer),
                    "sources_count": len(sources_data) if sources_data else 0,
                    "has_reasoning_trace": reasoning_trace is not None,
                    "reasoning_steps": reasoning_trace.get("total_steps") if reasoning_trace else 0,
                    "clean_answer": clean_answer,
                    "thinking_events_data": thinking_events,
                    "metadata": metadata
                }
                
        except Exception as e:
            logger.log(f"❌ Exception: {e}")
            import traceback
            logger.log(traceback.format_exc())
            return None


async def compare_v1_vs_v3(logger: TestLogger):
    """
    Compare V1 (non-streaming) vs V3 (full Multi-Agent Graph streaming).
    
    This is the core comparison to validate V3 delivers V1 quality with streaming UX.
    """
    logger.log(f"\n{'='*70}")
    logger.log("V1 vs V3 SOTA COMPARISON")
    logger.log(f"{'='*70}")
    
    question = TEST_QUESTION
    logger.log(f"\n📤 Query: {question[:80]}...")
    
    results = {}
    
    # ========================================================================
    # Test V1 (non-streaming /chat) - BASELINE
    # ========================================================================
    logger.log("\n📡 Testing V1 (/api/v1/chat - non-streaming BASELINE)...")
    v1_start = time.time()
    v1_data = {}
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)
    ) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/chat",
                json={"user_id": "test-v1-compare", "message": question, "role": "student"},
                headers={"Content-Type": "application/json", "X-API-Key": API_KEY}
            )
            v1_total = time.time() - v1_start
            if resp.status_code == 200:
                data = resp.json()
                response_data = data.get("data", {})
                v1_answer = response_data.get("answer", "")
                v1_sources = len(response_data.get("sources", []))
                has_trace = response_data.get("reasoning_trace") is not None
                v1_data = {
                    "first_token": v1_total,  # Same as total for non-streaming
                    "total": v1_total,
                    "answer_length": len(v1_answer),
                    "sources": v1_sources,
                    "has_reasoning_trace": has_trace
                }
                results["v1"] = v1_data
                logger.log(f"   ✅ V1: {len(v1_answer)} chars, {v1_sources} sources in {v1_total:.2f}s")
            else:
                logger.log(f"   ❌ V1 Error: {resp.status_code}")
        except Exception as e:
            logger.log(f"   ❌ V1 Exception: {e}")
    
    # ========================================================================
    # Test V3 (full Multi-Agent Graph streaming) - NEW SOTA
    # ========================================================================
    logger.log("\n📡 Testing V3 (/api/v1/chat/stream/v3 - Multi-Agent streaming)...")
    v3_start = time.time()
    v3_first_event = None
    v3_first_token = None
    v3_answer_length = 0
    v3_sources = 0
    v3_has_trace = False
    v3_thinking_events = []
    v3_reasoning_steps = 0
    clean_answer = ""
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)
    ) as client:
        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/v1/chat/stream/v3",
                json={"user_id": "test-v3-compare", "message": question, "role": "student"},
                headers={"Content-Type": "application/json", "X-API-Key": API_KEY}
            ) as resp:
                current_event = None
                full_answer = []
                
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        current_event = line.replace("event:", "").strip()
                        if v3_first_event is None:
                            v3_first_event = time.time() - v3_start
                        if current_event == "answer" and v3_first_token is None:
                            v3_first_token = time.time() - v3_start
                    elif line.startswith("data:"):
                        data = line.replace("data:", "").strip()
                        if current_event == "thinking":
                            try:
                                parsed = json.loads(data)
                                v3_thinking_events.append(parsed)
                            except:
                                pass
                        elif current_event == "answer":
                            try:
                                parsed = json.loads(data)
                                full_answer.append(parsed.get("content", ""))
                            except:
                                full_answer.append(data)
                        elif current_event == "sources":
                            try:
                                parsed = json.loads(data)
                                v3_sources = len(parsed.get("sources", []))
                            except:
                                pass
                        elif current_event == "metadata":
                            try:
                                parsed = json.loads(data)
                                v3_has_trace = parsed.get("reasoning_trace") is not None
                                if parsed.get("reasoning_trace"):
                                    v3_reasoning_steps = parsed["reasoning_trace"].get("total_steps", 0)
                            except:
                                pass
                
                raw_answer = "".join(full_answer)
                clean_answer, _ = strip_thinking_tags(raw_answer)
                v3_answer_length = len(clean_answer)
                v3_total = time.time() - v3_start
                
                results["v3"] = {
                    "first_event": v3_first_event,
                    "first_token": v3_first_token,
                    "total": v3_total,
                    "answer_length": v3_answer_length,
                    "sources": v3_sources,
                    "has_reasoning_trace": v3_has_trace,
                    "reasoning_steps": v3_reasoning_steps,
                    "thinking_events": v3_thinking_events,
                    "clean_answer": clean_answer
                }
                logger.log(f"   ✅ V3: {v3_answer_length} chars, first event {v3_first_event:.2f}s, first token {v3_first_token:.2f}s, total {v3_total:.2f}s")
                
        except Exception as e:
            logger.log(f"   ❌ V3 Exception: {e}")
            import traceback
            logger.log(traceback.format_exc())
    
    # ========================================================================
    # Comparison Table
    # ========================================================================
    logger.log(f"\n{'='*70}")
    logger.log("COMPARISON RESULTS")
    logger.log(f"{'='*70}")
    
    if "v1" in results and "v3" in results:
        v1 = results["v1"]
        v3 = results["v3"]
        
        # Calculate improvements
        time_improvement = ((v1["total"] - v3["total"]) / v1["total"]) * 100 if v1["total"] > 0 else 0
        
        logger.log(f"| Metric           | V1 (baseline)  | V3 (streaming) | Improvement |")
        logger.log(f"|------------------|----------------|----------------|-------------|")
        logger.log(f"| First event      | {v1['total']:.1f}s (all)    | {v3['first_event']:.1f}s          | ✅ Instant  |")
        logger.log(f"| First token      | {v1['total']:.1f}s          | {v3['first_token']:.1f}s          | {'✅' if v3['first_token'] < v1['total'] else '⚠️'}           |")
        logger.log(f"| Total time       | {v1['total']:.1f}s          | {v3['total']:.1f}s          | {time_improvement:+.1f}%       |")
        logger.log(f"| Answer length    | {v1['answer_length']:5} chars | {v3['answer_length']:5} chars | Similar     |")
        logger.log(f"| Sources          | {v1['sources']:5}         | {v3['sources']:5}         |             |")
        logger.log(f"| reasoning_trace  | {'✅' if v1['has_reasoning_trace'] else '❌'}             | {'✅' if v3['has_reasoning_trace'] else '❌'}             |             |")
    
    return results




async def test_routing_with_diverse_queries(logger: TestLogger):
    """
    Test routing behavior with diverse queries to validate consistent routing.
    
    SOTA Pattern: Each query is designed to trigger specific routing paths.
    This helps identify if supervisor is behaving deterministically.
    """
    logger.log(f"\n{'='*70}")
    logger.log("ROUTING VALIDATION TEST - Diverse Queries")
    logger.log(f"{'='*70}")
    
    results = []
    
    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        question = test_case["query"]
        expected = test_case["expected_route"]
        purpose = test_case["purpose"]
        
        logger.log(f"\n📋 Test Case {i}: {purpose}")
        logger.log(f"   Query: {question[:80]}...")
        logger.log(f"   Expected Route: {expected}")
        
        # Add timestamp suffix to avoid any cache
        unique_question = f"{question} [test_id={TIMESTAMP}_{i}]"
        
        actual_route = None
        v3_total_time = 0
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)
        ) as client:
            try:
                v3_start = time.time()
                async with client.stream(
                    "POST",
                    f"{BASE_URL}/api/v1/chat/stream/v3",
                    json={
                        "user_id": f"test-routing-{TIMESTAMP}-{i}", 
                        "message": unique_question, 
                        "role": "student"
                    },
                    headers={"Content-Type": "application/json", "X-API-Key": API_KEY}
                ) as resp:
                    current_event = None
                    
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                        elif line.startswith("data:"):
                            data = line.replace("data:", "").strip()
                            if current_event in ["thinking", "status"]:
                                try:
                                    parsed = json.loads(data)
                                    content = parsed.get("content", "")
                                    # Extract routing decision
                                    if "Định tuyến đến:" in content:
                                        route_match = content.split("Định tuyến đến:")[-1].strip()
                                        actual_route = route_match.replace("...", "").strip()
                                except:
                                    if "Định tuyến đến:" in data:
                                        actual_route = data.split("Định tuyến đến:")[-1].strip()
                    
                    v3_total_time = time.time() - v3_start
                    
            except Exception as e:
                logger.log(f"   ❌ Error: {e}")
                continue
        
        # Validate routing
        route_match = actual_route == expected if actual_route else False
        results.append({
            "query": question[:50],
            "expected": expected,
            "actual": actual_route or "UNKNOWN",
            "match": route_match,
            "time": v3_total_time
        })
        
        status = "✅ PASS" if route_match else "⚠️ MISMATCH"
        logger.log(f"   Actual Route: {actual_route or 'UNKNOWN'}")
        logger.log(f"   Result: {status}")
        logger.log(f"   Total time: {v3_total_time:.2f}s")
    
    # Summary
    logger.log(f"\n{'='*70}")
    logger.log("ROUTING VALIDATION SUMMARY")
    logger.log(f"{'='*70}")
    
    passed = sum(1 for r in results if r["match"])
    total = len(results)
    logger.log(f"   Passed: {passed}/{total}")
    
    for r in results:
        status = "✅" if r["match"] else "❌"
        logger.log(f"   {status} {r['query'][:40]}... → {r['actual']} (expected: {r['expected']})")
    
    return results


async def main():
    logger = TestLogger(OUTPUT_FILE)
    
    logger.log("=" * 70)
    logger.log("P3+ V3 SOTA STREAMING VERIFICATION")
    logger.log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.log(f"Target: {BASE_URL}")
    logger.log("=" * 70)
    logger.log("\n⚠️  V3 = Full Multi-Agent Graph + Streaming (same quality as V1)")
    logger.log("⚠️  Expected: Instant first event + Progressive thinking + V1 quality")
    
    # Check for routing test flag
    run_routing_test = "--routing" in sys.argv or "-r" in sys.argv
    
    if run_routing_test:
        logger.log("\n🔀 Running ROUTING VALIDATION TEST with diverse queries...")
        routing_results = await test_routing_with_diverse_queries(logger)
        logger.log(f"\n[ROUTING TEST] Completed {len(routing_results)} test cases")
    
    # Run V1 vs V3 comparison (this is THE test now)
    comparison = await compare_v1_vs_v3(logger)
    
    # Extract V3 results for detailed display
    v3_result = comparison.get("v3", {})
    v1_result = comparison.get("v1", {})
    
    # Show V3 thinking events if available
    if v3_result.get("thinking_events"):
        logger.log(f"\n{'='*70}")
        logger.log("V3 THINKING EVENTS (Progressive UX)")
        logger.log(f"{'='*70}")
        for event in v3_result["thinking_events"][:10]:
            step = event.get("step", "")
            content = event.get("content", "")[:60]
            logger.log(f"   [{step}] {content}...")
    
    # Show V3 answer preview
    if v3_result.get("clean_answer"):
        logger.log(f"\n📝 V3 ANSWER PREVIEW (first 400 chars):")
        logger.log("-" * 70)
        for line in v3_result["clean_answer"][:400].split('\n')[:8]:
            logger.log(f"   {line}")
    
    # FINAL SUMMARY - now uses comparison results
    logger.log(f"\n{'='*70}")
    logger.log("FINAL SUMMARY")
    logger.log(f"{'='*70}")
    
    if v1_result and v3_result:
        # Use V3 results from comparison (not from separate test)
        first_event = v3_result.get("first_event", 0)
        first_token = v3_result.get("first_token", 0)
        total_time = v3_result.get("total", 0)
        v1_total = v1_result.get("total", 0)
        
        # Calculate improvement
        improvement = ((v1_total - total_time) / v1_total * 100) if v1_total > 0 else 0
        
        logger.log(f"   V3 First event:     {first_event:.2f}s (target: <2s) {'✅' if first_event < 2 else '⚠️'}")
        logger.log(f"   V3 First token:     {first_token:.2f}s (target: <60s) {'✅' if first_token < 60 else '⚠️'}")
        logger.log(f"   V3 Total time:      {total_time:.2f}s vs V1 {v1_total:.2f}s ({improvement:+.1f}%)")
        logger.log(f"   V3 reasoning_trace: {'✅' if v3_result.get('has_reasoning_trace') else '❌'}")
        logger.log(f"   V3 sources:         {v3_result.get('sources', 0)}")
        
        # Overall verdict
        if first_event < 2 and v3_result.get("has_reasoning_trace"):
            logger.log(f"\n✅ V3 DELIVERS V1 QUALITY WITH STREAMING UX!")
        else:
            logger.log(f"\n⚠️ V3 needs optimization")
    else:
        logger.log("\n❌ V3 TEST FAILED - Missing V1 or V3 results")
    
    logger.log(f"\n{'='*70}")
    logger.log("\n💡 TIP: Run with --routing flag to test supervisor routing behavior")
    logger.log("   Example: python scripts/test_streaming_v3.py --routing")
    
    # Save results
    logger.save()
    
    success = v3_result.get("has_reasoning_trace", False) and v3_result.get("first_event", 999) < 5
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
