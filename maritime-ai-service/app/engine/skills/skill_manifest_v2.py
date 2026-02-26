"""
Sprint 191: Unified Skill Manifest — Data Models

Defines the canonical data model for skills/tools across all 4 systems:
- SkillType: Enum classifying skill origin
- SkillMetrics: Per-skill execution metrics (latency, success, cost)
- UnifiedSkillManifest: Normalized view of any skill/tool

Pattern:
  Each source system keeps its own storage (in-memory, filesystem, DB, remote).
  UnifiedSkillManifest is a **read-only projection** built at query time.
  No data migration needed — all existing systems remain unchanged.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class SkillType(str, Enum):
    """Classification of skill/tool origin system."""

    TOOL = "tool"                          # ToolRegistry LangChain tools
    DOMAIN_KNOWLEDGE = "domain_knowledge"  # DomainPlugin SKILL.md
    LIVING_AGENT = "living_agent"          # SkillBuilder wiii_skills table
    MCP_EXTERNAL = "mcp_external"          # MCP client external tools


@dataclass
class SkillMetrics:
    """
    Per-skill execution metrics.

    Updated by SkillMetricsTracker, stored in-memory with periodic DB flush.
    All fields are cumulative within the current session; DB holds historical.
    """

    total_invocations: int = 0
    successful_invocations: int = 0
    avg_latency_ms: float = 0.0
    total_tokens_used: int = 0
    cost_estimate_usd: float = 0.0
    last_used: Optional[datetime] = None
    # Sprint 195: Cost tracking per invocation type
    estimated_token_cost: float = 0.0      # Avg LLM token cost per invocation
    estimated_api_cost: float = 0.0        # Avg external API cost per invocation

    @property
    def success_rate(self) -> float:
        """Success rate as 0.0 – 1.0."""
        if self.total_invocations == 0:
            return 0.0
        return self.successful_invocations / self.total_invocations

    @property
    def avg_cost_per_invocation(self) -> float:
        """Average total cost (token + API) per invocation."""
        if self.total_invocations == 0:
            return 0.0
        return (self.cost_estimate_usd) / self.total_invocations


@dataclass
class UnifiedSkillManifest:
    """
    Canonical read-only view of a skill or tool.

    ID convention:
      "tool:<tool_name>"               e.g. "tool:tool_search_shopee"
      "domain:<domain_id>:<skill_id>"  e.g. "domain:maritime:colregs"
      "living:<skill_name>"            e.g. "living:colregs_rule_14"
      "mcp:<server>:<tool_name>"       e.g. "mcp:filesystem:read_file"

    Only one of the source-reference fields should be set (tool_name, content_path,
    wiii_skill_id, mcp_server) depending on skill_type.
    """

    id: str                                # Composite key (see convention above)
    name: str                              # Human-readable display name
    description: str                       # Brief description (Vietnamese or English)
    skill_type: SkillType                  # Origin system

    # Sprint 195: Progressive Disclosure (3-level)
    # L1 (always loaded, ~100 tokens): id + name + description_short
    # L2 (loaded when selected, <5k tokens): description + schema + usage examples
    # L3 (loaded during execution): resources, API keys, domain-specific configs
    description_short: str = ""            # L1: one-line summary (~20 words)
    instructions: str = ""                 # L2: full usage instructions
    disclosure_level: int = 1              # Current loaded level (1, 2, or 3)

    # Optional classification
    domain_id: Optional[str] = None        # Parent domain (maritime, traffic_law, ...)
    category: Optional[str] = None         # ToolCategory value for TOOL type
    triggers: List[str] = field(default_factory=list)  # Keywords for matching
    version: str = "1.0.0"

    # Source reference — exactly one should be set per skill_type
    tool_name: Optional[str] = None        # ToolRegistry: tool function name
    content_path: Optional[Path] = None    # DomainPlugin: path to SKILL.md
    wiii_skill_id: Optional[UUID] = None   # Living Agent: DB primary key
    mcp_server: Optional[str] = None       # MCP: server name

    # Living Agent-specific (populated only for LIVING_AGENT type)
    status: Optional[str] = None           # SkillStatus value
    confidence: Optional[float] = None     # 0-1 mastery level

    # Roles (from ToolRegistry or default)
    roles: List[str] = field(default_factory=lambda: ["student", "teacher", "admin"])

    # Execution metrics (populated by SkillMetricsTracker)
    metrics: SkillMetrics = field(default_factory=SkillMetrics)

    # Flexible metadata for system-specific extras
    extra: Dict[str, Any] = field(default_factory=dict)

    def matches_query(self, query: str) -> bool:
        """
        Simple keyword matching for skill discovery.

        Checks if any query word appears in name, description, or triggers.
        Case-insensitive. Returns True if at least one match found.
        """
        if not query or not query.strip():
            return False
        query_lower = query.lower()
        words = query_lower.split()

        searchable = (
            f"{self.name} {self.description} {' '.join(self.triggers)}"
        ).lower()

        return any(w in searchable for w in words)
