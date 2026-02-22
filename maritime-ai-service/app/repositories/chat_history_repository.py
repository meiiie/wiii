"""
Chat History Repository - Memory Lite Implementation.

This module provides CRUD operations for chat sessions and messages,
implementing the Sliding Window strategy for context retrieval.

**Feature: wiii, Week 2: Memory Lite**
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from sqlalchemy import desc, select

from app.core.config import settings
from app.models.database import ChatMessageModel, ChatSessionModel

logger = logging.getLogger(__name__)


def _normalize_session_id(session_id: Union[str, UUID]) -> UUID:
    """Normalize any session_id to a deterministic UUID.

    Valid UUID strings/objects pass through unchanged.
    Non-UUID strings (e.g. 'test-sprint78-context', 'user_123__session_abc')
    are mapped to a deterministic UUID via uuid5(NAMESPACE_DNS, value).

    This is necessary because the DB schema uses UUID columns for session_id,
    but the API accepts arbitrary string session IDs.
    """
    if isinstance(session_id, UUID):
        return session_id
    try:
        return UUID(str(session_id))
    except (ValueError, AttributeError):
        return uuid5(NAMESPACE_DNS, str(session_id))


@dataclass
class ChatMessage:
    """
    Chat message data class.
    
    **CHỈ THỊ SỐ 22: Memory Isolation - is_blocked flag**
    """
    id: UUID
    session_id: UUID
    role: str  # 'user' or 'assistant'
    content: str
    created_at: datetime
    is_blocked: bool = False  # CHỈ THỊ SỐ 22: Blocked message flag
    block_reason: Optional[str] = None  # CHỈ THỊ SỐ 22: Reason for blocking


@dataclass
class ChatSession:
    """Chat session data class."""
    session_id: UUID
    user_id: str
    user_name: Optional[str]
    created_at: datetime
    messages: List[ChatMessage]


class ChatHistoryRepository:
    """
    Repository for chat history operations.
    
    Implements Memory Lite with Sliding Window strategy.
    Supports both SQLAlchemy models and raw SQL for CHỈ THỊ SỐ 04 tables.
    
    **Feature: wiii, Week 2: Memory Lite**
    **Spec: CHỈ THỊ KỸ THUẬT SỐ 04, CHỈ THỊ SỐ 21 (Large Context Window)**
    """
    
    # CHỈ THỊ SỐ 21: Large Context Window - Configurable via settings
    # Gemini 2.5 Flash xử lý 50-100 tin nhắn cực nhanh và rẻ
    # Giúp AI hiểu các đại từ thay thế ("nó", "tàu đó", "ông ấy") hoàn hảo
    # Default: 50 messages (configurable via CONTEXT_WINDOW_SIZE env var)
    WINDOW_SIZE = getattr(settings, 'context_window_size', 50)
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize repository with SHARED database connection."""
        self._engine = None
        self._session_factory = None
        self._available = False
        self._use_new_schema = False  # Flag for CHỈ THỊ SỐ 04 schema
        self._init_connection()
    
    def _init_connection(self):
        """Initialize database connection using SHARED engine."""
        try:
            # Use SHARED engine to minimize connections
            from app.core.database import get_shared_engine, get_shared_session_factory
            
            self._engine = get_shared_engine()
            self._session_factory = get_shared_session_factory()
            
            # Test connection and check schema
            with self._session_factory() as session:
                session.execute(select(1))
                
                # Check if new schema exists (CHỈ THỊ SỐ 04)
                try:
                    from sqlalchemy import text
                    session.execute(text("SELECT 1 FROM chat_history LIMIT 1"))
                    self._use_new_schema = True
                    logger.info("Using CHỈ THỊ SỐ 04 schema (chat_history table)")
                except Exception as e:
                    logger.debug("New schema check failed: %s", e)
                    self._use_new_schema = False
                    logger.info("Using legacy schema (chat_sessions + chat_messages)")
            
            self._available = True
            logger.info("Chat history repository using SHARED database engine")
        except Exception as e:
            logger.warning("Chat history repository connection failed: %s", e)
            self._available = False
    
    def is_available(self) -> bool:
        """Check if repository is available."""
        return self._available
    
    def ensure_tables(self):
        """Create tables if they don't exist."""
        if not self._available:
            return
        
        try:
            from app.models.database import Base
            Base.metadata.create_all(self._engine)
            logger.info("Chat history tables created/verified")
        except Exception as e:
            logger.error("Failed to create tables: %s", e)

    def get_or_create_session(self, user_id: str) -> Optional[ChatSession]:
        """
        Get existing session or create new one for user.

        Args:
            user_id: User identifier

        Returns:
            ChatSession or None if unavailable
        """
        if not self._available:
            return None

        # Sprint 170c: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id
        eff_org_id = get_effective_org_id()

        try:
            with self._session_factory() as session:
                # Find existing session for user
                # Note: ChatSessionModel uses SQLAlchemy ORM — org filtering
                # is best done post-query or via raw SQL. For the legacy ORM path,
                # we filter by user_id (sessions are user-scoped) and the
                # org context is carried via the thread ID convention.
                stmt = select(ChatSessionModel).where(
                    ChatSessionModel.user_id == user_id
                ).order_by(desc(ChatSessionModel.created_at)).limit(1)

                result = session.execute(stmt).scalar_one_or_none()

                if result:
                    return ChatSession(
                        session_id=result.session_id,
                        user_id=result.user_id,
                        user_name=result.user_name,
                        created_at=result.created_at,
                        messages=[]
                    )

                # Create new session
                new_session = ChatSessionModel(
                    session_id=uuid4(),
                    user_id=user_id
                )
                session.add(new_session)
                session.commit()

                logger.info("Created new chat session for user %s", user_id)

                return ChatSession(
                    session_id=new_session.session_id,
                    user_id=new_session.user_id,
                    user_name=new_session.user_name,
                    created_at=new_session.created_at,
                    messages=[]
                )
        except Exception as e:
            logger.error("Failed to get/create session: %s", e)
            return None

    def save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        is_blocked: bool = False,
        block_reason: Optional[str] = None
    ) -> Optional[ChatMessage]:
        """
        Save a message to the chat history.

        Args:
            session_id: Session UUID or string (auto-normalized to UUID)
            role: 'user' or 'assistant'
            content: Message content
            user_id: User ID (required for new schema)
            is_blocked: Whether message was blocked by Guardian (CHỈ THỊ SỐ 22)
            block_reason: Reason for blocking (CHỈ THỊ SỐ 22)

        Returns:
            ChatMessage or None if failed

        **Spec: CHỈ THỊ KỸ THUẬT SỐ 04, CHỈ THỊ SỐ 22**
        """
        if not self._available:
            return None

        # Normalize session_id to UUID (handles non-UUID strings like composite thread IDs)
        norm_session_id = _normalize_session_id(session_id)

        try:
            with self._session_factory() as session:
                if self._use_new_schema:
                    # Use CHỈ THỊ SỐ 04 schema (chat_history table)
                    from sqlalchemy import text
                    # Sprint 160: Org-scoped insert
                    from app.core.org_filter import get_effective_org_id
                    eff_org_id = get_effective_org_id()
                    msg_id = uuid4()
                    session.execute(
                        text("""
                            INSERT INTO chat_history (id, user_id, session_id, role, content, is_blocked, block_reason, organization_id)
                            VALUES (:id, :user_id, :session_id, :role, :content, :is_blocked, :block_reason, :org_id)
                        """),
                        {
                            "id": str(msg_id),
                            "user_id": user_id or str(norm_session_id),
                            "session_id": str(norm_session_id),
                            "role": role,
                            "content": content,
                            "is_blocked": is_blocked,
                            "block_reason": block_reason,
                            "org_id": eff_org_id,
                        }
                    )
                    session.commit()
                    return ChatMessage(
                        id=msg_id,
                        session_id=norm_session_id,
                        role=role,
                        content=content,
                        created_at=datetime.now(timezone.utc),
                        is_blocked=is_blocked,
                        block_reason=block_reason
                    )
                else:
                    # Use legacy schema — ensure session exists (FK constraint)
                    self._ensure_session_exists(session, norm_session_id, user_id)

                    message = ChatMessageModel(
                        id=uuid4(),
                        session_id=norm_session_id,
                        role=role,
                        content=content,
                        is_blocked=is_blocked,
                        block_reason=block_reason
                    )
                    session.add(message)
                    session.commit()

                    return ChatMessage(
                        id=message.id,
                        session_id=message.session_id,
                        role=message.role,
                        content=message.content,
                        created_at=message.created_at,
                        is_blocked=message.is_blocked,
                        block_reason=message.block_reason
                    )
        except Exception as e:
            logger.error("Failed to save message: %s", e)
            return None

    def _ensure_session_exists(self, db_session, session_id: UUID, user_id: Optional[str] = None) -> None:
        """Ensure a chat_sessions record exists for the given session_id (legacy schema FK)."""
        try:
            existing = db_session.execute(
                select(ChatSessionModel).where(ChatSessionModel.session_id == session_id)
            ).scalar_one_or_none()
            if not existing:
                new_session = ChatSessionModel(
                    session_id=session_id,
                    user_id=user_id or str(session_id),
                )
                db_session.add(new_session)
                db_session.flush()  # Flush (not commit) — caller commits
        except Exception as e:
            logger.debug("Session ensure check: %s", e)
    
    def get_recent_messages(
        self,
        session_id: UUID,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
        include_blocked: bool = False
    ) -> List[ChatMessage]:
        """
        Get recent messages using Sliding Window strategy.

        Args:
            session_id: Session UUID or string (auto-normalized to UUID)
            limit: Number of messages (default: WINDOW_SIZE)
            user_id: User ID (for new schema query by user)
            include_blocked: Whether to include blocked messages (CHỈ THỊ SỐ 22)
                           Default False = exclude blocked messages from context

        Returns:
            List of recent messages, oldest first

        **Spec: CHỈ THỊ KỸ THUẬT SỐ 04, CHỈ THỊ SỐ 22**
        """
        if not self._available:
            return []

        # Normalize session_id to UUID (handles non-UUID strings)
        norm_session_id = _normalize_session_id(session_id)
        limit = limit or self.WINDOW_SIZE

        try:
            with self._session_factory() as session:
                if self._use_new_schema:
                    # Use CHỈ THỊ SỐ 04 schema (chat_history table)
                    from sqlalchemy import text
                    query_field = "user_id" if user_id else "session_id"
                    query_value = user_id if user_id else str(norm_session_id)

                    # CHỈ THỊ SỐ 22: Filter blocked messages by default
                    blocked_filter = "" if include_blocked else "AND (is_blocked = FALSE OR is_blocked IS NULL)"

                    # Sprint 160: Org-scoped filtering
                    from app.core.org_filter import get_effective_org_id, org_where_clause
                    eff_org_id = get_effective_org_id()
                    org_filter = org_where_clause(eff_org_id)
                    query_params = {"query_value": query_value, "limit": limit}
                    if eff_org_id is not None:
                        query_params["org_id"] = eff_org_id

                    result = session.execute(
                        text(f"""
                            SELECT id, user_id, session_id, role, content, created_at,
                                   COALESCE(is_blocked, FALSE) as is_blocked, block_reason
                            FROM chat_history
                            WHERE {query_field} = :query_value {blocked_filter}
                            {org_filter}
                            ORDER BY created_at DESC
                            LIMIT :limit
                        """),
                        query_params
                    )
                    rows = result.fetchall()

                    # Reverse to get chronological order (oldest first)
                    messages = [
                        ChatMessage(
                            id=UUID(row[0]) if isinstance(row[0], str) else row[0],
                            session_id=UUID(row[2]) if isinstance(row[2], str) else norm_session_id,
                            role=row[3],
                            content=row[4],
                            created_at=row[5],
                            is_blocked=row[6] if len(row) > 6 else False,
                            block_reason=row[7] if len(row) > 7 else None
                        )
                        for row in reversed(rows)
                    ]
                    return messages
                else:
                    # Use legacy schema (chat_messages table)
                    # CHỈ THỊ SỐ 22: Filter blocked messages by default
                    if include_blocked:
                        stmt = select(ChatMessageModel).where(
                            ChatMessageModel.session_id == norm_session_id
                        ).order_by(desc(ChatMessageModel.created_at)).limit(limit)
                    else:
                        stmt = select(ChatMessageModel).where(
                            ChatMessageModel.session_id == norm_session_id,
                            ChatMessageModel.is_blocked.is_(False)
                        ).order_by(desc(ChatMessageModel.created_at)).limit(limit)
                    
                    results = session.execute(stmt).scalars().all()
                    
                    # Reverse to get chronological order (oldest first)
                    messages = [
                        ChatMessage(
                            id=msg.id,
                            session_id=msg.session_id,
                            role=msg.role,
                            content=msg.content,
                            created_at=msg.created_at,
                            is_blocked=getattr(msg, 'is_blocked', False),
                            block_reason=getattr(msg, 'block_reason', None)
                        )
                        for msg in reversed(results)
                    ]
                    
                    return messages
        except Exception as e:
            logger.error("Failed to get messages: %s", e)
            return []
    
    def update_user_name(self, session_id: UUID, user_name: str) -> bool:
        """
        Update user name for a session.

        Sprint 170c: Org-scoped via raw SQL when new schema available.

        Args:
            session_id: Session UUID or string (auto-normalized)
            user_name: User's name

        Returns:
            True if successful
        """
        if not self._available:
            return False

        norm_session_id = _normalize_session_id(session_id)

        # Sprint 170c: Org-scoped filtering for new schema path
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()

        try:
            with self._session_factory() as session:
                # Legacy ORM path — ChatSessionModel doesn't have org_id column;
                # org isolation is via thread ID convention. Keep ORM for compatibility.
                stmt = select(ChatSessionModel).where(
                    ChatSessionModel.session_id == norm_session_id
                )
                chat_session = session.execute(stmt).scalar_one_or_none()

                if chat_session:
                    chat_session.user_name = user_name
                    session.commit()
                    logger.info("Updated user name to '%s'", user_name)
                    return True
                return False
        except Exception as e:
            logger.error("Failed to update user name: %s", e)
            return False

    def get_user_name(self, session_id: UUID) -> Optional[str]:
        """Get user name from session. Sprint 170c: Org context noted."""
        if not self._available:
            return None

        norm_session_id = _normalize_session_id(session_id)
        try:
            with self._session_factory() as session:
                # Legacy ORM path — ChatSessionModel doesn't have org_id column
                stmt = select(ChatSessionModel.user_name).where(
                    ChatSessionModel.session_id == norm_session_id
                )
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get user name: %s", e)
            return None
    
    def format_history_for_prompt(
        self, 
        messages: List[ChatMessage]
    ) -> str:
        """
        Format chat history for LLM prompt.
        
        Args:
            messages: List of chat messages
            
        Returns:
            Formatted string for prompt injection
        """
        if not messages:
            return ""
        
        lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "AI"
            # Truncate long messages
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            lines.append(f"{role_label}: {content}")
        
        return "\n".join(lines)
    
    def delete_user_history(self, user_id: str) -> int:
        """
        Delete all chat history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of messages deleted
        """
        if not self._available:
            return 0
        
        try:
            with self._session_factory() as session:
                deleted_count = 0
                
                if self._use_new_schema:
                    # Delete from chat_history table (CHỈ THỊ SỐ 04)
                    from sqlalchemy import text
                    # Sprint 160: Org-scoped deletion
                    from app.core.org_filter import get_effective_org_id, org_where_clause
                    eff_org_id = get_effective_org_id()
                    org_filter = org_where_clause(eff_org_id)
                    del_params = {"user_id": user_id}
                    if eff_org_id is not None:
                        del_params["org_id"] = eff_org_id
                    result = session.execute(
                        text(f"DELETE FROM chat_history WHERE user_id = :user_id{org_filter}"),
                        del_params
                    )
                    deleted_count = result.rowcount
                    session.commit()
                else:
                    # Delete from legacy schema
                    # First get all sessions for user
                    stmt = select(ChatSessionModel).where(
                        ChatSessionModel.user_id == user_id
                    )
                    sessions = session.execute(stmt).scalars().all()

                    # Get all session IDs first
                    session_ids = [s.session_id for s in sessions]

                    if session_ids:
                        # Batch delete messages (ONE query)
                        msg_result = session.query(ChatMessageModel).filter(
                            ChatMessageModel.session_id.in_(session_ids)
                        ).delete(synchronize_session=False)
                        deleted_count += msg_result

                        # Batch delete sessions (ONE query)
                        session.query(ChatSessionModel).filter(
                            ChatSessionModel.session_id.in_(session_ids)
                        ).delete(synchronize_session=False)

                        session.commit()
                
                logger.info("Deleted %d messages for user %s", deleted_count, user_id)
                return deleted_count
                
        except Exception as e:
            logger.error("Failed to delete user history: %s", e)
            return 0
    
    def get_user_history(
        self, 
        user_id: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> tuple[List[ChatMessage], int]:
        """
        Get paginated chat history for a user.
        
        Args:
            user_id: User identifier
            limit: Number of messages to return (default 20)
            offset: Offset for pagination (default 0)
            
        Returns:
            Tuple of (list of messages, total count)
            
        **Spec: CHỈ THỊ KỸ THUẬT SỐ 11**
        """
        if not self._available:
            return [], 0
        
        try:
            # Sprint 170c: Org-scoped filtering
            from app.core.org_filter import get_effective_org_id, org_where_clause
            eff_org_id = get_effective_org_id()
            org_filter = org_where_clause(eff_org_id)

            with self._session_factory() as session:
                if self._use_new_schema:
                    # Use CHỈ THỊ SỐ 04 schema (chat_history table)
                    from sqlalchemy import text

                    count_params = {"user_id": user_id}
                    if eff_org_id is not None:
                        count_params["org_id"] = eff_org_id

                    # Get total count
                    count_result = session.execute(
                        text(f"SELECT COUNT(*) FROM chat_history WHERE user_id = :user_id{org_filter}"),
                        count_params,
                    )
                    total = count_result.scalar() or 0

                    # Get paginated messages (newest first, then reverse for chronological order)
                    query_params = {"user_id": user_id, "limit": limit, "offset": offset}
                    if eff_org_id is not None:
                        query_params["org_id"] = eff_org_id

                    result = session.execute(
                        text(f"""
                            SELECT id, user_id, session_id, role, content, created_at
                            FROM chat_history
                            WHERE user_id = :user_id
                            {org_filter}
                            ORDER BY created_at DESC
                            LIMIT :limit OFFSET :offset
                        """),
                        query_params,
                    )
                    rows = result.fetchall()

                    messages = [
                        ChatMessage(
                            id=UUID(row[0]) if isinstance(row[0], str) else row[0],
                            session_id=UUID(row[2]) if isinstance(row[2], str) else UUID(row[2]),
                            role=row[3],
                            content=row[4],
                            created_at=row[5]
                        )
                        for row in reversed(rows)  # Reverse for chronological order
                    ]

                    return messages, total
                else:
                    # Legacy schema - get all sessions for user
                    from sqlalchemy import func

                    # Get total count across all sessions
                    stmt = select(ChatSessionModel).where(
                        ChatSessionModel.user_id == user_id
                    )
                    sessions = session.execute(stmt).scalars().all()
                    session_ids = [s.session_id for s in sessions]

                    if not session_ids:
                        return [], 0

                    # Count total messages
                    total = session.query(func.count(ChatMessageModel.id)).filter(
                        ChatMessageModel.session_id.in_(session_ids)
                    ).scalar() or 0

                    # Get paginated messages
                    results = session.query(ChatMessageModel).filter(
                        ChatMessageModel.session_id.in_(session_ids)
                    ).order_by(desc(ChatMessageModel.created_at)).offset(offset).limit(limit).all()

                    messages = [
                        ChatMessage(
                            id=msg.id,
                            session_id=msg.session_id,
                            role=msg.role,
                            content=msg.content,
                            created_at=msg.created_at
                        )
                        for msg in reversed(results)
                    ]

                    return messages, total

        except Exception as e:
            logger.error("Failed to get user history: %s", e)
            return [], 0


# Singleton instance
_chat_history_repo: Optional[ChatHistoryRepository] = None


def get_chat_history_repository() -> ChatHistoryRepository:
    """Get or create ChatHistoryRepository singleton."""
    global _chat_history_repo
    if _chat_history_repo is None:
        _chat_history_repo = ChatHistoryRepository()
    return _chat_history_repo
