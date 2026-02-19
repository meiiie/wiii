"""Sprint 135: Soul Emotion extraction tests."""
import pytest
from app.engine.soul_emotion import (
    extract_soul_emotion,
    _validate_emotion,
    SoulEmotion,
    ExtractionResult,
    VALID_MOODS,
    _FACE_RANGES,
)


class TestExtractSoulEmotion:
    """Tests for extract_soul_emotion()."""

    def test_valid_tag_extraction(self):
        text = '<!--WIII_SOUL:{"mood":"warm","face":{"blush":0.3},"intensity":0.8}-->Xin chào~'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.mood == "warm"
        assert result.emotion.face["blush"] == pytest.approx(0.3)
        assert result.emotion.intensity == pytest.approx(0.8)
        assert result.clean_text == "Xin chào~"

    def test_no_tag(self):
        text = "Xin chào! Tôi là Wiii."
        result = extract_soul_emotion(text)
        assert result.emotion is None
        assert result.clean_text == text

    def test_malformed_json(self):
        text = '<!--WIII_SOUL:{bad json}-->Hello'
        result = extract_soul_emotion(text)
        assert result.emotion is None
        assert "Hello" in result.clean_text

    def test_partial_face_fields(self):
        text = '<!--WIII_SOUL:{"mood":"excited","face":{"mouthCurve":0.5},"intensity":0.9}-->OK'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert "mouthCurve" in result.emotion.face
        assert len(result.emotion.face) == 1

    def test_unknown_mood_defaults_neutral(self):
        text = '<!--WIII_SOUL:{"mood":"angry","face":{},"intensity":0.5}-->Hi'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.mood == "neutral"

    def test_value_clamping(self):
        text = '<!--WIII_SOUL:{"mood":"warm","face":{"blush":5.0,"browRaise":-10.0},"intensity":2.0}-->Hi'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.face["blush"] == 1.0  # clamped
        assert result.emotion.face["browRaise"] == -1.0  # clamped
        assert result.emotion.intensity == 1.0  # clamped

    def test_mouth_shape_4_pout_accepted(self):
        """Sprint 144: mouthShape range expanded to 0-4 (pout ε at 4)."""
        text = '<!--WIII_SOUL:{"mood":"gentle","face":{"mouthShape":4},"intensity":0.9}-->Hi'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.face["mouthShape"] == 4.0

    def test_mouth_shape_over_4_clamped(self):
        text = '<!--WIII_SOUL:{"mood":"gentle","face":{"mouthShape":7},"intensity":0.9}-->Hi'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.face["mouthShape"] == 4.0

    def test_intensity_clamp_negative(self):
        text = '<!--WIII_SOUL:{"mood":"neutral","face":{},"intensity":-1}-->Hi'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.intensity == 0.0

    def test_empty_face_valid(self):
        text = '<!--WIII_SOUL:{"mood":"gentle","face":{},"intensity":0.6}-->Content'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.face == {}
        assert result.clean_text == "Content"

    def test_whitespace_before_tag(self):
        text = '  <!--WIII_SOUL:{"mood":"warm","face":{},"intensity":0.5}-->Text'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.mood == "warm"

    def test_tag_not_at_start_ignored(self):
        text = 'Some text <!--WIII_SOUL:{"mood":"warm","face":{},"intensity":0.5}-->More'
        result = extract_soul_emotion(text)
        # Tag NOT at start → regex anchored to ^ won't match
        assert result.emotion is None

    def test_empty_text(self):
        result = extract_soul_emotion("")
        assert result.emotion is None
        assert result.clean_text == ""

    def test_non_dict_rejected(self):
        result = _validate_emotion("not a dict")
        assert result is None

    def test_non_dict_face_ignored(self):
        result = _validate_emotion({"mood": "warm", "face": "invalid", "intensity": 0.5})
        assert result is not None
        assert result.face == {}

    def test_multiple_tags_first_only(self):
        text = '<!--WIII_SOUL:{"mood":"warm","face":{},"intensity":0.5}--><!--WIII_SOUL:{"mood":"excited","face":{},"intensity":0.9}-->Text'
        result = extract_soul_emotion(text)
        assert result.emotion is not None
        assert result.emotion.mood == "warm"  # first tag

    def test_non_number_face_fields_skipped(self):
        result = _validate_emotion({
            "mood": "warm",
            "face": {"blush": "high", "browRaise": 0.3},
            "intensity": 0.8
        })
        assert result is not None
        assert "blush" not in result.face  # string value skipped
        assert result.face["browRaise"] == pytest.approx(0.3)

    def test_serialization_roundtrip(self):
        import json
        emotion = SoulEmotion(mood="excited", face={"blush": 0.5}, intensity=0.9)
        data = {"mood": emotion.mood, "face": emotion.face, "intensity": emotion.intensity}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        validated = _validate_emotion(parsed)
        assert validated is not None
        assert validated.mood == "excited"
        assert validated.face["blush"] == pytest.approx(0.5)
