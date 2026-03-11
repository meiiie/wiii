"""LivingAgentConfig — autonomous life, browsing, learning, emotion (Sprint 170)."""
from typing import Optional

from pydantic import BaseModel


class LivingAgentConfig(BaseModel):
    """Living Agent — autonomous life, browsing, learning, emotion (Sprint 170)."""
    enabled: bool = False
    heartbeat_interval: int = 1800
    active_hours_start: int = 8
    active_hours_end: int = 23
    local_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    max_browse_items: int = 10
    enable_social_browse: bool = False
    enable_skill_building: bool = False
    enable_journal: bool = True
    require_human_approval: bool = True
    max_actions_per_heartbeat: int = 3
    max_skills_per_week: int = 5
    max_searches_per_heartbeat: int = 3
    max_daily_cycles: int = 48
    callmebot_api_key: Optional[str] = None
    notification_channel: str = "websocket"
    # Sprint 177: Skill Learning
    enable_skill_learning: bool = False
    quiz_questions_per_session: int = 3
    review_confidence_weight: float = 0.3
