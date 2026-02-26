"""
Unified Skill Architecture — Sprints 191-192

Provides a read-only unified view across 4 skill/tool systems:
1. ToolRegistry (LangChain tools)
2. DomainPlugin Skills (SKILL.md manifests)
3. Living Agent Skills (wiii_skills DB table)
4. MCP External Tools (remote MCP servers)

Plus intelligent tool selection (Sprint 192):
5. IntelligentToolSelector — 4-step selection pipeline

Feature-gated:
  enable_unified_skill_index=False
  enable_skill_metrics=False
  enable_intelligent_tool_selection=False
"""

from app.engine.skills.skill_manifest_v2 import (
    SkillType,
    SkillMetrics,
    UnifiedSkillManifest,
)
from app.engine.skills.unified_index import (
    UnifiedSkillIndex,
    get_unified_skill_index,
)
from app.engine.skills.skill_metrics import (
    SkillMetricsTracker,
    get_skill_metrics_tracker,
)
from app.engine.skills.skill_recommender import (
    IntelligentToolSelector,
    SelectionStrategy,
    ToolRecommendation,
    get_intelligent_tool_selector,
    CORE_TOOLS,
)

__all__ = [
    "SkillType",
    "SkillMetrics",
    "UnifiedSkillManifest",
    "UnifiedSkillIndex",
    "get_unified_skill_index",
    "SkillMetricsTracker",
    "get_skill_metrics_tracker",
    # Sprint 192
    "IntelligentToolSelector",
    "SelectionStrategy",
    "ToolRecommendation",
    "get_intelligent_tool_selector",
    "CORE_TOOLS",
]
