"""
Sprint 161: "Không Gian Riêng" — Org-Level Customization Tests.

Tests cover:
- OrgSettings Pydantic schema validation + defaults
- deep_merge() utility
- get_effective_settings() resolution with feature gate
- get_org_permissions() per-role
- has_permission() checks
- is_agent_visible() / is_feature_enabled()
- Persona prompt overlay injection
- Settings API endpoints (GET/PATCH settings, GET permissions)
"""

import copy
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ============================================================================
# Helpers
# ============================================================================

def _make_settings(**overrides):
    """Create a mock settings object with sensible defaults."""
    s = MagicMock()
    s.enable_multi_tenant = overrides.get("enable_multi_tenant", False)
    s.default_organization_id = overrides.get("default_organization_id", "default")
    return s


def _patch_settings(enable_multi_tenant=False):
    """Patch app.core.config.settings which org_settings imports lazily."""
    return patch(
        "app.core.config.settings",
        _make_settings(enable_multi_tenant=enable_multi_tenant),
    )


def _mock_org(settings_dict=None):
    """Create a mock organization with optional settings JSONB."""
    org = MagicMock()
    org.settings = settings_dict
    org.id = "test-org"
    return org


def _mock_repo(org=None):
    """Create a mock organization repository."""
    repo = MagicMock()
    repo.get_organization.return_value = org
    repo.is_user_in_org.return_value = True
    repo.update_organization.return_value = org
    return repo


# ============================================================================
# Group 1: OrgSettings Pydantic Schema (6 tests)
# ============================================================================

class TestOrgSettingsSchema:
    """Tests for OrgSettings Pydantic models in organization.py."""

    def test_org_settings_defaults(self):
        """OrgSettings() returns Wiii platform defaults."""
        from app.models.organization import OrgSettings
        s = OrgSettings()
        assert s.schema_version == 1
        assert s.branding.chatbot_name == "Wiii"
        assert s.branding.primary_color == "#AE5630"
        assert s.branding.accent_color == "#C4633A"
        assert s.branding.welcome_message == "Xin chào! Mình là Wiii"
        assert s.branding.institution_type == "general"

    def test_org_feature_flags_defaults(self):
        """Feature flags default to disabled (zero-footprint)."""
        from app.models.organization import OrgFeatureFlags
        f = OrgFeatureFlags()
        assert f.enable_product_search is False
        assert f.enable_deep_scanning is False
        assert f.enable_thinking_chain is False
        assert f.enable_browser_scraping is False
        assert f.max_search_iterations == 5
        assert "rag" in f.visible_agents
        assert "tutor" in f.visible_agents

    def test_org_permissions_defaults(self):
        """Permission defaults follow principle of least privilege."""
        from app.models.organization import OrgPermissions
        p = OrgPermissions()
        assert "read:chat" in p.student
        assert "manage:settings" not in p.student
        assert "manage:settings" in p.admin
        assert "read:analytics" in p.teacher
        assert "manage:members" in p.admin

    def test_org_ai_config_defaults(self):
        """AI config defaults to None (no overrides)."""
        from app.models.organization import OrgAIConfig
        c = OrgAIConfig()
        assert c.persona_prompt_overlay is None
        assert c.temperature_override is None
        assert c.max_response_length is None
        assert c.default_domain is None

    def test_org_onboarding_defaults(self):
        """Onboarding defaults to empty quick-start + show domain suggestions."""
        from app.models.organization import OrgOnboarding
        o = OrgOnboarding()
        assert o.quick_start_questions == []
        assert o.show_domain_suggestions is True

    def test_org_settings_custom_values(self):
        """OrgSettings accepts custom values via dict."""
        from app.models.organization import OrgSettings
        s = OrgSettings(**{
            "branding": {
                "chatbot_name": "Hải Bot",
                "primary_color": "#003366",
                "institution_type": "university",
            },
            "features": {
                "enable_product_search": True,
                "visible_agents": ["rag", "tutor", "direct"],
            },
            "ai_config": {
                "persona_prompt_overlay": "Bạn là trợ lý của Đại học Hàng hải",
            },
        })
        assert s.branding.chatbot_name == "Hải Bot"
        assert s.branding.primary_color == "#003366"
        assert s.features.enable_product_search is True
        assert "memory" not in s.features.visible_agents
        assert s.ai_config.persona_prompt_overlay == "Bạn là trợ lý của Đại học Hàng hải"
        # Defaults preserved for unspecified fields
        assert s.branding.accent_color == "#C4633A"
        assert s.permissions.student == ["read:chat", "read:knowledge", "use:tools"]


