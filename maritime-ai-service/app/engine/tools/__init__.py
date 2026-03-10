"""
Tool Registry Module - Centralized Tool Management

SOTA 2025 Pattern: Tool Registry with Categories

Usage:
    from app.engine.tools import get_tool_registry, TOOLS
    
    # Get all tools
    tools = get_tool_registry().get_all()
    
    # Get by category
    rag_tools = get_tool_registry().get_by_category(ToolCategory.RAG)
    memory_tools = get_tool_registry().get_by_category(ToolCategory.MEMORY)
    learning_tools = get_tool_registry().get_by_category(ToolCategory.LEARNING)
"""

import logging

# Import registry first
from app.engine.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolAccess,
    ToolInfo,
    get_tool_registry,
    register_tool
)

# Import and register tools
from app.engine.tools.rag_tools import (
    tool_knowledge_search,
    tool_maritime_search,  # backward compat alias
    init_rag_tools,
    get_last_retrieved_sources,
    clear_retrieved_sources
)

from app.engine.tools.memory_tools import (
    tool_save_user_info,
    tool_get_user_info,
    tool_remember,
    tool_forget,
    tool_list_memories,
    tool_clear_all_memories,
    init_memory_tools,
    set_current_user,
    get_user_cache
)

# Tutor Tools - Structured Learning (SOTA 2024)
from app.engine.tools.tutor_tools import (
    tool_start_lesson,
    tool_continue_lesson,
    tool_lesson_status,
    tool_end_lesson,
    init_tutor_tools,
    set_tutor_user,
    get_current_session_id
)

# Utility Tools - Calculator, DateTime (SOTA 2026)
from app.engine.tools.utility_tools import (
    tool_calculator,
    tool_current_datetime,
    init_utility_tools,
)

# Web Search Tools - DuckDuckGo (SOTA 2026)
# Sprint 102: Enhanced with news, legal, maritime search
from app.engine.tools.web_search_tools import (
    tool_web_search,
    tool_search_news,
    tool_search_legal,
    tool_search_maritime,
    init_web_search_tools,
)

# Sprint 147: Think Tool — structured mid-workflow reasoning scratchpad
from app.engine.tools.think_tool import tool_think

# Sprint 148: Progress Report Tool — multi-phase thinking chain
from app.engine.tools.progress_tool import tool_report_progress

# Sprint 13: Extended Tools (config-gated, lazy imports)
# Filesystem, Code Execution, and Skill Management tools
# are imported and registered only when enabled in config.

logger = logging.getLogger(__name__)


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

def get_all_tools() -> list:
    """Get all registered tools."""
    return get_tool_registry().get_all()


def get_tools_for_role(role: str) -> list:
    """
    Get tools filtered by user role.

    Sprint 26: Enforces role-based access control at tool level.
    Sensitive tools (filesystem, code execution, skill management,
    scheduler, factory reset) are restricted to appropriate roles.

    Args:
        role: User role (student, teacher, admin)

    Returns:
        List of tools the role is authorized to use
    """
    return get_tool_registry().get_for_role(role)


