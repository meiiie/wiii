"""
Sprint 148: Quick test for Product Search tools.
Tests all 5 platforms via Serper.dev + Excel report generation.
"""
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_google_shopping():
    """Test Serper.dev Google Shopping search."""
    print("=" * 60)
    print("TEST 1: Google Shopping (Serper /shopping)")
    print("=" * 60)

    from app.engine.tools.product_search_tools import tool_search_google_shopping

    result = tool_search_google_shopping.invoke({
        "query": "cuộn dây điện 3 ruột 2.5mm²",
        "max_results": 5,
    })

    data = json.loads(result)

    if "error" in data:
        print(f"  ERROR: {data['error']}")
        return False

    products = data.get("results", [])
    print(f"  Found: {data.get('count', 0)} products")

    for i, p in enumerate(products[:5], 1):
        price = p.get("price") or p.get("extracted_price", "N/A")
        print(f"  {i}. {p.get('title', 'N/A')[:60]}")
        print(f"     Price: {price} | Source: {p.get('source', 'N/A')}")

    return len(products) > 0


def test_platform(platform_name, tool_fn):
    """Test a platform-specific search tool."""
    print("=" * 60)
    print(f"TEST: {platform_name} (Serper site: filter)")
    print("=" * 60)

    result = tool_fn.invoke({
        "query": "dây điện 3 ruột 2.5mm",
        "max_results": 5,
    })

    data = json.loads(result)

    if "error" in data:
        print(f"  ERROR: {data['error']}")
        return False

    products = data.get("results", [])
    print(f"  Found: {data.get('count', 0)} results")

    for i, p in enumerate(products[:3], 1):
        print(f"  {i}. {p.get('title', 'N/A')[:60]}")
        print(f"     Link: {p.get('link', 'N/A')[:55]}")

    return len(products) > 0


def test_excel_report():
    """Test Excel report generation."""
    print("=" * 60)
    print("TEST: Excel Report Generation")
    print("=" * 60)

    from app.engine.tools.excel_report_tool import tool_generate_product_report

    sample_products = [
        {"platform": "Google Shopping", "title": "Dây điện Cadivi 3x2.5mm² (100m)", "price": "450,000₫", "extracted_price": 450000, "seller": "Điện Quang", "rating": 4.8, "sold_count": 150, "link": "https://example.com/1"},
        {"platform": "Shopee", "title": "Cuộn dây điện 3 ruột 2.5mm Sino", "price": "380,000₫", "extracted_price": 380000, "seller": "Siêu thị điện", "rating": 4.5, "sold_count": 80, "link": "https://shopee.vn/2"},
        {"platform": "Lazada", "title": "Dây cáp điện LS 3x2.5mm² cuộn 100m", "price": "520,000₫", "extracted_price": 520000, "seller": "LS Cable VN", "rating": 4.9, "sold_count": 200, "link": "https://lazada.vn/3"},
    ]

    result = tool_generate_product_report.invoke({
        "products_json": json.dumps(sample_products, ensure_ascii=False),
        "title": "So sánh dây điện 3x2.5mm²",
    })

    data = json.loads(result)

    if "error" in data:
        print(f"  ERROR: {data['error']}")
        return False

    print(f"  File: {data['file_path']}")
    print(f"  Products: {data['total_products']}")
    print(f"  Min: {data['min_price']:,.0f}d | Max: {data['max_price']:,.0f}d")
    return True


def main():
    print()
    print("Sprint 148: Product Search — Live API Test")
    print("=" * 60)
    print()

    from app.engine.tools.product_search_tools import (
        tool_search_shopee,
        tool_search_tiktok_shop,
        tool_search_lazada,
        tool_search_facebook_marketplace,
    )

    results = {}

    # Google Shopping
    try:
        results["Google Shopping"] = test_google_shopping()
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results["Google Shopping"] = False
    print()

    # Platform searches
    platforms = {
        "Shopee": tool_search_shopee,
        "Lazada": tool_search_lazada,
        "TikTok Shop": tool_search_tiktok_shop,
        "FB Marketplace": tool_search_facebook_marketplace,
    }

    for name, tool_fn in platforms.items():
        try:
            results[name] = test_platform(name, tool_fn)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results[name] = False
        print()

    # Excel
    try:
        results["Excel Report"] = test_excel_report()
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results["Excel Report"] = False

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")

    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{len(results)} tests passed")


if __name__ == "__main__":
    main()
