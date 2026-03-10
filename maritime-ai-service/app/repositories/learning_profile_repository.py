"""
Learning Profile Repository.

This module provides the repository pattern implementation for
Learning Profile persistence operations.

**Feature: wiii**
**Validates: Requirements 6.1, 6.3, 6.4**
**Spec: CHỈ THỊ KỸ THUẬT SỐ 04 - Memory & Personalization**
"""

import json
import logging
from typing import Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy import text

from app.models.learning_profile import (
    Assessment,
    LearnerLevel,
    LearningProfile,
    LearningStyle,
    create_default_profile,
)

logger = logging.getLogger(__name__)


class ILearningProfileRepository(Protocol):
    """
    Interface for Learning Profile repository operations.
    
    Defines the contract for CRUD operations on learning profiles.
    """
    
    async def get(self, user_id: UUID) -> Optional[LearningProfile]:
        """Get a learning profile by user ID."""
        ...
    
    async def create(self, profile: LearningProfile) -> LearningProfile:
        """Create a new learning profile."""
        ...
    
    async def update(self, profile: LearningProfile) -> LearningProfile:
        """Update an existing learning profile."""
        ...
    
    async def delete(self, user_id: UUID) -> bool:
        """Delete a learning profile."""
        ...
    
    async def get_or_create(self, user_id: UUID) -> LearningProfile:
        """Get existing profile or create default one."""
        ...


class InMemoryLearningProfileRepository:
    """
    In-memory implementation of Learning Profile repository.
    
    Used for development and testing. Production should use
    PostgreSQL-backed implementation.
    
    **Validates: Requirements 6.1, 6.3, 6.4**
    """
    
    def __init__(self):
        """Initialize with empty storage."""
        self._profiles: Dict[UUID, LearningProfile] = {}
    
    async def get(self, user_id: UUID) -> Optional[LearningProfile]:
        """
        Get a learning profile by user ID.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            LearningProfile if found, None otherwise
            
        **Validates: Requirements 6.3**
        """
        return self._profiles.get(user_id)

    
    async def create(self, profile: LearningProfile) -> LearningProfile:
        """
        Create a new learning profile.
        
        Args:
            profile: The profile to create
            
        Returns:
            The created profile
            
        Raises:
            ValueError: If profile already exists
        """
        if profile.user_id in self._profiles:
            raise ValueError(f"Profile already exists for user {profile.user_id}")
        
        self._profiles[profile.user_id] = profile
        logger.info("Created learning profile for user %s", profile.user_id)
        return profile
    
    async def update(self, profile: LearningProfile) -> LearningProfile:
        """
        Update an existing learning profile.
        
        Args:
            profile: The profile with updated data
            
        Returns:
            The updated profile
            
        **Validates: Requirements 6.4**
        """
        self._profiles[profile.user_id] = profile
        logger.debug("Updated learning profile for user %s", profile.user_id)
        return profile
    
    async def delete(self, user_id: UUID) -> bool:
        """
        Delete a learning profile.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            True if deleted, False if not found
        """
        if user_id in self._profiles:
            del self._profiles[user_id]
            logger.info("Deleted learning profile for user %s", user_id)
            return True
        return False
    
    async def get_or_create(self, user_id: UUID) -> LearningProfile:
        """
        Get existing profile or create default one.
        
        This is the primary method for ensuring a user has a profile.
        Creates with default values if not exists.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            Existing or newly created LearningProfile
            
        **Validates: Requirements 6.1**
        """
        profile = await self.get(user_id)
        if profile is None:
            profile = create_default_profile(user_id)
            await self.create(profile)
            logger.info("Created default profile for new user %s", user_id)
        return profile
    
    async def add_assessment(
        self, 
        user_id: UUID, 
        assessment: Assessment
    ) -> LearningProfile:
        """
        Add an assessment to a user's profile.
        
        Automatically updates weak_topics and completed_topics.
        
        Args:
            user_id: The user's unique identifier
            assessment: The assessment to add
            
        Returns:
            Updated LearningProfile
            
        **Validates: Requirements 6.2**
        """
        profile = await self.get_or_create(user_id)
        profile.add_assessment(assessment)
        return await self.update(profile)
    
    async def update_level(
        self, 
        user_id: UUID, 
        level: LearnerLevel
    ) -> LearningProfile:
        """
        Update a user's proficiency level.
        
        Args:
            user_id: The user's unique identifier
            level: The new level
            
        Returns:
            Updated LearningProfile
        """
        profile = await self.get_or_create(user_id)
        profile.current_level = level
        return await self.update(profile)
    
    async def update_learning_style(
        self, 
        user_id: UUID, 
        style: LearningStyle
    ) -> LearningProfile:
        """
        Update a user's learning style preference.
        
        Args:
            user_id: The user's unique identifier
            style: The preferred learning style
            
        Returns:
            Updated LearningProfile
        """
        profile = await self.get_or_create(user_id)
        profile.learning_style = style
        return await self.update(profile)
    
    def count(self) -> int:
        """Get total number of profiles."""
        return len(self._profiles)
    
    def clear(self) -> None:
        """Clear all profiles (for testing)."""
        self._profiles.clear()


