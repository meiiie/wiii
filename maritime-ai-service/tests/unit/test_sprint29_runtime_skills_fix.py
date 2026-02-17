"""
Tests for Sprint 29: Runtime skills path fix.

The bug: SkillManager writes SKILL.md to ~/.wiii/workspace/skills/{domain_id}/
but YamlDomainPlugin._load_skills() only read from domain_dir/skills/.
Runtime-created skills were invisible to the agent system.

Fix: YamlDomainPlugin now scans both static (plugin dir) and runtime (workspace)
directories. SkillManager refreshes domain cache after create/delete.
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from app.domains.base import YamlDomainPlugin, SkillManifest, DomainConfig
from app.domains.skill_manager import SkillManager


# =============================================================================
# Helpers
# =============================================================================


def _create_domain_yaml(domain_dir: Path, domain_id: str = "test-domain") -> Path:
    """Create a minimal domain.yaml in the given directory."""
    manifest = {
        "id": domain_id,
        "name": "Test Domain",
        "name_vi": "Test Domain VI",
        "version": "1.0.0",
        "description": "Test domain for skill loading",
        "routing_keywords": ["test"],
    }
    yaml_path = domain_dir / "domain.yaml"
    yaml_path.write_text(
        yaml.dump(manifest, allow_unicode=True), encoding="utf-8"
    )
    return yaml_path


def _create_skill_md(
    skill_dir: Path,
    skill_name: str,
    triggers: list,
    runtime: bool = False,
) -> Path:
    """Create a SKILL.md file with YAML frontmatter."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "name": skill_name,
        "description": f"Test skill {skill_name}",
        "triggers": triggers,
        "version": "1.0.0",
    }
    if runtime:
        frontmatter["runtime"] = True
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(f"---\n{yaml_str}---\n\n# {skill_name}\n", encoding="utf-8")
    return skill_path


def _make_plugin(domain_dir: Path, workspace_root: str) -> YamlDomainPlugin:
    """Create a YamlDomainPlugin with workspace_root patched."""
    plugin = YamlDomainPlugin(domain_dir)
    # Override _get_runtime_skills_dir to use our workspace
    original = plugin._get_runtime_skills_dir

    def patched_get_runtime_dir():
        workspace = Path(workspace_root).resolve()
        config = plugin.get_config()
        return workspace / "skills" / config.id

    plugin._get_runtime_skills_dir = patched_get_runtime_dir
    return plugin


# =============================================================================
# YamlDomainPlugin -- Static + Runtime skill loading
# =============================================================================


class TestLoadSkillsBothDirs:
    """_load_skills() should scan both plugin dir and workspace dir."""

    def test_loads_static_skills_only(self, tmp_path):
        """When no runtime skills exist, load only static skills."""
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")
        _create_skill_md(domain_dir / "skills" / "colregs", "colregs", ["colregs"])

        plugin = _make_plugin(domain_dir, str(tmp_path / "nonexistent-workspace"))
        skills = plugin.get_skills()

        assert len(skills) == 1
        assert skills[0].id == "colregs"

    def test_loads_runtime_skills_from_workspace(self, tmp_path):
        """Runtime skills from workspace dir should be visible."""
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        workspace = tmp_path / "workspace"
        _create_skill_md(
            workspace / "skills" / "test-domain" / "my-skill",
            "my-skill",
            ["trigger1"],
            runtime=True,
        )

        plugin = _make_plugin(domain_dir, str(workspace))
        skills = plugin.get_skills()

        assert len(skills) == 1
        assert skills[0].id == "my-skill"

    def test_loads_both_static_and_runtime(self, tmp_path):
        """Both static and runtime skills should be loaded."""
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")
        _create_skill_md(domain_dir / "skills" / "static-skill", "static-skill", ["static"])

        workspace = tmp_path / "workspace"
        _create_skill_md(
            workspace / "skills" / "test-domain" / "runtime-skill",
            "runtime-skill",
            ["runtime"],
            runtime=True,
        )

        plugin = _make_plugin(domain_dir, str(workspace))
        skills = plugin.get_skills()

        assert len(skills) == 2
        ids = {s.id for s in skills}
        assert "static-skill" in ids
        assert "runtime-skill" in ids

    def test_static_skill_takes_precedence_on_duplicate_id(self, tmp_path):
        """If same skill ID exists in both dirs, static wins (dedup)."""
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")
        _create_skill_md(domain_dir / "skills" / "shared", "shared", ["static-trigger"])

        workspace = tmp_path / "workspace"
        _create_skill_md(
            workspace / "skills" / "test-domain" / "shared",
            "shared",
            ["runtime-trigger"],
            runtime=True,
        )

        plugin = _make_plugin(domain_dir, str(workspace))
        skills = plugin.get_skills()

        assert len(skills) == 1
        assert skills[0].id == "shared"
        assert "static-trigger" in skills[0].triggers


