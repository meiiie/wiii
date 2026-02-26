"""
Skill ↔ Tool Bridge — Connects tool execution to skill advancement.

Sprint 205: "Cầu Nối Kỹ Năng"

SOTA 2026 Pattern (Voyager/OpenClaw):
    Tool execution feeds back into skill lifecycle.
    Mastered skills become priority tools.

Three feedback loops:
    1. Tool → Metrics: record_invocation() for IntelligentToolSelector reranking
    2. Tool → SkillBuilder: record_usage() for Living Agent skill advancement
    3. Skill → Tool: mastered skills auto-register as priority tools (Voyager pattern)

Usage (from graph.py, tutor_node.py, workers.py):
    from app.engine.skills.skill_tool_bridge import record_tool_usage
    record_tool_usage("tool_search_maritime", success=True, latency_ms=450, query="COLREGs")
"""

import logging

logger = logging.getLogger(__name__)

# Tool name → Living Agent skill domain mapping
_TOOL_SKILL_MAP = {
    "tool_knowledge_search": "knowledge_retrieval",
    "tool_maritime_search": "maritime_navigation",
    "tool_search_maritime": "maritime_navigation",
    "tool_web_search": "web_research",
    "tool_search_news": "news_analysis",
    "tool_search_legal": "legal_research",
    "tool_calculator": "calculation",
    "tool_current_datetime": None,  # Utility, no skill association
    "tool_think": None,  # Internal reasoning, no skill
    "tool_report_progress": None,  # Internal, no skill
    "tool_character_note": None,  # Character tracking, no skill
}

# Track which skills have already been registered as tools (avoid duplicate registration)
_registered_mastered: set[str] = set()


def record_tool_usage(
    tool_name: str,
    success: bool,
    latency_ms: int = 0,
    query_snippet: str = "",
    error_message: str = "",
    organization_id: str = "",
    tokens_used: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """Record a tool invocation — feeds both SkillMetricsTracker and SkillBuilder.

    This is the single entry point for tool→skill feedback.
    Gated behind enable_skill_metrics (metrics) and enable_skill_tool_bridge (skill advancement).

    Args:
        tool_name: Name of the tool invoked (e.g., "tool_search_maritime").
        success: Whether the invocation succeeded.
        latency_ms: Execution time in milliseconds.
        query_snippet: First 100 chars of the query (for debugging).
        error_message: Error text if failed.
        organization_id: Org context.
        tokens_used: LLM tokens consumed.
        cost_usd: Total cost estimate.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except Exception:
        return

    # Loop 1: Tool execution metrics (for IntelligentToolSelector reranking)
    if getattr(settings, "enable_skill_metrics", False) is True:
        try:
            from app.engine.skills.skill_metrics import get_skill_metrics_tracker
            tracker = get_skill_metrics_tracker()
            tracker.record_invocation(
                skill_id=f"tool:{tool_name}",
                success=success,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                query_snippet=query_snippet[:100] if query_snippet else "",
                error_message=error_message,
                organization_id=organization_id,
            )
        except Exception as e:
            logger.debug("[BRIDGE] Metrics recording failed: %s", e)

    # Loop 2: Living Agent skill advancement (for skill lifecycle progression)
    if getattr(settings, "enable_skill_tool_bridge", False) is True:
        _bridge_to_skill_builder(tool_name, success)


def _bridge_to_skill_builder(tool_name: str, success: bool) -> None:
    """Bridge tool usage to Living Agent SkillBuilder.

    Maps tool names to skill domains and records usage for lifecycle advancement.
    When a skill reaches MASTERED, triggers priority tool registration (Loop 3).
    Only active when enable_living_agent is also True.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "enable_living_agent", False):
            return

        skill_domain = _TOOL_SKILL_MAP.get(tool_name)
        if skill_domain is None:
            return  # No skill association for this tool

        from app.engine.living_agent.skill_builder import get_skill_builder
        builder = get_skill_builder()

        # Auto-discover the skill if not yet tracked
        existing = builder._find_by_name(skill_domain)
        if not existing:
            builder.discover(
                skill_name=skill_domain,
                domain=_infer_domain(tool_name),
                source=f"tool:{tool_name}",
            )

        builder.record_usage(skill_domain, success=success)
        logger.debug("[BRIDGE] Skill usage recorded: %s → %s (success=%s)",
                      tool_name, skill_domain, success)

        # Loop 3: Check if skill just reached MASTERED — register as priority tool
        updated = builder._find_by_name(skill_domain)
        if updated and _is_mastered(updated) and skill_domain not in _registered_mastered:
            _register_mastered_skill(skill_domain, tool_name, updated)

    except Exception as e:
        logger.debug("[BRIDGE] Skill builder bridge failed: %s", e)


