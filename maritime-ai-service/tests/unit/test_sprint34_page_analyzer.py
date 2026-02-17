"""
Tests for Sprint 34: PageAnalyzer — pure logic, no LLM.

Covers:
- PageAnalysisResult dataclass and is_visual_content property
- analyze_page with mock fitz.Page
- analyze_text_content (pure text analysis, no PDF needed)
- should_use_vision routing
- Detection: images, tables, diagrams, domain signals
- Short text fallback to vision
- Error handling in analyze_page
"""

import pytest
from unittest.mock import MagicMock, PropertyMock

from app.engine.page_analyzer import (
    PageAnalyzer,
    PageAnalysisResult,
)


# =============================================================================
# PageAnalysisResult
# =============================================================================


class TestPageAnalysisResult:
    def test_defaults(self):
        r = PageAnalysisResult(page_number=1)
        assert r.has_images is False
        assert r.has_tables is False
        assert r.has_diagrams is False
        assert r.has_domain_signals is False
        assert r.recommended_method == "direct"
        assert r.confidence == 1.0
        assert r.detection_reasons == []

    def test_is_visual_content_false(self):
        r = PageAnalysisResult(page_number=1)
        assert r.is_visual_content is False

    def test_is_visual_content_images(self):
        r = PageAnalysisResult(page_number=1, has_images=True)
        assert r.is_visual_content is True

    def test_is_visual_content_tables(self):
        r = PageAnalysisResult(page_number=1, has_tables=True)
        assert r.is_visual_content is True

    def test_is_visual_content_diagrams(self):
        r = PageAnalysisResult(page_number=1, has_diagrams=True)
        assert r.is_visual_content is True

    def test_is_visual_content_domain(self):
        r = PageAnalysisResult(page_number=1, has_domain_signals=True)
        assert r.is_visual_content is True


# =============================================================================
# analyze_text_content (pure text, no PDF)
# =============================================================================


class TestAnalyzeTextContent:
    def setup_method(self):
        self.analyzer = PageAnalyzer()

    def test_plain_text(self):
        result = self.analyzer.analyze_text_content(
            "This is a regular paragraph about maritime safety."
        )
        assert result["has_tables"] is False
        assert result["has_diagrams"] is False
        assert result["has_domain_signals"] is False
        assert result["is_visual"] is False

    def test_table_markdown(self):
        text = "| Column 1 | Column 2 |\n|---------|---------|"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_tables"] is True
        assert result["is_visual"] is True

    def test_table_unicode_box(self):
        text = "┌─────┐\n│ Cell│\n└─────┘"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_tables"] is True

    def test_table_ascii(self):
        text = "+-----+-----+\n| A   | B   |\n+-----+-----+"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_tables"] is True

    def test_diagram_keyword_vi(self):
        text = "Xem hình minh họa về đèn tín hiệu"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_diagrams"] is True

    def test_diagram_keyword_en(self):
        text = "See the figure below for the diagram"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_diagrams"] is True

    def test_domain_signal_vi(self):
        text = "Đèn tín hiệu hành trình phải được bật"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_domain_signals"] is True

    def test_domain_signal_en(self):
        text = "The starboard green light must be visible"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_domain_signals"] is True

    def test_text_length(self):
        text = "short"
        result = self.analyzer.analyze_text_content(text)
        assert result["text_length"] == 5

    def test_empty_text(self):
        result = self.analyzer.analyze_text_content("")
        assert result["text_length"] == 0
        assert result["is_visual"] is False

    def test_multiple_signals(self):
        text = "| Đèn | Tín hiệu |\n|-----|--------|\nHình 1: sơ đồ starboard"
        result = self.analyzer.analyze_text_content(text)
        assert result["has_tables"] is True
        assert result["has_diagrams"] is True
        assert result["has_domain_signals"] is True


# =============================================================================
# analyze_page (with mock fitz.Page)
# =============================================================================


def _mock_page(text="Some text content", images=None):
    """Create a mock fitz.Page."""
    page = MagicMock()
    page.get_text.return_value = text
    page.get_images.return_value = images or []
    return page


class TestAnalyzePage:
    def setup_method(self):
        self.analyzer = PageAnalyzer()

    def test_plain_text_page(self):
        page = _mock_page("A" * 200)
        result = self.analyzer.analyze_page(page, page_number=1)
        assert result.recommended_method == "direct"
        assert result.confidence >= 0.9

    def test_page_with_images(self):
        page = _mock_page("Some text", images=[(1, 0, 100, 100, 8, "DeviceRGB")])
        result = self.analyzer.analyze_page(page, page_number=2)
        assert result.has_images is True
        assert result.recommended_method == "vision"

    def test_page_with_table(self):
        text = "Data table\n| Col1 | Col2 |\n|------|------|\n| A    | B    |"
        page = _mock_page(text)
        result = self.analyzer.analyze_page(page, page_number=3)
        assert result.has_tables is True
        assert result.recommended_method == "vision"

    def test_page_with_diagram_keyword(self):
        text = "A" * 200 + "\nXem hình minh họa về quy trình"
        page = _mock_page(text)
        result = self.analyzer.analyze_page(page, page_number=4)
        assert result.has_diagrams is True
        assert result.recommended_method == "vision"

    def test_page_with_domain_keyword(self):
        text = "A" * 200 + "\nĐèn tín hiệu mạn phải"
        page = _mock_page(text)
        result = self.analyzer.analyze_page(page, page_number=5)
        assert result.has_domain_signals is True
        assert result.recommended_method == "vision"

    def test_short_text_falls_back_to_vision(self):
        page = _mock_page("Short")  # < 100 chars (default min_text_length)
        result = self.analyzer.analyze_page(page, page_number=6)
        assert result.recommended_method == "vision"
        assert result.confidence == 0.7

    def test_error_defaults_to_vision(self):
        page = MagicMock()
        page.get_images.side_effect = RuntimeError("PDF corrupt")
        result = self.analyzer.analyze_page(page, page_number=7)
        assert result.recommended_method == "vision"
        assert result.confidence == 0.5

    def test_text_length_recorded(self):
        page = _mock_page("Hello world")
        result = self.analyzer.analyze_page(page, page_number=1)
        assert result.text_length == len("Hello world")


# =============================================================================
# should_use_vision
# =============================================================================


class TestShouldUseVision:
    def setup_method(self):
        self.analyzer = PageAnalyzer()

    def test_vision_recommended(self):
        r = PageAnalysisResult(page_number=1, recommended_method="vision")
        assert self.analyzer.should_use_vision(r) is True

    def test_direct_recommended(self):
        r = PageAnalysisResult(page_number=1, recommended_method="direct")
        assert self.analyzer.should_use_vision(r) is False


# =============================================================================
# Custom initialization
# =============================================================================


class TestCustomInit:
    def test_custom_min_text_length(self):
        analyzer = PageAnalyzer(min_text_length=50)
        page = _mock_page("X" * 60)  # Above 50
        result = analyzer.analyze_page(page, page_number=1)
        assert result.recommended_method == "direct"

    def test_custom_keywords(self):
        analyzer = PageAnalyzer(domain_keywords=["custom_term"])
        result = analyzer.analyze_text_content("Contains custom_term here")
        assert result["has_domain_signals"] is True

    def test_custom_table_patterns(self):
        analyzer = PageAnalyzer(table_patterns=[r"###"])
        result = analyzer.analyze_text_content("### header line")
        assert result["has_tables"] is True
