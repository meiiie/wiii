"""ThinkingConfig — deep reasoning and thinking budget."""
from pydantic import BaseModel


class ThinkingConfig(BaseModel):
    """Deep reasoning and thinking budget."""
    enabled: bool = True
    include_summaries: bool = True
    budget_deep: int = 8192
    budget_moderate: int = 4096
    budget_light: int = 1024
    budget_minimal: int = 512
    gemini_level: str = "medium"
    enable_chain: bool = False
