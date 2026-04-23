"""
Soul Emotion — LLM-Driven Avatar Expression (Sprint 135).

Extracts inline emotion tags from LLM response text:
  <!--WIII_SOUL:{"mood":"warm","face":{"blush":0.3},"intensity":0.8}-->

Zero extra LLM cost (piggybacks on existing response generation).
Fallback: if LLM omits tag, existing keyword-based emotion detection
runs unchanged (zero behavioral impact when tag absent).

Tag format chosen for provider compatibility (Gemini, OpenAI, Ollama).
For guaranteed structured output, consider tool_use / response_schema
in future iterations.

Example:
    >>> result = extract_soul_emotion(
    ...     '<!--WIII_SOUL:{"mood":"warm","face":{"blush":0.3}}-->Hello!'
    ... )
    >>> result.emotion.mood
    'warm'
    >>> result.clean_text
    'Hello!'
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_MOODS = {"excited", "warm", "concerned", "gentle", "neutral"}

# Valid ranges for each FaceExpression field (must match avatar/types.ts)
_FACE_RANGES: Dict[str, Tuple[float, float]] = {
    "eyeOpenness": (0.5, 1.5),
    "pupilSize": (0.5, 1.5),
    "mouthCurve": (-1.0, 1.0),
    "mouthOpenness": (0.0, 1.0),
    "mouthWidth": (0.5, 1.5),
    "browRaise": (-1.0, 1.0),
    "browTilt": (-1.0, 1.0),
    "blush": (0.0, 1.0),
    "eyeShape": (0.0, 1.0),
    "mouthShape": (0.0, 4.0),
    "pupilOffsetX": (-1.0, 1.0),
    "pupilOffsetY": (-1.0, 1.0),
    "blinkRate": (5.0, 30.0),
}

# Max text length to scan (avoid regex on huge strings)
_MAX_SCAN_LENGTH = 2048

# Regex: tag at start of text (with optional leading whitespace).
# Non-greedy (.*?) stops at first "-->". re.DOTALL allows JSON with newlines.
_SOUL_TAG_RE = re.compile(r"^\s*<!--\s*WIII_SOUL:(.*?)-->", re.DOTALL)


@dataclass
class SoulEmotion:
    """Validated emotion data from LLM."""
    mood: str = "neutral"
    face: Dict[str, float] = field(default_factory=dict)
    intensity: float = 0.8


@dataclass
class ExtractionResult:
    """Result of soul emotion extraction from text."""
    emotion: Optional[SoulEmotion] = None
    clean_text: str = ""


def _validate_emotion(data: Dict[str, Any]) -> Optional[SoulEmotion]:
    """Validate and clamp emotion data from LLM JSON.

    All face fields and intensity are clamped to valid ranges.
    Unknown fields silently skipped. Invalid mood falls back to 'neutral'.
    """
    if not isinstance(data, dict):
        return None

    # Mood — case-insensitive for LLM robustness
    mood = data.get("mood", "neutral")
    if isinstance(mood, str):
        mood = mood.lower().strip()
    if mood not in VALID_MOODS:
        logger.debug("[SOUL] Invalid mood '%s', falling back to 'neutral'", mood)
        mood = "neutral"

    # Intensity — clamp to [0, 1]
    intensity = data.get("intensity", 0.8)
    if not isinstance(intensity, (int, float)):
        logger.debug("[SOUL] Non-numeric intensity '%s', using default 0.8", intensity)
        intensity = 0.8
    intensity = max(0.0, min(1.0, float(intensity)))

    # Face fields — validate and clamp each to its range
    raw_face = data.get("face", {})
    if not isinstance(raw_face, dict):
        raw_face = {}

    face: Dict[str, float] = {}
    for key, val in raw_face.items():
        if key not in _FACE_RANGES:
            continue
        if not isinstance(val, (int, float)):
            continue  # silently skip non-number fields
        lo, hi = _FACE_RANGES[key]
        face[key] = max(lo, min(hi, float(val)))

    return SoulEmotion(mood=mood, face=face, intensity=intensity)


def extract_soul_emotion(text: str) -> ExtractionResult:
    """
    Extract <!--WIII_SOUL:{...}--> tag from beginning of text.

    Returns ExtractionResult with:
      - emotion: parsed SoulEmotion if tag found, else None
      - clean_text: text with tag stripped

    Only the first tag is processed. Tag must be near the start
    (within first 2048 chars). Safe against ReDoS (non-greedy, no
    nested quantifiers, length-bounded).
    """
    if not text:
        return ExtractionResult(emotion=None, clean_text=text)

    # Length guard — only scan start of text for the tag
    scan_text = text[:_MAX_SCAN_LENGTH] if len(text) > _MAX_SCAN_LENGTH else text

    match = _SOUL_TAG_RE.search(scan_text)
    if not match:
        return ExtractionResult(emotion=None, clean_text=text)

    json_str = match.group(1).strip()
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[SOUL] Malformed JSON in soul tag: %s", json_str[:100])
        # Strip the malformed tag anyway
        clean = text[:match.start()] + text[match.end():]
        return ExtractionResult(emotion=None, clean_text=clean.lstrip())

    emotion = _validate_emotion(data)
    clean = text[:match.start()] + text[match.end():]

    if emotion:
        logger.debug(
            "[SOUL] Extracted: mood=%s, intensity=%.2f, face_fields=%d",
            emotion.mood, emotion.intensity, len(emotion.face),
        )

    return ExtractionResult(emotion=emotion, clean_text=clean.lstrip())
