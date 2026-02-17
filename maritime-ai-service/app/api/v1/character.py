"""
Character State API — Sprint 120
GET /api/v1/character/state — returns Wiii's character blocks for UI display.

Exposes the internal CharacterStateManager to the desktop app.
Feature-gated: settings.enable_character_tools (default: True)
"""
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import List

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/character", tags=["character"])


class CharacterBlockResponse(BaseModel):
    """A single character block."""
    label: str
    content: str = ""
    char_limit: int = 1000
    usage_percent: float = Field(0.0, description="Percentage of char_limit used")


class CharacterStateResponse(BaseModel):
    """Full character state response."""
    blocks: List[CharacterBlockResponse] = []
    total_blocks: int = 0


@router.get("/state", response_model=CharacterStateResponse)
@limiter.limit("30/minute")
async def get_character_state(
    request: Request,
    auth: RequireAuth,
) -> CharacterStateResponse:
    """
    Get Wiii's current character state (all blocks).

    Returns character blocks with content and usage statistics.
    Feature-gated: requires enable_character_tools=True.
    """
    try:
        from app.core.config import settings
        if not settings.enable_character_tools:
            return CharacterStateResponse()

        from app.engine.character.character_state import get_character_state_manager
        manager = get_character_state_manager()
        # Sprint 124: Per-user character blocks
        blocks_dict = manager.get_blocks(user_id=str(auth.user_id))

        blocks = []
        for label, block in blocks_dict.items():
            content_len = len(block.content) if block.content else 0
            char_limit = block.char_limit or 1000
            usage = min((content_len / char_limit) * 100, 100.0) if char_limit > 0 else 0.0
            blocks.append(CharacterBlockResponse(
                label=label,
                content=block.content or "",
                char_limit=char_limit,
                usage_percent=round(usage, 1),
            ))

        return CharacterStateResponse(
            blocks=blocks,
            total_blocks=len(blocks),
        )
    except Exception as e:
        logger.warning("[CHARACTER_API] Failed to get state: %s", e)
        return CharacterStateResponse()
