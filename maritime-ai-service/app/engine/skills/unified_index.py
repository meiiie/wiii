"""
Sprint 191: Unified Skill Index — Read-Only Query Interface

Singleton that aggregates skills/tools from 4 source systems into a single
queryable cache. Provides:
  - refresh()  → re-scan all sources, rebuild cache
  - search()   → keyword-based skill discovery
  - get_by_id() → direct lookup
  - get_all()  → filter by type, domain, category
  - count()    → summary statistics

Feature-gated: enable_unified_skill_index=False (default)

Pattern:
  - Each source adapter is a callable returning List[UnifiedSkillManifest]
  - Sources are scanned lazily on first access or explicit refresh()
  - Thread-safe via threading.Lock
  - Does NOT modify any source system — purely read-only projections
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from app.engine.skills.skill_manifest_v2 import (
    SkillType,
    UnifiedSkillManifest,
)

logger = logging.getLogger(__name__)

# Module-level singleton
_index_instance: Optional["UnifiedSkillIndex"] = None
_index_lock = threading.Lock()


def get_unified_skill_index() -> "UnifiedSkillIndex":
    """Get or create the singleton UnifiedSkillIndex."""
    global _index_instance
    if _index_instance is None:
        with _index_lock:
            if _index_instance is None:
                _index_instance = UnifiedSkillIndex()
    return _index_instance


class UnifiedSkillIndex:
    """
    Read-only unified view across all skill/tool systems.

    Source adapters are registered via register_source() and called
    during refresh() to populate the internal cache.

    Default sources (registered automatically if available):
      1. ToolRegistry → SkillType.TOOL
      2. DomainRegistry → SkillType.DOMAIN_KNOWLEDGE
      3. SkillBuilder (Living Agent) → SkillType.LIVING_AGENT
      4. MCPToolManager → SkillType.MCP_EXTERNAL
    """

    def __init__(self):
        self._cache: Dict[str, UnifiedSkillManifest] = {}
        self._sources: Dict[str, Callable[[], List[UnifiedSkillManifest]]] = {}
        self._lock = threading.Lock()
        self._last_refresh: float = 0.0
        self._auto_register_defaults()

    # ------------------------------------------------------------------
    # Source registration
    # ------------------------------------------------------------------

    def register_source(
        self,
        name: str,
        loader: Callable[[], List[UnifiedSkillManifest]],
    ) -> None:
        """
        Register a source adapter that produces UnifiedSkillManifest items.

        Args:
            name: Source identifier (e.g., "tool_registry", "domain_plugins")
            loader: Callable returning list of manifests (called during refresh)
        """
        with self._lock:
            self._sources[name] = loader
            logger.debug("Registered skill source: %s", name)

    def _auto_register_defaults(self) -> None:
        """Auto-register built-in source adapters (lazy, error-tolerant)."""
        self.register_source("tool_registry", _load_from_tool_registry)
        self.register_source("domain_plugins", _load_from_domain_plugins)
        self.register_source("living_agent", _load_from_living_agent)
        self.register_source("mcp_tools", _load_from_mcp_tools)

    # ------------------------------------------------------------------
    # Refresh / cache management
    # ------------------------------------------------------------------

    def refresh(self) -> int:
        """
        Re-scan all registered sources and rebuild the cache.

        Returns:
            Total number of skills indexed.
        """
        new_cache: Dict[str, UnifiedSkillManifest] = {}
        total = 0

        for source_name, loader in self._sources.items():
            try:
                items = loader()
                for item in items:
                    if item.id in new_cache:
                        logger.debug(
                            "Duplicate skill id '%s' from source '%s' — keeping first",
                            item.id, source_name,
                        )
                        continue
                    new_cache[item.id] = item
                    total += 1
                logger.debug(
                    "Source '%s' contributed %d skills", source_name, len(items)
                )
            except Exception as e:
                logger.warning(
                    "Failed to load skills from source '%s': %s",
                    source_name, str(e)[:200],
                )

        with self._lock:
            self._cache = new_cache
            self._last_refresh = time.time()

        logger.info("Unified skill index refreshed: %d skills total", total)
        return total

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_by_id(self, skill_id: str) -> Optional[UnifiedSkillManifest]:
        """Direct lookup by composite skill ID."""
        self._ensure_loaded()
        return self._cache.get(skill_id)

    def get_all(
        self,
        skill_type: Optional[SkillType] = None,
        domain_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[UnifiedSkillManifest]:
        """
        Get all skills, optionally filtered.

        Args:
            skill_type: Filter by origin system
            domain_id: Filter by domain
            category: Filter by ToolCategory value
        """
        self._ensure_loaded()
        results = list(self._cache.values())

        if skill_type is not None:
            results = [s for s in results if s.skill_type == skill_type]
        if domain_id is not None:
            results = [s for s in results if s.domain_id == domain_id]
        if category is not None:
            results = [s for s in results if s.category == category]

        return results

    def search(
        self,
        query: str,
        skill_types: Optional[List[SkillType]] = None,
        domain_id: Optional[str] = None,
        limit: int = 20,
        use_bm25: bool = True,
    ) -> List[UnifiedSkillManifest]:
        """
        Keyword-based skill discovery.

        Sprint 195: Uses BM25 ranking when available (faster, more accurate).
        Falls back to simple word overlap matching.

        Args:
            query: Search query (matched against name, description, triggers)
            skill_types: Filter by origin systems
            domain_id: Filter by domain
            limit: Max results
            use_bm25: Whether to use BM25 search (default True)

        Returns:
            List of matching skills, sorted by relevance.
        """
        self._ensure_loaded()
        if not query or not query.strip():
            return []

        # Sprint 195: Try BM25 search first
        if use_bm25:
            try:
                from app.engine.skills.skill_search import get_skill_search
                bm25 = get_skill_search()
                if not bm25.is_indexed:
                    bm25.build_index(list(self._cache.values()))
                results = bm25.search(query, limit=limit * 2)
                if results:
                    manifests = []
                    for r in results:
                        m = self._cache.get(r.skill_id)
                        if m is None:
                            continue
                        if skill_types and m.skill_type not in skill_types:
                            continue
                        if domain_id and m.domain_id != domain_id:
                            continue
                        manifests.append(m)
                        if len(manifests) >= limit:
                            break
                    if manifests:
                        return manifests
            except Exception as e:
                logger.debug("BM25 search failed, falling back: %s", str(e)[:100])

        # Fallback: simple word overlap
        candidates = list(self._cache.values())

        if skill_types:
            candidates = [s for s in candidates if s.skill_type in skill_types]
        if domain_id:
            candidates = [s for s in candidates if s.domain_id == domain_id]

        # Score by match count
        query_lower = query.lower()
        words = query_lower.split()
        scored = []
        for skill in candidates:
            searchable = (
                f"{skill.name} {skill.description} {' '.join(skill.triggers)}"
            ).lower()
            score = sum(1 for w in words if w in searchable)
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def count(self) -> Dict[str, int]:
        """
        Summary statistics by skill type.

        Returns:
            Dict mapping SkillType value → count.
        """
        self._ensure_loaded()
        counts: Dict[str, int] = {}
        for skill in self._cache.values():
            key = skill.skill_type.value
            counts[key] = counts.get(key, 0) + 1
        counts["total"] = len(self._cache)
        return counts

    @property
    def last_refresh_time(self) -> float:
        """Timestamp of last refresh (0.0 if never refreshed)."""
        return self._last_refresh

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Lazy-load: refresh if never loaded."""
        if self._last_refresh == 0.0:
            self.refresh()


