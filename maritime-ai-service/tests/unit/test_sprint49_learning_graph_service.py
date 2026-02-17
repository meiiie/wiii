"""
Tests for Sprint 49: LearningGraphService coverage.

Tests learning graph orchestration including:
- __init__ (default repos, custom repos)
- is_available (True/False)
- record_study_session (success, unavailable, error)
- mark_module_completed (success, unavailable)
- detect_and_record_weakness (success, unavailable, error)
- add_module_prerequisite (success, unavailable)
- get_user_learning_context (success, unavailable, error)
- Singleton
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# Helpers
# ============================================================================


def _make_service(graph_available=True):
    """Create LearningGraphService with mocked deps."""
    from app.services.learning_graph_service import LearningGraphService

    mock_graph = MagicMock()
    mock_graph.is_available.return_value = graph_available
    mock_semantic = MagicMock()
    return LearningGraphService(user_graph=mock_graph, semantic_repo=mock_semantic)


# ============================================================================
# __init__
# ============================================================================


class TestInit:
    """Test initialization."""

    def test_custom_repos(self):
        from app.services.learning_graph_service import LearningGraphService

        mock_g = MagicMock()
        mock_s = MagicMock()
        svc = LearningGraphService(user_graph=mock_g, semantic_repo=mock_s)
        assert svc._user_graph is mock_g
        assert svc._semantic_repo is mock_s

    def test_default_repos(self):
        from app.services.learning_graph_service import LearningGraphService

        with patch("app.services.learning_graph_service.get_user_graph_repository") as mock_ugr, \
             patch("app.services.learning_graph_service.get_semantic_memory_repository") as mock_smr:
            mock_ugr.return_value = MagicMock()
            mock_smr.return_value = MagicMock()
            svc = LearningGraphService()
            mock_ugr.assert_called_once()
            mock_smr.assert_called_once()


# ============================================================================
# is_available
# ============================================================================


class TestIsAvailable:
    """Test availability check."""

    def test_available(self):
        svc = _make_service(graph_available=True)
        assert svc.is_available() is True

    def test_not_available(self):
        svc = _make_service(graph_available=False)
        assert svc.is_available() is False


# ============================================================================
# record_study_session
# ============================================================================


class TestRecordStudySession:
    """Test study session recording."""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        svc._user_graph.ensure_module_node.return_value = None
        svc._user_graph.mark_studied.return_value = True

        result = await svc.record_study_session("u1", "mod1", "COLREGs Basics", 0.5)
        assert result is True
        svc._user_graph.ensure_module_node.assert_called_once_with(
            module_id="mod1", title="COLREGs Basics"
        )
        svc._user_graph.mark_studied.assert_called_once_with(
            user_id="u1", module_id="mod1", progress=0.5
        )

    @pytest.mark.asyncio
    async def test_unavailable(self):
        svc = _make_service(graph_available=False)
        result = await svc.record_study_session("u1", "mod1", "Title")
        assert result is False

    @pytest.mark.asyncio
    async def test_error(self):
        svc = _make_service()
        svc._user_graph.ensure_module_node.side_effect = Exception("Neo4j down")
        result = await svc.record_study_session("u1", "mod1", "Title")
        assert result is False


# ============================================================================
# mark_module_completed
# ============================================================================


class TestMarkModuleCompleted:
    """Test module completion."""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        svc._user_graph.mark_completed.return_value = True
        result = await svc.mark_module_completed("u1", "mod1")
        assert result is True

    @pytest.mark.asyncio
    async def test_unavailable(self):
        svc = _make_service(graph_available=False)
        result = await svc.mark_module_completed("u1", "mod1")
        assert result is False


# ============================================================================
# detect_and_record_weakness
# ============================================================================


class TestDetectAndRecordWeakness:
    """Test weakness recording."""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        svc._user_graph.ensure_topic_node.return_value = None
        svc._user_graph.mark_weak_at.return_value = True

        result = await svc.detect_and_record_weakness(
            "u1", "colregs_rule_15", "Rule 15", confidence=0.7
        )
        assert result is True
        svc._user_graph.ensure_topic_node.assert_called_once_with(
            topic_id="colregs_rule_15", name="Rule 15"
        )

    @pytest.mark.asyncio
    async def test_unavailable(self):
        svc = _make_service(graph_available=False)
        result = await svc.detect_and_record_weakness("u1", "t1", "Topic")
        assert result is False

    @pytest.mark.asyncio
    async def test_error(self):
        svc = _make_service()
        svc._user_graph.ensure_topic_node.side_effect = Exception("DB error")
        result = await svc.detect_and_record_weakness("u1", "t1", "Topic")
        assert result is False


# ============================================================================
# add_module_prerequisite
# ============================================================================


class TestAddModulePrerequisite:
    """Test prerequisite creation."""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        svc._user_graph.add_prerequisite.return_value = True
        result = await svc.add_module_prerequisite("mod2", "mod1")
        assert result is True

    @pytest.mark.asyncio
    async def test_unavailable(self):
        svc = _make_service(graph_available=False)
        result = await svc.add_module_prerequisite("mod2", "mod1")
        assert result is False


# ============================================================================
# get_user_learning_context
# ============================================================================


class TestGetUserLearningContext:
    """Test learning context retrieval."""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        svc._user_graph.get_learning_path.return_value = [
            {"module_id": "mod1", "title": "Basics", "progress": 0.5}
        ]
        svc._user_graph.get_knowledge_gaps.return_value = [
            {"topic_name": "Rule 15", "confidence": 0.3}
        ]

        ctx = await svc.get_user_learning_context("u1")
        assert len(ctx["learning_path"]) == 1
        assert len(ctx["knowledge_gaps"]) == 1
        assert len(ctx["recommendations"]) == 1
        assert "Rule 15" in ctx["recommendations"][0]

    @pytest.mark.asyncio
    async def test_unavailable(self):
        svc = _make_service(graph_available=False)
        ctx = await svc.get_user_learning_context("u1")
        assert ctx["learning_path"] == []
        assert ctx["knowledge_gaps"] == []
        assert ctx["recommendations"] == []

    @pytest.mark.asyncio
    async def test_error(self):
        svc = _make_service()
        svc._user_graph.get_learning_path.side_effect = Exception("Neo4j down")
        ctx = await svc.get_user_learning_context("u1")
        # Should not crash, returns empty context
        assert ctx["learning_path"] == []

    @pytest.mark.asyncio
    async def test_no_gaps_no_recommendations(self):
        svc = _make_service()
        svc._user_graph.get_learning_path.return_value = []
        svc._user_graph.get_knowledge_gaps.return_value = []

        ctx = await svc.get_user_learning_context("u1")
        assert ctx["recommendations"] == []


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_learning_graph_service(self):
        import app.services.learning_graph_service as mod
        mod._learning_graph_service = None

        with patch("app.services.learning_graph_service.get_user_graph_repository") as mock_ugr, \
             patch("app.services.learning_graph_service.get_semantic_memory_repository") as mock_smr:
            mock_ugr.return_value = MagicMock()
            mock_smr.return_value = MagicMock()
            s1 = mod.get_learning_graph_service()
            s2 = mod.get_learning_graph_service()
            assert s1 is s2

        mod._learning_graph_service = None  # Cleanup
