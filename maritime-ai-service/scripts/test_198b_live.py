"""
Sprint 198b LIVE Quality Test — Direct function calls with real Serper + Jina

Tests:
1. International search: Zebra ZXP7 printhead — multi-currency extraction
2. Dealer search: đầu in Zebra ZXP Series 7 — contacts + address quality
3. Price parsing: EUR/AED/SGD format verification
4. Address false positive check

Run: cd maritime-ai-service && python scripts/test_198b_live.py
"""

import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal env setup
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("API_KEY", "dummy")


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def test_price_parsing():
    """Test _parse_price_amount with real-world formats."""
    separator("TEST 1: Price Parsing (_parse_price_amount)")
    from app.engine.tools.international_search_tool import _parse_price_amount

    cases = [
        ("$299.99", 299.99),
        ("€1.234,50", 1234.5),       # European EUR — THE BUG
        ("€249,99", 249.99),          # European decimal
        ("£1,299.00", 1299.0),        # Anglo GBP
        ("AED 5,820", 5820.0),        # AED with comma thousands
        ("¥15,000", 15000.0),         # Yen
        ("S$450.00", 450.0),          # SGD (prefix only)
        ("5 820", 5820.0),            # Space separator
    ]

    all_pass = True
    for raw, expected in cases:
        # Strip currency symbols for _parse_price_amount
        import re
        nums = re.search(r'[\d,.\s]+', raw)
        if nums:
            result = _parse_price_amount(nums.group().strip())
            status = "PASS" if result == expected else "FAIL"
            if status == "FAIL":
                all_pass = False
            print(f"  [{status}] '{raw}' → {result} (expected {expected})")

    print(f"\n  Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


def test_extract_price_multi_currency():
    """Test _extract_price_from_text with full text + Serper metadata."""
    separator("TEST 2: Multi-Currency Price Extraction")
    from app.engine.tools.international_search_tool import _extract_price_from_text

    cases = [
        # (text, currency, serper_price, serper_range, expected_min, expected_max, label)
        ("Price: $299.99 USD", "USD", None, None, 299, 300, "USD symbol"),
        ("Preis: €1.234,50 inkl. MwSt.", "EUR", None, None, 1234, 1235, "EUR European format"),
        ("Price: €249.99", "EUR", None, None, 249, 250, "EUR Anglo format"),
        ("Price: £199.99", "GBP", None, None, 199, 200, "GBP symbol"),
        ("Price: AED 5,820", "AED", None, None, 5820, 5821, "AED code"),
        ("Price: S$450.00", "SGD", None, None, 450, 451, "SGD symbol"),
        ("", "USD", 299.99, None, 299, 300, "Serper price priority"),
        ("$999", "USD", None, "$200 - $400", 200, 201, "Serper range priority"),
    ]

    all_pass = True
    for text, cur, sp, sr, lo, hi, label in cases:
        result = _extract_price_from_text(text, cur, serper_price=sp, serper_price_range=sr)
        ok = result is not None and lo <= result <= hi
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {label}: {result} (expected {lo}-{hi})")

    print(f"\n  Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


def test_structural_address():
    """Test address extraction rejects noise, accepts real addresses."""
    separator("TEST 3: Structural Address Validation")
    from app.engine.tools.contact_extraction_tool import _extract_address

    # Should PASS (real addresses)
    real_addresses = [
        "Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM",
        "Trụ sở: Tầng 5, 456 Lê Lợi, Hà Nội",
        "Văn phòng: Lầu 3, Tòa nhà ABC, Đường Pasteur, Quận 3, TP.HCM",
        "Address: 79/63 Phan Đăng Lưu, Phường 7, Quận Phú Nhuận, TP.HCM",
    ]

    # Should FAIL (noise — false positives from Sprint 196)
    noise_lines = [
        "Địa chỉ Màn hình:LCD có độ phân giải cao, hỗ trợ nhiều tính năng đa dạng cho người dùng",
        "Địa chỉ: Hy vọng bài viết này sẽ giúp ích cho bạn trong việc tìm kiếm sản phẩm chất lượng",
        "Đường dẫn: https://example.com/product/zebra-zxp7-printhead-replacement-guide-2024",
        "Địa chỉ: Thông số kỹ thuật chi tiết của đầu in nhiệt Zebra ZXP Series 7 cho thẻ nhựa PVC",
    ]

    all_pass = True
    print("\n  Real addresses (should extract):")
    for addr in real_addresses:
        result = _extract_address(addr)
        ok = bool(result)
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"    [{status}] → '{result[:60]}...' " if len(result) > 60 else f"    [{status}] → '{result}'")

    print("\n  Noise lines (should reject):")
    for noise in noise_lines:
        result = _extract_address(noise)
        ok = result == ""
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"    [{status}] → '{result[:60]}'" if result else f"    [{status}] → (empty, correctly rejected)")

    print(f"\n  Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


def test_phone_normalization():
    """Test phone normalization handles spaces/dots/dashes."""
    separator("TEST 4: Phone Number Normalization")
    from app.engine.tools.contact_extraction_tool import _extract_all_contacts

    text = """
    Hotline: 090 1234 567
    Tel: 028.1234.5678
    Mobile: 091-234-5678
    Zalo: 0901234567
    """

    contacts = _extract_all_contacts(text)
    phones = contacts["phones"]

    print(f"  Input: '090 1234 567', '028.1234.5678', '091-234-5678', '0901234567'")
    print(f"  Extracted phones: {phones}")
    print(f"  Count: {len(phones)}")

    # Should find at least 3 phones (the space/dot/dash ones + standard)
    ok = len(phones) >= 3
    print(f"\n  Result: {'PASS' if ok else 'FAIL'} (expected ≥3 phones)")
    return ok


def test_live_international_search():
    """LIVE: Search Zebra ZXP7 printhead internationally."""
    separator("TEST 5: LIVE International Search — Zebra ZXP7 printhead")

    from app.engine.tools.serper_web_search import is_serper_available
    if not is_serper_available():
        print("  SKIP: SERPER_API_KEY not configured")
        return True

    from app.engine.tools.international_search_tool import _search_international

    start = time.time()
    result = _search_international("Zebra ZXP7 printhead P1037750-006", "USD")
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Results: {result['count']}")
    print(f"  Exchange rate: {result.get('exchange_rate')}")

    prices_found = 0
    for r in result.get("results", []):
        has_price = r.get("price_foreign") is not None
        if has_price:
            prices_found += 1
        pf = r.get('price_foreign')
        pv = r.get('price_vnd')
        pf_str = f"{pf:>10.2f}" if pf is not None else "       N/A"
        pv_str = f"{pv:>12,}" if pv is not None else "         N/A"
        print(f"  {'$' if has_price else ' '} {r.get('price_currency', 'USD')} {pf_str} → {pv_str} VND | {r['title'][:50]}")
        print(f"      URL: {r['url'][:80]}")

    print(f"\n  Prices extracted: {prices_found}/{result['count']}")
    ok = prices_found >= 1
    print(f"  Result: {'PASS' if ok else 'FAIL'} (expected ≥1 price)")
    return ok


def test_live_dealer_search():
    """LIVE: Search đầu in Zebra ZXP Series 7 dealers in Vietnam."""
    separator("TEST 6: LIVE Dealer Search — đầu in Zebra ZXP Series 7")

    from app.engine.tools.serper_web_search import is_serper_available
    if not is_serper_available():
        print("  SKIP: SERPER_API_KEY not configured")
        return True

    from app.engine.tools.dealer_search_tool import _search_dealers

    start = time.time()
    result = _search_dealers("đầu in Zebra ZXP Series 7")
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Dealers found: {result['count']}")
    print(f"  Pages scanned: {result.get('total_pages_scanned', 'N/A')}")

    contacts_found = 0
    has_new_fields = False
    false_positive_addresses = []

    for d in result.get("dealers", []):
        c = d.get("contacts", {})
        has_contact = d.get("has_contact_info", False)
        if has_contact:
            contacts_found += 1

        # Check for new fields (viber, facebook, intl_phones)
        if c.get("viber") or c.get("facebook") or c.get("international_phones"):
            has_new_fields = True

        # Check for false positive addresses
        addr = c.get("address", "")
        if addr:
            # Flag suspicious addresses (no numbers, no known location words)
            import re
            has_number = bool(re.search(r'\d', addr))
            has_location = any(w in addr.lower() for w in ["quận", "phường", "tp", "hà nội", "hcm", "đà nẵng"])
            if not has_number and not has_location:
                false_positive_addresses.append(addr)

        print(f"\n  {'*' if has_contact else ' '} {d['name'][:50]}")
        print(f"    Phones: {c.get('phones', [])[:3]}")
        print(f"    Emails: {c.get('emails', [])[:2]}")
        print(f"    Zalo:   {c.get('zalo', [])[:2]}")
        print(f"    Viber:  {c.get('viber', [])[:2]}")
        print(f"    FB:     {c.get('facebook', [])[:2]}")
        print(f"    Intl:   {c.get('international_phones', [])[:2]}")
        print(f"    Addr:   {addr[:80] if addr else '(none)'}")

    print(f"\n  Dealers with contacts: {contacts_found}/{result['count']}")
    print(f"  New fields (viber/fb/intl): {'YES' if has_new_fields else 'NO'}")
    print(f"  False positive addresses: {len(false_positive_addresses)}")
    for fp in false_positive_addresses:
        print(f"    ⚠ '{fp[:80]}'")

    ok = contacts_found >= 1 and len(false_positive_addresses) == 0
    print(f"\n  Result: {'PASS' if ok else 'WARN'}")
    return ok


def test_live_contact_extraction():
    """LIVE: Extract contacts from a known Vietnamese dealer page."""
    separator("TEST 7: LIVE Contact Extraction — known dealer page")

    from app.engine.tools.contact_extraction_tool import _fetch_page_markdown, _extract_all_contacts

    # Use a well-known Vietnamese tech distributor
    url = "https://mayin.vn"
    print(f"  Fetching: {url}")

    start = time.time()
    markdown = _fetch_page_markdown(url)
    elapsed = time.time() - start

    print(f"  Fetch time: {elapsed:.1f}s")
    print(f"  Content length: {len(markdown)} chars")

    if not markdown:
        print("  SKIP: Could not fetch page (may be blocked)")
        return True

    contacts = _extract_all_contacts(markdown)
    print(f"  Phones: {contacts['phones'][:5]}")
    print(f"  Intl phones: {contacts['international_phones'][:3]}")
    print(f"  Emails: {contacts['emails'][:3]}")
    print(f"  Zalo: {contacts['zalo'][:3]}")
    print(f"  Viber: {contacts['viber'][:3]}")
    print(f"  Facebook: {contacts['facebook'][:3]}")
    print(f"  Address: {contacts['address'][:80] if contacts['address'] else '(none)'}")

    total = (len(contacts['phones']) + len(contacts['emails'])
             + len(contacts['zalo']) + len(contacts['viber'])
             + len(contacts['facebook']) + len(contacts['international_phones']))
    print(f"  Total contact methods: {total}")

    ok = total >= 1
    print(f"\n  Result: {'PASS' if ok else 'WARN'}")
    return ok


if __name__ == "__main__":
    print("Sprint 198b LIVE Quality Test")
    print("=" * 70)

    results = {}

    # Offline tests (no network needed)
    results["price_parsing"] = test_price_parsing()
    results["multi_currency"] = test_extract_price_multi_currency()
    results["structural_address"] = test_structural_address()
    results["phone_normalization"] = test_phone_normalization()

    # Online tests (need Serper API key + internet)
    results["live_international"] = test_live_international_search()
    results["live_dealer"] = test_live_dealer_search()
    results["live_contact"] = test_live_contact_extraction()

    # Summary
    separator("SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'} — {name}")
    print(f"\n  {passed}/{total} tests passed")

    sys.exit(0 if passed == total else 1)
