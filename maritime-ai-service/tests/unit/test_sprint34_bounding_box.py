"""
Tests for Sprint 34: BoundingBoxExtractor — pure math/logic.

Covers:
- BoundingBox dataclass: to_dict, is_valid
- normalize_bbox: coordinate normalization to 0-1 ratio
- merge_boxes: overlapping/adjacent box merging
- _boxes_overlap: overlap detection with margin
"""

import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock fitz module before importing bounding_box_extractor
# (fitz is imported at module level, not lazily)
_mock_fitz = MagicMock()
with patch.dict(sys.modules, {"fitz": _mock_fitz}):
    from app.engine.bounding_box_extractor import (
        BoundingBox,
        BoundingBoxExtractor,
    )


# =============================================================================
# BoundingBox dataclass
# =============================================================================


class TestBoundingBox:
    def test_to_dict(self):
        box = BoundingBox(x0=0.10123, y0=0.20456, x1=0.50789, y1=0.80012)
        d = box.to_dict()
        assert d == {"x0": 0.1012, "y0": 0.2046, "x1": 0.5079, "y1": 0.8001}

    def test_to_dict_rounding(self):
        box = BoundingBox(x0=0.33335, y0=0.66665, x1=0.99995, y1=0.99999)
        d = box.to_dict()
        assert all(isinstance(v, float) for v in d.values())

    def test_is_valid_true(self):
        box = BoundingBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8)
        assert box.is_valid() is True

    def test_is_valid_zero_origin(self):
        box = BoundingBox(x0=0, y0=0, x1=1, y1=1)
        assert box.is_valid() is True

    def test_is_valid_x0_exceeds_x1(self):
        box = BoundingBox(x0=0.5, y0=0.1, x1=0.4, y1=0.8)
        assert box.is_valid() is False

    def test_is_valid_y0_exceeds_y1(self):
        box = BoundingBox(x0=0.1, y0=0.8, x1=0.9, y1=0.2)
        assert box.is_valid() is False

    def test_is_valid_negative(self):
        box = BoundingBox(x0=-0.05, y0=0.1, x1=0.5, y1=0.8)
        assert box.is_valid() is False

    def test_is_valid_over_1(self):
        box = BoundingBox(x0=0.1, y0=0.1, x1=1.05, y1=0.8)
        assert box.is_valid() is False

    def test_is_valid_equal_coordinates(self):
        """Equal x0==x1 or y0==y1 means zero-area — invalid."""
        box = BoundingBox(x0=0.5, y0=0.5, x1=0.5, y1=0.8)
        assert box.is_valid() is False


# =============================================================================
# normalize_bbox
# =============================================================================


class TestNormalizeBbox:
    def setup_method(self):
        self.extractor = BoundingBoxExtractor()

    def test_basic_normalization(self):
        # 100x200 point page, box at (25, 50, 75, 150)
        bbox = self.extractor.normalize_bbox(
            (25, 50, 75, 150), page_width=100, page_height=200
        )
        assert abs(bbox.x0 - 0.25) < 0.0001
        assert abs(bbox.y0 - 0.25) < 0.0001
        assert abs(bbox.x1 - 0.75) < 0.0001
        assert abs(bbox.y1 - 0.75) < 0.0001

    def test_full_page(self):
        bbox = self.extractor.normalize_bbox(
            (0, 0, 612, 792), page_width=612, page_height=792
        )
        assert abs(bbox.x0 - 0.0) < 0.0001
        assert abs(bbox.y0 - 0.0) < 0.0001
        assert abs(bbox.x1 - 1.0) < 0.0001
        assert abs(bbox.y1 - 1.0) < 0.0001

    def test_clamp_negative_values(self):
        bbox = self.extractor.normalize_bbox(
            (-10, -20, 50, 50), page_width=100, page_height=100
        )
        assert bbox.x0 == 0.0
        assert bbox.y0 == 0.0

    def test_clamp_over_1(self):
        bbox = self.extractor.normalize_bbox(
            (0, 0, 200, 200), page_width=100, page_height=100
        )
        assert bbox.x1 == 1.0
        assert bbox.y1 == 1.0

    def test_zero_page_width(self):
        bbox = self.extractor.normalize_bbox(
            (10, 10, 50, 50), page_width=0, page_height=100
        )
        assert bbox.x0 == 0.0
        assert bbox.x1 == 1.0  # Default when page_width=0

    def test_zero_page_height(self):
        bbox = self.extractor.normalize_bbox(
            (10, 10, 50, 50), page_width=100, page_height=0
        )
        assert bbox.y0 == 0.0
        assert bbox.y1 == 1.0


