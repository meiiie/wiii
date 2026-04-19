"""Skill Exporter — auto-generates YAML skills from successful conversations.

Pattern inspired by Firecrawl Web Agent's exportSkill tool:
after a successful multi-step agent conversation, distill the workflow
into a reusable YAML skill that can be loaded by ContextSkillLoader.

Feature-gated by settings.enable_skill_export (default: False).
Rate-limited by settings.skill_export_max_per_day (default: 5).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "context" / "skills" / "auto_generated"


@dataclass
class ExportedSkillCandidate:
    """A skill candidate extracted from a conversation."""

    name: str
    host_type: str = "auto_generated"
    page_types: List[str] = field(default_factory=lambda: ["*"])
    description: str = ""
    priority: float = 0.6
    prompt_addition: str = ""
    tools: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    source_conversation_id: str = ""
    confidence: float = 0.0


class SkillExporter:
    """Extracts reusable skills from successful agent conversations.

    Uses LLM (light tier) to analyze the tool call sequence, user query,
    and final response, then distills a YAML skill that captures the workflow.

    Rate-limited: max N exports per day (configurable).
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self._output_dir = output_dir or _DEFAULT_EXPORT_DIR
        self._daily_count: int = 0
        self._daily_reset: str = ""  # YYYY-MM-DD

    async def analyze_and_export(
        self,
        query: str,
        tools_used: List[Dict[str, Any]],
        final_response: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        min_tool_calls: int = 2,
        max_per_day: int = 5,
    ) -> Optional[ExportedSkillCandidate]:
        """Analyze a completed conversation and potentially export a skill.

        Steps:
        1. Check minimum complexity (at least min_tool_calls)
        2. Rate limit check (max per day)
        3. Build extraction prompt
        4. Call LLM to extract workflow
        5. Parse and validate
        6. Save YAML + register

        Returns the candidate if exported, None if skipped.
        """
        if len(tools_used) < min_tool_calls:
            return None

        if not self._check_rate_limit(max_per_day):
            return None

        extraction_prompt = self._build_extraction_prompt(
            query, tools_used, final_response
        )

        try:
            raw_output = await self._call_llm(extraction_prompt)
        except Exception as e:
            logger.warning("[SKILL_EXPORT] LLM extraction failed: %s", e)
            return None

        candidate = self._parse_extraction(raw_output, query)
        if not self._validate_candidate(candidate):
            return None

        saved_path = self._save_yaml(candidate)
        if saved_path:
            self._daily_count += 1
            logger.info(
                "[SKILL_EXPORT] Exported skill: %s → %s", candidate.name, saved_path
            )

        return candidate

    def _check_rate_limit(self, max_per_day: int) -> bool:
        """Check daily rate limit."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_reset:
            self._daily_count = 0
            self._daily_reset = today
        return self._daily_count < max_per_day

    def _build_extraction_prompt(
        self,
        query: str,
        tools_used: List[Dict[str, Any]],
        final_response: str,
    ) -> str:
        """Build the LLM prompt for skill extraction."""
        tools_summary = "\n".join(
            f"  {i+1}. {t.get('name', 'unknown')}: {t.get('args', {})}"
            for i, t in enumerate(tools_used)
        )
        response_preview = final_response[:500] if final_response else ""

        return f"""Analyze this successful AI agent interaction and extract a reusable skill.

USER QUERY: {query}

TOOLS CALLED (in order):
{tools_summary}

FINAL RESPONSE (first 500 chars):
{response_preview}

Extract a reusable YAML skill. Respond with ONLY the YAML block:

```yaml
name: auto-<descriptive-kebab-case>
description: "<mô tả một dòng bằng tiếng Việt có dấu>"
priority: 0.6
prompt_addition: |
  <Hướng dẫn bằng tiếng Việt có dấu cho AI cách xử lý loại yêu cầu này>
  <Bao gồm khuyến nghị công cụ cụ thể và chiến lược>
  <Giữ dưới 300 ký tự>
tools:
  - <tool_name_1>
  - <tool_name_2>
triggers:
  - "<từ khóa ý định 1>"
  - "<từ khóa ý định 2>"
```

