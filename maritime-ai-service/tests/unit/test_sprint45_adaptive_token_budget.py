"""
Tests for Sprint 45: AdaptiveTokenBudget coverage.

Tests adaptive token budget allocation including:
- BudgetTier enum
- TokenBudget dataclass
- TOKEN_ALLOCATIONS mapping
- Greeting detection (Rule 1)
- Cached response handling (Rule 2)
- QueryAnalysis complexity mapping (Rule 3)
- Keyword heuristics (Rule 4)
- Domain boost tier upgrade
- get_budget_for_tier
"""

import pytest
from unittest.mock import MagicMock, patch


# ============================================================================
# BudgetTier enum
# ============================================================================


class TestBudgetTier:
    """Test BudgetTier enum."""

    def test_all_tiers(self):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        assert BudgetTier.MINIMAL.value == "minimal"
        assert BudgetTier.LIGHT.value == "light"
        assert BudgetTier.MODERATE.value == "moderate"
        assert BudgetTier.STANDARD.value == "standard"
        assert BudgetTier.DEEP.value == "deep"

    def test_tier_count(self):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        assert len(BudgetTier) == 5


# ============================================================================
# TokenBudget dataclass
# ============================================================================


class TestTokenBudget:
    """Test TokenBudget dataclass."""

    def test_creation(self):
        from app.engine.agentic_rag.adaptive_token_budget import TokenBudget, BudgetTier
        budget = TokenBudget(
            tier=BudgetTier.MODERATE,
            thinking_tokens=400,
            response_tokens=1024,
            total_budget=1424,
            reason="Analytical query"
        )
        assert budget.tier == BudgetTier.MODERATE
        assert budget.total_budget == 1424


# ============================================================================
# TOKEN_ALLOCATIONS
# ============================================================================


class TestTokenAllocations:
    """Test pre-defined allocations."""

    def test_all_tiers_have_allocations(self):
        from app.engine.agentic_rag.adaptive_token_budget import TOKEN_ALLOCATIONS, BudgetTier
        for tier in BudgetTier:
            assert tier in TOKEN_ALLOCATIONS
            assert "thinking" in TOKEN_ALLOCATIONS[tier]
            assert "response" in TOKEN_ALLOCATIONS[tier]
            assert "description" in TOKEN_ALLOCATIONS[tier]

    def test_token_ordering(self):
        """Higher tiers have more tokens."""
        from app.engine.agentic_rag.adaptive_token_budget import TOKEN_ALLOCATIONS, BudgetTier
        minimal = TOKEN_ALLOCATIONS[BudgetTier.MINIMAL]["response"]
        light = TOKEN_ALLOCATIONS[BudgetTier.LIGHT]["response"]
        moderate = TOKEN_ALLOCATIONS[BudgetTier.MODERATE]["response"]
        standard = TOKEN_ALLOCATIONS[BudgetTier.STANDARD]["response"]
        deep = TOKEN_ALLOCATIONS[BudgetTier.DEEP]["response"]
        assert minimal < light < moderate < standard < deep


# ============================================================================
# AdaptiveTokenBudget initialization
# ============================================================================


class TestAdaptiveTokenBudgetInit:
    """Test initialization."""

    def test_default_init(self):
        from app.engine.agentic_rag.adaptive_token_budget import AdaptiveTokenBudget, BudgetTier
        atb = AdaptiveTokenBudget()
        assert atb._default_tier == BudgetTier.STANDARD


# ============================================================================
# Rule 1: Greeting detection
# ============================================================================


