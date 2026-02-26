"""
Sprint 201: "Ảnh Thật" — Product Image Enrichment Tests
Sprint 201b: "Ảnh Thật v2" — Image Enrichment Hardening + Card Data Quality

Tests for:
- should_enrich() — skip logic for platforms/images
- _extract_domain() — URL domain extraction
- _title_similarity() — Jaccard word overlap
- _has_category_mismatch() — cross-category rejection (Sprint 201b)
- _match_images_to_products() — domain + title matching
- _fetch_serper_images() — Serper /images API call
- enrich_product_images() — full pipeline
- workers.py integration — enrichment called in platform_worker
- workers.py rating/sold extraction (Sprint 201b)
- Config — defaults and validation
"""

import pytest
from unittest.mock import patch, MagicMock


# ─── should_enrich ──────────────────────────────────────────────────────


class TestShouldEnrich:
    """Tests for should_enrich() skip logic."""

    def test_skip_google_shopping(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [{"title": "Arduino", "link": "https://example.com"}]
        assert should_enrich("google_shopping", products) is False

    def test_skip_websosanh(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [{"title": "Arduino", "link": "https://example.com"}]
        assert should_enrich("websosanh", products) is False

    def test_skip_facebook_groups_auto(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [{"title": "Arduino", "link": "https://example.com"}]
        assert should_enrich("facebook_groups_auto", products) is False

    def test_skip_empty_products(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        assert should_enrich("shopee", []) is False

    def test_skip_when_half_have_images(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [
            {"title": "A", "image": "https://img.com/1.jpg"},
            {"title": "B", "image": "https://img.com/2.jpg"},
            {"title": "C"},
            {"title": "D"},
        ]
        # 2/4 = 50% → skip
        assert should_enrich("shopee", products) is False

    def test_enrich_shopee_without_images(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [
            {"title": "Arduino Mega", "link": "https://shopee.vn/abc"},
            {"title": "Arduino Uno", "link": "https://shopee.vn/xyz"},
        ]
        assert should_enrich("shopee", products) is True

    def test_enrich_lazada(self):
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [{"title": "Sensor", "link": "https://lazada.vn/p"}]
        assert should_enrich("lazada", products) is True

    def test_recognizes_image_url_field(self):
        """Products with image_url (not just image) count as having images."""
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [
            {"title": "A", "image_url": "https://img.com/1.jpg"},
            {"title": "B", "thumbnail": "https://img.com/2.jpg"},
        ]
        # 2/2 = 100% have images → skip
        assert should_enrich("shopee", products) is False

    # Sprint 201b: TikTok skip
    def test_skip_tiktok_shop(self):
        """Sprint 201b: tiktok_shop added to skip list (Serper returns garbage)."""
        from app.engine.search_platforms.image_enricher import should_enrich
        products = [{"title": "Raspberry Pi 5", "link": "https://tiktok.com/shop/p1"}]
        assert should_enrich("tiktok_shop", products) is False

    def test_tiktok_shop_not_in_site_hints(self):
        """Sprint 201b: tiktok_shop removed from _SITE_HINTS."""
        from app.engine.search_platforms.image_enricher import _SITE_HINTS
        assert "tiktok_shop" not in _SITE_HINTS


# ─── _extract_domain ────────────────────────────────────────────────────


class TestExtractDomain:
    """Tests for _extract_domain() URL parsing."""

    def test_simple_url(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("https://shopee.vn/product/123") == "shopee.vn"

    def test_subdomain(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("https://cf.shopee.vn/file/abc.jpg") == "shopee.vn"

    def test_www_prefix(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("https://www.lazada.vn/products/xyz") == "lazada.vn"

    def test_empty_url(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("") == ""

    def test_invalid_url(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("not a url") == ""

    def test_deep_subdomain(self):
        from app.engine.search_platforms.image_enricher import _extract_domain
        assert _extract_domain("https://img.cdn.shopee.vn/file/123") == "shopee.vn"


# ─── _title_similarity ──────────────────────────────────────────────────


class TestTitleSimilarity:
    """Tests for _title_similarity() Jaccard overlap."""

    def test_identical(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        assert _title_similarity("Arduino Mega 2560", "Arduino Mega 2560") == 1.0

    def test_no_overlap(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        assert _title_similarity("Arduino Mega", "Raspberry Pi") == 0.0

    def test_partial_overlap(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        # "Arduino Mega 2560" vs "Arduino Uno R3"
        # shared: {arduino} → 1/5 = 0.2
        sim = _title_similarity("Arduino Mega 2560", "Arduino Uno R3")
        assert 0.1 < sim < 0.3

    def test_case_insensitive(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        assert _title_similarity("ARDUINO mega", "arduino MEGA") == 1.0

    def test_empty_string(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        assert _title_similarity("", "Arduino") == 0.0
        assert _title_similarity("Arduino", "") == 0.0

    def test_high_overlap(self):
        from app.engine.search_platforms.image_enricher import _title_similarity
        # "Arduino Mega 2560 R3" vs "Arduino Mega 2560 CH340"
        # shared: {arduino, mega, 2560} → 3/5 = 0.6
        sim = _title_similarity("Arduino Mega 2560 R3", "Arduino Mega 2560 CH340")
        assert sim >= 0.5


# ─── _has_category_mismatch (Sprint 201b) ─────────────────────────────


class TestCategoryMismatch:
    """Sprint 201b: Tests for _has_category_mismatch() cross-category rejection."""

    def test_food_image_for_electronics_product_rejected(self):
        """Image with 'hộp cơm giữ nhiệt' should NOT match 'Raspberry Pi 5'."""
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch(
            "Raspberry Pi 5 8GB RAM",
            "Hộp Cơm Giữ Nhiệt LocknLock 3 tầng"
        ) is True

    def test_matching_categories_pass(self):
        """When product and image share the same category, no mismatch."""
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch(
            "Hộp cơm giữ nhiệt inox 3 tầng",
            "Hộp cơm giữ nhiệt LocknLock"
        ) is False

    def test_empty_strings_no_mismatch(self):
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch("", "Áo thun nam") is False
        assert _has_category_mismatch("Arduino", "") is False

    def test_clothing_image_for_tech_rejected(self):
        """Image with 'áo' but product is tech → rejected."""
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch(
            "ESP32 DevKit V1",
            "Áo thun nam cotton"
        ) is True

    def test_cosmetics_image_for_tech_rejected(self):
        """Image with 'mỹ phẩm' but product is tech → rejected."""
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch(
            "Arduino Uno R3",
            "Mỹ phẩm Hàn Quốc chính hãng"
        ) is True

    def test_no_reject_phrases_present(self):
        """Neither product nor image have reject phrases → no mismatch."""
        from app.engine.search_platforms.image_enricher import _has_category_mismatch
        assert _has_category_mismatch(
            "Arduino Mega 2560",
            "Arduino Board V2"
        ) is False


# ─── _match_images_to_products ───────────────────────────────────────────


class TestMatchImagesToProducts:
    """Tests for _match_images_to_products() matching algorithm."""

    def test_domain_match(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino", "link": "https://shopee.vn/product/123"},
        ]
        images = [
            {"title": "Arduino Board", "link": "https://shopee.vn/item/456", "thumbnailUrl": "https://encrypted-tbn0.gstatic.com/images?q=abc"},
        ]
        count = _match_images_to_products(products, images)
        assert count == 1
        assert products[0]["image"] == "https://encrypted-tbn0.gstatic.com/images?q=abc"

    def test_title_fallback(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino Mega 2560 R3", "link": "https://shopee.vn/p/1"},
        ]
        images = [
            # Different domain, but similar title
            {"title": "Arduino Mega 2560 Board", "link": "https://aliexpress.com/item/99", "thumbnailUrl": "https://encrypted-tbn0.gstatic.com/t1"},
        ]
        count = _match_images_to_products(products, images, min_similarity=0.25)
        assert count == 1
        assert products[0]["image"] == "https://encrypted-tbn0.gstatic.com/t1"

    def test_below_threshold_no_match(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino Mega 2560", "link": "https://shopee.vn/p/1"},
        ]
        images = [
            {"title": "Raspberry Pi 4", "link": "https://other.com/item", "thumbnailUrl": "https://t.gstatic.com/x"},
        ]
        count = _match_images_to_products(products, images, min_similarity=0.5)
        assert count == 0
        assert "image" not in products[0]

    def test_greedy_consumption(self):
        """Each image used at most once."""
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino A", "link": "https://shopee.vn/a"},
            {"title": "Arduino B", "link": "https://shopee.vn/b"},
        ]
        images = [
            {"title": "Arduino", "link": "https://shopee.vn/img1", "thumbnailUrl": "https://t1.gstatic.com/1"},
        ]
        count = _match_images_to_products(products, images)
        assert count == 1  # Only 1 image available

    def test_existing_images_not_overwritten(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino", "link": "https://shopee.vn/p", "image": "https://existing.jpg"},
        ]
        images = [
            {"title": "Arduino", "link": "https://shopee.vn/q", "thumbnailUrl": "https://new.jpg"},
        ]
        count = _match_images_to_products(products, images)
        assert count == 0
        assert products[0]["image"] == "https://existing.jpg"

    def test_empty_products(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        assert _match_images_to_products([], [{"title": "X", "thumbnailUrl": "t"}]) == 0

    def test_empty_images(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [{"title": "Arduino", "link": "https://shopee.vn/p"}]
        assert _match_images_to_products(products, []) == 0

    def test_uses_thumbnail_not_image_url(self):
        """Must use thumbnailUrl (Google cache) not imageUrl (CDN, CORS blocked)."""
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Board", "link": "https://shopee.vn/p/1"},
        ]
        images = [
            {
                "title": "Board",
                "link": "https://shopee.vn/item/2",
                "imageUrl": "https://cf.shopee.vn/file/cors-blocked.jpg",
                "thumbnailUrl": "https://encrypted-tbn0.gstatic.com/google-cached.jpg",
            },
        ]
        _match_images_to_products(products, images)
        assert products[0]["image"] == "https://encrypted-tbn0.gstatic.com/google-cached.jpg"

    def test_multiple_products_multiple_images(self):
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [
            {"title": "Arduino Mega 2560", "link": "https://shopee.vn/a"},
            {"title": "Arduino Uno R3", "link": "https://lazada.vn/b"},
            {"title": "ESP32 DevKit", "link": "https://shopee.vn/c"},
        ]
        images = [
            {"title": "ESP32 Board", "link": "https://shopee.vn/img_c", "thumbnailUrl": "https://t1"},
            {"title": "Arduino Mega 2560 Board", "link": "https://shopee.vn/img_a", "thumbnailUrl": "https://t2"},
            {"title": "Arduino Uno R3 Clone", "link": "https://lazada.vn/img_b", "thumbnailUrl": "https://t3"},
        ]
        count = _match_images_to_products(products, images, min_similarity=0.25)
        assert count == 3
        # Domain match: shopee→shopee, lazada→lazada
        assert products[0].get("image")  # Arduino Mega got image
        assert products[1].get("image")  # Arduino Uno got image
        assert products[2].get("image")  # ESP32 got image

    # Sprint 201b: Raised threshold tests
    def test_035_similarity_rejected_at_04_threshold(self):
        """Sprint 201b: 0.35 Jaccard is below new 0.4 default → no match."""
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        # "A B C D E" vs "A B X Y Z" → intersection={A,B}, union={A,B,C,D,E,X,Y,Z} → 2/8=0.25
        # Need something closer: "A B C D" vs "A B C X" → 3/5=0.6 passes
        # "A B C" vs "A X Y" → 1/5=0.2 fails at both
        # Target ~0.35: "A B C D E F" vs "A B C X Y Z" → 3/9=0.33
        products = [{"title": "alpha beta gamma delta epsilon", "link": "https://shopee.vn/p"}]
        images = [{"title": "alpha beta zeta theta", "link": "https://other.com/x", "thumbnailUrl": "https://t1"}]
        # Jaccard: {alpha, beta} / {alpha, beta, gamma, delta, epsilon, zeta, theta} = 2/7 ≈ 0.286
        count = _match_images_to_products(products, images, min_similarity=0.4)
        assert count == 0

    def test_045_similarity_passes_at_04_threshold(self):
        """Sprint 201b: 0.45+ Jaccard passes the new 0.4 threshold."""
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        # "A B C D" vs "A B C E" → {A,B,C}/{A,B,C,D,E} = 3/5 = 0.6 → passes
        products = [{"title": "Arduino Mega 2560 Board", "link": "https://shopee.vn/p"}]
        images = [{"title": "Arduino Mega 2560 Clone", "link": "https://other.com/x", "thumbnailUrl": "https://t1"}]
        count = _match_images_to_products(products, images, min_similarity=0.4)
        assert count == 1

    # Sprint 201b: Category mismatch in matching
    def test_category_mismatch_rejects_in_title_fallback(self):
        """Sprint 201b: Food image should NOT match electronics product via title fallback."""
        from app.engine.search_platforms.image_enricher import _match_images_to_products
        products = [{"title": "Raspberry Pi 5 Board", "link": "https://shopee.vn/p1"}]
        images = [
            {
                "title": "Hộp Cơm Giữ Nhiệt Raspberry Pi Pattern",  # Has 'hộp cơm' + 'raspberry pi'
                "link": "https://other.com/x",
                "thumbnailUrl": "https://t1",
            }
        ]
        count = _match_images_to_products(products, images, min_similarity=0.2)
        assert count == 0  # Rejected by category mismatch


# ─── _fetch_serper_images ────────────────────────────────────────────────


class TestFetchSerperImages:
    """Tests for _fetch_serper_images() API call."""

    def _mock_settings(self, **overrides):
        s = MagicMock()
        s.serper_api_key = "test-api-key"
        s.image_enrichment_timeout = 8
        for k, v in overrides.items():
            setattr(s, k, v)
        return s

    @patch("httpx.post")
    def test_successful_fetch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "images": [
                {"title": "Arduino", "thumbnailUrl": "https://t1.gstatic.com/1", "link": "https://shopee.vn/p1"},
                {"title": "Board", "thumbnailUrl": "https://t1.gstatic.com/2", "link": "https://shopee.vn/p2"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import _fetch_serper_images
            results = _fetch_serper_images("Arduino Mega", site_hint="shopee.vn")

        assert len(results) == 2
        assert results[0]["thumbnailUrl"] == "https://t1.gstatic.com/1"
        # Verify POST was called with correct params
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://google.serper.dev/images"
        payload = call_args[1]["json"]
        assert "site:shopee.vn" in payload["q"]

    @patch("httpx.post")
    def test_timeout_returns_empty(self, mock_post):
        mock_post.side_effect = Exception("Connection timeout")

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import _fetch_serper_images
            results = _fetch_serper_images("Arduino")

        assert results == []

    def test_no_api_key_returns_empty(self):
        with patch("app.core.config.get_settings", return_value=self._mock_settings(serper_api_key="")):
            with patch.dict("os.environ", {"SERPER_API_KEY": ""}, clear=False):
                from app.engine.search_platforms.image_enricher import _fetch_serper_images
                results = _fetch_serper_images("Arduino")
        assert results == []

    @patch("httpx.post")
    def test_site_hint_in_query(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"images": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import _fetch_serper_images
            _fetch_serper_images("Arduino", site_hint="lazada.vn")

        payload = mock_post.call_args[1]["json"]
        assert "site:lazada.vn" in payload["q"]

    @patch("httpx.post")
    def test_no_site_hint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"images": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import _fetch_serper_images
            _fetch_serper_images("Arduino", site_hint="")

        payload = mock_post.call_args[1]["json"]
        assert "site:" not in payload["q"]


# ─── enrich_product_images (full pipeline) ──────────────────────────────


class TestEnrichProductImages:
    """Tests for enrich_product_images() main entry point."""

    def _mock_settings(self, **overrides):
        s = MagicMock()
        s.serper_api_key = "test-api-key"
        s.image_enrichment_timeout = 8
        s.image_enrichment_min_similarity = 0.4
        for k, v in overrides.items():
            setattr(s, k, v)
        return s

    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_full_pipeline(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "Arduino Mega Board", "link": "https://shopee.vn/img1", "thumbnailUrl": "https://t.gstatic.com/1"},
        ]
        products = [
            {"title": "Arduino Mega 2560", "link": "https://shopee.vn/p1"},
        ]

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import enrich_product_images
            result = enrich_product_images(products, "Arduino Mega", "shopee")

        assert result[0].get("image") == "https://t.gstatic.com/1"
        mock_fetch.assert_called_once()

    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_skip_google_shopping_platform(self, mock_fetch):
        products = [{"title": "Arduino", "link": "https://google.com/p1"}]

        from app.engine.search_platforms.image_enricher import enrich_product_images
        result = enrich_product_images(products, "Arduino", "google_shopping")

        mock_fetch.assert_not_called()
        assert "image" not in result[0]

    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_empty_products(self, mock_fetch):
        from app.engine.search_platforms.image_enricher import enrich_product_images
        result = enrich_product_images([], "Arduino", "shopee")

        mock_fetch.assert_not_called()
        assert result == []

    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_api_failure_graceful(self, mock_fetch):
        mock_fetch.return_value = []  # API failed
        products = [
            {"title": "Arduino", "link": "https://shopee.vn/p1"},
        ]

        from app.engine.search_platforms.image_enricher import enrich_product_images
        result = enrich_product_images(products, "Arduino", "shopee")

        assert "image" not in result[0]  # No enrichment, but no crash

    # Sprint 201b: Skip tiktok_shop in full pipeline
    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_skip_tiktok_shop_in_pipeline(self, mock_fetch):
        """Sprint 201b: tiktok_shop skipped by should_enrich."""
        products = [{"title": "Arduino", "link": "https://tiktok.com/shop/p1"}]

        from app.engine.search_platforms.image_enricher import enrich_product_images
        result = enrich_product_images(products, "Arduino", "tiktok_shop")

        mock_fetch.assert_not_called()

    # Sprint 201b: Instagram fix — enrichment runs for instagram platform
    @patch("app.engine.search_platforms.image_enricher._fetch_serper_images")
    def test_instagram_enrichment_runs(self, mock_fetch):
        """Sprint 201b: instagram (not instagram_shopping) runs enrichment."""
        mock_fetch.return_value = [
            {"title": "Arduino", "link": "https://instagram.com/p/1", "thumbnailUrl": "https://t.gstatic.com/ig"},
        ]
        products = [{"title": "Arduino Board", "link": "https://instagram.com/p/1"}]

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            from app.engine.search_platforms.image_enricher import enrich_product_images
            result = enrich_product_images(products, "Arduino", "instagram")

        mock_fetch.assert_called_once()
        # Verify site_hint is 'instagram.com'
        call_args = mock_fetch.call_args
        assert call_args[1].get("site_hint", call_args[0][1] if len(call_args[0]) > 1 else "") == "instagram.com" or "instagram.com" in str(call_args)


# ─── Instagram key fix (Sprint 201b) ─────────────────────────────────────


class TestInstagramKeyFix:
    """Sprint 201b: Verify _SITE_HINTS uses 'instagram' not 'instagram_shopping'."""

    def test_instagram_key_exists(self):
        from app.engine.search_platforms.image_enricher import _SITE_HINTS
        assert "instagram" in _SITE_HINTS
        assert _SITE_HINTS["instagram"] == "instagram.com"

    def test_instagram_shopping_key_removed(self):
        from app.engine.search_platforms.image_enricher import _SITE_HINTS
        assert "instagram_shopping" not in _SITE_HINTS


# ─── workers.py integration ──────────────────────────────────────────────


class TestWorkersIntegration:
    """Tests for image enrichment integration in platform_worker."""

    def _mock_settings(self, **overrides):
        s = MagicMock()
        s.enable_product_image_enrichment = True
        s.enable_product_preview_cards = False  # Disable preview for simpler tests
        s.product_preview_max_cards = 20
        s.serper_api_key = "test-key"
        s.image_enrichment_timeout = 8
        s.image_enrichment_min_similarity = 0.4
        for k, v in overrides.items():
            setattr(s, k, v)
        return s

    @pytest.mark.asyncio
    async def test_enrichment_called_when_enabled(self):
        """Image enrichment is called when flag enabled and products exist."""
        mock_settings = self._mock_settings()
        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Arduino", "link": "https://shopee.vn/p1"}
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.search_platforms.image_enricher.enrich_product_images") as mock_enrich:
            mock_enrich.return_value = [{"title": "Arduino", "link": "https://shopee.vn/p1", "image": "https://t.gstatic.com/1"}]

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            state = {"platform_id": "shopee", "query": "Arduino", "max_results": 5, "page": 1}
            result = await platform_worker(state)

            mock_enrich.assert_called_once()
            assert len(result["all_products"]) == 1

    @pytest.mark.asyncio
    async def test_enrichment_skipped_when_disabled(self):
        """Image enrichment NOT called when flag disabled."""
        mock_settings = self._mock_settings(enable_product_image_enrichment=False)
        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Arduino", "link": "https://shopee.vn/p1"}
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.search_platforms.image_enricher.enrich_product_images") as mock_enrich:

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            state = {"platform_id": "shopee", "query": "Arduino", "max_results": 5, "page": 1}
            result = await platform_worker(state)

            mock_enrich.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrichment_error_does_not_break_worker(self):
        """If enrichment throws, worker still returns products."""
        mock_settings = self._mock_settings()
        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Arduino", "link": "https://shopee.vn/p1"}
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.search_platforms.image_enricher.enrich_product_images", side_effect=RuntimeError("Boom")):

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            state = {"platform_id": "shopee", "query": "Arduino", "max_results": 5, "page": 1}
            result = await platform_worker(state)

            # Worker should still succeed despite enrichment error
            assert len(result["all_products"]) == 1
            assert result["platform_errors"] == []

    @pytest.mark.asyncio
    async def test_enriched_images_in_preview_events(self):
        """Preview events use enriched image URLs."""
        mock_settings = self._mock_settings(enable_product_preview_cards=True)
        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Arduino", "link": "https://shopee.vn/p1"}
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        # Capture preview events
        import asyncio
        eq = asyncio.Queue()

        def _mock_get_eq(bus_id):
            return eq

        enriched_product = {"title": "Arduino", "link": "https://shopee.vn/p1", "image": "https://t.gstatic.com/enriched"}

        with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.search_platforms.image_enricher.enrich_product_images", return_value=[enriched_product]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", side_effect=_mock_get_eq):

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            state = {"platform_id": "shopee", "query": "Arduino", "max_results": 5, "page": 1, "_event_bus_id": "test-bus"}
            await platform_worker(state)

            # Drain queue and find preview events
            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) >= 1
            assert preview_events[0]["content"]["image_url"] == "https://t.gstatic.com/enriched"


# ─── Rating/Sold Extraction (Sprint 201b) ────────────────────────────────


class TestRatingExtraction:
    """Sprint 201b: Tests for _extract_rating() from snippets."""

    def test_rating_slash_5(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Sản phẩm 4.8/5 tuyệt vời") == 4.8

    def test_rating_sao(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Đạt 4.5 sao từ 200 đánh giá") == 4.5

    def test_rating_danh_gia(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Đánh giá 4.2 trên Shopee") == 4.2

    def test_rating_stars(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Rated 4.7 stars by users") == 4.7

    def test_no_rating_returns_none(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Sản phẩm tốt, giá rẻ") is None

    def test_empty_string_returns_none(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("") is None

    def test_rating_out_of_range_rejected(self):
        """Rating > 5.0 should be rejected."""
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        # "7.5/5" → 7.5 > 5.0 → None
        assert _extract_rating("Sản phẩm 7.5/5 wow") is None

    def test_rating_comma_as_decimal(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_rating
        assert _extract_rating("Đánh giá 4,8 trên Lazada") == 4.8


class TestSoldExtraction:
    """Sprint 201b: Tests for _extract_sold() from snippets."""

    def test_da_ban_k_suffix(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("Đã bán 1.2k sản phẩm") == 1200

    def test_da_ban_plain_number(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("Đã bán 523 chiếc") == 523

    def test_number_da_ban_reversed(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("1k đã bán") == 1000

    def test_no_sold_returns_none(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("Sản phẩm chính hãng, giá tốt") is None

    def test_empty_string_returns_none(self):
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("") is None

    def test_da_ban_comma_k(self):
        """Vietnamese often uses comma as decimal: '1,5k' = 1500."""
        from app.engine.multi_agent.subagents.search.workers import _extract_sold
        assert _extract_sold("Đã bán 1,5k") == 1500


class TestParseSoldNumber:
    """Sprint 201b: Tests for _parse_sold_number() helper."""

    def test_plain_number(self):
        from app.engine.multi_agent.subagents.search.workers import _parse_sold_number
        assert _parse_sold_number("523") == 523

    def test_k_suffix(self):
        from app.engine.multi_agent.subagents.search.workers import _parse_sold_number
        assert _parse_sold_number("2.5k") == 2500

    def test_m_suffix(self):
        from app.engine.multi_agent.subagents.search.workers import _parse_sold_number
        assert _parse_sold_number("1.2M") == 1200000

    def test_empty_returns_none(self):
        from app.engine.multi_agent.subagents.search.workers import _parse_sold_number
        assert _parse_sold_number("") is None


# ─── Config ──────────────────────────────────────────────────────────────


class TestConfig:
    """Tests for Sprint 201/201b config fields."""

    def test_defaults(self):
        """Sprint 201b: Config default for min_similarity is now 0.4."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            database_url="sqlite:///test.db",
            enable_product_image_enrichment=False,
        )
        assert s.enable_product_image_enrichment is False
        assert s.image_enrichment_timeout == 8
        assert s.image_enrichment_min_similarity == 0.4  # Sprint 201b: was 0.25

    def test_validation_bounds(self):
        """Config validates field bounds."""
        from pydantic import ValidationError
        from app.core.config import Settings

        # Timeout too low
        with pytest.raises(ValidationError):
            Settings(
                google_api_key="test",
                api_key="test",
                database_url="sqlite:///test.db",
                image_enrichment_timeout=1,  # min is 2
            )

        # Similarity out of range
        with pytest.raises(ValidationError):
            Settings(
                google_api_key="test",
                api_key="test",
                database_url="sqlite:///test.db",
                image_enrichment_min_similarity=1.5,  # max is 1.0
            )