# ======================================================================
# Source adapters — each returns List[UnifiedSkillManifest]
# ======================================================================


def _load_from_tool_registry() -> List[UnifiedSkillManifest]:
    """Load tools from ToolRegistry singleton."""
    try:
        from app.engine.tools.registry import get_tool_registry
    except ImportError:
        logger.debug("ToolRegistry not available — skipping")
        return []

    try:
        registry = get_tool_registry()
        # Sprint 195: Fix — registry has no _initialized attribute; check _tools dict
        if not getattr(registry, '_tools', None):
            return []

        results = []
        for name, info in registry._tools.items():
            manifest = UnifiedSkillManifest(
                id=f"tool:{name}",
                name=name,
                description=info.description or "",
                skill_type=SkillType.TOOL,
                category=info.category.value if info.category else None,
                tool_name=name,
                roles=list(info.roles) if info.roles else ["student", "teacher", "admin"],
            )
            results.append(manifest)
        return results
    except Exception as e:
        logger.warning("Error loading from ToolRegistry: %s", str(e)[:200])
        return []


def _load_from_domain_plugins() -> List[UnifiedSkillManifest]:
    """Load skills from DomainRegistry (all active domains)."""
    try:
        from app.domains.registry import get_domain_registry
    except ImportError:
        logger.debug("DomainRegistry not available — skipping")
        return []

    try:
        domain_registry = get_domain_registry()
        results = []
        for domain_id in domain_registry.list_ids():
            plugin = domain_registry.get(domain_id)
            if plugin is None:
                continue
            for skill in plugin.get_skills():
                manifest = UnifiedSkillManifest(
                    id=f"domain:{domain_id}:{skill.id}",
                    name=skill.name,
                    description=skill.description,
                    skill_type=SkillType.DOMAIN_KNOWLEDGE,
                    domain_id=domain_id,
                    triggers=list(skill.triggers),
                    content_path=skill.content_path,
                    version=skill.version,
                )
                results.append(manifest)
        return results
    except Exception as e:
        logger.warning("Error loading from DomainRegistry: %s", str(e)[:200])
        return []