# ============================================================================
# Group 2: deep_merge() utility (5 tests)
# ============================================================================

class TestDeepMerge:
    """Tests for deep_merge() in org_settings.py."""

    def test_empty_overlay(self):
        """Empty overlay returns base unchanged."""
        from app.core.org_settings import deep_merge
        base = {"a": 1, "b": {"c": 2}}
        result = deep_merge(base, {})
        assert result == base

    def test_shallow_override(self):
        """Overlay value replaces base value at same key."""
        from app.core.org_settings import deep_merge
        base = {"color": "red", "size": 10}
        overlay = {"color": "blue"}
        result = deep_merge(base, overlay)
        assert result["color"] == "blue"
        assert result["size"] == 10

    def test_nested_merge(self):
        """Nested dicts are merged recursively."""
        from app.core.org_settings import deep_merge
        base = {"branding": {"name": "Wiii", "color": "#AE5630"}, "version": 1}
        overlay = {"branding": {"name": "Hải Bot"}}
        result = deep_merge(base, overlay)
        assert result["branding"]["name"] == "Hải Bot"
        assert result["branding"]["color"] == "#AE5630"
        assert result["version"] == 1

    def test_overlay_adds_new_keys(self):
        """Overlay can add keys not present in base."""
        from app.core.org_settings import deep_merge
        base = {"a": 1}
        overlay = {"b": 2, "c": {"d": 3}}
        result = deep_merge(base, overlay)
        assert result["b"] == 2
        assert result["c"]["d"] == 3

    def test_no_mutation_of_originals(self):
        """deep_merge does not mutate base or overlay."""
        from app.core.org_settings import deep_merge
        base = {"nested": {"x": 1}}
        overlay = {"nested": {"y": 2}}
        base_copy = copy.deepcopy(base)
        overlay_copy = copy.deepcopy(overlay)
        deep_merge(base, overlay)
        assert base == base_copy
        assert overlay == overlay_copy


# ============================================================================
# Group 3: get_effective_settings() (5 tests)
# ============================================================================

