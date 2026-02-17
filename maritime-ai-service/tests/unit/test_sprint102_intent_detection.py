"""
Sprint 102: Intent Detection + Supervisor Routing Tests

Tests for expanded _WEB_INTENT_KEYWORDS, _needs_news_search, _needs_legal_search,
and routing prompt examples.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.graph import (
    _needs_web_search, _needs_datetime,
    _needs_news_search, _needs_legal_search,
)

if not _had_cs:
    sys.modules.pop(_cs_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# =============================================================================
# Intent detection in graph.py
# =============================================================================

class TestNeedsNewsSearch:
    """Test _needs_news_search intent detection."""

    def test_detects_tin_tuc(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Tin tức hôm nay") is True

    def test_detects_thoi_su(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Thời sự Việt Nam") is True

    def test_detects_ban_tin(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Bản tin sáng nay") is True

    def test_detects_bao_chi(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Báo chí nói gì") is True

    def test_detects_without_diacritics(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("tin tuc hom nay") is True

    def test_rejects_general_query(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Python là gì") is False

    def test_rejects_greeting(self):
        from app.engine.multi_agent.graph import _needs_news_search
        assert _needs_news_search("Xin chào") is False


class TestNeedsLegalSearch:
    """Test _needs_legal_search intent detection."""

    def test_detects_nghi_dinh(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Nghị định 100 về phạt giao thông") is True

    def test_detects_thong_tu(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Thông tư 15 về an toàn lao động") is True

    def test_detects_luat_so(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Luật số 40 về hàng hải") is True

    def test_detects_bo_luat(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Bộ luật hình sự") is True

    def test_detects_van_ban_phap_luat(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Tìm văn bản pháp luật mới") is True

    def test_detects_without_diacritics(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("nghi dinh 100") is True

    def test_rejects_unrelated(self):
        from app.engine.multi_agent.graph import _needs_legal_search
        assert _needs_legal_search("Thời tiết hôm nay") is False


class TestExpandedWebIntentKeywords:
    """Test expanded _WEB_INTENT_KEYWORDS includes legal/news/maritime signals."""

    def test_legal_keywords_trigger_web_search(self):
        from app.engine.multi_agent.graph import _needs_web_search
        assert _needs_web_search("nghị định 100") is True
        assert _needs_web_search("thông tư mới nhất") is True
        assert _needs_web_search("văn bản pháp luật") is True

    def test_maritime_web_keywords_trigger(self):
        from app.engine.multi_agent.graph import _needs_web_search
        assert _needs_web_search("IMO regulation 2026") is True
        assert _needs_web_search("cục hàng hải") is True

    def test_bao_chi_triggers(self):
        from app.engine.multi_agent.graph import _needs_web_search
        assert _needs_web_search("Báo chí nói gì") is True

    def test_original_keywords_still_work(self):
        """Sprint 99 keywords should still trigger."""
        from app.engine.multi_agent.graph import _needs_web_search
        assert _needs_web_search("tin tức hôm nay") is True
        assert _needs_web_search("tìm trên mạng AI") is True
        assert _needs_web_search("giá vàng") is True


class TestForceToolsIncludesNewIntents:
    """Verify _force_tools logic includes news/legal intent."""

    def test_legal_query_forces_tools(self):
        from app.engine.multi_agent.graph import (
            _needs_web_search, _needs_news_search,
            _needs_legal_search, _needs_datetime,
        )
        query = "nghị định 100 về phạt giao thông"
        force = (
            _needs_web_search(query) or _needs_datetime(query)
            or _needs_news_search(query) or _needs_legal_search(query)
        )
        assert force is True

    def test_news_query_forces_tools(self):
        from app.engine.multi_agent.graph import (
            _needs_web_search, _needs_news_search,
            _needs_legal_search, _needs_datetime,
        )
        query = "tin tức hàng hải hôm nay"
        force = (
            _needs_web_search(query) or _needs_datetime(query)
            or _needs_news_search(query) or _needs_legal_search(query)
        )
        assert force is True


# Sprint 103: TestSupervisorWebKeywords deleted — WEB_KEYWORDS removed from supervisor.py.
# Web search routing is handled by LLM structured routing with web_search intent.


# =============================================================================
# Routing prompt examples
# =============================================================================

class TestRoutingPromptExamples:
    """Verify routing prompt includes Sprint 102+103 examples."""

    def test_prompt_includes_legal_example(self):
        from app.engine.multi_agent.supervisor import ROUTING_PROMPT_TEMPLATE
        assert "Nghị định 100" in ROUTING_PROMPT_TEMPLATE

    def test_prompt_includes_news_maritime_example(self):
        from app.engine.multi_agent.supervisor import ROUTING_PROMPT_TEMPLATE
        assert "Tin tức hàng hải" in ROUTING_PROMPT_TEMPLATE

    def test_prompt_includes_web_search_intent(self):
        """Sprint 103: Prompt template includes web_search intent."""
        from app.engine.multi_agent.supervisor import ROUTING_PROMPT_TEMPLATE
        assert "web_search" in ROUTING_PROMPT_TEMPLATE
        assert "intent=web_search" in ROUTING_PROMPT_TEMPLATE
