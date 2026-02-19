"""
Soul Emotion Buffer — Stateful buffer for extracting emotion tags from SSE stream.

Sprint 135: Buffers the first N bytes of answer_delta events to detect and extract
<!--WIII_SOUL:{...}--> before forwarding clean text to the client.

Usage in graph_streaming.py:
    buf = SoulEmotionBuffer()
    for chunk in answer_deltas:
        emotion, clean_chunks = buf.feed(chunk)
        if emotion: yield emotion_event
        for c in clean_chunks: yield answer_event(c)

Sequential access only (one buffer per request, processed in event loop order).
"""

import logging
from typing import List, Optional, Tuple

from app.engine.soul_emotion import SoulEmotion, extract_soul_emotion

logger = logging.getLogger(__name__)


class SoulEmotionBuffer:
    """
    Accumulates answer chunks looking for a soul emotion tag at the start.

    Once the tag is found (or buffer limit reached), passes through all
    subsequent chunks without buffering.

    Note: This class is NOT thread-safe. It is designed for sequential access
    within a single async event loop (one buffer per streaming request).
    """

    def __init__(self, max_bytes: int = 512):
        self._max_bytes = max_bytes
        self._buffer = ""
        self._buffer_bytes = 0  # Track UTF-8 byte count incrementally
        self._done = False
        self._emotion: Optional[SoulEmotion] = None

    @property
    def is_done(self) -> bool:
        """True once extraction is complete (tag found, limit hit, or flushed)."""
        return self._done

    def feed(self, chunk: str) -> Tuple[Optional[SoulEmotion], List[str]]:
        """
        Feed an answer chunk into the buffer.

        Returns:
            (emotion, clean_chunks) where emotion is set once (first detection),
            and clean_chunks are text chunks to forward to the client.
        """
        if self._done:
            # Passthrough mode — no buffering
            return (None, [chunk] if chunk else [])

        # Track bytes incrementally (avoid O(n²) re-encoding)
        chunk_bytes = len(chunk.encode("utf-8")) if chunk else 0
        self._buffer_bytes += chunk_bytes
        self._buffer += chunk

        # Check if tag end marker is in buffer
        if "-->" in self._buffer:
            return self._extract()

        # Check if buffer limit exceeded (no tag found)
        if self._buffer_bytes >= self._max_bytes:
            logger.debug(
                "[SOUL_BUFFER] Buffer limit (%d bytes) reached without tag, releasing %d chars",
                self._max_bytes, len(self._buffer),
            )
            return self._finalize_no_tag()

        # Still accumulating — hold chunks
        return (None, [])

    def flush(self) -> Tuple[Optional[SoulEmotion], List[str]]:
        """
        Force extraction (e.g., when a non-answer event arrives).

        Returns any buffered content as clean chunks.
        """
        if self._done:
            return (None, [])

        if self._buffer:
            logger.debug("[SOUL_BUFFER] Flushed with %d chars buffered", len(self._buffer))
            return self._extract()

        self._done = True
        return (None, [])

    def _extract(self) -> Tuple[Optional[SoulEmotion], List[str]]:
        """Attempt extraction from accumulated buffer."""
        self._done = True
        result = extract_soul_emotion(self._buffer)
        self._emotion = result.emotion
        self._buffer = ""  # Free memory immediately
        self._buffer_bytes = 0

        if result.emotion:
            logger.info(
                "[SOUL_BUFFER] Extracted emotion: mood=%s, intensity=%.2f, face_keys=%s",
                result.emotion.mood,
                result.emotion.intensity,
                list(result.emotion.face.keys()),
            )

        clean_chunks = [result.clean_text] if result.clean_text else []
        return (result.emotion, clean_chunks)

    def _finalize_no_tag(self) -> Tuple[Optional[SoulEmotion], List[str]]:
        """Buffer limit reached with no tag — release all buffered text."""
        self._done = True
        text = self._buffer
        self._buffer = ""
        self._buffer_bytes = 0
        return (None, [text] if text else [])
