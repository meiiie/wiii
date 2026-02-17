"""
Sprint 103 Post-Implementation: 200-Message Live API Test
Tests routing accuracy, response quality, latency, and error rates.

Categories:
  1. Social/Greeting (20 msgs) → expect DIRECT
  2. Personal/Memory (20 msgs) → expect MEMORY
  3. Domain Knowledge - Maritime (30 msgs) → expect RAG
  4. Teaching/Learning (20 msgs) → expect TUTOR
  5. Off-topic (20 msgs) → expect DIRECT
  6. Web Search (20 msgs) → expect DIRECT (with tools)
  7. Legal Search (15 msgs) → expect DIRECT (with tools)
  8. News Search (15 msgs) → expect DIRECT (with tools)
  9. Vietnamese No-Diacritics (20 msgs) → mixed routing
  10. Edge Cases (20 msgs) → mixed routing
"""

import asyncio
import aiohttp
import json
import time
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

API_URL = "http://localhost:8000/api/v1/chat"
API_KEY = "local-dev-key"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

# ---------------------------------------------------------------------------
# Test Messages by Category
# ---------------------------------------------------------------------------

SOCIAL_GREETING = [
    "Xin chào",
    "Hello",
    "Chào bạn",
    "Hi there",
    "Chào buổi sáng",
    "Cảm ơn bạn",
    "Tạm biệt",
    "Bye bye",
    "Chúc ngủ ngon",
    "Cảm ơn nhiều lắm",
    "Hẹn gặp lại nhé",
    "Chào buổi tối",
    "Good morning",
    "Thanks",
    "Bạn khỏe không?",
    "Mình đi đây",
    "Ok cảm ơn nha",
    "Được rồi, cảm ơn",
    "Vâng ạ",
    "Dạ vâng",
]

PERSONAL_MEMORY = [
    "Tên tôi là gì?",
    "Bạn có nhớ tôi không?",
    "Lần trước mình nói chuyện về gì?",
    "Tôi thích gì nhỉ?",
    "Nhớ lại cuộc trò chuyện trước đi",
    "Tôi quê ở đâu?",
    "Sở thích của tôi là gì?",
    "Tôi học ở trường nào?",
    "Bạn biết gì về tôi?",
    "Tôi bao nhiêu tuổi?",
    "Hãy nhớ rằng tôi thích cà phê",
    "Tên tôi là Minh, nhớ nhé",
    "Quê tôi ở Hải Phòng",
    "Tôi là sinh viên năm 3",
    "Nhớ lần trước không?",
    "Mình đã hỏi gì trước đó?",
    "Bạn có biết nghề nghiệp của tôi không?",
    "Tôi đang học chuyên ngành gì?",
    "Tôi sống ở đâu?",
    "Ghi nhớ là tôi thích bóng đá",
]

DOMAIN_MARITIME = [
    "COLREGs Rule 13 là gì?",
    "Quy tắc tránh va trên biển",
    "SOLAS chương III nói về gì?",
    "MARPOL Annex VI quy định gì?",
    "Tín hiệu đèn tàu thuyền ban đêm",
    "Quy định an toàn hàng hải quốc tế",
    "STCW là gì và áp dụng như thế nào?",
    "ISM Code quy định những gì?",
    "Luật biển Việt Nam quy định vùng lãnh hải bao xa?",
    "Điều 15 COLREGs nói về tình huống đối hướng",
    "Cách xác định tàu nhường đường trong COLREGs",
    "Tàu máy và tàu buồm ai nhường ai?",
    "Quy tắc hành trình trong luồng hẹp",
    "Hệ thống phân luồng giao thông hàng hải",
    "An toàn cứu sinh trên tàu biển",
    "Thiết bị chống cháy trên tàu theo SOLAS",
    "Chứng chỉ thuyền viên theo STCW",
    "Quy định xả thải trên biển theo MARPOL",
    "Kiểm tra tàu biển theo PSC là gì?",
    "Đèn hành trình của tàu đánh cá",
    "Tàu neo đậu cần hiển thị tín hiệu gì?",
    "Quy định về cầu cảng và bến cảng",
    "An toàn hoa tiêu hàng hải",
    "MLC 2006 quy định gì cho thuyền viên?",
    "Luật Hàng hải Việt Nam 2015 có bao nhiêu chương?",
    "IMDG Code áp dụng cho hàng hóa nào?",
    "Tàu chở dầu cần tuân thủ quy định nào?",
    "Khu vực đặc biệt theo MARPOL là gì?",
    "Hệ thống VTS hoạt động như thế nào?",
    "Quy trình man overboard trên tàu biển",
]