class TestGetEffectiveSettings:
    """Tests for settings resolution with feature gate."""

    def test_disabled_returns_defaults(self):
        """When multi-tenant disabled, returns PLATFORM_DEFAULTS."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import get_effective_settings, PLATFORM_DEFAULTS
            result = get_effective_settings("any-org")
            assert result.branding.chatbot_name == PLATFORM_DEFAULTS.branding.chatbot_name

    def test_none_org_returns_defaults(self):
        """When org_id is None, returns PLATFORM_DEFAULTS."""
        with _patch_settings(enable_multi_tenant=True):
            from app.core.org_settings import get_effective_settings, PLATFORM_DEFAULTS
            result = get_effective_settings(None)
            assert result == PLATFORM_DEFAULTS

    def test_org_not_found_returns_defaults(self):
        """When org doesn't exist in DB, returns PLATFORM_DEFAULTS."""
        with _patch_settings(enable_multi_tenant=True):
            mock_repo = _mock_repo(org=None)
            with patch(
                "app.repositories.organization_repository.get_organization_repository",
                return_value=mock_repo,
            ):
                from app.core.org_settings import get_effective_settings, PLATFORM_DEFAULTS
                result = get_effective_settings("nonexistent")
                assert result.branding.chatbot_name == PLATFORM_DEFAULTS.branding.chatbot_name

    def test_org_with_settings_merges(self):
        """Org settings are deep-merged with platform defaults."""
        with _patch_settings(enable_multi_tenant=True):
            org = _mock_org(settings_dict={
                "branding": {"chatbot_name": "Phường Bot", "institution_type": "government"},
            })
            mock_repo = _mock_repo(org=org)
            with patch(
                "app.repositories.organization_repository.get_organization_repository",
                return_value=mock_repo,
            ):
                from app.core.org_settings import get_effective_settings
                result = get_effective_settings("phuong-luu-kiem")
                assert result.branding.chatbot_name == "Phường Bot"
                assert result.branding.institution_type == "government"
                # Defaults preserved
                assert result.branding.primary_color == "#AE5630"
                assert result.features.enable_product_search is False

    def test_exception_returns_defaults(self):
        """When repo throws, returns PLATFORM_DEFAULTS gracefully."""
        with _patch_settings(enable_multi_tenant=True):
            with patch(
                "app.repositories.organization_repository.get_organization_repository",
                side_effect=Exception("DB down"),
            ):
                from app.core.org_settings import get_effective_settings, PLATFORM_DEFAULTS
                result = get_effective_settings("any-org")
                assert result == PLATFORM_DEFAULTS


# ============================================================================
# Group 4: Permissions helpers (6 tests)
# ============================================================================

class TestPermissions:
    """Tests for permission resolution functions."""

    def test_student_permissions(self):
        """Student gets basic read + use permissions."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import get_org_permissions
            perms = get_org_permissions(None, "student")
            assert "read:chat" in perms
            assert "use:tools" in perms
            assert "manage:settings" not in perms

    def test_teacher_permissions(self):
        """Teacher gets analytics + courses on top of student."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import get_org_permissions
            perms = get_org_permissions(None, "teacher")
            assert "read:analytics" in perms
            assert "manage:courses" in perms
            assert "manage:settings" not in perms

    def test_admin_permissions(self):
        """Admin gets all permissions including manage:settings."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import get_org_permissions
            perms = get_org_permissions(None, "admin")
            assert "manage:settings" in perms
            assert "manage:members" in perms
            assert "manage:branding" in perms

    def test_unknown_role_defaults_to_student(self):
        """Unknown role falls back to student permissions."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import get_org_permissions
            perms = get_org_permissions(None, "alien")
            assert perms == get_org_permissions(None, "student")

    def test_has_permission_true(self):
        """has_permission returns True for valid admin permission."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import has_permission
            assert has_permission(None, "admin", "manage", "settings") is True

    def test_has_permission_false(self):
        """has_permission returns False for student managing settings."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import has_permission
            assert has_permission(None, "student", "manage", "settings") is False


# ============================================================================
# Group 5: Agent/Feature visibility (4 tests)
# ============================================================================

class TestAgentVisibility:
    """Tests for is_agent_visible() and is_feature_enabled()."""

    def test_default_visible_agents(self):
        """Default config shows rag, tutor, direct, memory."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import is_agent_visible
            assert is_agent_visible(None, "rag") is True
            assert is_agent_visible(None, "tutor") is True
            assert is_agent_visible(None, "direct") is True
            assert is_agent_visible(None, "memory") is True

    def test_product_search_hidden_by_default(self):
        """product_search_agent is NOT in default visible_agents."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import is_agent_visible
            assert is_agent_visible(None, "product_search_agent") is False

    def test_feature_disabled_by_default(self):
        """enable_product_search defaults to False."""
        with _patch_settings(enable_multi_tenant=False):
            from app.core.org_settings import is_feature_enabled
            assert is_feature_enabled(None, "enable_product_search") is False

    def test_feature_enabled_with_org_override(self):
        """Org can enable features via settings."""
        with _patch_settings(enable_multi_tenant=True):
            org = _mock_org(settings_dict={
                "features": {"enable_product_search": True},
            })
            mock_repo = _mock_repo(org=org)
            with patch(
                "app.repositories.organization_repository.get_organization_repository",
                return_value=mock_repo,
            ):
                from app.core.org_settings import is_feature_enabled
                assert is_feature_enabled("test-org", "enable_product_search") is True


