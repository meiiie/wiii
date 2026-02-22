"""
Shared Database Engine - Singleton Pattern.

This module provides a SINGLE shared database engine for all repositories.

**CHỈ THỊ KỸ THUẬT SỐ 19: Migration to Neon**
- Neon Serverless Postgres với Pooled Connection
- Khắc phục vĩnh viễn lỗi MaxClients từ Supabase
- Pool sizes from config: async_pool_min_size / async_pool_max_size
"""

import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# SINGLETON DATABASE ENGINE
# =============================================================================

_shared_engine = None
_shared_session_factory = None
_engine_initialized = False


def get_shared_engine():
    """
    Get the shared SQLAlchemy engine (Singleton).
    
    Creates ONE engine that all repositories share.
    CHỈ THỊ 19: Now using Neon Serverless Postgres.
    
    Connection Pool Settings (from config.py):
    - pool_size=settings.async_pool_min_size: Persistent connections
    - max_overflow=max_size - min_size: Extra connections under load
    - pool_timeout=30: Wait 30s for connection
    - pool_recycle=1800: Recycle connections every 30 minutes
    - pool_pre_ping=True: Check connection health before use
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _shared_engine, _engine_initialized
    
    if _shared_engine is None:
        try:
            # Sprint 165: Use postgresql+psycopg:// dialect for psycopg3 sync driver
            # (psycopg2-binary was removed in Sprint 154, replaced by psycopg[binary]>=3.1)
            sync_url = settings.postgres_url_sync
            if sync_url.startswith("postgresql://") and "+psycopg" not in sync_url:
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg://", 1)

            pool_size = settings.async_pool_min_size
            max_overflow = settings.async_pool_max_size - settings.async_pool_min_size
            _shared_engine = create_engine(
                sync_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=30,
                pool_recycle=1800
            )
            # Sprint 171: Set statement_timeout + idle_in_transaction on checkout
            # CIS PostgreSQL Benchmark 5.4 — prevent runaway queries
            stmt_timeout = getattr(settings, "postgres_statement_timeout_ms", 30000)
            idle_timeout = getattr(settings, "postgres_idle_in_transaction_timeout_ms", 60000)

            @event.listens_for(_shared_engine, "connect")
            def _set_pg_timeouts(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute(f"SET statement_timeout = {int(stmt_timeout)}")
                cursor.execute(f"SET idle_in_transaction_session_timeout = {int(idle_timeout)}")
                cursor.close()

            _engine_initialized = True
            logger.info(
                "Shared database engine created: "
                "pool_size=%d, max_overflow=%d, pool_timeout=30s, "
                "statement_timeout=%dms, idle_tx_timeout=%dms",
                pool_size, max_overflow, stmt_timeout, idle_timeout,
            )
        except Exception as e:
            logger.error("Failed to create shared database engine: %s", e)
            raise
    
    return _shared_engine


def get_shared_session_factory():
    """
    Get the shared SQLAlchemy session factory (Singleton).
    
    Returns:
        SQLAlchemy sessionmaker bound to shared engine
    """
    global _shared_session_factory
    
    if _shared_session_factory is None:
        engine = get_shared_engine()
        _shared_session_factory = sessionmaker(bind=engine)
        logger.info("Shared session factory created")
    
    return _shared_session_factory


def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        session_factory = get_shared_session_factory()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection test failed: %s", e)
        return False


def close_shared_engine():
    """
    Close the shared engine and release all connections.
    
    Call this during application shutdown.
    """
    global _shared_engine, _shared_session_factory, _engine_initialized
    
    if _shared_engine is not None:
        _shared_engine.dispose()
        _shared_engine = None
        _shared_session_factory = None
        _engine_initialized = False
        logger.info("Shared database engine closed")
