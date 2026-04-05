"""
LmsPushPort — Clean Architecture port for pushing content to LMS.

Abstracts the LMS API so that REST, MCP, or mock implementations
can be swapped via configuration.

Design spec v2.0 (2026-03-22).
"""

from abc import ABC, abstractmethod


class LmsPushPort(ABC):
    """Push generated course content to LMS Backend.

    Implementations: RestLmsPushAdapter (uses existing LMSPushService),
    McpLmsPushAdapter (future Phase 3), MockLmsPush (test).
    """

    @abstractmethod
    async def create_course_shell(self, request: dict) -> dict:
        """Create an empty course shell in LMS.

        Args:
            request: { teacherId, categoryId, title, description, deliveryMode, priceType }

        Returns:
            { courseId: str } on success.

        Raises:
            PushError: If LMS API returns error.
        """
        ...

    @abstractmethod
    async def push_chapter(self, course_id: str, chapter: dict) -> dict:
        """Push one completed chapter with lessons and sections to LMS.

        Args:
            course_id: UUID of the course (from create_course_shell).
            chapter: Full chapter content with nested lessons and sections.

        Returns:
            { chapterId: str, status: str } on success.

        Raises:
            PushError: If LMS API returns error.
        """
        ...
