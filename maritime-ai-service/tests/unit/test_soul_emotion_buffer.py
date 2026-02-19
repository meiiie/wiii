"""Sprint 135: Soul Emotion Buffer tests."""
import pytest
from app.engine.soul_emotion_buffer import SoulEmotionBuffer


class TestSoulEmotionBuffer:
    """Tests for SoulEmotionBuffer."""

    def test_complete_tag_single_chunk(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        emotion, chunks = buf.feed('<!--WIII_SOUL:{"mood":"warm","face":{},"intensity":0.8}-->Hello world')
        assert emotion is not None
        assert emotion.mood == "warm"
        assert chunks == ["Hello world"]
        assert buf.is_done

    def test_tag_split_across_chunks(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        # First chunk — no end marker yet
        emotion1, chunks1 = buf.feed('<!--WIII_SOUL:{"mood":"warm","face":{}')
        assert emotion1 is None
        assert chunks1 == []
        assert not buf.is_done

        # Second chunk completes the tag
        emotion2, chunks2 = buf.feed(',"intensity":0.8}-->Content here')
        assert emotion2 is not None
        assert emotion2.mood == "warm"
        assert chunks2 == ["Content here"]
        assert buf.is_done

    def test_buffer_limit_reached_no_tag(self):
        buf = SoulEmotionBuffer(max_bytes=20)
        emotion, chunks = buf.feed("x" * 25)
        assert emotion is None
        assert len(chunks) == 1
        assert chunks[0] == "x" * 25
        assert buf.is_done

    def test_passthrough_after_extraction(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        buf.feed('<!--WIII_SOUL:{"mood":"neutral","face":{},"intensity":0.5}-->First')
        assert buf.is_done

        # Subsequent feeds pass through
        emotion, chunks = buf.feed("Second chunk")
        assert emotion is None
        assert chunks == ["Second chunk"]

    def test_flush_on_non_answer(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        buf.feed("Some text without tag")
        assert not buf.is_done

        emotion, chunks = buf.flush()
        assert emotion is None
        assert len(chunks) == 1
        assert "Some text without tag" in chunks[0]
        assert buf.is_done

    def test_empty_feed(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        emotion, chunks = buf.feed("")
        assert emotion is None
        assert chunks == []

    def test_emotion_returned_once(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        emotion1, _ = buf.feed('<!--WIII_SOUL:{"mood":"warm","face":{},"intensity":0.8}-->Text')
        assert emotion1 is not None

        # Subsequent feeds should NOT return emotion again
        emotion2, chunks2 = buf.feed("More text")
        assert emotion2 is None
        assert chunks2 == ["More text"]

    def test_clean_text_after_tag(self):
        buf = SoulEmotionBuffer(max_bytes=1024)
        emotion, chunks = buf.feed('<!--WIII_SOUL:{"mood":"excited","face":{"blush":0.5},"intensity":0.9}-->Xin chào bạn!')
        assert emotion is not None
        assert "Xin chào bạn!" in chunks[0]
        assert "WIII_SOUL" not in chunks[0]

    def test_flush_empty(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        emotion, chunks = buf.flush()
        assert emotion is None
        assert chunks == []
        assert buf.is_done

    def test_unicode_vietnamese(self):
        buf = SoulEmotionBuffer(max_bytes=512)
        emotion, chunks = buf.feed(
            '<!--WIII_SOUL:{"mood":"warm","face":{"mouthCurve":0.3},"intensity":0.8}-->'
            'Xin chào! Mình là Wiii, trợ lý ảo thông minh~'
        )
        assert emotion is not None
        assert "Xin chào" in chunks[0]
