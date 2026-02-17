"""
Task Broker Configuration — Taskiq + Valkey

Sprint 18: Virtual Agent-per-User Architecture
Configures the async-native task queue using Taskiq with Valkey (Redis-compatible) broker.

Why Taskiq over Celery:
- Async-native (our entire codebase is async)
- FastAPI-native integration (lifespan hooks)
- 10x lighter memory footprint
- Direct asyncio support (no worker pool overhead)

Feature-gated: Only activates when `enable_background_tasks=True`.

Usage:
    from app.core.task_broker import get_broker

    broker = get_broker()

    @broker.task
    async def my_task(arg: str):
        ...
"""

import logging

logger = logging.getLogger(__name__)

_broker = None
_scheduler = None


def get_broker():
    """
    Get the Taskiq broker instance (lazy-initialized).

    Returns a real ListQueueBroker when Taskiq + Valkey are available,
    or an InMemoryBroker for development/testing.
    """
    global _broker

    if _broker is not None:
        return _broker

    try:
        from app.core.config import settings

        if not settings.enable_background_tasks:
            logger.info("Background tasks disabled (enable_background_tasks=False)")
            return _get_inmemory_broker()

        # Try to create Valkey-backed broker
        try:
            from taskiq_redis import ListQueueBroker
            _broker = ListQueueBroker(url=settings.valkey_url)
            logger.info("Taskiq broker initialized (Valkey: %s)", settings.valkey_url)
            return _broker
        except ImportError:
            logger.warning("taskiq-redis not installed — using in-memory broker")
            return _get_inmemory_broker()

    except Exception as e:
        logger.warning("Task broker initialization failed: %s", e)
        return _get_inmemory_broker()


def _get_inmemory_broker():
    """Get or create an in-memory broker for development."""
    global _broker
    try:
        from taskiq import InMemoryBroker
        _broker = InMemoryBroker()
        logger.info("Taskiq in-memory broker initialized (development mode)")
    except ImportError:
        logger.info("Taskiq not installed — background tasks unavailable")
        _broker = None
    return _broker


def get_scheduler():
    """
    Get the Taskiq scheduler instance (for cron-based tasks).

    Only available when both Taskiq and Valkey are configured.
    """
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    try:
        from app.core.config import settings

        if not settings.enable_scheduler:
            return None

        broker = get_broker()
        if broker is None:
            return None

        from taskiq import TaskiqScheduler
        from taskiq_redis import RedisScheduleSource

        _scheduler = TaskiqScheduler(
            broker=broker,
            sources=[RedisScheduleSource(settings.valkey_url)],
        )
        logger.info("Taskiq scheduler initialized")
        return _scheduler

    except ImportError:
        logger.info("Taskiq scheduler dependencies not available")
        return None
    except Exception as e:
        logger.warning("Taskiq scheduler initialization failed: %s", e)
        return None