# ============================================================================
# Group 6: Persona Prompt Overlay (4 tests)
# ============================================================================

class TestPersonaOverlay:
    """Tests for org persona overlay injection into system prompt."""

    def _build_prompt(self, org_id=None, org_settings=None):
        """Helper to build system prompt with optional org context."""
        from app.prompts.prompt_loader import PromptLoader

        pronoun = {"user_called": "bạn", "ai_self": "tôi"}

        # Mock get_effective_settings if org_settings provided
        if org_settings:
            with patch("app.core.org_settings.get_effective_settings", return_value=org_settings):
                loader = PromptLoader()
                return loader.build_system_prompt(
                    role="student",
                    user_name="Test",
                    pronoun_style=pronoun,
                    organization_id=org_id,
                )
        else:
            loader = PromptLoader()
            return loader.build_system_prompt(
                role="student",
                user_name="Test",
                pronoun_style=pronoun,
            )

    def test_no_org_id_no_overlay(self):
        """Without org_id, no org sections appear."""
        prompt = self._build_prompt()
        assert "HƯỚNG DẪN TỔ CHỨC" not in prompt
        assert "TÊN HIỂN THỊ" not in prompt

    def test_org_with_custom_chatbot_name(self):
        """Org with custom chatbot_name gets TÊN HIỂN THỊ section."""
        from app.models.organization import OrgSettings
        settings = OrgSettings(**{
            "branding": {"chatbot_name": "Hải Bot"},
        })
        prompt = self._build_prompt(org_id="test-org", org_settings=settings)
        assert "TÊN HIỂN THỊ" in prompt
        assert "Hải Bot" in prompt

    def test_org_with_persona_overlay(self):
        """Org with persona_prompt_overlay gets HƯỚNG DẪN TỔ CHỨC section."""
        from app.models.organization import OrgSettings
        settings = OrgSettings(**{
            "ai_config": {
                "persona_prompt_overlay": "Bạn là trợ lý AI của UBND Phường Lưu Kiếm.",
            },
        })
        prompt = self._build_prompt(org_id="phuong-luu-kiem", org_settings=settings)
        assert "HƯỚNG DẪN TỔ CHỨC" in prompt
        assert "Phường Lưu Kiếm" in prompt

    def test_default_chatbot_name_no_display_section(self):
        """Org keeping 'Wiii' chatbot name doesn't get TÊN HIỂN THỊ section."""
        from app.models.organization import OrgSettings
        settings = OrgSettings()  # All defaults
        prompt = self._build_prompt(org_id="test-org", org_settings=settings)
        assert "TÊN HIỂN THỊ" not in prompt


# ============================================================================
# Group 7: Settings API endpoints (7 tests)
# ============================================================================