def _init_extended_tools():
    """
    Initialize Sprint 13 extended tools (config-gated).

    Only registers tools when explicitly enabled in config.
    Uses try/except fail-graceful pattern (warn, don't crash).
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except Exception as e:
        logger.debug("Extended tools: config not available: %s", e)
        return

    registry = get_tool_registry()

    # Filesystem Tools (sandboxed)
    # Sprint 26: Restricted to admin — file operations are privileged
    if settings.enable_filesystem_tools:
        try:
            from app.engine.tools.filesystem_tools import get_filesystem_tools
            for tool_fn in get_filesystem_tools():
                registry.register(
                    tool_fn, ToolCategory.FILESYSTEM, ToolAccess.WRITE,
                    roles=["admin"]
                )
            logger.info("Filesystem tools registered (sandboxed, admin-only)")
        except Exception as e:
            logger.warning("Filesystem tools init failed: %s", e)

    # Code Execution Tool (sandboxed)
    # Sprint 26: Restricted to admin — code execution is privileged
    if settings.enable_code_execution:
        try:
            from app.engine.tools.code_execution_tools import get_code_execution_tools
            for tool_fn in get_code_execution_tools():
                registry.register(
                    tool_fn, ToolCategory.EXECUTION, ToolAccess.WRITE,
                    roles=["admin"]
                )
            logger.info("Code execution tools registered (sandboxed, admin-only)")
        except Exception as e:
            logger.warning("Code execution tools init failed: %s", e)

    # Browser Sandbox Tools (OpenSandbox-backed, admin-only)
    if (
        settings.enable_browser_agent
        and settings.enable_privileged_sandbox
        and settings.sandbox_provider == "opensandbox"
        and settings.sandbox_allow_browser_workloads
    ):
        try:
            from app.engine.tools.browser_sandbox_tools import get_browser_sandbox_tools
            for tool_fn in get_browser_sandbox_tools():
                registry.register(
                    tool_fn, ToolCategory.EXECUTION, ToolAccess.WRITE,
                    roles=["admin"]
                )
            logger.info("Browser sandbox tools registered (admin-only)")
        except Exception as e:
            logger.warning("Browser sandbox tools init failed: %s", e)

    # Skill Management Tools (self-extending agent)
    # Sprint 26: Restricted to admin — creating/modifying skills is privileged
    if settings.enable_skill_creation:
        try:
            from app.engine.tools.skill_tools import get_skill_tools
            for tool_fn in get_skill_tools():
                registry.register(
                    tool_fn, ToolCategory.SKILL_MANAGEMENT, ToolAccess.WRITE,
                    roles=["admin"]
                )
            logger.info("Skill management tools registered (admin-only)")
        except Exception as e:
            logger.warning("Skill management tools init failed: %s", e)

    # Scheduler Tools (Sprint 19: proactive agent)
    # Sprint 26: Restricted to teacher/admin — students cannot schedule tasks
    if settings.enable_scheduler:
        try:
            from app.engine.tools.scheduler_tools import get_scheduler_tools
            for tool_fn in get_scheduler_tools():
                registry.register(
                    tool_fn, ToolCategory.SCHEDULER, ToolAccess.WRITE,
                    roles=["teacher", "admin"]
                )
            logger.info("Scheduler tools registered (proactive agent, teacher/admin)")
        except Exception as e:
            logger.warning("Scheduler tools init failed: %s", e)

    # Product Search Tools (Sprint 148: multi-platform e-commerce)
    if settings.enable_product_search:
        try:
            from app.engine.tools.product_search_tools import init_product_search_tools
            from app.engine.tools.excel_report_tool import init_excel_report_tool
            init_product_search_tools()
            init_excel_report_tool()
            # Sprint 150: Product page scraper tool
            from app.engine.tools.product_page_scraper import get_product_page_scraper_tools
            for scraper_tool in get_product_page_scraper_tools():
                registry.register(scraper_tool, ToolCategory.PRODUCT_SEARCH, ToolAccess.READ)
            logger.info("Product search + Excel report + page scraper tools registered")
        except Exception as e:
            logger.warning("Product search tools init failed: %s", e)

    # Sprint 200: Visual Product Search (image → product identification)
    if settings.enable_visual_product_search:
        try:
            from app.engine.tools.visual_product_search import get_visual_product_search_tool
            _vps_tool = get_visual_product_search_tool()
            registry.register(_vps_tool, ToolCategory.PRODUCT_SEARCH, ToolAccess.READ)
            logger.info("Visual product search tool registered")
        except Exception as e:
            logger.warning("Visual product search tool init failed: %s", e)

    # LMS Tools (Sprint 175 tools, Sprint 220 registration)
    if settings.enable_lms_integration:
        try:
            from app.engine.tools.lms_tools import register_lms_tools
            register_lms_tools()
            logger.info("LMS tools registered (gate: enable_lms_integration)")
        except Exception as e:
            logger.warning("LMS tools init failed: %s", e)

    # Character Tools (Sprint 95: self-editing character state)
    if settings.enable_character_tools:
        try:
            from app.engine.character.character_tools import get_character_tools
            for tool_fn in get_character_tools():
                registry.register(
                    tool_fn, ToolCategory.CHARACTER, ToolAccess.WRITE,
                )
            logger.info("Character tools registered (%d tools)", len(get_character_tools()))
        except Exception as e:
            logger.warning("Character tools init failed: %s", e)


_tools_initialized = False


def init_all_tools(rag_agent=None, semantic_memory=None, user_id: str = None, domain_id: str = None):
    """
    Initialize all tools with required dependencies.

    Args:
        rag_agent: RAG agent for knowledge retrieval
        semantic_memory: Semantic memory engine for user facts
        user_id: Current user ID
        domain_id: Domain ID for domain-specific tool registration
    """
    global _tools_initialized
    if _tools_initialized:
        # Sprint 153: Idempotency guard — per-user context still updates below
        logger.debug("init_all_tools already called, updating user context only")

    if rag_agent:
        init_rag_tools(rag_agent)

    if semantic_memory:
        init_memory_tools(semantic_memory, user_id)

    # Initialize tutor tools with user context
    if user_id:
        init_tutor_tools(user_id)

    # Sprint 124: Initialize character tools with user context (per-user isolation)
    if user_id:
        try:
            from app.engine.character.character_tools import set_character_user
            set_character_user(user_id)
        except Exception as e:
            logger.debug("Character user init skipped: %s", e)

    # Initialize utility tools (always available)
    init_utility_tools()

    # Deterministic output generation tools (HTML/Excel/Word)
    try:
        from app.engine.tools.output_generation_tools import init_output_generation_tools

        init_output_generation_tools()
    except Exception as e:
        logger.warning("Output generation tools init failed: %s", e)

    # Sprint 147: Register think tool as core utility (always available)
    registry = get_tool_registry()
    if "tool_think" not in registry.get_all_names():
        registry.register(
            tool_think, ToolCategory.UTILITY, ToolAccess.READ,
            description="Think step-by-step about complex problems (private scratchpad)",
        )

    # Sprint 148: Register progress report tool as core utility (always available)
    if "tool_report_progress" not in registry.get_all_names():
        registry.register(
            tool_report_progress, ToolCategory.UTILITY, ToolAccess.READ,
            description="Report progress and start a new analysis phase (multi-phase thinking)",
        )

    # Initialize web search tools (always available)
    init_web_search_tools()

    # Sprint 13: Extended Tools (config-gated)
    _init_extended_tools()

    # Register domain-specific tools if available
    if domain_id:
        try:
            from app.domains.registry import get_domain_registry
            domain_registry = get_domain_registry()
            domain_plugin = domain_registry.get(domain_id)
            if domain_plugin:
                domain_tools = domain_plugin.get_tools()
                registry = get_tool_registry()
                for tool_fn in domain_tools:
                    registry.register(tool_fn, ToolCategory.RAG)
                if domain_tools:
                    logger.info("Registered %d domain tools for '%s'", len(domain_tools), domain_id)
        except Exception as e:
            logger.debug("Domain tool registration skipped: %s", e)

    registry = get_tool_registry()
    summary = registry.summary()
    logger.info("Tool Registry initialized: %s", summary)
    _tools_initialized = True


# Sprint 153: Removed stale module-level TOOLS snapshot.
# Use get_all_tools() to get current tools (was evaluated before init_all_tools()).
TOOLS = get_all_tools  # Backward compat: call TOOLS() instead of TOOLS


__all__ = [
    # Registry
    "ToolRegistry",
    "ToolCategory",
    "ToolAccess",
    "ToolInfo",
    "get_tool_registry",
    "register_tool",
    
    # RAG Tools
    "tool_knowledge_search",
    "tool_maritime_search",  # backward compat alias
    "init_rag_tools",
    "get_last_retrieved_sources",
    "clear_retrieved_sources",
    
    # Memory Tools
    "tool_save_user_info",
    "tool_get_user_info",
    "tool_remember",
    "tool_forget",
    "tool_list_memories",
    "tool_clear_all_memories",
    "init_memory_tools",
    "set_current_user",
    "get_user_cache",
    
    # Tutor Tools (Structured Learning)
    "tool_start_lesson",
    "tool_continue_lesson",
    "tool_lesson_status",
    "tool_end_lesson",
    "init_tutor_tools",
    "set_tutor_user",
    "get_current_session_id",
    
    # Utility Tools
    "tool_calculator",
    "tool_current_datetime",
    "init_utility_tools",

    # Web Search Tools (Sprint 102: enhanced)
    "tool_web_search",
    "tool_search_news",
    "tool_search_legal",
    "tool_search_maritime",
    "init_web_search_tools",

    # Extended Tools (Sprint 13, config-gated)
    "_init_extended_tools",

    # Think Tool (Sprint 147)
    "tool_think",

    # Progress Report Tool (Sprint 148)
    "tool_report_progress",

    # Sprint 196: B2B Sourcing Tools (config-gated, registered via product_search_tools)
    # tool_dealer_search, tool_extract_contacts, tool_international_search

    # Convenience
    "get_all_tools",
    "get_tools_for_role",
    "init_all_tools",
    "TOOLS"
]

