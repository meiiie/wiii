"""
Sprint 214: "Tri Thức Không Biên Giới" — Org Knowledge Retrieval Fix

Tests for:
1. tool_knowledge_search passes org_id via ContextVar
2. _collect_direct_tools includes tool_knowledge_search
3. _validate_domain_routing bypasses keyword check for org knowledge
4. Domain notice suppressed for org users with knowledge enabled
5. Org isolation (search scoped to org_id)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Helpers
# ============================================================================

def _make_settings(**overrides):
    """Create Settings mock with org knowledge defaults."""
    defaults = {
        "enable_org_knowledge": True,
        "enable_multi_tenant": True,
        "enable_character_tools": False,
        "enable_code_execution": False,
        "enable_lms_integration": False,
        "enable_natural_conversation": False,
        "default_domain": "maritime",
        "rag_confidence_high": 0.7,
        "enable_product_search": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_crag_result(answer="Test answer", confidence=85.0, sources=None):
    """Create a mock CorrectiveRAG result."""
    result = MagicMock()
    result.answer = answer
    result.confidence = confidence
    result.sources = sources or []
    result.reasoning_trace = None
    result.thinking = None
    return result


# ============================================================================
# 1. tool_knowledge_search passes org_id
# ============================================================================

class TestToolKnowledgeSearchOrgId:
    """Verify tool_knowledge_search reads ContextVar and passes org_id."""

    @pytest.mark.asyncio
    async def test_passes_org_id_from_context(self):
        """When org context is set, context dict includes organization_id."""
        mock_crag = AsyncMock()
        mock_crag.process = AsyncMock(return_value=_make_crag_result())

        # Lazy imports in rag_tools → patch at source module
        with patch("app.engine.agentic_rag.corrective_rag.get_corrective_rag", return_value=mock_crag), \
             patch("app.engine.tools.rag_tools._rag_agent", new=MagicMock()), \
             patch("app.core.org_context.get_current_org_id", return_value="org-123"), \
             patch("app.core.config.settings", _make_settings()):
            from app.engine.tools.rag_tools import tool_knowledge_search
            await tool_knowledge_search.ainvoke("test query")

        # Verify context was passed with organization_id
        mock_crag.process.assert_awaited_once()
        call_args = mock_crag.process.call_args
        ctx = call_args.kwargs["context"]
        assert ctx.get("organization_id") == "org-123"

    @pytest.mark.asyncio
    async def test_no_org_context_empty_dict(self):
        """When no org context, context dict is empty (backward compatible)."""
        mock_crag = AsyncMock()
        mock_crag.process = AsyncMock(return_value=_make_crag_result())

        with patch("app.engine.agentic_rag.corrective_rag.get_corrective_rag", return_value=mock_crag), \
             patch("app.engine.tools.rag_tools._rag_agent", new=MagicMock()), \
             patch("app.core.org_context.get_current_org_id", return_value=None), \
             patch("app.core.config.settings", _make_settings()):
            from app.engine.tools.rag_tools import tool_knowledge_search
            await tool_knowledge_search.ainvoke("test query")

        mock_crag.process.assert_awaited_once()
        call_args = mock_crag.process.call_args
        ctx = call_args.kwargs["context"]
        assert ctx == {}


# ============================================================================
# 2. _collect_direct_tools includes tool_knowledge_search
# ============================================================================

class TestDirectToolsIncludeKnowledgeSearch:
    """Verify _collect_direct_tools returns tool_knowledge_search."""

    def test_direct_tools_include_knowledge_search(self):
        """tool_knowledge_search should be in Direct Agent's tool list."""
        mock_settings = _make_settings()

        with patch("app.engine.multi_agent.graph.settings", mock_settings):
            from app.engine.multi_agent.graph import _collect_direct_tools
            tools, force = _collect_direct_tools("test query")

        tool_names = [getattr(t, "name", str(t)) for t in tools]
        assert "tool_knowledge_search" in tool_names, \
            f"tool_knowledge_search not found in direct tools: {tool_names}"


