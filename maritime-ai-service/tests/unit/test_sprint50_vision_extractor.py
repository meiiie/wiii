"""
Tests for Sprint 50: VisionExtractor coverage.

Tests vision extraction including:
- ExtractionResult dataclass
- __init__ (defaults, custom model/key)
- client property (lazy init)
- _rate_limit (enforces delay)
- _analyze_extraction (tables, diagrams, headings, empty)
- validate_extraction (success, failure, short text)
- extract_from_url (success, error)
- extract_from_image (success, error)
- Singleton
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image


# ============================================================================
# ExtractionResult
# ============================================================================


class TestExtractionResult:
    """Test ExtractionResult dataclass."""

    def test_defaults(self):
        from app.engine.vision_extractor import ExtractionResult
        r = ExtractionResult(text="Hello")
        assert r.text == "Hello"
        assert r.has_tables is False
        assert r.has_diagrams is False
        assert r.headings_found == []
        assert r.success is True
        assert r.error is None
        assert r.processing_time == 0.0

    def test_with_all_fields(self):
        from app.engine.vision_extractor import ExtractionResult
        r = ExtractionResult(
            text="Content", has_tables=True, has_diagrams=True,
            headings_found=["Rule 15"], success=True, processing_time=1.5
        )
        assert r.has_tables is True
        assert r.headings_found == ["Rule 15"]


# ============================================================================
# __init__
# ============================================================================


class TestInit:
    """Test initialization."""

    def test_defaults(self):
        from app.engine.vision_extractor import VisionExtractor
        with patch("app.engine.vision_extractor.settings") as mock_s:
            mock_s.google_model = "gemini-3.1-flash-lite-preview"
            mock_s.google_api_key = "test-key"
            ve = VisionExtractor()
        assert ve.model_name == "gemini-3.1-flash-lite-preview"
        assert ve.api_key == "test-key"
        assert ve._client is None

    def test_custom_params(self):
        from app.engine.vision_extractor import VisionExtractor
        ve = VisionExtractor(model="custom-model", api_key="custom-key")
        assert ve.model_name == "custom-model"
        assert ve.api_key == "custom-key"


# ============================================================================
# _analyze_extraction
# ============================================================================


class TestAnalyzeExtraction:
    """Test text analysis for metadata."""

    def _make_extractor(self):
        from app.engine.vision_extractor import VisionExtractor
        return VisionExtractor(model="test", api_key="test")

    def test_has_tables(self):
        ve = self._make_extractor()
        text = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        result = ve._analyze_extraction(text)
        assert result.has_tables is True

    def test_no_tables(self):
        ve = self._make_extractor()
        result = ve._analyze_extraction("Just plain text here")
        assert result.has_tables is False

    def test_has_diagrams(self):
        ve = self._make_extractor()
        text = "Đèn đỏ bên trái, đèn xanh bên phải"
        result = ve._analyze_extraction(text)
        assert result.has_diagrams is True

    def test_no_diagrams(self):
        ve = self._make_extractor()
        result = ve._analyze_extraction("This is about mathematics and physics")
        assert result.has_diagrams is False

    def test_headings_dieu(self):
        ve = self._make_extractor()
        text = "Theo Điều 15 và Điều 16 của COLREGS"
        result = ve._analyze_extraction(text)
        assert "Điều 15" in result.headings_found
        assert "Điều 16" in result.headings_found

    def test_headings_khoan(self):
        ve = self._make_extractor()
        text = "Khoản 1 quy định rằng..."
        result = ve._analyze_extraction(text)
        assert "Khoản 1" in result.headings_found

    def test_headings_rule(self):
        ve = self._make_extractor()
        text = "According to Rule 15 and rule 7"
        result = ve._analyze_extraction(text)
        assert any("Rule 15" in h or "rule 15" in h for h in result.headings_found)
        assert any("rule 7" in h or "Rule 7" in h for h in result.headings_found)

    def test_headings_deduplicated(self):
        ve = self._make_extractor()
        text = "Rule 15 says... Rule 15 also says..."
        result = ve._analyze_extraction(text)
        # Should be deduplicated
        rule_15_count = sum(1 for h in result.headings_found if "15" in h)
        assert rule_15_count == 1

    def test_empty_text(self):
        ve = self._make_extractor()
        result = ve._analyze_extraction("")
        assert result.text == ""
        assert result.has_tables is False
        assert result.has_diagrams is False
        assert result.headings_found == []

    def test_mixed_content(self):
        ve = self._make_extractor()
        text = """## Điều 15 - Crossing situation
