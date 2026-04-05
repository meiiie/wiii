"""
Pydantic schemas for AI Course Generation — used with .with_structured_output().

Follows existing pattern: structured_schemas.py, organization.py, etc.
Design spec v2.0 (2026-03-22), expert Fix 3.
"""

from typing import Optional

from pydantic import BaseModel, Field


# === OUTLINE (Node 1 output — teacher reviews this) ===

class LessonOutline(BaseModel):
    """One lesson in the course outline."""
    title: str
    type: str = "LECTURE"  # LECTURE, VIDEO, READING, QUIZ, ASSIGNMENT, DISCUSSION
    estimatedMinutes: int = Field(ge=5, le=120, default=30)
    sourcePages: list[int] = Field(default_factory=list)


class ChapterOutline(BaseModel):
    """One chapter in the course outline."""
    title: str
    description: str = ""
    orderIndex: int = Field(ge=0)
    estimatedLessons: int = Field(ge=1, le=20, default=3)
    keyTopics: list[str] = Field(default_factory=list)
    sourcePages: list[int] = Field(default_factory=list)
    dependsOn: list[int] = Field(default_factory=list)
    lessons: list[LessonOutline]


class CourseOutlineSchema(BaseModel):
    """Schema for .with_structured_output() — OUTLINE node.

    LLM generates this structure from document markdown.
    Teacher reviews and approves before content generation.
    """
    title: str
    description: str
    estimatedDuration: str = ""
    chapters: list[ChapterOutline] = Field(min_length=1, max_length=30)


# === CHAPTER CONTENT (Node 2 output — one chapter at a time) ===

class SectionContent(BaseModel):
    """One section within a lesson."""
    title: str
    type: str = "TEXT"  # TEXT, FILE, QUIZ_PLACEHOLDER, VIDEO, EMBED
    content: Optional[str] = None  # HTML for TEXT sections, null for QUIZ_PLACEHOLDER
    orderIndex: int = Field(ge=0)


class LessonContent(BaseModel):
    """One lesson with full section content."""
    title: str
    description: str = ""
    type: str = "LECTURE"
    orderIndex: int = Field(ge=0)
    durationMinutes: int = Field(ge=5, le=120, default=30)
    isFree: bool = False
    sections: list[SectionContent] = Field(min_length=1)


class ChapterContentSchema(BaseModel):
    """Schema for .with_structured_output() — EXPAND node.

    LLM generates full content for one chapter at a time.
    Per-chapter transaction on LMS side.
    """
    title: str
    description: str = ""
    orderIndex: int = Field(ge=0)
    lessons: list[LessonContent] = Field(min_length=1)