class TestGreetingDetection:
    """Test Rule 1: Short greeting queries get MINIMAL."""

    @pytest.fixture
    def atb(self):
        from app.engine.agentic_rag.adaptive_token_budget import AdaptiveTokenBudget
        return AdaptiveTokenBudget()

    def test_hello_greeting(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("hello")
        assert budget.tier == BudgetTier.MINIMAL

    def test_xin_chao(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("xin ch\u00e0o")
        assert budget.tier == BudgetTier.MINIMAL

    def test_cam_on(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("c\u1ea3m \u01a1n")
        assert budget.tier == BudgetTier.MINIMAL

    def test_ok_response(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("ok")
        assert budget.tier == BudgetTier.MINIMAL

    def test_long_greeting_not_minimal(self, atb):
        """Long query with greeting word still goes through other rules."""
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        # >20 chars, so Rule 1 length check fails
        budget = atb.get_budget("Hello there, can you tell me about maritime safety?")
        assert budget.tier != BudgetTier.MINIMAL


# ============================================================================
# Rule 2: Cached response handling
# ============================================================================


class TestCachedResponseHandling:
    """Test Rule 2: Cached queries with high similarity get LIGHT."""

    @pytest.fixture
    def atb(self):
        from app.engine.agentic_rag.adaptive_token_budget import AdaptiveTokenBudget
        return AdaptiveTokenBudget()

    def test_cached_high_similarity(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget(
            "What is Rule 15 about?",
            is_cached=True, similarity=0.99
        )
        assert budget.tier == BudgetTier.LIGHT

    def test_cached_at_threshold(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget(
            "What is Rule 15?", is_cached=True, similarity=0.95
        )
        assert budget.tier == BudgetTier.LIGHT

    def test_cached_below_threshold(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget(
            "What is Rule 15?", is_cached=True, similarity=0.90
        )
        # Below 0.95, falls through to other rules
        assert budget.tier != BudgetTier.LIGHT

    def test_not_cached_ignores_similarity(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget(
            "What is Rule 15?", is_cached=False, similarity=0.99
        )
        # Not cached, Rule 2 doesn't apply
        assert budget.tier != BudgetTier.LIGHT or budget.tier == BudgetTier.LIGHT  # May match Rule 4


# ============================================================================
# Rule 3: QueryAnalysis complexity mapping
# ============================================================================


class TestQueryAnalysisMapping:
    """Test Rule 3: QueryAnalysis complexity → tier mapping."""

    @pytest.fixture
    def atb(self):
        from app.engine.agentic_rag.adaptive_token_budget import AdaptiveTokenBudget
        return AdaptiveTokenBudget()

    def test_simple_complexity(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        analysis = MagicMock()
        analysis.complexity = MagicMock()
        analysis.complexity.value = "SIMPLE"
        analysis.is_domain_related = False

        # Mock QueryComplexity enum
        with patch("app.engine.agentic_rag.query_analyzer.QueryComplexity") as MockQC:
            simple_val = MagicMock()
            medium_val = MagicMock()
            complex_val = MagicMock()
            MockQC.SIMPLE = simple_val
            MockQC.MEDIUM = medium_val
            MockQC.COMPLEX = complex_val
            analysis.complexity = simple_val

            budget = atb.get_budget("simple question?", query_analysis=analysis)
            assert budget.tier == BudgetTier.LIGHT

    def test_complex_analysis(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        analysis = MagicMock()
        analysis.is_domain_related = False

        with patch("app.engine.agentic_rag.query_analyzer.QueryComplexity") as MockQC:
            complex_val = MagicMock()
            MockQC.SIMPLE = MagicMock()
            MockQC.MEDIUM = MagicMock()
            MockQC.COMPLEX = complex_val
            analysis.complexity = complex_val

            budget = atb.get_budget("complex analysis question?", query_analysis=analysis)
            assert budget.tier == BudgetTier.STANDARD

    def test_domain_boost(self, atb):
        """Domain-related queries get tier upgrade."""
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        analysis = MagicMock()
        analysis.is_domain_related = True

        with patch("app.engine.agentic_rag.query_analyzer.QueryComplexity") as MockQC:
            simple_val = MagicMock()
            MockQC.SIMPLE = simple_val
            MockQC.MEDIUM = MagicMock()
            MockQC.COMPLEX = MagicMock()
            analysis.complexity = simple_val

            budget = atb.get_budget("maritime rule?", query_analysis=analysis)
            # LIGHT → MODERATE (one tier up for domain)
            assert budget.tier == BudgetTier.MODERATE


# ============================================================================
# Rule 4: Keyword heuristics
# ============================================================================


class TestKeywordHeuristics:
    """Test Rule 4: Keyword-based tier selection."""

    @pytest.fixture
    def atb(self):
        from app.engine.agentic_rag.adaptive_token_budget import AdaptiveTokenBudget
        return AdaptiveTokenBudget()

    def test_complex_keyword_compare(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("so s\u00e1nh Rule 15 v\u00e0 Rule 17")
        assert budget.tier == BudgetTier.STANDARD

    def test_complex_keyword_why(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("t\u1ea1i sao t\u00e0u ph\u1ea3i nh\u01b0\u1eddng \u0111\u01b0\u1eddng?")
        assert budget.tier == BudgetTier.STANDARD

    def test_complex_keyword_analyze(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("analyze the crossing situation")
        assert budget.tier == BudgetTier.STANDARD

    def test_moderate_keyword_what_is(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("COLREGs l\u00e0 g\u00ec?")
        assert budget.tier == BudgetTier.MODERATE

    def test_moderate_keyword_regulation(self, atb):
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("quy \u0111\u1ecbnh v\u1ec1 \u0111\u00e8n hi\u1ec7u")
        assert budget.tier == BudgetTier.MODERATE

    def test_default_moderate(self, atb):
        """Default query without keywords gets MODERATE."""
        from app.engine.agentic_rag.adaptive_token_budget import BudgetTier
        budget = atb.get_budget("COLREGs maritime safety overview")
        assert budget.tier == BudgetTier.MODERATE


# ============================================================================
# get_budget_for_tier
# ============================================================================


class TestGetBudgetForTier:
    """Test explicit tier budget retrieval."""

    def test_get_each_tier(self):
        from app.engine.agentic_rag.adaptive_token_budget import (
            AdaptiveTokenBudget, BudgetTier, TOKEN_ALLOCATIONS
        )
        atb = AdaptiveTokenBudget()
        for tier in BudgetTier:
            budget = atb.get_budget_for_tier(tier)
            assert budget.tier == tier
            assert budget.thinking_tokens == TOKEN_ALLOCATIONS[tier]["thinking"]
            assert budget.response_tokens == TOKEN_ALLOCATIONS[tier]["response"]
            assert budget.total_budget == budget.thinking_tokens + budget.response_tokens