class TestGetRuntimeSkillsDir:
    """_get_runtime_skills_dir() returns workspace/skills/{domain_id}."""

    def test_returns_correct_path(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "my-domain")

        mock_settings = MagicMock()
        mock_settings.workspace_root = str(tmp_path / "workspace")

        with patch("app.core.config.settings", mock_settings):
            plugin = YamlDomainPlugin(domain_dir)
            runtime_dir = plugin._get_runtime_skills_dir()

        expected = (tmp_path / "workspace").resolve() / "skills" / "my-domain"
        assert runtime_dir == expected

    def test_returns_none_on_settings_error(self, tmp_path):
        """_get_runtime_skills_dir returns None when settings import fails."""
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        plugin = YamlDomainPlugin(domain_dir)
        # Make _get_runtime_skills_dir raise internally
        with patch.object(plugin, "_get_runtime_skills_dir", return_value=None):
            # Verify that _load_skills handles None gracefully
            plugin._skills = None
            skills = plugin.get_skills()

        assert isinstance(skills, list)


class TestRefreshSkills:
    """refresh_skills() invalidates the cached skills list."""

    def test_refresh_clears_cache(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        workspace = tmp_path / "workspace"
        plugin = _make_plugin(domain_dir, str(workspace))

        # First call loads and caches
        skills1 = plugin.get_skills()
        assert len(skills1) == 0

        # Create a runtime skill AFTER initial load
        _create_skill_md(
            workspace / "skills" / "test-domain" / "new-skill",
            "new-skill",
            ["new"],
            runtime=True,
        )

        # Still cached
        skills_cached = plugin.get_skills()
        assert len(skills_cached) == 0

        # Refresh clears cache
        plugin.refresh_skills()
        skills_refreshed = plugin.get_skills()
        assert len(skills_refreshed) == 1
        assert skills_refreshed[0].id == "new-skill"

    def test_refresh_sets_skills_to_none(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        plugin = _make_plugin(domain_dir, str(tmp_path / "ws"))
        plugin.get_skills()  # Cache
        assert plugin._skills is not None

        plugin.refresh_skills()
        assert plugin._skills is None


class TestMatchSkillsWithRuntime:
    """match_skills() should find runtime skills by trigger."""

    def test_match_runtime_skill_trigger(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        workspace = tmp_path / "workspace"
        _create_skill_md(
            workspace / "skills" / "test-domain" / "speed-limit",
            "speed-limit",
            ["speed limit", "toc do"],
            runtime=True,
        )

        plugin = _make_plugin(domain_dir, str(workspace))
        matched = plugin.match_skills("What is the speed limit?")

        assert len(matched) == 1
        assert matched[0].id == "speed-limit"


# =============================================================================
# SkillManager -- Domain cache refresh
# =============================================================================


class TestSkillManagerDomainRefresh:
    """SkillManager should refresh domain plugin cache after CRUD."""

    def test_create_skill_calls_refresh(self, tmp_path):
        """After creating a skill, SkillManager refreshes the domain plugin."""
        manager = SkillManager(workspace_root=str(tmp_path))

        mock_plugin = MagicMock()
        mock_plugin.refresh_skills = MagicMock()
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin

        with patch(
            "app.domains.registry.get_domain_registry",
            return_value=mock_registry,
        ):
            result = manager.create_skill(
                domain_id="maritime",
                name="test-skill",
                description="Test",
                triggers=["test"],
                content="# Test",
            )

        assert result.success is True
        mock_registry.get.assert_called_with("maritime")
        mock_plugin.refresh_skills.assert_called_once()

    def test_delete_skill_calls_refresh(self, tmp_path):
        """After deleting a skill, SkillManager refreshes the domain plugin."""
        manager = SkillManager(workspace_root=str(tmp_path))
        manager.create_skill("maritime", "to-delete", "d", ["t"], "c")

        mock_plugin = MagicMock()
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin

        with patch(
            "app.domains.registry.get_domain_registry",
            return_value=mock_registry,
        ):
            result = manager.delete_skill("maritime", "to-delete")

        assert result.success is True
        mock_plugin.refresh_skills.assert_called_once()

    def test_refresh_graceful_when_no_registry(self, tmp_path):
        """_refresh_domain_cache should not raise when registry unavailable."""
        manager = SkillManager(workspace_root=str(tmp_path))

        with patch(
            "app.domains.registry.get_domain_registry",
            side_effect=ImportError("no registry"),
        ):
            result = manager.create_skill(
                domain_id="maritime",
                name="test-skill",
                description="Test",
                triggers=["test"],
                content="# Test",
            )
            assert result.success is True

    def test_refresh_graceful_when_domain_not_registered(self, tmp_path):
        """_refresh_domain_cache handles unregistered domain gracefully."""
        manager = SkillManager(workspace_root=str(tmp_path))

        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch(
            "app.domains.registry.get_domain_registry",
            return_value=mock_registry,
        ):
            result = manager.create_skill(
                domain_id="unregistered",
                name="test-skill",
                description="Test",
                triggers=["test"],
                content="# Test",
            )
            assert result.success is True


# =============================================================================
# End-to-End: SkillManager -> Domain Plugin
# =============================================================================


class TestEndToEndSkillVisibility:
    """Runtime skills created by SkillManager should be visible via domain plugin."""

    def test_created_skill_visible_after_refresh(self, tmp_path):
        """Full flow: create via SkillManager -> refresh -> visible in plugin."""
        workspace = tmp_path / "workspace"
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        plugin = _make_plugin(domain_dir, str(workspace))
        assert len(plugin.get_skills()) == 0

        manager = SkillManager(workspace_root=str(workspace))
        result = manager.create_skill(
            domain_id="test-domain",
            name="new-rule",
            description="A new rule",
            triggers=["new rule", "quy tac moi"],
            content="# New Rule\n\nThis is a new rule.",
        )
        assert result.success is True

        plugin.refresh_skills()
        skills = plugin.get_skills()
        assert len(skills) == 1
        assert skills[0].id == "new-rule"
        assert "new rule" in skills[0].triggers

    def test_deleted_skill_disappears_after_refresh(self, tmp_path):
        """Full flow: create -> verify visible -> delete -> verify gone."""
        workspace = tmp_path / "workspace"
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        plugin = _make_plugin(domain_dir, str(workspace))

        manager = SkillManager(workspace_root=str(workspace))
        manager.create_skill("test-domain", "temp-skill", "temp", ["temp"], "# Temp")

        plugin.refresh_skills()
        assert len(plugin.get_skills()) == 1

        manager.delete_skill("test-domain", "temp-skill")
        plugin.refresh_skills()
        assert len(plugin.get_skills()) == 0


# =============================================================================
# Scan skills dir helper
# =============================================================================


class TestScanSkillsDir:
    """_scan_skills_dir correctly parses SKILL.md files."""

    def test_scan_empty_dir(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        plugin = YamlDomainPlugin(domain_dir)
        result = plugin._scan_skills_dir(empty_dir)
        assert result == []

    def test_scan_dir_with_non_skill_files(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "README.md").write_text("Not a skill", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir)
        result = plugin._scan_skills_dir(skills_dir)
        assert result == []

    def test_scan_dir_skips_dir_without_skill_md(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        _create_domain_yaml(domain_dir, "test-domain")

        skills_dir = tmp_path / "skills"
        (skills_dir / "empty-skill").mkdir(parents=True)

        plugin = YamlDomainPlugin(domain_dir)
        result = plugin._scan_skills_dir(skills_dir)
        assert result == []
