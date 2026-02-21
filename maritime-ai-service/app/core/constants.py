"""
Wiii Platform Constants

Centralized magic numbers and threshold values used across the platform.
Change values here instead of hunting through multiple files.
"""

# =============================================================================
# Content Truncation Limits
# =============================================================================

MAX_CONTENT_SNIPPET_LENGTH = 200
"""Max characters for content snippets in API responses and previews."""

MAX_DOCUMENT_PREVIEW_LENGTH = 1000
"""Max characters for full document content sent to LLM grading."""

# =============================================================================
# Confidence Scoring
# =============================================================================

CONFIDENCE_BASE = 0.5
"""Base confidence score when sources are present."""

CONFIDENCE_PER_SOURCE = 0.1
"""Confidence increment per additional source document."""

CONFIDENCE_MAX = 1.0
"""Maximum confidence score cap."""

# =============================================================================
# Health Checks
# =============================================================================

HEALTH_CHECK_TIMEOUT = 5
"""Timeout in seconds for individual health check operations."""

# =============================================================================
# RAG Pipeline Defaults
# =============================================================================

DEFAULT_RELEVANCE_THRESHOLD = 7.0
"""Default minimum score for a document to be considered relevant."""

# =============================================================================
# Embedding Validation
# =============================================================================

EXPECTED_EMBEDDING_DIMENSIONS = 768
"""Expected embedding vector dimensions (Gemini embedding-001 default)."""

# =============================================================================
# Preview System (Sprint 166)
# =============================================================================

PREVIEW_SNIPPET_MAX_LENGTH = 300
"""Max characters for preview card snippet text."""

PREVIEW_TITLE_MAX_LENGTH = 120
"""Max characters for preview card title."""

PREVIEW_MAX_PER_MESSAGE = 20
"""Max preview cards emitted per single message/response."""

PREVIEW_CONFIDENCE_THRESHOLD = 0.3
"""Minimum relevance score for a source to generate a preview card."""
