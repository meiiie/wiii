"""
Subagent architecture for Wiii multi-agent system.

Feature-gated: ``enable_subagent_architecture=False`` by default.

Provides
--------
- SubagentResult / SubagentConfig / SubagentRegistry — Core primitives
- execute_subagent / execute_parallel_subagents — Timeout + retry wrapper
- RequestScopedToolCache — Avoid duplicate API calls within a request
- SubagentMetrics — Per-subagent observability
- search/, rag/, tutor/ — Domain-specific subgraph packages
"""

from app.engine.multi_agent.subagents.result import (
    SubagentResult,
    SubagentStatus,
    SearchSubagentResult,
    RAGSubagentResult,
    TutorSubagentResult,
)
from app.engine.multi_agent.subagents.config import (
    SubagentConfig,
    FallbackBehavior,
)
from app.engine.multi_agent.subagents.registry import SubagentRegistry
from app.engine.multi_agent.subagents.tool_cache import RequestScopedToolCache
from app.engine.multi_agent.subagents.metrics import SubagentMetrics
from app.engine.multi_agent.subagents.report import (
    SubagentReport,
    ReportVerdict,
    AggregatorDecision,
    build_report,
)

__all__ = [
    "SubagentResult",
    "SubagentStatus",
    "SearchSubagentResult",
    "RAGSubagentResult",
    "TutorSubagentResult",
    "SubagentConfig",
    "FallbackBehavior",
    "SubagentRegistry",
    "RequestScopedToolCache",
    "SubagentMetrics",
    # Phase 4
    "SubagentReport",
    "ReportVerdict",
    "AggregatorDecision",
    "build_report",
]
