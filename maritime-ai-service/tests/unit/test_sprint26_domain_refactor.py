"""
Tests for Sprint 26: YamlDomainPlugin base class and domain refactoring.

Covers:
- YamlDomainPlugin loads domain.yaml manifest
- YamlDomainPlugin provides get_config(), get_prompts_dir(), get_skills()
- YamlDomainPlugin._parse_skill_frontmatter uses dynamic domain_id
- MaritimeDomain extends YamlDomainPlugin correctly
- TrafficLawDomain extends YamlDomainPlugin correctly
- DomainLoader excludes YamlDomainPlugin from instantiation
- Backward compatibility: all existing domain tests still pass
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.domains.base import DomainPlugin, YamlDomainPlugin, DomainConfig, SkillManifest


# =============================================================================
# YamlDomainPlugin Base Class
# =============================================================================

class TestYamlDomainPlugin:
    """Test the new YamlDomainPlugin intermediate base class."""

    def test_is_subclass_of_domain_plugin(self):
        """YamlDomainPlugin should extend DomainPlugin."""
        assert issubclass(YamlDomainPlugin, DomainPlugin)

    def test_loads_manifest_from_domain_dir(self, tmp_path):
        """Should load domain.yaml from the provided directory."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text(
            "id: test_domain\nname: Test Domain\nname_vi: Domain Test\nversion: 1.0.0\n",
            encoding="utf-8",
        )

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        config = plugin.get_config()

        assert config.id == "test_domain"
        assert config.name == "Test Domain"
        assert config.name_vi == "Domain Test"
        assert config.version == "1.0.0"

    def test_default_values_when_manifest_missing_fields(self, tmp_path):
        """Should use sensible defaults when YAML fields are missing."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: minimal\n", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        config = plugin.get_config()

        assert config.id == "minimal"
        assert config.routing_keywords == []
        assert config.description == ""

    def test_default_id_from_directory_name(self, tmp_path):
        """When id is missing from YAML, should use directory name."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("name: Some Name\n", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        config = plugin.get_config()

        assert config.id == tmp_path.name

    def test_get_prompts_dir(self, tmp_path):
        """Should return domain_dir/prompts."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: test\n", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        assert plugin.get_prompts_dir() == tmp_path / "prompts"

    def test_get_skills_empty_when_no_skills_dir(self, tmp_path):
        """Should return empty list when skills/ doesn't exist."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: test\n", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        assert plugin.get_skills() == []

    def test_get_skills_loads_from_skills_dir(self, tmp_path):
        """Should load SKILL.md files from skills/ subdirectories."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: test_domain\n", encoding="utf-8")

        skills_dir = tmp_path / "skills" / "colregs"
        skills_dir.mkdir(parents=True)

        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: colregs\ndisplay_name: COLREGs\ndescription: Navigation rules\ntriggers:\n  - colregs\n  - navigation\nversion: 1.0.0\n---\nFull content here.\n",
            encoding="utf-8",
        )

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        skills = plugin.get_skills()

        assert len(skills) == 1
        assert skills[0].id == "colregs"
        assert skills[0].name == "COLREGs"
        assert skills[0].domain_id == "test_domain"  # Dynamic, not hardcoded
        assert "colregs" in skills[0].triggers

    def test_parse_skill_frontmatter_uses_dynamic_domain_id(self, tmp_path):
        """domain_id in SkillManifest should come from get_config().id."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: dynamic_test\n", encoding="utf-8")

        skills_dir = tmp_path / "skills" / "test_skill"
        skills_dir.mkdir(parents=True)
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: test_skill\ndescription: A test\n---\nBody.\n",
            encoding="utf-8",
        )

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        result = plugin._parse_skill_frontmatter(skill_md)

        assert result is not None
        assert result.domain_id == "dynamic_test"

    def test_manifest_missing_file_graceful(self, tmp_path):
        """Should handle missing domain.yaml gracefully."""
        # No domain.yaml file
        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        config = plugin.get_config()

        assert config.id == tmp_path.name  # Falls back to dir name

    def test_config_caching(self, tmp_path):
        """get_config() should cache result after first call."""
        manifest = tmp_path / "domain.yaml"
        manifest.write_text("id: cached\n", encoding="utf-8")

        plugin = YamlDomainPlugin(domain_dir=tmp_path)
        config1 = plugin.get_config()
        config2 = plugin.get_config()

        assert config1 is config2  # Same object (cached)