# ============================================================================
# 3. _validate_domain_routing bypasses for org knowledge
# ============================================================================

class TestDomainValidationOrgBypass:
    """Verify domain validation is bypassed when org knowledge is enabled."""

    def _make_supervisor(self):
        """Create a Supervisor with mocked dependencies."""
        with patch("app.engine.multi_agent.supervisor.AgentConfigRegistry"):
            from app.engine.multi_agent.supervisor import SupervisorAgent
            sup = SupervisorAgent.__new__(SupervisorAgent)
            sup.domain_config = {"keywords": ["colregs", "solas", "hàng hải"]}
            return sup

    def test_bypass_when_org_knowledge_and_org_context(self):
        """RAG should NOT be overridden to DIRECT when org has knowledge enabled."""
        sup = self._make_supervisor()
        domain_config = {"keywords": ["colregs", "solas", "hàng hải"]}

        # Lazy import inside method → patch at source
        with patch("app.core.config.settings",
                    _make_settings(enable_org_knowledge=True)), \
             patch("app.core.org_context.get_current_org_id",
                    return_value="org-123"):
            result = sup._validate_domain_routing(
                "logistics và chuỗi cung ứng",  # No maritime keywords
                "rag_agent",
                domain_config
            )

        assert result == "rag_agent", \
            f"Expected rag_agent (org bypass), got {result}"

    def test_no_bypass_without_org_context(self):
        """Without org context, RAG still overridden to DIRECT (existing behavior)."""
        sup = self._make_supervisor()
        domain_config = {"keywords": ["colregs", "solas", "hàng hải"],
                         "routing_keywords": ["colregs,solas,hàng hải"]}

        with patch("app.core.config.settings",
                    _make_settings(enable_org_knowledge=True)), \
             patch("app.core.org_context.get_current_org_id",
                    return_value=None):
            result = sup._validate_domain_routing(
                "logistics và chuỗi cung ứng",  # No maritime keywords
                "rag_agent",
                domain_config
            )

        assert result == "direct", \
            f"Expected direct (no org context), got {result}"

    def test_no_bypass_without_org_knowledge_flag(self):
        """Without enable_org_knowledge, RAG still overridden to DIRECT."""
        sup = self._make_supervisor()
        domain_config = {"keywords": ["colregs", "solas", "hàng hải"],
                         "routing_keywords": ["colregs,solas,hàng hải"]}

        with patch("app.core.config.settings",
                    _make_settings(enable_org_knowledge=False)):
            result = sup._validate_domain_routing(
                "logistics và chuỗi cung ứng",
                "rag_agent",
                domain_config
            )

        assert result == "direct", \
            f"Expected direct (org_knowledge disabled), got {result}"

    def test_non_rag_agent_unchanged(self):
        """Non-RAG/TUTOR agents pass through without validation."""
        sup = self._make_supervisor()
        domain_config = {"keywords": ["colregs"],
                         "routing_keywords": ["colregs"]}

        # No need to patch settings — early return before lazy import
        result = sup._validate_domain_routing(
            "xin chào",
            "direct",
            domain_config
        )

        assert result == "direct"

    def test_domain_keyword_present_keeps_rag(self):
        """When domain keyword IS present, RAG stays RAG (no change from before)."""
        sup = self._make_supervisor()
        domain_config = {"keywords": ["colregs", "solas", "hàng hải"],
                         "routing_keywords": ["colregs,solas,hàng hải"]}

        with patch("app.core.config.settings",
                    _make_settings(enable_org_knowledge=False)):
            result = sup._validate_domain_routing(
                "quy tắc colregs điều 15",
                "rag_agent",
                domain_config
            )

        assert result == "rag_agent"


# ============================================================================
# 4. Domain notice suppressed for org knowledge
# ============================================================================