Rules:
- name must be kebab-case, prefixed with "auto-"
- prompt_addition must be in Vietnamese WITH proper diacritics (tiếng Việt có dấu)
- tools must only include tools actually used
- triggers capture INTENT not exact query
- Only export if this is a REUSABLE pattern"""

    async def _call_llm(self, prompt: str) -> str:
        """Call light-tier LLM for skill extraction."""
        try:
            from app.engine.llm_providers.unified_client import UnifiedLLMClient

            client = UnifiedLLMClient.get_client()
            response = await client.chat.completions.create(
                model="gemini-3.1-flash-lite-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            return response.choices[0].message.content or ""
        except Exception:
            # Fallback: try any available client
            from app.engine.llm_providers.unified_client import UnifiedLLMClient

            for provider_name in ["google", "zhipu", "openai"]:
                try:
                    client = UnifiedLLMClient.get_client(provider_name)
                    response = await client.chat.completions.create(
                        model="gemini-3.1-flash-lite-preview",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=800,
                    )
                    return response.choices[0].message.content or ""
                except Exception:
                    continue
            raise

    def _parse_extraction(
        self, raw_output: str, original_query: str
    ) -> Optional[ExportedSkillCandidate]:
        """Parse LLM output into a skill candidate."""
        # Extract YAML block from markdown code fence
        yaml_match = re.search(r"```yaml\s*\n(.*?)```", raw_output, re.DOTALL)
        if not yaml_match:
            yaml_match = re.search(r"```(.*?)```", raw_output, re.DOTALL)
        if not yaml_match:
            # Try parsing the whole output as YAML
            yaml_text = raw_output
        else:
            yaml_text = yaml_match.group(1).strip()

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            return None

        if not isinstance(data, dict):
            return None

        return ExportedSkillCandidate(
            name=data.get("name", ""),
            description=data.get("description", ""),
            priority=float(data.get("priority", 0.6)),
            prompt_addition=data.get("prompt_addition", ""),
            tools=data.get("tools", []),
            triggers=data.get("triggers", []),
        )

    def _validate_candidate(
        self, candidate: Optional[ExportedSkillCandidate]
    ) -> bool:
        """Validate the candidate has all required fields."""
        if not candidate:
            return False
        if not candidate.name or not candidate.name.startswith("auto-"):
            return False
        if not candidate.prompt_addition or len(candidate.prompt_addition) < 30:
            return False
        if not candidate.tools:
            return False
        return True

    def _save_yaml(self, candidate: ExportedSkillCandidate) -> Optional[Path]:
        """Save the skill candidate as a YAML file."""
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            # Sanitize name for filename
            safe_name = re.sub(r"[^a-z0-9\-]", "", candidate.name)
            if not safe_name:
                return None
            filename = f"{safe_name}.skill.yaml"
            path = self._output_dir / filename

            yaml_data = {
                "name": candidate.name,
                "host_type": candidate.host_type,
                "page_types": candidate.page_types,
                "description": candidate.description,
                "priority": candidate.priority,
                "prompt_addition": candidate.prompt_addition,
                "tools": candidate.tools,
                "triggers": candidate.triggers,
                "_meta": {
                    "auto_generated": True,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            path.write_text(
                yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
            return path
        except Exception as e:
            logger.warning("[SKILL_EXPORT] Failed to save YAML: %s", e)
            return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_EXPORTER: Optional[SkillExporter] = None


def get_skill_exporter() -> SkillExporter:
    """Get or create the SkillExporter singleton."""
    global _EXPORTER
    if _EXPORTER is None:
        _EXPORTER = SkillExporter()
    return _EXPORTER