# =============================================================================
# Real Domain Plugins — Backward Compatibility
# =============================================================================

class TestMaritimeDomainRefactored:
    """Test MaritimeDomain after refactoring to extend YamlDomainPlugin."""

    @pytest.fixture
    def maritime(self):
        from app.domains.maritime import MaritimeDomain
        return MaritimeDomain()

    def test_is_yaml_domain_plugin(self, maritime):
        """Should be a YamlDomainPlugin subclass."""
        assert isinstance(maritime, YamlDomainPlugin)
        assert isinstance(maritime, DomainPlugin)

    def test_config_id(self, maritime):
        """Should have id='maritime'."""
        assert maritime.get_config().id == "maritime"

    def test_prompts_dir_exists(self, maritime):
        """Prompts directory should exist."""
        assert maritime.get_prompts_dir().exists()

    def test_tool_instruction_not_empty(self, maritime):
        """Should return domain-specific tool instruction."""
        instruction = maritime.get_tool_instruction()
        assert "COLREGs" in instruction or "tool_knowledge_search" in instruction

    def test_hyde_templates_vi_and_en(self, maritime):
        """Should have both Vietnamese and English HyDE templates."""
        templates = maritime.get_hyde_templates()
        assert "vi" in templates
        assert "en" in templates
        assert "{question}" in templates["vi"]

    def test_routing_config(self, maritime):
        """Should return routing config with required keys."""
        config = maritime.get_routing_config()
        assert "routing_keywords" in config
        assert "rag_description" in config

    def test_greetings(self, maritime):
        """Should have Vietnamese and English greetings."""
        greetings = maritime.get_greetings()
        assert len(greetings) >= 3


class TestTrafficLawDomainRefactored:
    """Test TrafficLawDomain after refactoring to extend YamlDomainPlugin."""

    @pytest.fixture
    def traffic_law(self):
        from app.domains.traffic_law import TrafficLawDomain
        return TrafficLawDomain()

    def test_is_yaml_domain_plugin(self, traffic_law):
        """Should be a YamlDomainPlugin subclass."""
        assert isinstance(traffic_law, YamlDomainPlugin)

    def test_config_id(self, traffic_law):
        """Should have id='traffic_law'."""
        assert traffic_law.get_config().id == "traffic_law"

    def test_tool_instruction_has_traffic_keywords(self, traffic_law):
        """Should mention traffic-specific topics."""
        instruction = traffic_law.get_tool_instruction()
        assert "giao thông" in instruction.lower() or "traffic" in instruction.lower()

    def test_hyde_templates(self, traffic_law):
        """Should have HyDE templates."""
        templates = traffic_law.get_hyde_templates()
        assert "vi" in templates
        assert "en" in templates


# =============================================================================
# DomainLoader — YamlDomainPlugin Exclusion
# =============================================================================

class TestDomainLoaderExclusion:
    """Test that DomainLoader excludes YamlDomainPlugin from instantiation."""

    def test_excludes_yaml_domain_plugin(self):
        """DomainLoader._load_domain should not instantiate YamlDomainPlugin itself."""
        from app.domains.loader import DomainLoader

        domains_dir = Path(__file__).parent.parent.parent / "app" / "domains"
        loader = DomainLoader(domains_dir)

        # Discover should find concrete domains, not the base class
        plugins = loader.discover()
        plugin_types = [type(p).__name__ for p in plugins]

        assert "YamlDomainPlugin" not in plugin_types
        assert "MaritimeDomain" in plugin_types
        assert "TrafficLawDomain" in plugin_types
