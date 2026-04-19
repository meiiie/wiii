"""Tests for Data Completeness Guard."""

import pytest

from app.engine.search_platforms.completeness_guard import (
    CompletenessConfig,
    CompletenessGuard,
    CompletenessReport,
)


class TestCompletenessEvaluation:
    def test_empty_results(self):
        guard = CompletenessGuard()
        report = guard.evaluate([])
        assert report.score < 0.3
        assert report.is_sufficient is False
        assert report.result_count == 0
        assert report.platform_count == 0

    def test_single_result_single_platform(self):
        guard = CompletenessGuard()
        results = [
            {"platform": "Shopee", "title": "MacBook Pro", "price": "45tr", "extracted_price": 45000000}
        ]
        report = guard.evaluate(results)
        # With 1/3 count, 1/2 platforms: score = 0.33*0.3 + 0.5*0.2 + 1.0*0.25 + 1.0*0.25 = 0.70
        # Exactly at threshold — single result still has sparse diversity
        assert report.result_count == 1
        assert report.platform_count == 1
        assert len(report.suggestion) > 0  # Should still suggest improvement

    def test_sufficient_results(self):
        guard = CompletenessGuard()
        results = [
            {"platform": "Shopee", "title": "MacBook Pro M4", "price": "45tr", "extracted_price": 45000000},
            {"platform": "Lazada", "title": "MacBook Pro M4", "price": "46tr", "extracted_price": 46000000},
            {"platform": "WebSosanh", "title": "MacBook Pro M4", "price": "44tr", "extracted_price": 44000000},
            {"platform": "TikTok Shop", "title": "MacBook Pro M4", "price": "45.5tr", "extracted_price": 45500000},
        ]
        report = guard.evaluate(results)
        assert report.is_sufficient is True
        assert report.result_count == 4
        assert report.platform_count == 4
        assert report.score >= 0.7

    def test_many_results_single_platform(self):
        """Many results but from 1 platform — high score but still 1 platform."""
        guard = CompletenessGuard()
        results = [
            {"platform": "Shopee", "title": f"Item {i}", "price": f"{i}00k", "extracted_price": i * 100000}
            for i in range(5)
        ]
        report = guard.evaluate(results)
        # count=5/3=1.0, platforms=1/2=0.5, fields=1.0, price=1.0
        # score = 0.30 + 0.10 + 0.25 + 0.25 = 0.90
        assert report.platform_count == 1
        assert report.score >= 0.8  # High but not 1.0 due to single platform

    def test_results_missing_prices(self):
        guard = CompletenessGuard()
        results = [
            {"platform": "Shopee", "title": "Item A"},
            {"platform": "Lazada", "title": "Item B"},
            {"platform": "WebSosanh", "title": "Item C"},
        ]
        report = guard.evaluate(results)
        assert report.price_coverage == 0.0
        assert report.is_sufficient is False

    def test_custom_config(self):
        config = CompletenessConfig(min_results=1, min_platforms=1, confidence_threshold=0.5)
        guard = CompletenessGuard(config)
        results = [
            {"platform": "Shopee", "title": "Item", "price": "100k", "extracted_price": 100000}
        ]
        report = guard.evaluate(results)
        assert report.is_sufficient is True

    def test_price_coverage_calculation(self):
        guard = CompletenessGuard()
        results = [
            {"platform": "A", "title": "X", "price": "100k", "extracted_price": 100000},
            {"platform": "B", "title": "Y"},  # no price
            {"platform": "C", "title": "Z", "price": "200k", "extracted_price": 200000},
        ]
        report = guard.evaluate(results)
        assert abs(report.price_coverage - 2/3) < 0.01

    def test_suggestion_for_sparse_results(self):
        guard = CompletenessGuard()
        report = guard.evaluate([{"platform": "Shopee", "title": "A"}])
        assert len(report.suggestion) > 0
        assert "Shopee" in report.suggestion or "ket qua" in report.suggestion.lower() or "nền tảng" in report.suggestion or "nen tang" in report.suggestion

    def test_suggestion_when_sufficient(self):
        guard = CompletenessGuard()
        results = [
            {"platform": "A", "title": "X", "price": "100k", "extracted_price": 100},
            {"platform": "B", "title": "Y", "price": "200k", "extracted_price": 200},
            {"platform": "C", "title": "Z", "price": "300k", "extracted_price": 300},
        ]
        report = guard.evaluate(results)
        assert report.suggestion == "Ket qua da du."

    def test_missing_fields_detection(self):
        guard = CompletenessGuard()
        # All results lack price
        results = [
            {"platform": "A", "title": "X"},
            {"platform": "B", "title": "Y"},
            {"platform": "C", "title": "Z"},
        ]
        report = guard.evaluate(results)
        assert "price" in report.missing_fields


class TestRetryTracking:
    def test_can_retry_initially(self):
        guard = CompletenessGuard()
        assert guard.can_retry() is True

    def test_consume_retry(self):
        guard = CompletenessGuard(CompletenessConfig(max_extra_rounds=2))
        guard.consume_retry()
        assert guard.extra_rounds_used == 1
        assert guard.can_retry() is True

    def test_max_retries_reached(self):
        guard = CompletenessGuard(CompletenessConfig(max_extra_rounds=2))
        guard.consume_retry()
        guard.consume_retry()
        assert guard.can_retry() is False
        assert guard.extra_rounds_used == 2

    def test_zero_max_retries(self):
        guard = CompletenessGuard(CompletenessConfig(max_extra_rounds=0))
        assert guard.can_retry() is False