def _load_from_living_agent() -> List[UnifiedSkillManifest]:
    """Load skills from Living Agent SkillBuilder (DB-backed)."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.enable_living_agent:
            return []
    except Exception:
        return []

    try:
        from app.engine.living_agent.skill_builder import get_skill_builder
    except ImportError:
        logger.debug("Living Agent SkillBuilder not available — skipping")
        return []

    try:
        builder = get_skill_builder()
        # get_all_skills may require async; wrap safely
        # For now, return empty if not initialized
        if not hasattr(builder, '_skills_cache') or builder._skills_cache is None:
            return []

        results = []
        for skill in builder._skills_cache:
            manifest = UnifiedSkillManifest(
                id=f"living:{skill.skill_name}",
                name=skill.skill_name,
                description=skill.notes[:200] if skill.notes else "",
                skill_type=SkillType.LIVING_AGENT,
                domain_id=skill.domain if hasattr(skill, 'domain') else None,
                wiii_skill_id=skill.id if hasattr(skill, 'id') else None,
                status=skill.status.value if hasattr(skill, 'status') and skill.status else None,
                confidence=skill.confidence if hasattr(skill, 'confidence') else None,
                extra={
                    "usage_count": getattr(skill, 'usage_count', 0),
                    "success_rate": getattr(skill, 'success_rate', 0.0),
                },
            )
            results.append(manifest)
        return results
    except Exception as e:
        logger.warning("Error loading from Living Agent: %s", str(e)[:200])
        return []


def _load_from_mcp_tools() -> List[UnifiedSkillManifest]:
    """Load tools from MCP external servers."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.enable_mcp_client:
            return []
    except Exception:
        return []

    try:
        from app.mcp.client import MCPToolManager
    except ImportError:
        logger.debug("MCPToolManager not available — skipping")
        return []

    try:
        tools = MCPToolManager.get_tools()
        if not tools:
            return []

        results = []
        for tool in tools:
            tool_name = getattr(tool, 'name', str(tool))
            description = getattr(tool, 'description', '')
            manifest = UnifiedSkillManifest(
                id=f"mcp:external:{tool_name}",
                name=tool_name,
                description=description or "",
                skill_type=SkillType.MCP_EXTERNAL,
                mcp_server="external",
            )
            results.append(manifest)
        return results
    except Exception as e:
        logger.warning("Error loading from MCP: %s", str(e)[:200])
        return []