TEACHING_LEARNING = [
    "Giải thích COLREGs Rule 13 cho mình",
    "Dạy tôi về SOLAS",
    "Hãy giải thích chi tiết về tín hiệu đèn tàu",
    "Cho ví dụ về tình huống tránh va",
    "Quiz về COLREGs cho tôi",
    "Giảng bài về MARPOL Annex I",
    "Phân tích tình huống tàu gặp nhau",
    "Tại sao tàu máy phải nhường tàu buồm?",
    "So sánh SOLAS và MARPOL",
    "Làm bài tập về đèn hành trình",
    "Hướng dẫn cách đọc hải đồ",
    "Giải thích nguyên lý hoạt động radar hàng hải",
    "Dạy tôi cách tính toán ổn định tàu",
    "Cho bài test về an toàn hàng hải",
    "Trình bày quy trình rời cảng an toàn",
    "Phân biệt các loại phao tiêu hàng hải",
    "Hướng dẫn sử dụng la bàn từ",
    "Giải thích hiệu ứng tương tác giữa hai tàu",
    "Tóm tắt nội dung chính của ISM Code",
    "Kiểm tra kiến thức về STCW Convention",
]

OFF_TOPIC = [
    "Python là gì?",
    "Cách nấu phở bò",
    "Thời tiết hôm nay thế nào?",
    "Ai là tổng thống Mỹ?",
    "Cách học tiếng Anh hiệu quả",
    "Bitcoin giá bao nhiêu?",
    "Viết code JavaScript cho tôi",
    "Cách làm bánh mì",
    "Bóng đá Việt Nam hôm nay",
    "Cách giảm cân nhanh",
    "Lịch sử Việt Nam thời Lê",
    "Công thức nấu cơm tấm",
    "Cách chơi piano",
    "Thủ đô nước Pháp là gì?",
    "Trái đất quay quanh mặt trời bao lâu?",
    "Cách trồng cây trong nhà",
    "Ai phát minh ra điện thoại?",
    "Cách viết CV xin việc",
    "Hà Nội có gì vui?",
    "Cách sửa xe máy bị hỏng",
]

WEB_SEARCH = [
    "Tìm trên mạng về tàu biển lớn nhất",
    "Search Google về COLREGs 2026",
    "Tra cứu trên internet quy định mới",
    "Giá dầu hôm nay bao nhiêu?",
    "Thời tiết biển Đông tuần này",
    "Tìm kiếm thông tin về cảng Cát Lái",
    "Google cho tôi về IMO 2026",
    "Tra cứu website Cục Hàng hải",
    "Tìm thông tin tuyển dụng thuyền viên",
    "Kiểm tra lịch tàu cập cảng hôm nay",
    "Tìm số điện thoại Cảng vụ Hải Phòng",
    "Xem bản đồ hàng hải trực tuyến",
    "Tra cứu danh sách cảng Việt Nam",
    "Tìm giá cước vận tải biển 2026",
    "Kiểm tra tình trạng thời tiết biển",
    "Xem giá nhiên liệu tàu biển",
    "Tìm thông tin đào tạo hàng hải",
    "Search tuyến hàng hải quốc tế",
    "Tra cứu mã HS hàng hóa xuất khẩu",
    "Kiểm tra giá vé tàu cao tốc",
]

LEGAL_SEARCH = [
    "Nghị định 100 về phạt giao thông",
    "Thông tư mới nhất của Bộ GTVT",
    "Luật Hàng hải Việt Nam sửa đổi 2026",
    "Văn bản pháp luật về an toàn hàng hải",
    "Nghị định xử phạt vi phạm hành chính trên biển",
    "Quy chuẩn kỹ thuật quốc gia về tàu biển",
    "Luật số 40 về hàng hải",
    "Bộ luật hình sự quy định về tai nạn hàng hải",
    "Thông tư 15 về an toàn lao động hàng hải",
    "Nghị định về đăng kiểm tàu biển",
    "Pháp lệnh về thuyền viên tàu biển",
    "Quy định pháp luật về bảo hiểm hàng hải",
    "Nghị quyết về phát triển kinh tế biển",
    "Luật biển Việt Nam 2012 nội dung chính",
    "Văn bản hướng dẫn thi hành luật hàng hải",
]