class LearningProfileRepository:
    """
    PostgreSQL implementation of Learning Profile repository.
    
    Uses the learning_profile table created by CHỈ THỊ SỐ 04 SQL script.
    
    **Spec: CHỈ THỊ KỸ THUẬT SỐ 04**
    **Validates: Requirements 6.1, 6.3, 6.4**
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize with SHARED database connection."""
        self._engine = None
        self._session_factory = None
        self._available = False
        self._init_connection()
    
    def _init_connection(self):
        """Initialize database connection using SHARED engine."""
        try:
            # Use SHARED engine to minimize connections
            from app.core.database import get_shared_engine, get_shared_session_factory
            
            self._engine = get_shared_engine()
            self._session_factory = get_shared_session_factory()
            
            # Test connection
            with self._session_factory() as session:
                session.execute(text("SELECT 1"))
            
            self._available = True
            logger.info("Learning profile repository using SHARED database engine")
        except Exception as e:
            logger.warning("Learning profile repository connection failed: %s", e)
            self._available = False
    
    def is_available(self) -> bool:
        """Check if repository is available."""
        return self._available
    
    async def get(self, user_id: str) -> Optional[dict]:
        """
        Get a learning profile by user ID.

        Args:
            user_id: The user's unique identifier (string from LMS)

        Returns:
            Profile dict if found, None otherwise
        """
        if not self._available:
            return None

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            user_id_param = str(self._convert_user_id(user_id))
            params: dict = {"user_id": user_id_param}
            if eff_org_id is not None:
                params["org_id"] = eff_org_id

            with self._session_factory() as session:
                result = session.execute(
                    text(f"""
                        SELECT user_id, attributes, weak_areas, strong_areas,
                               total_sessions, total_messages, updated_at
                        FROM learning_profile
                        WHERE user_id = :user_id{org_filter}
                    """),
                    params,
                )
                row = result.fetchone()

                if row:
                    return {
                        "user_id": str(row[0]),
                        "attributes": row[1] or {},
                        "weak_areas": row[2] or [],
                        "strong_areas": row[3] or [],
                        "total_sessions": row[4] or 0,
                        "total_messages": row[5] or 0,
                        "updated_at": row[6]
                    }
                return None
        except Exception as e:
            logger.error("Failed to get learning profile: %s", e)
            return None
    
    def _convert_user_id(self, user_id: str):
        """
        Convert user_id to UUID if it's a valid UUID string.
        Otherwise return as-is for TEXT column compatibility.
        """
        try:
            # Try to parse as UUID
            return UUID(user_id)
        except (ValueError, TypeError):
            # Not a valid UUID, return as string
            # This handles cases like "test-user"
            return user_id
    
    async def create(self, user_id: str, attributes: dict = None) -> Optional[dict]:
        """
        Create a new learning profile.

        Args:
            user_id: The user's unique identifier
            attributes: Initial attributes (level, style, language)

        Returns:
            The created profile dict
        """
        if not self._available:
            return None

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id
        eff_org_id = get_effective_org_id()

        try:
            user_id_param = str(self._convert_user_id(user_id))
            insert_cols = "user_id, attributes"
            insert_vals = ":user_id, :attributes"
            params: dict = {
                "user_id": user_id_param,
                "attributes": json.dumps(attributes or {"level": "beginner"}),
            }
            if eff_org_id is not None:
                insert_cols += ", organization_id"
                insert_vals += ", :org_id"
                params["org_id"] = eff_org_id

            with self._session_factory() as session:
                session.execute(
                    text(f"""
                        INSERT INTO learning_profile ({insert_cols})
                        VALUES ({insert_vals})
                        ON CONFLICT (user_id) DO NOTHING
                    """),
                    params,
                )
                session.commit()
                logger.info("Created learning profile for user %s", user_id)
                return await self.get(user_id)
        except Exception as e:
            logger.error("Failed to create learning profile: %s", e)
            return None
    
    async def get_or_create(self, user_id: str) -> Optional[dict]:
        """
        Get existing profile or create default one.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            Existing or newly created profile dict
        """
        profile = await self.get(user_id)
        if profile is None:
            profile = await self.create(user_id)
        return profile
    
    async def update_weak_areas(self, user_id: str, weak_areas: List[str]) -> bool:
        """
        Update user's weak areas.

        Args:
            user_id: The user's unique identifier
            weak_areas: List of weak topic names

        Returns:
            True if successful
        """
        if not self._available:
            return False

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            user_id_param = str(self._convert_user_id(user_id))
            params: dict = {
                "user_id": user_id_param,
                "weak_areas": json.dumps(weak_areas),
            }
            if eff_org_id is not None:
                params["org_id"] = eff_org_id

            with self._session_factory() as session:
                session.execute(
                    text(f"""
                        UPDATE learning_profile
                        SET weak_areas = :weak_areas, updated_at = NOW()
                        WHERE user_id = :user_id{org_filter}
                    """),
                    params,
                )
                session.commit()
                logger.info("Updated weak areas for user %s", user_id)
                return True
        except Exception as e:
            logger.error("Failed to update weak areas: %s", e)
            return False
    
    async def update_strong_areas(self, user_id: str, strong_areas: List[str]) -> bool:
        """
        Update user's strong areas.

        Args:
            user_id: The user's unique identifier
            strong_areas: List of strong topic names

        Returns:
            True if successful
        """
        if not self._available:
            return False

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            user_id_param = str(self._convert_user_id(user_id))
            params: dict = {
                "user_id": user_id_param,
                "strong_areas": json.dumps(strong_areas),
            }
            if eff_org_id is not None:
                params["org_id"] = eff_org_id

            with self._session_factory() as session:
                session.execute(
                    text(f"""
                        UPDATE learning_profile
                        SET strong_areas = :strong_areas, updated_at = NOW()
                        WHERE user_id = :user_id{org_filter}
                    """),
                    params,
                )
                session.commit()
                logger.info("Updated strong areas for user %s", user_id)
                return True
        except Exception as e:
            logger.error("Failed to update strong areas: %s", e)
            return False
    
    async def increment_stats(self, user_id: str, messages: int = 1) -> bool:
        """
        Increment user's message count.

        Args:
            user_id: The user's unique identifier
            messages: Number of messages to add

        Returns:
            True if successful
        """
        if not self._available:
            return False

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            await self.get_or_create(user_id)
            user_id_param = str(self._convert_user_id(user_id))
            params: dict = {"user_id": user_id_param, "messages": messages}
            if eff_org_id is not None:
                params["org_id"] = eff_org_id

            with self._session_factory() as session:
                session.execute(
                    text(f"""
                        UPDATE learning_profile
                        SET total_messages = total_messages + :messages,
                            updated_at = NOW()
                        WHERE user_id = :user_id{org_filter}
                    """),
                    params,
                )
                session.commit()
                return True
        except Exception as e:
            logger.error("Failed to increment stats: %s", e)
            return False


# Singleton instance
_pg_profile_repo: Optional[LearningProfileRepository] = None


def get_learning_profile_repository() -> LearningProfileRepository:
    """Get or create PostgreSQL LearningProfileRepository singleton."""
    global _pg_profile_repo
    if _pg_profile_repo is None:
        _pg_profile_repo = LearningProfileRepository()
    return _pg_profile_repo
