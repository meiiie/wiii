"""
ResponseTracker — Manages pending request-response futures for SoulBridge.

Sprint 215: "Hỏi Bro" — Cross-Soul Query Routing

Enables ask_peer() to await a reply from a remote soul by correlating
request_id with reply_to_id on incoming messages.

Design:
    - asyncio.Future per pending request
    - Timeout handled by caller (asyncio.wait_for)
    - cleanup() cancels all pending futures (used during shutdown)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ResponseTracker:
    """Tracks pending request-response futures for SoulBridge.ask_peer().

    Usage:
        tracker = ResponseTracker()
        future = tracker.create_future("req-123")
        # ... send message with request_id="req-123" ...
        # When reply arrives with reply_to_id="req-123":
        tracker.resolve("req-123", response_message)
        # The future now has its result
    """

    def __init__(self) -> None:
        self._pending: Dict[str, asyncio.Future] = {}

    def create_future(self, request_id: str) -> asyncio.Future:
        """Create a future for a pending request.

        Args:
            request_id: Unique ID to correlate with reply_to_id.

        Returns:
            asyncio.Future that will be resolved when the reply arrives.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[request_id] = future
        return future

    def resolve(self, reply_to_id: str, message: Any) -> bool:
        """Resolve a pending future with the reply message.

        Args:
            reply_to_id: The request_id from the original request.
            message: The reply message (SoulBridgeMessage).

        Returns:
            True if a pending future was found and resolved, False otherwise.
        """
        future = self._pending.pop(reply_to_id, None)
        if future is None or future.done():
            return False
        future.set_result(message)
        return True

    def cancel(self, request_id: str) -> bool:
        """Cancel a pending future.

        Args:
            request_id: The request ID to cancel.

        Returns:
            True if cancelled, False if not found.
        """
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return False
        future.cancel()
        return True

    def cleanup(self) -> int:
        """Cancel all pending futures. Used during shutdown.

        Returns:
            Number of futures cancelled.
        """
        count = 0
        for request_id, future in list(self._pending.items()):
            if not future.done():
                future.cancel()
                count += 1
        self._pending.clear()
        return count

    @property
    def pending_count(self) -> int:
        """Number of currently pending requests."""
        return len(self._pending)
