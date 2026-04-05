"""Sprint 210d: SOTA LLM-based sentiment analysis for Living Agent.

Replaces fragile keyword matching with contextual LLM understanding.
The LLM already comprehends context, sarcasm, mixed languages, and nuance
— we just need to ask it.

Architecture:
    ChatOrchestrator/ChatStream → (response sent to user) → fire-and-forget
    → SentimentAnalyzer.analyze(message, response)
    → SentimentResult → EmotionEngine.process_event()

Zero user-facing latency. Runs fully async after response delivery.

SOTA references:
    - Nomi.ai: LLM inner monologue for emotion tracking
    - MECoT (2024): Multi-step Emotion Chain of Thought
    - Letta/MemGPT: Agent reasons about user emotional state
    - Anthropic model spec: "Describe WHO the AI IS, not WHAT it MUST NOT do"

Cost: Gemini Flash ~$0.00001/call → 10K messages/day = $0.10/day
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class SentimentResult(BaseModel):
    """LLM-analyzed sentiment from a conversation exchange."""

    user_sentiment: str = Field(
        default="neutral",
        description=(
            "The user's emotional state: "
            "positive, negative, neutral, curious, confused, "
            "frustrated, grateful, excited, dismissive"
        ),
    )
    intensity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="How strong the emotion is. 0.0 = barely noticeable, 1.0 = overwhelming",
    )
    life_event_type: str = Field(
        default="USER_CONVERSATION",
        description=(
            "What kind of life event this represents: "
            "USER_CONVERSATION, POSITIVE_FEEDBACK, NEGATIVE_FEEDBACK, "
            "LEARNING_MOMENT, HELP_REQUEST"
        ),
    )
    importance: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="How much this should affect Wiii's emotional state",
    )
    episode_summary: str = Field(
        default="",
        description="Natural language description of the experience from Wiii's perspective",
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an emotion analyst for Wiii — a Vietnamese AI companion for maritime students.
Your job: analyze a conversation exchange and assess the user's emotional state.

RULES:
- Consider the FULL context, not just individual words.
- Vietnamese users often type without diacritics (e.g. "cam on" = "cảm ơn").
- Detect sarcasm, irony, mixed signals, and implicit emotions.
- "importance" = how much this should affect Wiii's mood.
  A casual greeting = 0.1-0.2. Heartfelt thanks = 0.7-0.8. Harsh criticism = 0.6-0.8.
  A learning question = 0.3-0.4. Emotional sharing = 0.5-0.7.
- "episode_summary" = describe the experience from Wiii's first-person perspective,
  in Vietnamese, naturally (e.g. "Một bạn sinh viên cảm ơn mình vì giải thích COLREG dễ hiểu. Mình thấy tự hào.")

Return ONLY valid JSON with these fields:
{
  "user_sentiment": "<positive|negative|neutral|curious|confused|frustrated|grateful|excited|dismissive>",
  "intensity": <0.0-1.0>,
  "life_event_type": "<USER_CONVERSATION|POSITIVE_FEEDBACK|NEGATIVE_FEEDBACK|LEARNING_MOMENT|HELP_REQUEST>",
  "importance": <0.0-1.0>,
  "episode_summary": "<Vietnamese first-person summary>"
}"""

_USER_TEMPLATE = """\
User ({user_id}) said: "{user_message}"

Wiii responded: "{ai_response}"

Analyze the user's emotional state and this exchange's importance to Wiii."""

_MICRO_BANTER_EXACT = {
    "hehe",
    "he he",
    "haha",
    "ha ha",
    "hihi",
    "hi hi",
    "wow",
    "woa",
    "wao",
    "gi do",
    "gi vay",
    "ok",
    "alo",
    "uay",
    "ui",
    "oi",
}


