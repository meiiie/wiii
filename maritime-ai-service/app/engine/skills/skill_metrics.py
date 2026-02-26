"""
Sprint 191: Skill Metrics Tracker

In-memory metrics cache with periodic DB flush for per-tool/skill execution
tracking. Records latency, success rate, token usage, and cost.

Feature-gated: enable_skill_metrics=False (default)

Architecture:
  - Hot path: In-memory Dict[str, SkillMetrics] — O(1) reads/writes
  - Cold path: Periodic DB flush via background task (configurable interval)
  - EMA latency: new_avg = α * current + (1 − α) * prev (α = 0.3)

Integration point:
  After each tool call in agentic loop, call:
    tracker.record_invocation(skill_id, success, latency_ms, tokens, cost)
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.engine.skills.skill_manifest_v2 import SkillMetrics

logger = logging.getLogger(__name__)

# Module-level singleton
_tracker_instance: Optional["SkillMetricsTracker"] = None
_tracker_lock = threading.Lock()

# EMA smoothing factor (0.3 weight on new value, 0.7 on historical)
_EMA_ALPHA = 0.3


def get_skill_metrics_tracker() -> "SkillMetricsTracker":
    """Get or create the singleton SkillMetricsTracker."""
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = SkillMetricsTracker()
    return _tracker_instance


class SkillMetricsTracker:
    """
    Thread-safe in-memory metrics tracker with DB flush capability.

    Tracks per-skill execution metrics:
    - Invocation count (total + successful)
    - Average latency (EMA smoothed)
    - Token usage and cost estimates
    - Last-used timestamp

    The flush_to_db() method writes pending records to the
    tool_execution_metrics table. Called by background scheduler
    or manually for testing.
    """

    def __init__(self, flush_interval_seconds: int = 60):
        self._metrics: Dict[str, SkillMetrics] = {}
        self._pending_records: List[Dict] = []
        self._lock = threading.Lock()
        self._flush_interval = flush_interval_seconds
        self._last_flush: float = 0.0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_invocation(
        self,
        skill_id: str,
        success: bool,
        latency_ms: int = 0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        query_snippet: str = "",
        error_message: str = "",
        organization_id: str = "",
        token_cost: float = 0.0,
        api_cost: float = 0.0,
    ) -> None:
        """
        Record a single skill/tool invocation.

        Args:
            skill_id: Composite skill ID (e.g., "tool:tool_search_shopee")
            success: Whether invocation completed successfully
            latency_ms: Execution time in milliseconds
            tokens_used: LLM tokens consumed
            cost_usd: Estimated total cost in USD
            query_snippet: First 100 chars of query (for debugging)
            error_message: Error text if failed
            organization_id: Org context
            token_cost: Sprint 195 — LLM token cost for this invocation
            api_cost: Sprint 195 — External API cost for this invocation
        """
        with self._lock:
            if skill_id not in self._metrics:
                self._metrics[skill_id] = SkillMetrics()

            m = self._metrics[skill_id]
            m.total_invocations += 1
            if success:
                m.successful_invocations += 1

            # EMA latency
            if latency_ms > 0:
                m.avg_latency_ms = _EMA_ALPHA * latency_ms + (1 - _EMA_ALPHA) * m.avg_latency_ms

            m.total_tokens_used += tokens_used
            m.cost_estimate_usd += cost_usd
            m.last_used = datetime.now(timezone.utc)

            # Sprint 195: EMA cost tracking
            if token_cost > 0:
                m.estimated_token_cost = (
                    _EMA_ALPHA * token_cost + (1 - _EMA_ALPHA) * m.estimated_token_cost
                )
            if api_cost > 0:
                m.estimated_api_cost = (
                    _EMA_ALPHA * api_cost + (1 - _EMA_ALPHA) * m.estimated_api_cost
                )

            # Queue for DB flush
            self._pending_records.append({
                "skill_id": skill_id,
                "skill_type": self._infer_skill_type(skill_id),
                "success": success,
                "latency_ms": latency_ms,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
                "query_snippet": query_snippet[:100] if query_snippet else "",
                "error_message": error_message[:500] if error_message else "",
                "organization_id": organization_id,
                "created_at": datetime.now(timezone.utc),
            })

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_metrics(self, skill_id: str) -> Optional[SkillMetrics]:
        """Get current metrics for a skill (from in-memory cache)."""
        return self._metrics.get(skill_id)

    def get_all_metrics(self) -> Dict[str, SkillMetrics]:
        """Get a copy of all metrics."""
        with self._lock:
            return dict(self._metrics)

    def get_top_performers(self, n: int = 10) -> List[Tuple[str, SkillMetrics]]:
        """
        Get top-N skills ranked by: success_rate * sqrt(total_invocations).

        Balances reliability with usage volume.
        """
        scored = []
        for skill_id, m in self._metrics.items():
            if m.total_invocations == 0:
                continue
            score = m.success_rate * (m.total_invocations ** 0.5)
            scored.append((score, skill_id, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(sid, m) for _, sid, m in scored[:n]]

    def get_slow_tools(self, threshold_ms: int = 5000) -> List[Tuple[str, SkillMetrics]]:
        """Get skills with average latency exceeding threshold."""
        return [
            (sid, m) for sid, m in self._metrics.items()
            if m.avg_latency_ms > threshold_ms and m.total_invocations > 0
        ]

    def get_summary(self) -> Dict:
        """Summary statistics across all tracked skills."""
        total_skills = len(self._metrics)
        total_invocations = sum(m.total_invocations for m in self._metrics.values())
        total_tokens = sum(m.total_tokens_used for m in self._metrics.values())
        total_cost = sum(m.cost_estimate_usd for m in self._metrics.values())
        avg_success = 0.0
        if total_skills > 0:
            rates = [m.success_rate for m in self._metrics.values() if m.total_invocations > 0]
            avg_success = sum(rates) / len(rates) if rates else 0.0

        return {
            "total_skills_tracked": total_skills,
            "total_invocations": total_invocations,
            "total_tokens_used": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_success_rate": round(avg_success, 4),
            "pending_flush_records": len(self._pending_records),
        }

    # ------------------------------------------------------------------
    # DB Flush
    # ------------------------------------------------------------------

    def flush_to_db(self) -> int:
        """
        Write pending records to tool_execution_metrics table.

        Returns number of records flushed.
        Called by background scheduler or manually.
        """
        with self._lock:
            records = list(self._pending_records)
            self._pending_records.clear()
            self._last_flush = time.time()

        if not records:
            return 0

        try:
            self._write_records_to_db(records)
            logger.info("Flushed %d skill metrics records to DB", len(records))
            return len(records)
        except Exception as e:
            logger.error("Failed to flush skill metrics to DB: %s", str(e)[:200])
            # Re-queue failed records
            with self._lock:
                self._pending_records = records + self._pending_records
            return 0

    def _write_records_to_db(self, records: List[Dict]) -> None:
        """
        Write records to PostgreSQL tool_execution_metrics table.

        Uses asyncpg pool. Lazy import to avoid circular dependencies.
        """
        try:
            from app.core.database import get_asyncpg_pool
        except ImportError:
            logger.debug("asyncpg pool not available — skipping DB flush")
            return

        import asyncio

        async def _do_insert():
            pool = await get_asyncpg_pool(create=True)
            if pool is None:
                logger.debug("No asyncpg pool — skipping DB flush")
                return

            async with pool.acquire() as conn:
                for record in records:
                    await conn.execute(
                        """
                        INSERT INTO tool_execution_metrics
                            (skill_id, skill_type, success, latency_ms,
                             tokens_used, cost_usd, query_snippet,
                             error_message, organization_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        record["skill_id"],
                        record["skill_type"],
                        record["success"],
                        record["latency_ms"],
                        record["tokens_used"],
                        record["cost_usd"],
                        record["query_snippet"],
                        record["error_message"],
                        record["organization_id"],
                    )

        # Sprint 195: Safe async flush — catch errors and re-queue on failure
        async def _safe_insert():
            try:
                await _do_insert()
            except Exception as flush_err:
                logger.error("Async skill metrics flush failed: %s", str(flush_err)[:200])
                # Re-queue records so they aren't lost
                with self._lock:
                    self._pending_records = records + self._pending_records

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_safe_insert())
        except RuntimeError:
            try:
                asyncio.run(_do_insert())
            except Exception as sync_err:
                logger.error("Sync skill metrics flush failed: %s", str(sync_err)[:200])
                with self._lock:
                    self._pending_records = records + self._pending_records

    @property
    def pending_count(self) -> int:
        """Number of records pending DB flush."""
        return len(self._pending_records)

    @property
    def last_flush_time(self) -> float:
        """Timestamp of last DB flush (0.0 if never flushed)."""
        return self._last_flush

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all metrics and pending records. For testing only."""
        with self._lock:
            self._metrics.clear()
            self._pending_records.clear()
            self._last_flush = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_skill_type(skill_id: str) -> str:
        """Infer SkillType value from composite skill ID prefix."""
        if skill_id.startswith("tool:"):
            return "tool"
        elif skill_id.startswith("domain:"):
            return "domain_knowledge"
        elif skill_id.startswith("living:"):
            return "living_agent"
        elif skill_id.startswith("mcp:"):
            return "mcp_external"
        return "unknown"