NEWS_SEARCH = [
    "Tin tức hàng hải hôm nay",
    "Thời sự Việt Nam về kinh tế biển",
    "Bản tin sáng nay về vận tải biển",
    "Báo chí nói gì về cảng biển Việt Nam",
    "Tin tức mới nhất về IMO",
    "Thời sự quốc tế về hàng hải",
    "Tin nóng về tai nạn tàu biển",
    "Bản tin thời tiết biển hôm nay",
    "Tin tức về ngành logistics Việt Nam",
    "Tin mới nhất về Cục Hàng hải",
    "Báo cáo thị trường vận tải biển",
    "Tin tức đóng tàu Việt Nam",
    "Thời sự về biển Đông",
    "Tin tức nghề cá Việt Nam",
    "Bản tin kinh tế hàng hải tuần này",
]

NO_DIACRITICS = [
    "xin chao ban",
    "COLREGs la gi?",
    "giai thich SOLAS chuong III",
    "ten toi la Minh",
    "tim tren mang ve tau bien",
    "nghi dinh 100",
    "tin tuc hang hai",
    "hoc ve an toan hang hai",
    "cach nau pho bo",
    "thoi tiet hom nay",
    "luat hang hai Viet Nam",
    "toi que o Hai Phong",
    "day toi ve MARPOL",
    "cam on ban nhieu",
    "kiem tra kien thuc COLREGs",
    "ban co nho toi khong",
    "tra cuu van ban phap luat",
    "ban tin thoi su",
    "giai thich den hanh trinh tau",
    "Python la gi",
]

EDGE_CASES = [
    "?",
    "...",
    "a",
    "ok",
    "hmm",
    "   ",
    "🚢",
    "12345",
    "COLREGs" * 50,  # Very long repetitive
    "A" * 500,  # Long single char
    "Tôi muốn hỏi về COLREGs nhưng cũng muốn biết tin tức và nhớ tên tôi",  # Multi-intent
    "Không",
    "Có",
    "Tàu",  # Polysemy: ship vs train
    "Rule 13",
    "Vì sao?",
    "Tiếp tục",
    "Nói lại đi",
    "Tôi không hiểu",
    "Hết rồi à?",
]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    category: str
    query: str
    status: str  # "success" | "error" | "timeout"
    response_time_ms: float
    answer_length: int = 0
    answer_preview: str = ""
    routing_intent: str = ""
    domain_notice: Optional[str] = None
    error_msg: str = ""
    metadata: dict = field(default_factory=dict)


