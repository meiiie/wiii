"""SQLAlchemy models for the active Wiii database schema."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.schemas import utc_now


class Base(DeclarativeBase):
    """Base class for all database models."""


class ChatHistoryModel(Base):
    """Canonical chat history table used for session/message persistence."""

    __tablename__ = "chat_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    session_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )
    is_blocked: Mapped[bool] = mapped_column(
        default=False,
        index=True,
    )
    block_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    user_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )


class DatabaseManager:
    """Manages SQLAlchemy engine lifecycle for local utility code."""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._engine = None

    def get_engine(self):
        """Get or create the underlying engine."""
        if self._engine is None:
            self._engine = create_engine(
                self._database_url,
                echo=False,
                pool_pre_ping=True,
            )
        return self._engine

    def create_tables(self):
        """Create all currently active ORM tables."""
        engine = self.get_engine()
        Base.metadata.create_all(engine)

    def drop_tables(self):
        """Drop all ORM-managed tables."""
        engine = self.get_engine()
        Base.metadata.drop_all(engine)