# =============================================================================
# merge_boxes
# =============================================================================


class TestMergeBoxes:
    def setup_method(self):
        self.extractor = BoundingBoxExtractor()

    def test_single_box(self):
        boxes = [BoundingBox(0.1, 0.1, 0.5, 0.5)]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 1

    def test_empty_list(self):
        result = self.extractor.merge_boxes([])
        assert result == []

    def test_non_overlapping(self):
        boxes = [
            BoundingBox(0.1, 0.1, 0.3, 0.3),
            BoundingBox(0.6, 0.6, 0.8, 0.8),
        ]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 2

    def test_overlapping_merged(self):
        boxes = [
            BoundingBox(0.1, 0.1, 0.5, 0.5),
            BoundingBox(0.3, 0.3, 0.7, 0.7),
        ]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 1
        assert result[0].x0 == 0.1
        assert result[0].y0 == 0.1
        assert result[0].x1 == 0.7
        assert result[0].y1 == 0.7

    def test_adjacent_within_margin(self):
        """Boxes within 5% margin should merge."""
        boxes = [
            BoundingBox(0.1, 0.1, 0.5, 0.5),
            BoundingBox(0.53, 0.1, 0.8, 0.5),  # 0.03 gap < 0.05 margin
        ]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 1

    def test_three_boxes_chain_merge(self):
        """A-B overlap, B-C overlap → all merge to one."""
        boxes = [
            BoundingBox(0.1, 0.1, 0.4, 0.4),
            BoundingBox(0.35, 0.1, 0.65, 0.4),
            BoundingBox(0.6, 0.1, 0.9, 0.4),
        ]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 1
        assert result[0].x0 == 0.1
        assert result[0].x1 == 0.9

    def test_sorted_by_position(self):
        """Boxes are sorted by y0, then x0 before merging."""
        boxes = [
            BoundingBox(0.6, 0.6, 0.8, 0.8),
            BoundingBox(0.1, 0.1, 0.3, 0.3),
        ]
        result = self.extractor.merge_boxes(boxes)
        assert len(result) == 2
        # First should be the top-left one
        assert result[0].y0 <= result[1].y0


# =============================================================================
# _boxes_overlap
# =============================================================================


class TestBoxesOverlap:
    def setup_method(self):
        self.extractor = BoundingBoxExtractor()

    def test_overlapping(self):
        a = BoundingBox(0.1, 0.1, 0.5, 0.5)
        b = BoundingBox(0.3, 0.3, 0.7, 0.7)
        assert self.extractor._boxes_overlap(a, b) is True

    def test_non_overlapping(self):
        a = BoundingBox(0.1, 0.1, 0.3, 0.3)
        b = BoundingBox(0.6, 0.6, 0.8, 0.8)
        assert self.extractor._boxes_overlap(a, b) is False

    def test_adjacent_no_margin(self):
        a = BoundingBox(0.1, 0.1, 0.5, 0.5)
        b = BoundingBox(0.55, 0.1, 0.8, 0.5)
        assert self.extractor._boxes_overlap(a, b, margin=0) is False

    def test_adjacent_with_margin(self):
        a = BoundingBox(0.1, 0.1, 0.5, 0.5)
        b = BoundingBox(0.55, 0.1, 0.8, 0.5)
        assert self.extractor._boxes_overlap(a, b, margin=0.1) is True

    def test_contained(self):
        """One box inside another."""
        outer = BoundingBox(0, 0, 1, 1)
        inner = BoundingBox(0.2, 0.2, 0.8, 0.8)
        assert self.extractor._boxes_overlap(outer, inner) is True
