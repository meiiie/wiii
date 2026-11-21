import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestSkillBuilderOrgScope:
    """Test org-scoped autonomous skill-learning guardrails."""

    def test_skill_discover_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Skill discovery fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.skill_builder import SkillBuilder

        builder = SkillBuilder()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                skill = builder.discover(
                    "PRIVATE SKILL TOPIC",
                    domain="private",
                    source="https://example.invalid/private",
                )
        finally:
            current_org_id.reset(token)

        assert skill is None
        mock_factory.assert_not_called()
        assert "skill_builder_blocked_missing_org_context" in caplog.text
        assert "PRIVATE SKILL TOPIC" not in caplog.text

    def test_skill_query_filters_by_org_context(self, monkeypatch):
        """Skill list reads only query the current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.models import SkillStatus
        from app.engine.living_agent.skill_builder import SkillBuilder

        builder = SkillBuilder()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        row = (
            uuid4(),
            "Org A Skill",
            "maritime",
            SkillStatus.LEARNING.value,
            0.4,
            "notes",
            json.dumps(["https://example.invalid"]),
            1,
            0.8,
            datetime.now(timezone.utc),
            None,
            None,
            "org-A",
            json.dumps({"review_schedule": {"interval_days": 1}}),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [row]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                skills = builder.get_all_skills(status=SkillStatus.LEARNING, domain="maritime")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert len(skills) == 1
        assert skills[0].organization_id == "org-A"
        assert skills[0].metadata["review_schedule"]["interval_days"] == 1
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_skill_update_filters_by_org_context(self, monkeypatch):
        """Skill lifecycle updates cannot mutate another org's row id."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.models import WiiiSkill
        from app.engine.living_agent.skill_builder import SkillBuilder

        builder = SkillBuilder()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        skill = WiiiSkill(
            skill_name="PRIVATE SKILL TOPIC",
            notes="private notes",
            metadata={"review_schedule": {"interval_days": 1}},
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                builder._update_skill(skill)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert params["meta"] == json.dumps(skill.metadata, ensure_ascii=False)

    def test_skill_metadata_update_filters_by_org_context(self, monkeypatch):
        """Metadata-only writes keep the same org boundary as lifecycle writes."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.models import WiiiSkill
        from app.engine.living_agent.skill_builder import SkillBuilder

        builder = SkillBuilder()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        skill = WiiiSkill(
            skill_name="PRIVATE SKILL TOPIC",
            metadata={"learning_materials": [{"url": "https://example.invalid/private"}]},
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                builder.update_skill_metadata(skill)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_skill_learn_step_blocks_missing_org_before_llm(
        self,
        monkeypatch,
        caplog,
    ):
        """Learning steps fail closed before DB reads or local LLM calls."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.skill_builder import SkillBuilder

        builder = SkillBuilder()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                learned = await builder.learn_step("PRIVATE SKILL TOPIC")
        finally:
            current_org_id.reset(token)

        assert learned is False
        mock_factory.assert_not_called()
        mock_llm.assert_not_called()
        assert "skill_builder_blocked_missing_org_context" in caplog.text
        assert "PRIVATE SKILL TOPIC" not in caplog.text
