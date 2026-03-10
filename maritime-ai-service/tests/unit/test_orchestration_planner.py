"""Tests for capability-aware parallel orchestration planning."""

from unittest.mock import MagicMock, patch

from app.engine.skills.skill_handbook import SkillHandbookEntry


def _entry(
    tool_name: str,
    selector_category: str,
    capability_path: tuple[str, ...],
    *,
    competence: float = 0.7,
    latency: float = 300.0,
    cost: float = 0.0,
):
    return SkillHandbookEntry(
        tool_name=tool_name,
        skill_domain=None,
        selector_category=selector_category,
        capability_path=capability_path,
        description="test",
        tags=tuple(),
        competence_score=competence,
        avg_latency_ms=latency,
        avg_cost_usd=cost,
    )


class TestParallelTargetPlanner:
    @patch("app.engine.multi_agent.orchestration_planner.get_skill_handbook")
    def test_learning_query_pairs_tutor_with_rag(self, mock_get_handbook):
        from app.engine.multi_agent.orchestration_planner import plan_parallel_targets

        mock_get_handbook.return_value = MagicMock(
            suggest_for_query=MagicMock(
                return_value=[
                    _entry("tool_knowledge_search", "rag", ("knowledge", "retrieval")),
                    _entry("tool_start_lesson", "learning", ("learning", "teaching")),
                ]
            )
        )

        targets = plan_parallel_targets(
            "Giải thích quy tắc 13 và cho ví dụ dễ hiểu",
            "tutor_agent",
            intent="learning",
        )

        assert targets == ["tutor", "rag"]

    @patch("app.engine.multi_agent.orchestration_planner.get_skill_handbook")
    def test_product_search_query_pairs_search_with_rag(self, mock_get_handbook):
        from app.engine.multi_agent.orchestration_planner import plan_parallel_targets

        mock_get_handbook.return_value = MagicMock(
            suggest_for_query=MagicMock(
                return_value=[
                    _entry("tool_search_websosanh", "product_search", ("commerce", "comparison")),
                    _entry("tool_knowledge_search", "rag", ("knowledge", "retrieval")),
                ]
            )
        )

        targets = plan_parallel_targets(
            "Tìm iPhone 17 Pro Max rẻ nhất rồi phân tích nguồn nào đáng tin nhất",
            "product_search_agent",
            intent="product_search",
        )

        assert targets == ["search", "rag"]

    def test_unknown_primary_agent_returns_empty(self):
        from app.engine.multi_agent.orchestration_planner import plan_parallel_targets

        assert plan_parallel_targets("test", "direct", intent="social") == []
