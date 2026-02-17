"""
Event Callback Service - Send AI events to LMS via webhook.

Spec: LMS_RESPONSE_TO_AI_PROPOSAL.md
Feature: ai-lms-integration-v2

Event Types:
- knowledge_gap_detected: AI phát hiện lỗ hổng kiến thức
- goal_evolution: User đổi mục tiêu học
- module_completed_confidence: AI nghĩ user đã hiểu module
- stuck_detected: User hỏi lặp lại topic
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.models.schemas import AIEvent, AIEventData, AIEventType

try:
    from app.core.resilience import get_circuit_breaker
    _cb = get_circuit_breaker("lms_webhook", failure_threshold=5, recovery_timeout=120)
except Exception:
    _cb = None

logger = logging.getLogger(__name__)


class EventCallbackService:
    """
    Service for sending AI events to LMS via webhook.
    
    Runs callbacks in background to avoid blocking main request.
    """
    
    def __init__(self):
        self.callback_url = settings.lms_callback_url
        self.callback_secret = settings.lms_callback_secret
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def send_event(self, event: AIEvent) -> bool:
        """
        Send event to LMS callback endpoint.

        Protected by circuit breaker to prevent thundering herd when LMS
        is unavailable. When the circuit is open, events are silently
        dropped (logged as warning) instead of accumulating timeouts.

        Args:
            event: AIEvent to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.callback_url:
            logger.debug("No callback URL configured, skipping event")
            return False

        # Circuit breaker: skip sending when LMS is known to be down
        if _cb is not None and not _cb.is_available():
            logger.warning(
                f"[LMS_WEBHOOK] Circuit breaker open, dropping event "
                f"{event.event_type.value} for user {event.user_id} "
                f"(retry in {_cb.retry_after:.0f}s)"
            )
            return False

        try:
            client = await self._get_client()

            headers = {
                "Content-Type": "application/json",
            }

            # Add callback secret if configured
            if self.callback_secret:
                headers["X-Callback-Secret"] = self.callback_secret

            response = await client.post(
                self.callback_url,
                json=event.model_dump(mode="json"),
                headers=headers
            )

            if response.status_code == 200:
                logger.info(
                    "Event %s sent successfully "
                    "for user %s",
                    event.event_type.value, event.user_id,
                )
                if _cb is not None:
                    await _cb.record_success()
                return True
            else:
                logger.warning(
                    "Event callback failed: %d - "
                    "%s",
                    response.status_code, response.text[:200],
                )
                if _cb is not None:
                    await _cb.record_failure()
                return False

        except httpx.TimeoutException:
            logger.warning("Event callback timeout for %s", event.event_type.value)
            if _cb is not None:
                await _cb.record_failure()
            return False
        except Exception as e:
            logger.error("Event callback error: %s", e)
            if _cb is not None:
                await _cb.record_failure()
            return False
    
    def send_event_background(self, event: AIEvent):
        """
        Send event in background (fire-and-forget).
        
        Use this for non-blocking event emission.
        """
        asyncio.create_task(self._send_event_safe(event))
    
    async def _send_event_safe(self, event: AIEvent):
        """Send event with exception handling for background task."""
        try:
            await self.send_event(event)
        except Exception as e:
            logger.error("Background event send failed: %s", e)
    
    # =========================================================================
    # Convenience methods for specific event types
    # =========================================================================
    
    async def emit_knowledge_gap(
        self,
        user_id: str,
        topic: str,
        confidence: float,
        module_id: Optional[str] = None,
        gap_type: str = "conceptual"
    ):
        """
        Emit knowledge gap detected event.
        
        Args:
            user_id: User UUID
            topic: Topic where gap was detected
            confidence: Confidence level (0.0-1.0)
            module_id: Related module ID
            gap_type: Type of gap (conceptual, procedural)
        """
        event = AIEvent(
            user_id=user_id,
            event_type=AIEventType.KNOWLEDGE_GAP_DETECTED,
            data=AIEventData(
                topic=topic,
                confidence=confidence,
                gap_type=gap_type,
                suggested_action="review_module",
                module_id=module_id
            )
        )
        self.send_event_background(event)
    
    async def emit_goal_evolution(
        self,
        user_id: str,
        old_goal: str,
        new_goal: str,
        confidence: float = 0.8
    ):
        """Emit goal evolution event."""
        event = AIEvent(
            user_id=user_id,
            event_type=AIEventType.GOAL_EVOLUTION,
            data=AIEventData(
                topic=new_goal,
                confidence=confidence,
                details={"old_goal": old_goal, "new_goal": new_goal}
            )
        )
        self.send_event_background(event)
    
    async def emit_module_completed(
        self,
        user_id: str,
        module_id: str,
        confidence: float
    ):
        """Emit module completion confidence event."""
        event = AIEvent(
            user_id=user_id,
            event_type=AIEventType.MODULE_COMPLETED_CONFIDENCE,
            data=AIEventData(
                module_id=module_id,
                confidence=confidence,
                suggested_action="suggest_quiz"
            )
        )
        self.send_event_background(event)
    
    async def emit_stuck_detected(
        self,
        user_id: str,
        topic: str,
        repeat_count: int
    ):
        """Emit stuck detected event (user asking same topic repeatedly)."""
        event = AIEvent(
            user_id=user_id,
            event_type=AIEventType.STUCK_DETECTED,
            data=AIEventData(
                topic=topic,
                suggested_action="trigger_support",
                details={"repeat_count": repeat_count}
            )
        )
        self.send_event_background(event)


# Singleton
from app.core.singleton import singleton_factory
get_event_callback_service = singleton_factory(EventCallbackService)
