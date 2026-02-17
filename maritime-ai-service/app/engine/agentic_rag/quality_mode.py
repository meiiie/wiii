"""
Quality Mode Presets - SOTA 2025 Self-Reflective RAG.

Provides preset configurations for different RAG quality/speed trade-offs.

Pattern References:
- LangGraph: Configurable agent parameters
- Self-RAG: Adaptive iteration based on context
- OpenAI/Anthropic: Quality tiers

Modes:
- speed: Fastest response, minimal iteration
- balanced: Default, good quality/speed balance  
- quality: Maximum accuracy, full reflection

Feature: self-reflective-rag-phase4
"""

from dataclasses import dataclass
from typing import Dict
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QualityModePreset:
    """Preset configuration for a quality mode."""
    name: str
    confidence_high: float
    confidence_medium: float
    max_iterations: int
    enable_reflection: bool
    early_exit: bool
    thinking_level: str
    enable_verification: bool
    description: str


# Quality mode presets
QUALITY_PRESETS: Dict[str, QualityModePreset] = {
    "speed": QualityModePreset(
        name="speed",
        confidence_high=0.70,      # Lower threshold = fewer iterations
        confidence_medium=0.50,
        max_iterations=1,           # Single pass only
        enable_reflection=False,    # Skip reflection for speed
        early_exit=True,
        thinking_level="low",       # Minimal Gemini thinking
        enable_verification=False,  # Skip verification
        description="Fastest response, minimal iteration. Best for simple queries."
    ),
    "balanced": QualityModePreset(
        name="balanced",
        confidence_high=0.85,       # Default threshold
        confidence_medium=0.60,
        max_iterations=2,           # Allow one correction
        enable_reflection=True,     # Enable Self-RAG
        early_exit=True,
        thinking_level="medium",    # Moderate reasoning
        enable_verification=True,   # Verify when complex
        description="Good quality/speed balance. Default for most queries."
    ),
    "quality": QualityModePreset(
        name="quality",
        confidence_high=0.92,       # High threshold = more thorough
        confidence_medium=0.75,
        max_iterations=3,           # Allow multiple corrections
        enable_reflection=True,     # Full Self-RAG
        early_exit=False,           # Don't exit early
        thinking_level="high",      # Maximum reasoning
        enable_verification=True,   # Always verify
        description="Maximum accuracy, full reflection. Best for complex/critical queries."
    ),
}


def get_quality_preset(mode: str = None) -> QualityModePreset:
    """
    Get quality mode preset.
    
    Args:
        mode: Quality mode name, uses settings.rag_quality_mode if None
        
    Returns:
        QualityModePreset for the specified mode
    """
    mode = mode or settings.rag_quality_mode
    
    if mode not in QUALITY_PRESETS:
        logger.warning("Unknown quality mode '%s', using 'balanced'", mode)
        mode = "balanced"
    
    preset = QUALITY_PRESETS[mode]
    logger.debug("[QualityMode] Using preset: %s", preset.name)
    
    return preset
