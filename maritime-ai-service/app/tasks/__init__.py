"""
Background Tasks Module for Wiii

Sprint 18: Virtual Agent-per-User Architecture
Provides async background task execution via Taskiq + Valkey.

Task categories:
- memory_tasks: Daily memory consolidation, dedup
- summarize_tasks: Session summarization (cross-session context)
- ingest_tasks: Background PDF/document ingestion
- scheduler_tasks: Proactive agent scheduled task execution

Feature-gated: Requires `enable_background_tasks=True` in config.
"""