async def send_message(session: aiohttp.ClientSession, message: str, idx: int) -> dict:
    """Send a single message to the API."""
    payload = {
        "message": message,
        "user_id": "test-sprint103-audit",
        "role": "student",
    }
    start = time.monotonic()
    try:
        async with session.post(
            API_URL, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            elapsed = (time.monotonic() - start) * 1000
            body = await resp.json()
            return {"status_code": resp.status, "body": body, "elapsed_ms": elapsed}
    except asyncio.TimeoutError:
        elapsed = (time.monotonic() - start) * 1000
        return {"status_code": 0, "body": {}, "elapsed_ms": elapsed, "error": "TIMEOUT"}
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return {"status_code": 0, "body": {}, "elapsed_ms": elapsed, "error": str(e)}


async def run_category(
    session: aiohttp.ClientSession,
    category: str,
    messages: list,
    results: list,
    semaphore: asyncio.Semaphore,
    progress: dict,
):
    """Run all messages in a category sequentially (to avoid rate limits)."""
    for i, msg in enumerate(messages):
        async with semaphore:
            display_msg = msg[:60] + "..." if len(msg) > 60 else msg
            progress["done"] += 1
            n = progress["done"]
            total = progress["total"]
            pct = n * 100 // total
            print(f"  [{n:3d}/{total}] ({pct:2d}%) [{category:18s}] {display_msg}", flush=True)

            resp = await send_message(session, msg, i)

            result = TestResult(
                category=category,
                query=msg[:100],
                status="error",
                response_time_ms=resp["elapsed_ms"],
            )

            if "error" in resp:
                result.error_msg = resp["error"]
                result.status = "timeout" if "TIMEOUT" in resp.get("error", "") else "error"
            elif resp["status_code"] == 200 and resp["body"].get("status") == "success":
                data = resp["body"].get("data", {})
                meta = resp["body"].get("metadata", {})
                answer = data.get("answer", "")
                result.status = "success"
                result.answer_length = len(answer)
                result.answer_preview = answer[:120].replace("\n", " ")
                result.domain_notice = data.get("domain_notice")
                result.metadata = meta
                # Try to extract routing info from metadata
                routing = meta.get("routing_metadata", {})
                result.routing_intent = routing.get("intent", "unknown")
            else:
                result.status = "error"
                result.error_msg = json.dumps(resp["body"], ensure_ascii=False)[:200]

            results.append(result)

            # Small delay to avoid hammering the server
            await asyncio.sleep(0.3)


async def main():
    print("=" * 80)
    print("  Wiii AI — 200-Message Live API Test (Sprint 103)")
    print("=" * 80)
    print()

    all_categories = [
        ("Social/Greeting", SOCIAL_GREETING),
        ("Personal/Memory", PERSONAL_MEMORY),
        ("Domain/Maritime", DOMAIN_MARITIME),
        ("Teaching/Learning", TEACHING_LEARNING),
        ("Off-Topic", OFF_TOPIC),
        ("Web Search", WEB_SEARCH),
        ("Legal Search", LEGAL_SEARCH),
        ("News Search", NEWS_SEARCH),
        ("No-Diacritics", NO_DIACRITICS),
        ("Edge Cases", EDGE_CASES),
    ]

    total_msgs = sum(len(msgs) for _, msgs in all_categories)
    print(f"Total messages: {total_msgs}")
    print(f"Categories: {len(all_categories)}")
    print()

    results: list[TestResult] = []
    progress = {"done": 0, "total": total_msgs}

    # Use semaphore to control concurrency (sequential per category, 2 categories at a time)
    semaphore = asyncio.Semaphore(2)

    start_time = time.monotonic()

    async with aiohttp.ClientSession() as session:
        # Run categories with some parallelism
        tasks = []
        for cat_name, cat_msgs in all_categories:
            task = asyncio.create_task(
                run_category(session, cat_name, cat_msgs, results, semaphore, progress)
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

    total_time = time.monotonic() - start_time

    # ---------------------------------------------------------------------------
    # Analysis
    # ---------------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  RESULTS ANALYSIS")
    print("=" * 80)

    # 1. Overall stats
    success = [r for r in results if r.status == "success"]
    errors = [r for r in results if r.status == "error"]
    timeouts = [r for r in results if r.status == "timeout"]

    print(f"\n--- Overall ---")
    print(f"Total:    {len(results)}")
    print(f"Success:  {len(success)} ({len(success)*100//len(results)}%)")
    print(f"Errors:   {len(errors)}")
    print(f"Timeouts: {len(timeouts)}")
    print(f"Total time: {total_time:.1f}s")

    if success:
        latencies = [r.response_time_ms for r in success]
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        p50 = sorted(latencies)[len(latencies) // 2]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"\n--- Latency (success only) ---")
        print(f"Avg:  {avg_lat:.0f}ms")
        print(f"Min:  {min_lat:.0f}ms")
        print(f"Max:  {max_lat:.0f}ms")
        print(f"P50:  {p50:.0f}ms")
        print(f"P95:  {p95:.0f}ms")

    # 2. Per-category stats
    print(f"\n--- Per Category ---")
    print(f"{'Category':20s} {'OK':>4s} {'Err':>4s} {'TO':>4s} {'Avg(ms)':>8s} {'P95(ms)':>8s} {'AvgLen':>7s}")
    print("-" * 60)

    for cat_name, _ in all_categories:
        cat_results = [r for r in results if r.category == cat_name]
        cat_ok = [r for r in cat_results if r.status == "success"]
        cat_err = len([r for r in cat_results if r.status == "error"])
        cat_to = len([r for r in cat_results if r.status == "timeout"])

        if cat_ok:
            cat_lats = [r.response_time_ms for r in cat_ok]
            cat_avg = sum(cat_lats) / len(cat_lats)
            cat_p95 = sorted(cat_lats)[int(len(cat_lats) * 0.95)]
            cat_avg_len = sum(r.answer_length for r in cat_ok) // len(cat_ok)
        else:
            cat_avg = cat_p95 = cat_avg_len = 0

        print(f"{cat_name:20s} {len(cat_ok):4d} {cat_err:4d} {cat_to:4d} {cat_avg:8.0f} {cat_p95:8.0f} {cat_avg_len:7d}")

    # 3. Routing intent distribution
    print(f"\n--- Routing Intent Distribution ---")
    intent_counts = defaultdict(int)
    for r in success:
        intent_counts[r.routing_intent] += 1
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"  {intent:20s}: {count:4d} ({count*100//len(success):2d}%)")

    # 4. Domain notice analysis
    notices = [r for r in success if r.domain_notice]
    print(f"\n--- Domain Notice ---")
    print(f"Messages with domain_notice: {len(notices)}/{len(success)}")
    if notices:
        notice_cats = defaultdict(int)
        for r in notices:
            notice_cats[r.category] += 1
        for cat, count in sorted(notice_cats.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    # 5. Errors detail
    if errors or timeouts:
        print(f"\n--- Errors & Timeouts ---")
        for r in (errors + timeouts)[:20]:
            print(f"  [{r.category}] {r.query[:60]} → {r.status}: {r.error_msg[:100]}")

    # 6. Routing accuracy check (expected vs actual)
    print(f"\n--- Routing Accuracy (Heuristic) ---")
    expected_map = {
        "Social/Greeting": {"social", "greeting", "unknown"},
        "Personal/Memory": {"personal", "unknown"},
        "Domain/Maritime": {"lookup", "learning", "unknown"},
        "Teaching/Learning": {"learning", "lookup", "unknown"},
        "Off-Topic": {"off_topic", "general", "unknown", "web_search"},
        "Web Search": {"web_search", "lookup", "off_topic", "unknown"},
        "Legal Search": {"web_search", "lookup", "unknown"},
        "News Search": {"web_search", "unknown", "off_topic"},
        "No-Diacritics": {"social", "personal", "lookup", "learning", "off_topic", "web_search", "unknown", "greeting", "general"},
        "Edge Cases": {"social", "off_topic", "unknown", "lookup", "learning", "greeting", "general", "personal", "web_search"},
    }

    total_checked = 0
    total_matched = 0
    for cat_name, expected_intents in expected_map.items():
        cat_results = [r for r in success if r.category == cat_name]
        matched = sum(1 for r in cat_results if r.routing_intent in expected_intents)
        mismatched = [r for r in cat_results if r.routing_intent not in expected_intents]
        total_checked += len(cat_results)
        total_matched += matched
        pct = matched * 100 // len(cat_results) if cat_results else 0
        print(f"  {cat_name:20s}: {matched}/{len(cat_results)} ({pct}%) match expected")
        for r in mismatched[:3]:
            print(f"    MISMATCH: '{r.query[:50]}' → intent={r.routing_intent}")

    if total_checked:
        print(f"\n  Overall routing accuracy: {total_matched}/{total_checked} ({total_matched*100//total_checked}%)")

    # 7. Answer quality samples
    print(f"\n--- Answer Quality Samples ---")
    for cat_name, _ in all_categories:
        cat_ok = [r for r in success if r.category == cat_name]
        if cat_ok:
            sample = cat_ok[0]
            print(f"\n  [{cat_name}] Q: {sample.query[:60]}")
            print(f"    A: {sample.answer_preview[:100]}")
            print(f"    Intent: {sample.routing_intent} | Len: {sample.answer_length} | {sample.response_time_ms:.0f}ms")

    # 8. Slow queries (>30s)
    slow = [r for r in success if r.response_time_ms > 30000]
    if slow:
        print(f"\n--- Slow Queries (>30s) ---")
        for r in sorted(slow, key=lambda x: -x.response_time_ms):
            print(f"  {r.response_time_ms/1000:.1f}s [{r.category}] {r.query[:60]}")

    # 9. Empty/very short answers
    short = [r for r in success if r.answer_length < 20]
    if short:
        print(f"\n--- Very Short Answers (<20 chars) ---")
        for r in short:
            print(f"  [{r.category}] Q: {r.query[:50]} → A: '{r.answer_preview}'")

    # Save detailed results to JSON
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_messages": len(results),
        "success": len(success),
        "errors": len(errors),
        "timeouts": len(timeouts),
        "total_time_seconds": round(total_time, 1),
        "results": [
            {
                "category": r.category,
                "query": r.query,
                "status": r.status,
                "response_time_ms": round(r.response_time_ms),
                "answer_length": r.answer_length,
                "answer_preview": r.answer_preview,
                "routing_intent": r.routing_intent,
                "domain_notice": r.domain_notice,
                "error_msg": r.error_msg,
            }
            for r in results
        ],
    }

    output_path = "scripts/test_200_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nDetailed results saved to: {output_path}")

    print("\n" + "=" * 80)
    print("  TEST COMPLETE")
    print("=" * 80)

    # Return exit code
    if len(errors) + len(timeouts) > len(results) * 0.1:
        print("\nWARNING: >10% failure rate!")
        return 1
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
