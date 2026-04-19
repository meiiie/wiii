"""Tests for Skill Exporter."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.engine.skills.skill_exporter import (
    ExportedSkillCandidate,
    SkillExporter,
    get_skill_exporter,
)


class TestExportedSkillCandidate:
    def test_defaults(self):
        candidate = ExportedSkillCandidate(name="auto-test-skill")
        assert candidate.host_type == "auto_generated"
        assert candidate.page_types == ["*"]
        assert candidate.priority == 0.6

    def test_with_values(self):
        candidate = ExportedSkillCandidate(
            name="auto-product-comparison",
            description="So sanh gia san pham",
            prompt_addition="Tim kiem tren nhieu nen tang",
            tools=["tool_web_search", "tool_knowledge_search"],
            triggers=["so sanh gia", "gia re nhat"],
        )
        assert candidate.name == "auto-product-comparison"
        assert len(candidate.tools) == 2


class TestSkillExporterValidation:
    def test_validate_valid_candidate(self):
        exporter = SkillExporter()
        candidate = ExportedSkillCandidate(
            name="auto-test",
            prompt_addition="Day la huong dan chi tiet cho AI ve cach xu ly loai cau hoi nay",
            tools=["tool_web_search"],
        )
        assert exporter._validate_candidate(candidate) is True

    def test_validate_rejects_no_auto_prefix(self):
        exporter = SkillExporter()
        candidate = ExportedSkillCandidate(
            name="test-skill",  # Missing auto- prefix
            prompt_addition="Day la huong dan chi tiet cho AI",
            tools=["tool_web_search"],
        )
        assert exporter._validate_candidate(candidate) is False

    def test_validate_rejects_short_prompt(self):
        exporter = SkillExporter()
        candidate = ExportedSkillCandidate(
            name="auto-test",
            prompt_addition="Ngan qua",  # < 30 chars
            tools=["tool_web_search"],
        )
        assert exporter._validate_candidate(candidate) is False

    def test_validate_rejects_no_tools(self):
        exporter = SkillExporter()
        candidate = ExportedSkillCandidate(
            name="auto-test",
            prompt_addition="Day la huong dan chi tiet cho AI ve cach xu ly",
            tools=[],
        )
        assert exporter._validate_candidate(candidate) is False

    def test_validate_rejects_none(self):
        exporter = SkillExporter()
        assert exporter._validate_candidate(None) is False


class TestSkillExtractionPrompt:
    def test_build_extraction_prompt(self):
        exporter = SkillExporter()
        prompt = exporter._build_extraction_prompt(
            query="So sanh gia MacBook Pro M4",
            tools_used=[
                {"name": "tool_web_search", "args": {"q": "MacBook Pro M4 gia"}},
                {"name": "tool_knowledge_search", "args": {"q": "MacBook Pro M4"}},
            ],
            final_response="MacBook Pro M4 gia tu 44-46 trieu tren cac san",
        )
        assert "MacBook Pro M4" in prompt
        assert "tool_web_search" in prompt
        assert "tool_knowledge_search" in prompt
        assert "auto-" in prompt


class TestSkillParsing:
    def test_parse_yaml_from_code_fence(self):
        exporter = SkillExporter()
        raw = """Here is the skill:

```yaml
name: auto-product-price-compare
description: "So sanh gia san pham"
priority: 0.7
prompt_addition: |
  Khi nguoi dung hoi ve gia san pham, tim kiem tren nhieu nen tang
  va so sanh gia de tim gia re nhat.
tools:
  - tool_web_search
  - tool_knowledge_search
triggers:
  - "so sanh gia"
  - "gia re nhat"
```
"""
        candidate = exporter._parse_extraction(raw, "test query")
        assert candidate is not None
        assert candidate.name == "auto-product-price-compare"
        assert len(candidate.tools) == 2
        assert "so sanh gia" in candidate.triggers

    def test_parse_plain_yaml(self):
        exporter = SkillExporter()
        raw = """name: auto-test-skill
description: "Test"
prompt_addition: |
  Day la prompt dai hon 30 ky tu cho viec test
tools:
  - tool_search
"""
        candidate = exporter._parse_extraction(raw, "test")
        assert candidate is not None
        assert candidate.name == "auto-test-skill"

    def test_parse_invalid_yaml(self):
        exporter = SkillExporter()
        candidate = exporter._parse_extraction("not yaml at all {{{{", "test")
        assert candidate is None


class TestSkillYAMLSave:
    def test_save_yaml(self, tmp_path):
        exporter = SkillExporter(output_dir=tmp_path)
        candidate = ExportedSkillCandidate(
            name="auto-test-save",
            description="Test save",
            prompt_addition="Day la huong dan chi tiet de test luu file YAML",
            tools=["tool_web_search"],
            triggers=["test"],
        )
        path = exporter._save_yaml(candidate)
        assert path is not None
        assert path.exists()
        assert "auto-test-save" in path.name

        # Verify YAML content
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["name"] == "auto-test-save"
        assert data["_meta"]["auto_generated"] is True

    def test_save_sanitize_name(self, tmp_path):
        exporter = SkillExporter(output_dir=tmp_path)
        candidate = ExportedSkillCandidate(
            name="auto-test WITH SPACES & special! chars",
            prompt_addition="Test with special characters in name",
            tools=["tool_search"],
        )
        path = exporter._save_yaml(candidate)
        assert path is not None
        assert " " not in path.name


class TestRateLimit:
    def test_rate_limit_allows_under_max(self):
        exporter = SkillExporter()
        assert exporter._check_rate_limit(5) is True

    def test_rate_limit_blocks_over_max(self):
        from datetime import datetime, timezone
        exporter = SkillExporter()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        exporter._daily_count = 5
        exporter._daily_reset = today  # Same day — count stays
        assert exporter._check_rate_limit(5) is False

    def test_rate_limit_resets_on_new_day(self):
        exporter = SkillExporter()
        exporter._daily_count = 5
        exporter._daily_reset = "2020-01-01"  # Old date
        assert exporter._check_rate_limit(5) is True
        assert exporter._daily_count == 0


class TestSkillExporterSingleton:
    def test_get_skill_exporter(self):
        exporter = get_skill_exporter()
        assert isinstance(exporter, SkillExporter)


class TestAnalyzeAndExport:
    @pytest.mark.asyncio
    async def test_skip_when_too_few_tools(self):
        exporter = SkillExporter()
        result = await exporter.analyze_and_export(
            query="test",
            tools_used=[{"name": "tool_search"}],
            final_response="response",
            min_tool_calls=2,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_rate_limited(self):
        exporter = SkillExporter()
        exporter._daily_count = 10
        result = await exporter.analyze_and_export(
            query="test",
            tools_used=[{"name": "a"}, {"name": "b"}],
            final_response="response",
            max_per_day=5,
        )
        assert result is None