def _is_mastered(skill) -> bool:
    """Check if a skill has reached MASTERED status."""
    try:
        from app.engine.living_agent.models import SkillStatus
        return skill.status == SkillStatus.MASTERED
    except Exception:
        return False


def _register_mastered_skill(skill_domain: str, tool_name: str, skill) -> None:
    """Register a mastered skill as a priority tool in IntelligentToolSelector.

    Voyager pattern: mastered skills get boosted selection priority.
    This does NOT create new LangChain tools — it boosts existing tool scores
    via the SkillMetricsTracker, so IntelligentToolSelector Step 4 picks them up.
    """
    try:
        from app.engine.skills.skill_metrics import get_skill_metrics_tracker
        tracker = get_skill_metrics_tracker()

        # Inject a synthetic "mastery bonus" into metrics for this tool
        # This gives the tool a high success_rate signal that Step 4 will read
        tracker.record_invocation(
            skill_id=f"tool:{tool_name}",
            success=True,
            latency_ms=0,  # Zero latency = synthetic signal
            query_snippet=f"[MASTERY] {skill_domain} reached MASTERED",
        )

        _registered_mastered.add(skill_domain)
        logger.info("[BRIDGE] Mastered skill registered as priority tool: %s → %s",
                     skill_domain, tool_name)

    except Exception as e:
        logger.debug("[BRIDGE] Mastered skill registration failed: %s", e)


def _infer_domain(tool_name: str) -> str:
    """Infer domain from tool name."""
    if "maritime" in tool_name:
        return "maritime"
    if "legal" in tool_name:
        return "legal"
    if "news" in tool_name:
        return "news"
    return "general"


def get_mastery_score(tool_name: str) -> float:
    """Get mastery score for a tool from Living Agent SkillBuilder.

    Returns 0.0 if no skill data available, or the skill confidence (0-1).
    Used by IntelligentToolSelector for mastery-weighted reranking.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "enable_skill_tool_bridge", False):
            return 0.0
        if not getattr(settings, "enable_living_agent", False):
            return 0.0

        skill_domain = _TOOL_SKILL_MAP.get(tool_name)
        if skill_domain is None:
            return 0.0

        from app.engine.living_agent.skill_builder import get_skill_builder
        builder = get_skill_builder()
        skill = builder._find_by_name(skill_domain)
        if skill:
            return skill.confidence
    except Exception:
        pass
    return 0.0


def get_mastered_tools() -> list[str]:
    """Get list of tool names whose associated skills are MASTERED.

    Used by IntelligentToolSelector to boost mastered tools.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "enable_skill_tool_bridge", False):
            return []
        if not getattr(settings, "enable_living_agent", False):
            return []

        from app.engine.living_agent.skill_builder import get_skill_builder
        from app.engine.living_agent.models import SkillStatus
        builder = get_skill_builder()
        mastered = builder.get_all_skills(status=SkillStatus.MASTERED)
        mastered_domains = {s.skill_name for s in mastered}

        # Reverse-map: skill domain → tool names
        tools = []
        for tool_name, domain in _TOOL_SKILL_MAP.items():
            if domain in mastered_domains:
                tools.append(tool_name)
        return tools
    except Exception:
        return []