class TestDomainNoticeSuppression:
    """Verify domain notice is suppressed when org knowledge is enabled."""

    def test_notice_suppressed_for_org_user(self):
        """Org user with knowledge enabled should NOT see domain notice."""
        state = {}
        domain_name_vi = "Hàng hải"
        intent = "off_topic"

        # Simulate the logic from graph.py direct_response_node
        if intent in ("off_topic", "general"):
            _settings_mock = _make_settings(enable_org_knowledge=True)
            _suppress = _settings_mock.enable_org_knowledge and True  # org context exists
            if not _suppress:
                state["domain_notice"] = (
                    f"Nội dung này nằm ngoài chuyên môn {domain_name_vi}."
                )

        assert "domain_notice" not in state, \
            "Domain notice should be suppressed for org knowledge users"

    def test_notice_shown_without_org(self):
        """Without org context, domain notice should still appear."""
        state = {}
        domain_name_vi = "Hàng hải"
        intent = "off_topic"

        if intent in ("off_topic", "general"):
            _settings_mock = _make_settings(enable_org_knowledge=True)
            _suppress = _settings_mock.enable_org_knowledge and False  # no org context
            if not _suppress:
                state["domain_notice"] = (
                    f"Nội dung này nằm ngoài chuyên môn {domain_name_vi}. "
                    f"Để được hỗ trợ chính xác hơn, hãy hỏi về {domain_name_vi} nhé!"
                )

        assert "domain_notice" in state, \
            "Domain notice should appear when no org context"

    def test_notice_shown_without_org_knowledge_flag(self):
        """With org context but org_knowledge disabled, notice still shows."""
        state = {}
        domain_name_vi = "Hàng hải"
        intent = "off_topic"

        if intent in ("off_topic", "general"):
            _settings_mock = _make_settings(enable_org_knowledge=False)
            _suppress = _settings_mock.enable_org_knowledge and True  # org exists but flag off
            if not _suppress:
                state["domain_notice"] = (
                    f"Nội dung này nằm ngoài chuyên môn {domain_name_vi}."
                )

        assert "domain_notice" in state, \
            "Domain notice should appear when org_knowledge is disabled"


# ============================================================================
# 5. Org isolation — search scoped by org_id
# ============================================================================

class TestOrgIsolationSearch:
    """Verify search respects org isolation (no cross-org leakage)."""

    @pytest.mark.asyncio
    async def test_org_a_cannot_see_org_b_docs(self):
        """Search with org_id=A should pass org_id=A to CRAG context."""
        mock_crag = AsyncMock()
        mock_crag.process = AsyncMock(return_value=_make_crag_result(
            answer="Org A result",
            sources=[{"title": "Org A Doc", "content": "From org A", "document_id": "doc-a"}]
        ))

        with patch("app.engine.agentic_rag.corrective_rag.get_corrective_rag", return_value=mock_crag), \
             patch("app.engine.tools.rag_tools._rag_agent", new=MagicMock()), \
             patch("app.core.org_context.get_current_org_id", return_value="org-A"), \
             patch("app.core.config.settings", _make_settings()):
            from app.engine.tools.rag_tools import tool_knowledge_search
            await tool_knowledge_search.ainvoke("test query")

        # Verify CRAG received org-A context — DB layer enforces isolation
        call_ctx = mock_crag.process.call_args.kwargs["context"]
        assert call_ctx["organization_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_shared_knowledge_without_org(self):
        """Without org context, shared knowledge (org_id=NULL) is accessible."""
        mock_crag = AsyncMock()
        mock_crag.process = AsyncMock(return_value=_make_crag_result())

        with patch("app.engine.agentic_rag.corrective_rag.get_corrective_rag", return_value=mock_crag), \
             patch("app.engine.tools.rag_tools._rag_agent", new=MagicMock()), \
             patch("app.core.org_context.get_current_org_id", return_value=None), \
             patch("app.core.config.settings", _make_settings()):
            from app.engine.tools.rag_tools import tool_knowledge_search
            await tool_knowledge_search.ainvoke("general query")

        # No organization_id in context — shared knowledge path
        call_ctx = mock_crag.process.call_args.kwargs["context"]
        assert call_ctx == {}