class TestSettingsAPI:
    """Tests for org settings REST endpoints."""

    def _make_auth(self, role="admin", user_id="user-1"):
        """Create mock AuthenticatedUser."""
        auth = MagicMock()
        auth.role = role
        auth.user_id = user_id
        return auth

    def _patch_api_settings(self, enable_multi_tenant=True):
        """Patch the settings reference inside organizations.py (module-level import)."""
        return patch(
            "app.api.v1.organizations.settings",
            _make_settings(enable_multi_tenant=enable_multi_tenant),
        )

    @pytest.mark.asyncio
    async def test_get_settings_returns_effective(self):
        """GET /{org_id}/settings returns merged settings."""
        from app.api.v1.organizations import get_org_settings
        from app.models.organization import OrgSettings

        auth = self._make_auth()
        org = _mock_org(settings_dict={"branding": {"chatbot_name": "Test Bot"}})
        mock_repo = _mock_repo(org=org)

        with self._patch_api_settings(enable_multi_tenant=True):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                effective = OrgSettings(**{"branding": {"chatbot_name": "Test Bot"}})
                with patch("app.core.org_settings.get_effective_settings", return_value=effective):
                    request = MagicMock()
                    result = await get_org_settings(request, "test-org", auth)
                    assert result["branding"]["chatbot_name"] == "Test Bot"

    @pytest.mark.asyncio
    async def test_get_settings_404_when_disabled(self):
        """GET settings returns 404 when multi-tenant disabled."""
        from app.api.v1.organizations import get_org_settings
        from fastapi import HTTPException

        auth = self._make_auth()
        with self._patch_api_settings(enable_multi_tenant=False):
            request = MagicMock()
            with pytest.raises(HTTPException) as exc:
                await get_org_settings(request, "test-org", auth)
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_settings_403_non_member(self):
        """GET settings returns 403 for non-member non-admin."""
        from app.api.v1.organizations import get_org_settings
        from fastapi import HTTPException

        auth = self._make_auth(role="student")
        org = _mock_org()
        mock_repo = _mock_repo(org=org)
        mock_repo.is_user_in_org.return_value = False

        with self._patch_api_settings(enable_multi_tenant=True):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                request = MagicMock()
                with pytest.raises(HTTPException) as exc:
                    await get_org_settings(request, "test-org", auth)
                assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_settings_admin_only(self):
        """PATCH settings returns 403 for non-admin."""
        from app.api.v1.organizations import update_org_settings
        from fastapi import HTTPException

        auth = self._make_auth(role="student")
        with self._patch_api_settings(enable_multi_tenant=True):
            request = MagicMock()
            with pytest.raises(HTTPException) as exc:
                await update_org_settings(request, "test-org", {}, auth)
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_settings_deep_merges(self):
        """PATCH settings deep-merges with existing."""
        from app.api.v1.organizations import update_org_settings
        from app.models.organization import OrgSettings

        auth = self._make_auth()
        org = _mock_org(settings_dict={"branding": {"chatbot_name": "Old Bot"}})
        mock_repo = _mock_repo(org=org)

        with self._patch_api_settings(enable_multi_tenant=True):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                effective = OrgSettings(**{"branding": {"chatbot_name": "New Bot"}})
                with patch("app.core.org_settings.get_effective_settings", return_value=effective):
                    request = MagicMock()
                    result = await update_org_settings(
                        request, "test-org",
                        {"branding": {"chatbot_name": "New Bot"}},
                        auth,
                    )
                    assert result["branding"]["chatbot_name"] == "New Bot"
                    # Verify repo.update_organization was called
                    mock_repo.update_organization.assert_called_once()

    @pytest.mark.asyncio
    async def test_permissions_endpoint_returns_role_perms(self):
        """GET /{org_id}/permissions returns permissions for user's role."""
        from app.api.v1.organizations import get_org_permissions_endpoint

        auth = self._make_auth(role="teacher")
        mock_repo = _mock_repo()

        with self._patch_api_settings(enable_multi_tenant=True):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                with patch("app.core.org_settings.get_org_permissions", return_value=["read:chat", "read:analytics"]):
                    request = MagicMock()
                    result = await get_org_permissions_endpoint(request, "test-org", auth)
                    assert result["role"] == "teacher"
                    assert "read:analytics" in result["permissions"]

    @pytest.mark.asyncio
    async def test_permissions_endpoint_403_non_member(self):
        """GET permissions returns 403 for non-member."""
        from app.api.v1.organizations import get_org_permissions_endpoint
        from fastapi import HTTPException

        auth = self._make_auth(role="student")
        mock_repo = _mock_repo()
        mock_repo.is_user_in_org.return_value = False

        with self._patch_api_settings(enable_multi_tenant=True):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                request = MagicMock()
                with pytest.raises(HTTPException) as exc:
                    await get_org_permissions_endpoint(request, "test-org", auth)
                assert exc.value.status_code == 403
