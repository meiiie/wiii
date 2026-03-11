"""CharacterConfig — character reflection, personality, emotion."""
from pydantic import BaseModel


class CharacterConfig(BaseModel):
    """Character reflection, personality, emotion."""
    enable_reflection: bool = True
    reflection_interval: int = 5
    enable_tools: bool = True
    reflection_threshold: float = 5.0
    experience_retention_days: int = 90
    enable_emotional_state: bool = False
    emotional_decay_rate: float = 0.15
    enable_soul_emotion: bool = False
