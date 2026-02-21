"""Per-subagent configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class FallbackBehavior(str, Enum):
    """What to do when a subagent exhausts all retries."""

    RETURN_EMPTY = "return_empty"
    RAISE_ERROR = "raise_error"
    USE_PARENT = "use_parent"
    RETRY_DIFFERENT = "retry_different"


class SubagentConfig(BaseModel):
    """Configuration for a single subagent execution."""

    name: str = Field(..., min_length=1, max_length=64)
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    max_retries: int = Field(default=1, ge=0, le=3)
    fallback_behavior: FallbackBehavior = FallbackBehavior.RETURN_EMPTY
    max_iterations: int = Field(default=15, ge=1, le=50)
    llm_tier: str = Field(default="moderate", pattern=r"^(deep|moderate|light)$")
    streaming_enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Parallel execution settings
    parallel_enabled: bool = False
    max_parallel_workers: int = Field(default=3, ge=1, le=10)