def _normalize_micro_text(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", str(text or "").lower())
    stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    stripped = re.sub(r"[^a-z0-9\s!?]", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _looks_like_micro_banter(text: str) -> bool:
    normalized = _normalize_micro_text(text)
    if not normalized:
        return False
    if len(normalized) > 24 or len(normalized.split()) > 3:
        return False
    if normalized in _MICRO_BANTER_EXACT:
        return True
    collapsed = normalized.replace(" ", "")
    return bool(re.fullmatch(r"(he|ha|hi|huhu|hic|wow|woa|wao|ok|alo|uay|ui|oi)+", collapsed))


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """SOTA LLM-based sentiment analysis.

    Uses the LLM pool (Gemini Flash / configured provider) with structured
    output for fast, accurate, context-aware sentiment extraction.

    Fallback chain:
        1. LLM structured output (primary — fast, accurate)
        2. LLM raw JSON parse (if structured output fails)
        3. Default neutral result (never blocks, never crashes)
    """

    _TIMEOUT_SECONDS = 8  # Max time for LLM call

    async def analyze(
        self,
        user_message: str,
        ai_response: str,
        user_id: str = "unknown",
    ) -> SentimentResult:
        """Analyze sentiment using LLM. Returns SentimentResult always."""
        fast_path = self._fast_path_result(user_message, user_id)
        if fast_path is not None:
            return fast_path
        try:
            return await asyncio.wait_for(
                self._analyze_llm(user_message, ai_response, user_id),
                timeout=self._TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("[SENTIMENT] LLM analysis timed out (%ds)", self._TIMEOUT_SECONDS)
            return self._default_result(user_message, user_id)
        except Exception as e:
            logger.warning("[SENTIMENT] LLM analysis failed: %s", e)
            return self._default_result(user_message, user_id)

    async def _analyze_llm(
        self,
        user_message: str,
        ai_response: str,
        user_id: str,
    ) -> SentimentResult:
        """Primary path: LLM with structured output."""
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = self._get_llm()
        if llm is None:
            return self._default_result(user_message, user_id)

        # Try structured output first
        try:
            from app.services.structured_invoke_service import StructuredInvokeService

            result = await StructuredInvokeService.ainvoke(
                llm=llm,
                schema=SentimentResult,
                payload=[
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(content=_USER_TEMPLATE.format(
                        user_id=user_id,
                        user_message=user_message[:500],
                        ai_response=(ai_response or "")[:500],
                    )),
                ],
                tier="light",
            )
            if isinstance(result, SentimentResult):
                logger.debug(
                    "[SENTIMENT] LLM result: sentiment=%s intensity=%.2f importance=%.2f",
                    result.user_sentiment, result.intensity, result.importance,
                )
                return result
        except Exception as e:
            logger.debug("[SENTIMENT] Structured output failed (%s), trying raw JSON", e)

        # Fallback: raw invoke + parse JSON
        try:
            response = await llm.ainvoke([
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=_USER_TEMPLATE.format(
                    user_id=user_id,
                    user_message=user_message[:500],
                    ai_response=(ai_response or "")[:500],
                )),
            ])
            text = response.content if isinstance(response.content, str) else str(response.content)
            # Extract JSON from response (may be wrapped in markdown)
            json_str = text
            if "```" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
            data = json.loads(json_str)
            return SentimentResult(**data)
        except Exception as e2:
            logger.debug("[SENTIMENT] Raw JSON fallback also failed: %s", e2)

        return self._default_result(user_message, user_id)

    def _get_llm(self):
        """Get the lightest available LLM."""
        try:
            from app.engine.llm_pool import ThinkingTier, get_llm_for_provider

            return get_llm_for_provider(
                "auto",
                default_tier=ThinkingTier.LIGHT,
                strict_pin=False,
            )
        except Exception:
            pass
        try:
            from app.engine.llm_factory import create_llm, ThinkingTier
            return create_llm(tier=ThinkingTier.MINIMAL, temperature=0.3, include_thoughts=False)
        except Exception:
            pass
        return None

    @staticmethod
    def _fast_path_result(user_message: str, user_id: str) -> Optional[SentimentResult]:
        normalized = _normalize_micro_text(user_message)
        if not _looks_like_micro_banter(user_message):
            return None

        if normalized in {"wow", "woa", "wao"}:
            return SentimentResult(
                user_sentiment="excited",
                intensity=0.28,
                life_event_type="USER_CONVERSATION",
                importance=0.1,
                episode_summary="Người dùng vừa buông một tiếng reo ngắn để bắt nhịp với mình.",
            )

        if normalized in {"gi do", "gi vay"}:
            return SentimentResult(
                user_sentiment="curious",
                intensity=0.22,
                life_event_type="USER_CONVERSATION",
                importance=0.1,
                episode_summary="Người dùng vừa thả một nhịp nửa đùa nửa gợi mở để mình nối câu chuyện tiếp.",
            )

        return SentimentResult(
            user_sentiment="positive",
            intensity=0.16,
            life_event_type="USER_CONVERSATION",
            importance=0.08,
            episode_summary="Người dùng vừa gửi cho mình một nhịp xã giao rất ngắn và nhẹ.",
        )

    @staticmethod
    def _default_result(user_message: str, user_id: str) -> SentimentResult:
        """Safe default when LLM is unavailable."""
        return SentimentResult(
            user_sentiment="neutral",
            intensity=0.3,
            life_event_type="USER_CONVERSATION",
            importance=0.3,
            episode_summary=f"Mình vừa có một cuộc trò chuyện với {user_id}.",
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create the singleton SentimentAnalyzer."""
    global _instance
    if _instance is None:
        _instance = SentimentAnalyzer()
    return _instance