| Vessel | Action |
|--------|--------|
| Give-way | Alter course |
[Hình: Đèn đỏ bên mạn trái]"""
        result = ve._analyze_extraction(text)
        assert result.has_tables is True
        assert result.has_diagrams is True
        assert "Điều 15" in result.headings_found


# ============================================================================
# validate_extraction
# ============================================================================


class TestValidateExtraction:
    """Test extraction validation."""

    def test_valid(self):
        from app.engine.vision_extractor import VisionExtractor, ExtractionResult
        ve = VisionExtractor(model="test", api_key="test")
        result = ExtractionResult(text="A" * 100, success=True)
        assert ve.validate_extraction(result) is True

    def test_not_success(self):
        from app.engine.vision_extractor import VisionExtractor, ExtractionResult
        ve = VisionExtractor(model="test", api_key="test")
        result = ExtractionResult(text="", success=False, error="Failed")
        assert ve.validate_extraction(result) is False

    def test_too_short(self):
        from app.engine.vision_extractor import VisionExtractor, ExtractionResult
        ve = VisionExtractor(model="test", api_key="test")
        result = ExtractionResult(text="Short", success=True)
        assert ve.validate_extraction(result) is False


# ============================================================================
# extract_from_url
# ============================================================================


class TestExtractFromUrl:
    """Test URL-based extraction."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = 0.0

        mock_response = MagicMock()
        mock_response.text = "Điều 15 - Crossing situation content that is long enough"
        mock_models = MagicMock()
        mock_models.generate_content.return_value = mock_response
        mock_client = MagicMock()
        mock_client.models = mock_models
        ve._client = mock_client

        result = await ve.extract_from_url("https://example.com/img.jpg")
        assert result.success is True
        assert "Điều 15" in result.text
        assert result.processing_time >= 0

    @pytest.mark.asyncio
    async def test_error(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = 0.0

        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("API error")
        mock_client = MagicMock()
        mock_client.models = mock_models
        ve._client = mock_client

        result = await ve.extract_from_url("https://example.com/img.jpg")
        assert result.success is False
        assert "API error" in result.error


# ============================================================================
# extract_from_image
# ============================================================================


class TestExtractFromImage:
    """Test PIL Image-based extraction."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = 0.0

        mock_response = MagicMock()
        mock_response.text = "Rule 15 describes the crossing situation between vessels"
        mock_models = MagicMock()
        mock_models.generate_content.return_value = mock_response
        mock_client = MagicMock()
        mock_client.models = mock_models
        ve._client = mock_client

        img = Image.new("RGB", (100, 100), color="white")
        result = await ve.extract_from_image(img)
        assert result.success is True
        assert "Rule 15" in result.text

    @pytest.mark.asyncio
    async def test_error(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = 0.0

        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("Vision failed")
        mock_client = MagicMock()
        mock_client.models = mock_models
        ve._client = mock_client

        img = Image.new("RGB", (100, 100))
        result = await ve.extract_from_image(img)
        assert result.success is False
        assert "Vision failed" in result.error


# ============================================================================
# _rate_limit
# ============================================================================


class TestRateLimit:
    """Test rate limiting."""

    @pytest.mark.asyncio
    async def test_no_wait_first_request(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = 0.0  # Long ago

        start = time.time()
        await ve._rate_limit()
        elapsed = time.time() - start
        # Should not wait since last request was long ago
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_waits_if_too_soon(self):
        from app.engine.vision_extractor import VisionExtractor

        ve = VisionExtractor(model="test", api_key="test")
        ve._last_request_time = time.time()  # Just now
        ve.REQUEST_INTERVAL = 0.1  # Reduce for test speed

        start = time.time()
        await ve._rate_limit()
        elapsed = time.time() - start
        # Should have waited approximately REQUEST_INTERVAL
        assert elapsed >= 0.05


# ============================================================================
# Constants
# ============================================================================


class TestConstants:
    """Test class constants."""

    def test_max_requests_per_minute(self):
        from app.engine.vision_extractor import VisionExtractor
        assert VisionExtractor.MAX_REQUESTS_PER_MINUTE == 10

    def test_request_interval(self):
        from app.engine.vision_extractor import VisionExtractor
        assert abs(VisionExtractor.REQUEST_INTERVAL - 6.0) < 0.01

    def test_prompt_content(self):
        from app.engine.vision_extractor import VisionExtractor
        assert "Markdown" in VisionExtractor.MARITIME_EXTRACTION_PROMPT
        assert "Hàng hải" in VisionExtractor.MARITIME_EXTRACTION_PROMPT


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton factory."""

    def test_get_vision_extractor(self):
        from app.engine.vision_extractor import get_vision_extractor
        with patch("app.engine.vision_extractor.settings") as mock_s:
            mock_s.google_model = "test"
            mock_s.google_api_key = "test"
            v1 = get_vision_extractor()
            v2 = get_vision_extractor()
        assert v1 is v2
