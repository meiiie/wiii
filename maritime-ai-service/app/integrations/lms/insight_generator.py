"""
LMS Insight Generator — Sprint 220: "Cắm Phích" Production Connection

Post-conversation analysis: extracts pedagogical insights from AI chat
and pushes them to LMS for the teacher dashboard.

Runs as fire-and-forget after each chat response (zero latency impact).

Insight types:
  - knowledge_gap: Student asked about a topic they scored low on
  - confusion: Student asked the same concept multiple times
  - strength: Student demonstrated mastery beyond grade level
  - engagement: Student actively exploring beyond curriculum

Feature-gated: enable_lms_integration=True required.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.integrations.lms.context_loader import LMSStudentContext

logger = logging.getLogger(__name__)


@dataclass
class LMSInsight:
    """A single pedagogical insight from an AI conversation."""

    insight_type: str  # knowledge_gap | confusion | strength | engagement
    content: str  # Vietnamese description
    related_course_id: Optional[str] = None
    related_course_name: Optional[str] = None
    confidence: float = 0.7


class LMSInsightGenerator:
    """Generates pedagogical insights from AI conversations for LMS push.

    Uses rule-based analysis (no LLM call) to keep cost zero and latency low.
    LLM-based deep analysis can be added in a future sprint.
    """

    def analyze_conversation(
        self,
        user_id: str,
        message: str,
        response: str,
        lms_context: Optional[LMSStudentContext] = None,
    ) -> List[LMSInsight]:
        """Generate insights from a single chat exchange.

        Args:
            user_id: Student's Wiii user ID
            message: Student's question
            response: AI's response
            lms_context: Student's LMS data (if loaded)

        Returns:
            List of insights (may be empty if nothing notable)
        """
        insights: List[LMSInsight] = []

        if not message or not response:
            return insights

        message_lower = message.lower()

        # Skip trivial messages (greetings, thanks)
        if len(message_lower) < 15 or _is_trivial_message(message_lower):
            return insights

        # Analysis 1: Knowledge gap detection
        if lms_context and lms_context.grades:
            gap_insight = self._detect_knowledge_gap(
                message_lower, lms_context
            )
            if gap_insight:
                insights.append(gap_insight)

        # Analysis 2: Engagement detection (exploring beyond curriculum)
        engagement_insight = self._detect_engagement(
            message_lower, response, lms_context
        )
        if engagement_insight:
            insights.append(engagement_insight)

        # Analysis 3: Confusion signals
        confusion_insight = self._detect_confusion(message_lower)
        if confusion_insight:
            insights.append(confusion_insight)

        return insights

    def _detect_knowledge_gap(
        self,
        message_lower: str,
        lms_context: LMSStudentContext,
    ) -> Optional[LMSInsight]:
        """Check if student is asking about a topic they scored low on."""
        # Find courses with low grades (<60%)
        weak_courses = []
        for g in lms_context.grades:
            pct = g.get("percentage", 0)
            if pct < 60:
                weak_courses.append(g)

        if not weak_courses:
            return None

        # Check if the message mentions any weak course topic
        for g in weak_courses:
            course_name = (g.get("course_name") or "").lower()
            if not course_name:
                continue
            # Simple keyword check: does the message reference this course?
            keywords = course_name.split()
            match_count = sum(1 for kw in keywords if kw in message_lower and len(kw) > 2)
            if match_count >= 2 or (len(keywords) <= 2 and match_count >= 1):
                return LMSInsight(
                    insight_type="knowledge_gap",
                    content=(
                        f"Sinh viên đang hỏi về chủ đề liên quan đến {g.get('course_name')}, "
                        f"môn này có điểm thấp ({g.get('percentage', 0):.0f}%). "
                        f"Sinh viên có thể cần hỗ trợ thêm."
                    ),
                    related_course_id=g.get("course_id"),
                    related_course_name=g.get("course_name"),
                    confidence=0.75,
                )

        return None

    def _detect_engagement(
        self,
        message_lower: str,
        response: str,
        lms_context: Optional[LMSStudentContext],
    ) -> Optional[LMSInsight]:
        """Detect if student is exploring beyond basic curriculum."""
        # Keywords indicating deep exploration
        deep_signals = [
            "tại sao", "vì sao", "giải thích", "phân tích",
            "so sánh", "khác biệt", "ứng dụng", "thực tế",
            "nâng cao", "chuyên sâu", "nghiên cứu", "tham khảo thêm",
        ]
        signal_count = sum(1 for s in deep_signals if s in message_lower)

        if signal_count >= 2 and len(message_lower) > 50:
            return LMSInsight(
                insight_type="engagement",
                content=(
                    "Sinh viên thể hiện sự tò mò và chủ động tìm hiểu sâu. "
                    "Có thể hưởng lợi từ tài liệu nâng cao hoặc dự án nghiên cứu."
                ),
                confidence=0.65,
            )

        return None

    def _detect_confusion(self, message_lower: str) -> Optional[LMSInsight]:
        """Detect confusion signals in the question."""
        confusion_signals = [
            "không hiểu", "khó quá", "giải thích lại",
            "vẫn chưa rõ", "lần nữa", "bối rối",
            "em không biết", "mình không hiểu",
            "sao lại", "tại sao không", "mâu thuẫn",
        ]
        signal_count = sum(1 for s in confusion_signals if s in message_lower)

        if signal_count >= 1:
            return LMSInsight(
                insight_type="confusion",
                content=(
                    "Sinh viên gặp khó khăn trong việc hiểu nội dung. "
                    "Có thể cần giảng viên giải thích thêm hoặc cung cấp bài tập bổ sung."
                ),
                confidence=0.70,
            )

        return None


async def analyze_and_push_insights(
    user_id: str,
    message: str,
    response: str,
    lms_context: Optional[LMSStudentContext] = None,
    connector_id: str = "maritime-lms",
) -> None:
    """Fire-and-forget: Analyze conversation and push insights to LMS.

    Called via asyncio.ensure_future() after chat response.
    Never raises exceptions — logs and swallows all errors.
    """
    try:
        generator = LMSInsightGenerator()
        insights = generator.analyze_conversation(
            user_id=user_id,
            message=message,
            response=response,
            lms_context=lms_context,
        )

        if not insights:
            return

        # Push to LMS via existing push service
        from app.integrations.lms.push_service import get_push_service

        push_service = get_push_service(connector_id)
        if push_service is None:
            logger.debug("[LMS] Push service not available for connector '%s'", connector_id)
            return

        for insight in insights:
            push_service.push_student_insight(
                student_id=user_id,
                insight_type=insight.insight_type,
                content=insight.content,
                metadata={
                    "confidence": insight.confidence,
                    "related_course_id": insight.related_course_id,
                    "related_course_name": insight.related_course_name,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        logger.info(
            "[LMS] Pushed %d insights for user %s", len(insights), user_id
        )

    except Exception as e:
        logger.debug("[LMS] Insight generation/push failed for user %s: %s", user_id, e)


def _is_trivial_message(msg: str) -> bool:
    """Check if a message is trivial (greeting, thanks, etc.)."""
    trivial_patterns = [
        "chào", "xin chào", "hello", "hi ", "hey",
        "cảm ơn", "thank", "bye", "tạm biệt",
        "ok", "được", "ừ", "vâng", "dạ",
    ]
    return any(msg.startswith(p) or msg == p for p in trivial_patterns)
