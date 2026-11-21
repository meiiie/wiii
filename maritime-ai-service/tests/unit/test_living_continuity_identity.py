import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    _make_settings,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestIdentityCoreOrgScope:
    """Test org-scoped identity insight cache guardrails."""

    def test_identity_context_filters_by_org_context(self, monkeypatch):
        """Hot-path identity context only exposes current-org insights."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.identity_core import IdentityCore
        from app.engine.living_agent.models import IdentityInsight

        core = IdentityCore()
        core._insights = [
            IdentityInsight(text="Org A identity", validated=True, organization_id="org-A"),
            IdentityInsight(text="Org B identity", validated=True, organization_id="org-B"),
            IdentityInsight(text="Legacy identity", validated=True),
        ]
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        app_settings = _make_settings(
            enable_living_agent=True,
            enable_identity_core=True,
            enable_multi_tenant=True,
            environment="production",
            default_organization_id="default",
        )

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.config.get_settings", return_value=app_settings):
                context = core.get_identity_context()
        finally:
            current_org_id.reset(token)

        assert "Org A identity" in context
        assert "Org B identity" not in context
        assert "Legacy identity" not in context

    @pytest.mark.asyncio
    async def test_identity_generation_blocks_missing_org_before_reflection_or_llm(
        self,
        monkeypatch,
        caplog,
    ):
        """Identity generation fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.identity_core import IdentityCore

        core = IdentityCore()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        app_settings = _make_settings(
            enable_living_agent=True,
            enable_identity_core=True,
            enable_multi_tenant=True,
            environment="production",
            default_organization_id="default",
        )
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.config.get_settings", return_value=app_settings), \
                 patch("app.engine.living_agent.reflector.get_reflector") as mock_reflector, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                insights = await core.generate_self_insights()
        finally:
            current_org_id.reset(token)

        assert insights == []
        mock_reflector.assert_not_called()
        mock_llm.assert_not_called()
        assert "identity_core_blocked_missing_org_context" in caplog.text

    @pytest.mark.asyncio
    async def test_identity_generation_tags_insights_with_org(self, monkeypatch):
        """Cold-path identity insights are generated and cached for one org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.identity_core import IdentityCore

        core = IdentityCore()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        app_settings = _make_settings(
            enable_living_agent=True,
            enable_identity_core=True,
            enable_multi_tenant=True,
            environment="production",
            default_organization_id="default",
        )
        soul = MagicMock()
        soul.core_truths = []
        soul.boundaries = []

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.config.get_settings", return_value=app_settings), \
                 patch.object(core, "_get_recent_reflection_text", new_callable=AsyncMock, return_value="Reflection") as mock_reflection, \
                 patch.object(core, "_get_skills_summary", return_value="Skills") as mock_skills, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm, \
                 patch("app.engine.living_agent.soul_loader.get_soul", return_value=soul):
                mock_llm.return_value.generate = AsyncMock(return_value="- Minh hoc nhanh hon")
                insights = await core.generate_self_insights()
        finally:
            current_org_id.reset(token)

        assert len(insights) == 1
        assert insights[0].organization_id == "org-A"
        assert core.get_all_insights("org-A")[0].organization_id == "org-A"
        mock_reflection.assert_awaited_once_with("org-A")
        mock_skills.assert_called_once_with("org-A")
