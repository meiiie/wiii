"""
Tests for Sprint 67: Structured Outputs (Constrained Decoding).

Tests:
1. Pydantic schema validation (all 6 schemas)
2. Config flag (enable_structured_outputs)
3. Supervisor routing — structured vs legacy path
4. Grader agent — structured vs legacy path
5. Guardian agent — structured vs legacy path
6. RetrievalGrader — structured single + batch vs legacy path
7. Feature gate — disabled uses legacy path
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import ValidationError

# Pre-load modules to break circular import:
# graph → tutor_node → services → chat_service → graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
if not _had_cs:
    sys.modules[_cs_key] = types.ModuleType(_cs_key)
try:
    import app.engine.multi_agent.supervisor  # noqa: F401
    import app.engine.multi_agent.agents.grader_agent  # noqa: F401
except ImportError:
    pass
finally:
    if not _had_cs:
        sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestRoutingDecisionSchema:
    """Test RoutingDecision schema."""

    def test_valid_agents(self):
        from app.engine.structured_schemas import RoutingDecision
        for agent in ["RAG_AGENT", "TUTOR_AGENT", "MEMORY_AGENT", "DIRECT"]:
            d = RoutingDecision(agent=agent)
            assert d.agent == agent

    def test_invalid_agent_rejected(self):
        from app.engine.structured_schemas import RoutingDecision
        with pytest.raises(ValidationError):
            RoutingDecision(agent="INVALID_AGENT")

    def test_agent_required(self):
        from app.engine.structured_schemas import RoutingDecision
        with pytest.raises(ValidationError):
            RoutingDecision()


class TestQualityGradeResultSchema:
    """Test QualityGradeResult schema."""

    def test_valid_result(self):
        from app.engine.structured_schemas import QualityGradeResult
        r = QualityGradeResult(
            score=8.5, is_helpful=True, is_accurate=True,
            is_complete=True, feedback="Good answer"
        )
        assert r.score == 8.5
        assert r.is_helpful is True

    def test_score_bounds(self):
        from app.engine.structured_schemas import QualityGradeResult
        with pytest.raises(ValidationError):
            QualityGradeResult(
                score=11.0, is_helpful=True, is_accurate=True,
                is_complete=True, feedback="test"
            )
        with pytest.raises(ValidationError):
            QualityGradeResult(
                score=-1.0, is_helpful=True, is_accurate=True,
                is_complete=True, feedback="test"
            )

    def test_model_dump(self):
        from app.engine.structured_schemas import QualityGradeResult
        r = QualityGradeResult(
            score=7.0, is_helpful=True, is_accurate=False,
            is_complete=True, feedback="OK"
        )
        d = r.model_dump()
        assert d["score"] == 7.0
        assert d["is_accurate"] is False


class TestGuardianLLMResultSchema:
    """Test GuardianLLMResult schema."""

    def test_allow(self):
        from app.engine.structured_schemas import GuardianLLMResult
        r = GuardianLLMResult(action="ALLOW")
        assert r.action == "ALLOW"
        assert r.reason is None
        assert r.confidence == 0.8

    def test_block_with_reason(self):
        from app.engine.structured_schemas import GuardianLLMResult
        r = GuardianLLMResult(action="BLOCK", reason="Inappropriate", confidence=0.95)
        assert r.action == "BLOCK"
        assert r.reason == "Inappropriate"
        assert r.confidence == 0.95

    def test_invalid_action(self):
        from app.engine.structured_schemas import GuardianLLMResult
        with pytest.raises(ValidationError):
            GuardianLLMResult(action="WARN")

    def test_with_pronoun_request(self):
        from app.engine.structured_schemas import GuardianLLMResult, PronounRequestInfo
        pronoun = PronounRequestInfo(
            detected=True, appropriate=True,
            user_called="cong chua", ai_self="tram"
        )
        r = GuardianLLMResult(action="ALLOW", pronoun_request=pronoun)
        assert r.pronoun_request.detected is True
        assert r.pronoun_request.user_called == "cong chua"

    def test_confidence_bounds(self):
        from app.engine.structured_schemas import GuardianLLMResult
        with pytest.raises(ValidationError):
            GuardianLLMResult(action="ALLOW", confidence=1.5)
        with pytest.raises(ValidationError):
            GuardianLLMResult(action="ALLOW", confidence=-0.1)


class TestPronounRequestInfoSchema:
    """Test PronounRequestInfo schema."""

    def test_defaults(self):
        from app.engine.structured_schemas import PronounRequestInfo
        p = PronounRequestInfo()
        assert p.detected is False
        assert p.appropriate is False
        assert p.user_called == "ban"  or p.user_called  # Has default
        assert p.ai_self == "toi" or p.ai_self  # Has default

    def test_custom_values(self):
        from app.engine.structured_schemas import PronounRequestInfo
        p = PronounRequestInfo(
            detected=True, appropriate=True,
            user_called="captain", ai_self="sailor"
        )
        assert p.user_called == "captain"


class TestSingleDocGradeSchema:
    """Test SingleDocGrade schema."""

    def test_valid(self):
        from app.engine.structured_schemas import SingleDocGrade
        g = SingleDocGrade(score=7.5, is_relevant=True, reason="Direct answer")
        assert g.score == 7.5

    def test_score_bounds(self):
        from app.engine.structured_schemas import SingleDocGrade
        with pytest.raises(ValidationError):
            SingleDocGrade(score=11, is_relevant=True, reason="test")


class TestBatchDocGradesSchema:
    """Test BatchDocGrades schema."""

    def test_valid_batch(self):
        from app.engine.structured_schemas import BatchDocGrades, BatchDocGradeItem
        items = [
            BatchDocGradeItem(doc_index=0, score=8.0, is_relevant=True, reason="Good"),
            BatchDocGradeItem(doc_index=1, score=3.0, is_relevant=False, reason="Off topic"),
        ]
        b = BatchDocGrades(grades=items)
        assert len(b.grades) == 2
        assert b.grades[0].score == 8.0
        assert b.grades[1].is_relevant is False

    def test_empty_batch(self):
        from app.engine.structured_schemas import BatchDocGrades
        b = BatchDocGrades(grades=[])
        assert len(b.grades) == 0


# =============================================================================
# Config Tests
# =============================================================================


class TestConfigFlag:
    """Test enable_structured_outputs config field."""

    def test_default_enabled(self):
        """Sprint 103: default changed from False to True."""
        from app.core.config import Settings
        field_info = Settings.model_fields["enable_structured_outputs"]
        assert field_info.default is True

    def test_description(self):
        from app.core.config import Settings
        field_info = Settings.model_fields["enable_structured_outputs"]
        assert "structured" in field_info.description.lower()


# =============================================================================
# Supervisor Structured Output Tests
# =============================================================================


def _make_mock_settings(enable_structured=False):
    """Create a mock settings object with structured outputs flag."""
    mock = MagicMock()
    mock.enable_structured_outputs = enable_structured
    return mock


def _make_structured_llm(return_value):
    """Create a mock LLM with .with_structured_output() that returns from .ainvoke()."""
    mock_structured_chain = MagicMock()
    mock_structured_chain.ainvoke = AsyncMock(return_value=return_value)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_chain)
    return mock_llm


class TestSupervisorStructuredRoute:
    """Test Supervisor routing with structured output enabled."""

    def _make_supervisor(self, mock_llm):
        """Create supervisor instance without __init__."""
        from app.engine.multi_agent.supervisor import SupervisorAgent
        sup = SupervisorAgent.__new__(SupervisorAgent)
        sup._llm = mock_llm
        return sup

    @pytest.mark.asyncio
    async def test_structured_route_rag(self):
        from app.engine.structured_schemas import RoutingDecision
        mock_llm = _make_structured_llm(RoutingDecision(agent="RAG_AGENT"))

        sup = self._make_supervisor(mock_llm)
        # Sprint 103: No feature flag — always structured
        result = await sup.route({"query": "SOLAS Chapter V?", "context": {}, "domain_config": {}})

        assert result == "rag_agent"
        mock_llm.with_structured_output.assert_called_once_with(RoutingDecision)

    @pytest.mark.asyncio
    async def test_structured_route_direct(self):
        from app.engine.structured_schemas import RoutingDecision
        mock_llm = _make_structured_llm(RoutingDecision(agent="DIRECT"))

        sup = self._make_supervisor(mock_llm)
        result = await sup.route({"query": "Xin chao!", "context": {}, "domain_config": {}})

        assert result == "direct"

    @pytest.mark.asyncio
    async def test_structured_route_tutor(self):
        from app.engine.structured_schemas import RoutingDecision
        mock_llm = _make_structured_llm(RoutingDecision(agent="TUTOR_AGENT"))

        sup = self._make_supervisor(mock_llm)
        result = await sup.route({"query": "Giai thich COLREGs", "context": {}, "domain_config": {}})

        assert result == "tutor_agent"

    @pytest.mark.asyncio
    async def test_structured_route_memory(self):
        from app.engine.structured_schemas import RoutingDecision
        mock_llm = _make_structured_llm(RoutingDecision(agent="MEMORY_AGENT"))

        sup = self._make_supervisor(mock_llm)
        result = await sup.route({"query": "Ten toi la gi?", "context": {}, "domain_config": {}})

        assert result == "memory_agent"

    @pytest.mark.asyncio
    async def test_structured_fallback_on_error(self):
        """If structured output raises, falls back to rule-based."""
        mock_llm = MagicMock()
        mock_err_chain = MagicMock()
        mock_err_chain.ainvoke = AsyncMock(side_effect=Exception("Schema error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_err_chain)

        sup = self._make_supervisor(mock_llm)
        result = await sup.route({"query": "Xin chao", "context": {}, "domain_config": {}})

        # Falls back to rule-based: short greeting -> direct
        assert result == "direct"


# Sprint 103: TestSupervisorLegacyRoute deleted — _route_legacy() removed.
# Supervisor always uses structured routing now.


# =============================================================================
# Grader Agent Structured Output Tests
# =============================================================================


class TestGraderStructuredOutput:
    """Test GraderAgentNode with structured output."""

    def _make_grader(self, mock_llm):
        from app.engine.multi_agent.agents.grader_agent import GraderAgentNode
        grader = GraderAgentNode.__new__(GraderAgentNode)
        grader._llm = mock_llm
        grader._min_score = 6.0
        grader._config = MagicMock(id="grader")
        return grader

    @pytest.mark.asyncio
    async def test_structured_grade(self):
        from app.engine.structured_schemas import QualityGradeResult

        mock_result = QualityGradeResult(
            score=8.5, is_helpful=True, is_accurate=True,
            is_complete=True, feedback="Excellent"
        )
        mock_llm = _make_structured_llm(mock_result)

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            result = await grader._grade_response("What is SOLAS?", "SOLAS is a convention...")

        assert result["score"] == 8.5
        assert result["is_helpful"] is True
        assert result["feedback"] == "Excellent"
        mock_llm.with_structured_output.assert_called_once_with(QualityGradeResult)

    @pytest.mark.asyncio
    async def test_structured_grade_fallback_on_error(self):
        """If structured output fails, falls back to rule-based."""
        mock_llm = MagicMock()
        mock_err_chain = MagicMock()
        mock_err_chain.ainvoke = AsyncMock(side_effect=Exception("Parse error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_err_chain)

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            result = await grader._grade_response("test", "A long answer with enough content to score")

        # Falls back to rule-based
        assert "score" in result
        assert result.get("feedback") == "Rule-based grading"

    @pytest.mark.asyncio
    async def test_legacy_grade_when_disabled(self):
        """When disabled, uses legacy JSON parsing."""
        mock_response = MagicMock()
        mock_response.content = '{"score": 7, "is_helpful": true, "is_accurate": true, "is_complete": true, "feedback": "OK"}'
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=False)):
            result = await grader._grade_response("test", "answer")

        assert result["score"] == 7
        mock_llm.with_structured_output.assert_not_called()


# =============================================================================
# Guardian Agent Structured Output Tests
# =============================================================================


class TestGuardianStructuredOutput:
    """Test Guardian Agent with structured output."""

    def _make_guardian(self, mock_llm):
        from app.engine.guardian_agent import GuardianAgent, GuardianConfig
        agent = GuardianAgent.__new__(GuardianAgent)
        agent._llm = mock_llm
        agent._config = GuardianConfig()
        agent._cache = {}
        agent._fallback = None
        return agent

    @pytest.mark.asyncio
    async def test_structured_allow(self):
        from app.engine.structured_schemas import GuardianLLMResult
        mock_llm = _make_structured_llm(GuardianLLMResult(action="ALLOW", confidence=0.95))

        agent = self._make_guardian(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            decision = await agent._validate_with_llm("Hello there")

        assert decision.action == "ALLOW"
        assert decision.confidence == 0.95
        assert decision.used_llm is True

    @pytest.mark.asyncio
    async def test_structured_block(self):
        from app.engine.structured_schemas import GuardianLLMResult
        mock_llm = _make_structured_llm(GuardianLLMResult(action="BLOCK", reason="Bad words", confidence=0.9))

        agent = self._make_guardian(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            decision = await agent._validate_with_llm("bad message")

        assert decision.action == "BLOCK"
        assert decision.reason == "Bad words"

    @pytest.mark.asyncio
    async def test_structured_with_pronoun(self):
        from app.engine.structured_schemas import GuardianLLMResult, PronounRequestInfo
        mock_llm = _make_structured_llm(GuardianLLMResult(
            action="ALLOW", confidence=0.9,
            pronoun_request=PronounRequestInfo(
                detected=True, appropriate=True,
                user_called="cong chua", ai_self="tram"
            )
        ))

        agent = self._make_guardian(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            decision = await agent._validate_with_llm("Goi toi la cong chua")

        assert decision.action == "ALLOW"
        assert decision.custom_pronouns["user_called"] == "cong chua"
        assert decision.custom_pronouns["ai_self"] == "tram"

    @pytest.mark.asyncio
    async def test_structured_pronoun_not_appropriate(self):
        """Pronoun detected but not appropriate -> no custom_pronouns."""
        from app.engine.structured_schemas import GuardianLLMResult, PronounRequestInfo
        mock_llm = _make_structured_llm(GuardianLLMResult(
            action="ALLOW", confidence=0.8,
            pronoun_request=PronounRequestInfo(detected=True, appropriate=False)
        ))

        agent = self._make_guardian(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            decision = await agent._validate_with_llm("test")

        assert decision.custom_pronouns is None

    @pytest.mark.asyncio
    async def test_structured_fallback_on_error(self):
        """If structured output fails, exception propagates (Guardian re-raises)."""
        mock_llm = MagicMock()
        mock_err_chain = MagicMock()
        mock_err_chain.ainvoke = AsyncMock(side_effect=Exception("Schema error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_err_chain)

        agent = self._make_guardian(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            with pytest.raises(Exception, match="Schema error"):
                await agent._validate_with_llm("test")


# =============================================================================
# RetrievalGrader Structured Output Tests
# =============================================================================


class TestRetrievalGraderStructuredSingle:
    """Test RetrievalGrader single doc with structured output."""

    def _make_grader(self, mock_llm):
        from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = mock_llm
        grader._threshold = 6.0
        return grader

    @pytest.mark.asyncio
    async def test_structured_single_grade(self):
        from app.engine.structured_schemas import SingleDocGrade
        mock_llm = _make_structured_llm(SingleDocGrade(score=8.0, is_relevant=True, reason="Truc tiep tra loi"))

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grade = await grader.grade_document(
                "SOLAS Chapter V?",
                {"id": "doc1", "content": "SOLAS Chapter V covers navigation"}
            )

        assert grade.score == 8.0
        assert grade.is_relevant is True
        assert grade.reason == "Truc tiep tra loi"
        mock_llm.with_structured_output.assert_called_once_with(SingleDocGrade)

    @pytest.mark.asyncio
    async def test_structured_single_grade_low_score(self):
        from app.engine.structured_schemas import SingleDocGrade
        mock_llm = _make_structured_llm(SingleDocGrade(score=3.0, is_relevant=False, reason="Khong lien quan"))

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grade = await grader.grade_document("test", {"id": "doc1", "content": "unrelated"})

        assert grade.score == 3.0
        assert grade.is_relevant is False

    @pytest.mark.asyncio
    async def test_structured_single_fallback_on_error(self):
        """If structured fails, falls back to rule-based."""
        mock_llm = MagicMock()
        mock_err_chain = MagicMock()
        mock_err_chain.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_err_chain)

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grade = await grader.grade_document("SOLAS", {"id": "doc1", "content": "SOLAS text"})

        # Falls back to rule-based keyword matching
        assert grade.document_id == "doc1"
        assert "Keyword overlap" in grade.reason


class TestRetrievalGraderStructuredBatch:
    """Test RetrievalGrader batch with structured output."""

    def _make_grader(self, mock_llm):
        from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = mock_llm
        grader._threshold = 6.0
        return grader

    @pytest.mark.asyncio
    async def test_structured_batch_grade(self):
        from app.engine.structured_schemas import BatchDocGrades, BatchDocGradeItem

        mock_result = BatchDocGrades(grades=[
            BatchDocGradeItem(doc_index=0, score=9.0, is_relevant=True, reason="Excellent"),
            BatchDocGradeItem(doc_index=1, score=2.0, is_relevant=False, reason="Off topic"),
        ])
        mock_llm = _make_structured_llm(mock_result)

        docs = [
            {"id": "d1", "content": "SOLAS Chapter V navigation"},
            {"id": "d2", "content": "Random cooking recipe"},
        ]

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grades = await grader.batch_grade_documents("SOLAS?", docs)

        assert len(grades) == 2
        assert grades[0].score == 9.0
        assert grades[0].is_relevant is True
        assert grades[1].score == 2.0
        assert grades[1].is_relevant is False
        mock_llm.with_structured_output.assert_called_once_with(BatchDocGrades)

    @pytest.mark.asyncio
    async def test_structured_batch_out_of_range_index(self):
        """Doc index out of range is safely skipped."""
        from app.engine.structured_schemas import BatchDocGrades, BatchDocGradeItem

        mock_result = BatchDocGrades(grades=[
            BatchDocGradeItem(doc_index=0, score=7.0, is_relevant=True, reason="OK"),
            BatchDocGradeItem(doc_index=99, score=5.0, is_relevant=False, reason="Ghost"),
        ])
        mock_llm = _make_structured_llm(mock_result)

        docs = [{"id": "d1", "content": "Only one doc"}]

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grades = await grader.batch_grade_documents("test", docs)

        # Only index 0 is valid
        assert len(grades) == 1
        assert grades[0].score == 7.0

    @pytest.mark.asyncio
    async def test_structured_batch_fallback_on_error(self):
        """If structured batch fails, falls back to sequential."""
        mock_llm = MagicMock()
        mock_err_chain = MagicMock()
        mock_err_chain.ainvoke = AsyncMock(side_effect=Exception("Batch error"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_err_chain)
        # Sequential fallback needs ainvoke for legacy path
        mock_response = MagicMock()
        mock_response.content = '{"score": 5, "is_relevant": false, "reason": "fallback"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        docs = [{"id": "d1", "content": "some content"}]

        grader = self._make_grader(mock_llm)
        with patch("app.core.config.settings", _make_mock_settings(enable_structured=True)):
            grades = await grader.batch_grade_documents("test", docs)

        # Falls back to sequential
        assert len(grades) == 1


class TestRetrievalGraderLegacy:
    """Test RetrievalGrader legacy path when structured disabled."""

    @pytest.mark.asyncio
    async def test_legacy_single_grade(self):
        mock_response = MagicMock()
        mock_response.content = '{"score": 7, "is_relevant": true, "reason": "Good match"}'
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = mock_llm
        grader._threshold = 6.0

        with patch("app.core.config.settings", _make_mock_settings(enable_structured=False)):
            grade = await grader.grade_document("test", {"id": "d1", "content": "content"})

        assert grade.score == 7.0
        assert grade.is_relevant is True
        mock_llm.with_structured_output.assert_not_called()


# =============================================================================
# Feature Gate Integration Tests
# =============================================================================


class TestFeatureGateIntegration:
    """Test that feature gate properly switches between paths."""

    # Sprint 103: test_supervisor_disabled_uses_legacy deleted — legacy path removed.

    @pytest.mark.asyncio
    async def test_grader_disabled_uses_legacy(self):
        mock_response = MagicMock()
        mock_response.content = '{"score": 6, "is_helpful": true, "is_accurate": true, "is_complete": false, "feedback": "Can them"}'
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        from app.engine.multi_agent.agents.grader_agent import GraderAgentNode
        grader = GraderAgentNode.__new__(GraderAgentNode)
        grader._llm = mock_llm
        grader._min_score = 6.0
        grader._config = MagicMock(id="grader")

        with patch("app.core.config.settings", _make_mock_settings(enable_structured=False)):
            result = await grader._grade_response("q", "answer")

        assert result["score"] == 6
        mock_llm.with_structured_output.assert_not_called()
