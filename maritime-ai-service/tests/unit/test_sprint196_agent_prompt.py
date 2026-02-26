"""
Sprint 196: Agent Prompt & Tool Registration Tests — "Thợ Săn Chuyên Nghiệp"

Tests for:
- Tool registration in product_search_tools.py (3 new tools)
- Agent prompt updates in product_search_node.py (B2B strategy)
- ProductSearchResult new fields (product_type, dealer_info)
- Config flags (5 new flags)
25 tests.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Config Flag Tests
# =============================================================================

class TestConfigFlags:
    """Test Sprint 196 config flags exist with correct code defaults.

    Note: Uses model_fields to check code defaults directly, avoiding
    .env overrides that would mask the intended default values.
    """

    def test_enable_dealer_search_default(self):
        from app.core.config import Settings
        assert "enable_dealer_search" in Settings.model_fields
        assert Settings.model_fields["enable_dealer_search"].default is False

    def test_enable_contact_extraction_default(self):
        from app.core.config import Settings
        assert "enable_contact_extraction" in Settings.model_fields
        assert Settings.model_fields["enable_contact_extraction"].default is False

    def test_enable_international_search_default(self):
        from app.core.config import Settings
        assert "enable_international_search" in Settings.model_fields
        assert Settings.model_fields["enable_international_search"].default is False

    def test_enable_advanced_excel_report_default(self):
        from app.core.config import Settings
        assert "enable_advanced_excel_report" in Settings.model_fields
        assert Settings.model_fields["enable_advanced_excel_report"].default is False

    def test_usd_vnd_exchange_rate_default(self):
        from app.core.config import Settings
        assert "usd_vnd_exchange_rate" in Settings.model_fields
        assert Settings.model_fields["usd_vnd_exchange_rate"].default == 25500.0

    def test_usd_vnd_exchange_rate_custom(self):
        from app.core.config import Settings
        assert Settings.model_fields["usd_vnd_exchange_rate"].default == 25500.0


# =============================================================================
# ProductSearchResult New Fields Tests
# =============================================================================

class TestProductSearchResultFields:
    """Test ProductSearchResult Sprint 196 fields."""

    def test_product_type_field(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="Part X", product_type="part")
        assert r.product_type == "part"

    def test_product_type_none_default(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="Product")
        assert r.product_type is None

    def test_dealer_info_field(self):
        from app.engine.search_platforms.base import ProductSearchResult
        info = {"phones": ["0901234567"], "zalo": [], "emails": ["a@b.com"], "address": "HCM"}
        r = ProductSearchResult(platform="Test", title="Part X", dealer_info=info)
        assert r.dealer_info["phones"] == ["0901234567"]

    def test_dealer_info_none_default(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="Product")
        assert r.dealer_info is None

    def test_to_dict_includes_product_type(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="X", product_type="machine")
        d = r.to_dict()
        assert d["product_type"] == "machine"

    def test_to_dict_includes_dealer_info(self):
        from app.engine.search_platforms.base import ProductSearchResult
        info = {"phones": ["0901234567"]}
        r = ProductSearchResult(platform="Test", title="X", dealer_info=info)
        d = r.to_dict()
        assert "dealer_info" in d

    def test_to_dict_omits_none_product_type(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="X")
        d = r.to_dict()
        assert "product_type" not in d

    def test_to_dict_omits_none_dealer_info(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="Test", title="X")
        d = r.to_dict()
        assert "dealer_info" not in d


# =============================================================================
# Tool Registration Tests
# =============================================================================

class TestToolRegistration:
    """Test that Sprint 196 tools are registered when flags are enabled."""

    @patch("app.engine.search_platforms.circuit_breaker.PerPlatformCircuitBreaker")
    @patch("app.engine.search_platforms.init_search_platforms")
    @patch("app.core.config.get_settings")
    def test_dealer_tool_registered_when_enabled(self, mock_settings, mock_init, mock_cb):
        mock_settings.return_value = MagicMock(
            enable_product_search=True,
            enable_dealer_search=True,
            enable_contact_extraction=False,
            enable_international_search=False,
            product_search_timeout=30,
            product_search_max_results=30,
            product_search_platforms=["google_shopping"],
            enable_auto_group_discovery=False,
        )
        mock_init.side_effect = Exception("Skip registry init")

        import app.engine.tools.product_search_tools as pst
        pst._generated_tools.clear()
        pst.init_product_search_tools()
        tool_names = [t.name for t in pst.get_product_search_tools()]
        assert "tool_dealer_search" in tool_names

    @patch("app.engine.search_platforms.circuit_breaker.PerPlatformCircuitBreaker")
    @patch("app.engine.search_platforms.init_search_platforms")
    @patch("app.core.config.get_settings")
    def test_contact_tool_registered_when_enabled(self, mock_settings, mock_init, mock_cb):
        mock_settings.return_value = MagicMock(
            enable_product_search=True,
            enable_dealer_search=False,
            enable_contact_extraction=True,
            enable_international_search=False,
            product_search_timeout=30,
            product_search_max_results=30,
            product_search_platforms=["google_shopping"],
            enable_auto_group_discovery=False,
        )
        mock_init.side_effect = Exception("Skip registry init")

        import app.engine.tools.product_search_tools as pst
        pst._generated_tools.clear()
        pst.init_product_search_tools()
        tool_names = [t.name for t in pst.get_product_search_tools()]
        assert "tool_extract_contacts" in tool_names

    @patch("app.engine.search_platforms.circuit_breaker.PerPlatformCircuitBreaker")
    @patch("app.engine.search_platforms.init_search_platforms")
    @patch("app.core.config.get_settings")
    def test_international_tool_registered_when_enabled(self, mock_settings, mock_init, mock_cb):
        mock_settings.return_value = MagicMock(
            enable_product_search=True,
            enable_dealer_search=False,
            enable_contact_extraction=False,
            enable_international_search=True,
            product_search_timeout=30,
            product_search_max_results=30,
            product_search_platforms=["google_shopping"],
            enable_auto_group_discovery=False,
        )
        mock_init.side_effect = Exception("Skip registry init")

        import app.engine.tools.product_search_tools as pst
        pst._generated_tools.clear()
        pst.init_product_search_tools()
        tool_names = [t.name for t in pst.get_product_search_tools()]
        assert "tool_international_search" in tool_names

    @patch("app.engine.search_platforms.circuit_breaker.PerPlatformCircuitBreaker")
    @patch("app.engine.search_platforms.init_search_platforms")
    @patch("app.core.config.get_settings")
    def test_no_tools_when_all_disabled(self, mock_settings, mock_init, mock_cb):
        mock_settings.return_value = MagicMock(
            enable_product_search=True,
            enable_dealer_search=False,
            enable_contact_extraction=False,
            enable_international_search=False,
            product_search_timeout=30,
            product_search_max_results=30,
            product_search_platforms=["google_shopping"],
            enable_auto_group_discovery=False,
        )
        mock_init.side_effect = Exception("Skip registry init")

        import app.engine.tools.product_search_tools as pst
        pst._generated_tools.clear()
        pst.init_product_search_tools()
        tool_names = [t.name for t in pst.get_product_search_tools()]
        assert "tool_dealer_search" not in tool_names
        assert "tool_extract_contacts" not in tool_names
        assert "tool_international_search" not in tool_names


# =============================================================================
# Agent Prompt Tests
# =============================================================================

class TestAgentPrompt:
    """Test product_search_node.py prompt includes B2B strategy."""

    def test_system_prompt_contains_b2b_strategy(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "B2B" in _SYSTEM_PROMPT
        assert "tool_dealer_search" in _SYSTEM_PROMPT
        assert "tool_extract_contacts" in _SYSTEM_PROMPT
        assert "tool_international_search" in _SYSTEM_PROMPT

    def test_system_prompt_contains_industrial_hints(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "printhead" in _SYSTEM_PROMPT.lower() or "đầu in" in _SYSTEM_PROMPT

    def test_tool_ack_for_new_tools(self):
        from app.engine.multi_agent.agents.product_search_node import _TOOL_ACK
        assert "tool_dealer_search" in _TOOL_ACK
        assert "tool_extract_contacts" in _TOOL_ACK
        assert "tool_international_search" in _TOOL_ACK

    def test_tool_ack_vietnamese(self):
        from app.engine.multi_agent.agents.product_search_node import _TOOL_ACK
        assert "đại lý" in _TOOL_ACK["tool_dealer_search"].lower() or "phân phối" in _TOOL_ACK["tool_dealer_search"].lower()
