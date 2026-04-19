"""Data Completeness Guard — ensures product search results are sufficient.

Pattern inspired by Firecrawl Web Agent: agents must collect ALL data,
not samples. The guard evaluates result quality after each ReAct iteration
and triggers additional search rounds when results are sparse, single-platform,
or missing critical fields.

Feature-gated by settings.enable_completeness_guard (default: False).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompletenessConfig:
    """Configuration for result completeness checking."""

    min_results: int = 3  # Minimum total results to consider adequate
    min_platforms: int = 2  # Results should span at least N platforms
    required_fields: List[str] = field(
        default_factory=lambda: ["title", "price"]
    )
    price_coverage_min: float = 0.6  # At least 60% of results must have a price
    max_extra_rounds: int = 2  # Max additional search rounds triggered by guard
    confidence_threshold: float = 0.7  # Overall completeness score to pass


@dataclass
class CompletenessReport:
    """Result of a completeness evaluation."""

    score: float  # 0.0 - 1.0
    is_sufficient: bool  # True if score >= threshold
    result_count: int
    platform_count: int
    price_coverage: float  # Fraction of results with extracted_price
    missing_fields: List[str]  # Required fields with low coverage
    suggestion: str  # Vietnamese guidance for next action


class CompletenessGuard:
    """Evaluates whether product search results are complete enough for synthesis.

    Integrated into the ReAct loop to trigger additional search rounds
    when results are sparse, single-platform, or missing critical fields.

    Weighted score:
    - Result count: 30% (how many results vs minimum)
    - Platform diversity: 20% (how many distinct platforms)
    - Required fields: 25% (coverage of title, price, etc.)
    - Price coverage: 25% (how many results have a price)
    """

    def __init__(self, config: Optional[CompletenessConfig] = None):
        self._config = config or CompletenessConfig()
        self._extra_rounds_used: int = 0

    def evaluate(self, results: List[Dict[str, Any]]) -> CompletenessReport:
        """Evaluate completeness of accumulated product results."""
        result_count = len(results)
        platforms = set(r.get("platform", "") for r in results if r.get("platform"))
        platform_count = len(platforms)

        # Required field coverage
        missing_fields: List[str] = []
        for req_field in self._config.required_fields:
            if result_count == 0:
                missing_fields.append(req_field)
                continue
            present = sum(1 for r in results if r.get(req_field))
            coverage = present / result_count
            if coverage < 0.5:
                missing_fields.append(req_field)

        # Price coverage
        with_price = sum(
            1 for r in results if r.get("extracted_price") or r.get("price")
        )
        price_coverage = with_price / max(result_count, 1)

        # Weighted score (0.0 - 1.0)
        count_score = min(result_count / max(self._config.min_results, 1), 1.0)
        platform_score = min(
            platform_count / max(self._config.min_platforms, 1), 1.0
        )
        field_score = 1.0 - len(missing_fields) / max(
            len(self._config.required_fields), 1
        )
        price_score = min(price_coverage, 1.0)

        score = count_score * 0.30 + platform_score * 0.20 + field_score * 0.25 + price_score * 0.25
        score = min(score, 1.0)

        is_sufficient = score >= self._config.confidence_threshold
        suggestion = self._build_suggestion(
            result_count, platform_count, price_coverage, missing_fields
        )

        return CompletenessReport(
            score=score,
            is_sufficient=is_sufficient,
            result_count=result_count,
            platform_count=platform_count,
            price_coverage=price_coverage,
            missing_fields=missing_fields,
            suggestion=suggestion,
        )

    def can_retry(self) -> bool:
        """Whether the guard can trigger another search round."""
        return self._extra_rounds_used < self._config.max_extra_rounds

    def consume_retry(self) -> None:
        """Mark one extra round as used."""
        self._extra_rounds_used += 1

    @property
    def extra_rounds_used(self) -> int:
        return self._extra_rounds_used

    def _build_suggestion(
        self,
        result_count: int,
        platform_count: int,
        price_coverage: float,
        missing_fields: List[str],
    ) -> str:
        """Build a Vietnamese suggestion for the LLM to improve search."""
        parts: List[str] = []

        if result_count < self._config.min_results:
            parts.append(
                f"Chỉ có {result_count}/{self._config.min_results} kết quả. "
                f"Thử tìm thêm trên các sàn khác."
            )

        if platform_count < self._config.min_platforms:
            parts.append(
                f"Kết quả chỉ từ {platform_count} nền tảng. "
                f"Thử Shopee, Lazada, hoặc WebSosanh để so sánh giá."
            )

        if price_coverage < self._config.price_coverage_min:
            parts.append(
                f"Chỉ {price_coverage:.0%} có giá. "
                f"Thử tìm chi tiết hơn để lấy thông tin giá."
            )

        if missing_fields:
            field_names = ", ".join(missing_fields)
            parts.append(f"Thiếu trường: {field_names}.")

        if not parts:
            return "Kết quả đã đủ."

        return " ".join(parts)
