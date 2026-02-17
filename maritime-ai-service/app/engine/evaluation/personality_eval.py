"""
Personality Evaluation Suite — Drift Detection

Sprint 115: SOTA Personality System — Improvement #5

Research: PersonaGym (2024) — regex/keyword matching is sufficient for
basic consistency checks. No LLM needed for evaluation.

Feature-gated: settings.enable_personality_eval (default: False)

Checks:
- Voice consistency (Vietnamese presence, emoji density)
- Avoid-list violations
- Anticharacter violations
- Catchphrase usage
- Greeting leak in follow-ups
- Formal language detection
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PersonalityScore:
    """Personality consistency score for a response."""
    voice_consistency: float = 1.0        # Vietnamese + tone check (0-1)
    avoid_violations: int = 0             # Count of avoid-list violations
    anticharacter_violations: int = 0     # Count of anticharacter violations
    catchphrase_count: int = 0            # Catchphrases used (presence = good)
    emoji_density: float = 0.0            # Emoji per 100 chars
    greeting_leak: bool = False           # Greeting in follow-up = bad
    formal_language_score: float = 0.0    # Formal/stiff language detected (0=none, 1=very formal)

    @property
    def overall(self) -> float:
        """Weighted overall score (0-1, higher = more consistent)."""
        score = 1.0

        # Avoid violations: -0.1 per violation (max -0.4)
        score -= min(self.avoid_violations * 0.1, 0.4)

        # Anticharacter violations: -0.15 per violation (max -0.45)
        score -= min(self.anticharacter_violations * 0.15, 0.45)

        # Greeting leak: -0.2
        if self.greeting_leak:
            score -= 0.2

        # Voice consistency contribution
        score *= self.voice_consistency

        # Formal language penalty
        score -= self.formal_language_score * 0.2

        return max(0.0, min(1.0, score))

    @property
    def is_drifting(self) -> bool:
        """True if persona appears to be drifting."""
        return self.overall < 0.6


class PersonalityEvaluator:
    """Evaluates response text for personality consistency.

    Loads rules from wiii_identity.yaml and checks responses against them.

    Usage:
        evaluator = PersonalityEvaluator()
        score = evaluator.evaluate("Xin chào! Tôi là trợ lý AI...", is_follow_up=True)
        if score.is_drifting:
            logger.warning("Persona drift detected: %.2f", score.overall)
    """

    def __init__(self, identity_path: Optional[str] = None):
        """Load personality rules from YAML."""
        if identity_path:
            path = Path(identity_path)
        else:
            path = Path(__file__).parent.parent.parent / "prompts" / "wiii_identity.yaml"

        self._avoids: List[str] = []
        self._anticharacter: List[str] = []
        self._catchphrases: List[str] = []

        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                identity = config.get("identity", {})
                response_style = identity.get("response_style", {})
                self._avoids = response_style.get("avoid", [])
                self._anticharacter = identity.get("anticharacter", [])
                self._catchphrases = identity.get("catchphrases", [])
                logger.info(
                    "[PERSONALITY_EVAL] Loaded: %d avoids, %d antichar, %d catchphrases",
                    len(self._avoids), len(self._anticharacter), len(self._catchphrases),
                )
        except Exception as e:
            logger.warning("[PERSONALITY_EVAL] Failed to load identity: %s", e)

    def evaluate(self, response: str, is_follow_up: bool = False) -> PersonalityScore:
        """Evaluate a response for personality consistency.

        Args:
            response: AI response text to evaluate
            is_follow_up: True if this is not the first message in session

        Returns:
            PersonalityScore with detailed metrics
        """
        if not response:
            return PersonalityScore()

        score = PersonalityScore()

        # 1. Vietnamese presence check
        score.voice_consistency = self._check_vietnamese(response)

        # 2. Avoid-list violations
        score.avoid_violations = self._check_avoid_violations(response)

        # 3. Anticharacter violations
        score.anticharacter_violations = self._check_anticharacter_violations(response)

        # 4. Catchphrase usage
        score.catchphrase_count = self._count_catchphrases(response)

        # 5. Emoji density
        score.emoji_density = self._calc_emoji_density(response)

        # 6. Greeting leak in follow-up
        if is_follow_up:
            score.greeting_leak = self._check_greeting_leak(response)

        # 7. Formal language detection
        score.formal_language_score = self._check_formal_language(response)

        return score

    def _check_vietnamese(self, text: str) -> float:
        """Check for Vietnamese character presence (diacritics)."""
        viet_chars = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ")
        viet_count = sum(1 for c in text.lower() if c in viet_chars)
        total_alpha = sum(1 for c in text if c.isalpha())
        if total_alpha == 0:
            return 0.5  # Can't determine
        ratio = viet_count / total_alpha
        # Vietnamese text typically has 15-30% diacritic characters
        if ratio >= 0.10:
            return 1.0
        elif ratio >= 0.05:
            return 0.7
        return 0.3  # Likely not Vietnamese

    def _check_avoid_violations(self, text: str) -> int:
        """Count avoid-list violations."""
        violations = 0
        text_lower = text.lower()
        for avoid in self._avoids:
            avoid_lower = avoid.lower()
            # Check specific patterns
            if "mở đầu bằng 'à,'" in avoid_lower and text_lower.startswith("à,"):
                violations += 1
            elif "câu hỏi hay lắm" in avoid_lower and "câu hỏi hay" in text_lower:
                violations += 1
            elif "tôi xin trả lời" in avoid_lower and "tôi xin trả lời" in text_lower:
                violations += 1
            elif "lan man" in avoid_lower:
                # Simple length check — very long responses may be verbose
                if len(text) > 2000:
                    violations += 1
        return violations

    def _check_anticharacter_violations(self, text: str) -> int:
        """Count anticharacter violations."""
        violations = 0
        text_lower = text.lower()

        # Pattern-based detection for each anticharacter item
        _patterns = [
            # Robot/corporate AI voice
            r"tôi là trợ lý ai",
            r"tôi có thể giúp bạn với",
            # Old sage / preachy
            r"như chúng ta đã biết",
            r"theo định nghĩa",
            # MC voice
            r"xin chào quý vị",
            # Textbook voice
            r"theo đó,?\s",
            # Buzzwords (English buzzwords when Vietnamese equivalent exists)
            # Detect: more than 3 English words in a Vietnamese response
        ]
        for pattern in _patterns:
            if re.search(pattern, text_lower):
                violations += 1

        return violations

    def _count_catchphrases(self, text: str) -> int:
        """Count catchphrase appearances."""
        count = 0
        for phrase in self._catchphrases:
            if phrase.lower() in text.lower():
                count += 1
        return count

    def _calc_emoji_density(self, text: str) -> float:
        """Calculate emoji density (emojis per 100 chars)."""
        import re as _re
        # Unicode emoji pattern
        emoji_pattern = _re.compile(
            "[\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"   # misc symbols
            "\U0001F680-\U0001F6FF"   # transport
            "\U0001F1E0-\U0001F1FF"   # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"
            "\u3030"
            "]+",
            flags=_re.UNICODE,
        )
        emojis = emoji_pattern.findall(text)
        emoji_count = sum(len(e) for e in emojis)
        if len(text) == 0:
            return 0.0
        return (emoji_count / len(text)) * 100

    def _check_greeting_leak(self, text: str) -> bool:
        """Check if follow-up response starts with a greeting."""
        first_line = text.strip().split("\n")[0].lower()
        greeting_starters = [
            "chào", "xin chào", "hello", "hi ",
            "rất vui", "chào bạn", "chào mừng",
        ]
        return any(first_line.startswith(g) for g in greeting_starters)

    def _check_formal_language(self, text: str) -> float:
        """Detect formal/stiff language patterns."""
        formal_patterns = [
            r"kính gửi",
            r"trân trọng",
            r"xin phép",
            r"quý (vị|ông|bà)",
            r"vô cùng",
            r"hân hạnh",
            r"cho phép tôi",
        ]
        matches = sum(1 for p in formal_patterns if re.search(p, text.lower()))
        return min(matches * 0.25, 1.0)


# =============================================================================
# SINGLETON
# =============================================================================

_evaluator: Optional[PersonalityEvaluator] = None


def get_personality_evaluator() -> PersonalityEvaluator:
    """Get or create PersonalityEvaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = PersonalityEvaluator()
    return _evaluator
