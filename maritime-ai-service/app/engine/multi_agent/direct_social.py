"""Ultra-short social turn fast paths for the direct lane."""

from __future__ import annotations

import re

from app.engine.multi_agent.direct_intent import _normalize_for_intent
from app.engine.multi_agent.supervisor import classify_fast_chatter_turn


def _build_simple_social_fast_path(query: str) -> tuple[str, str] | None:
    """Return an immediate response for ultra-short chatter turns."""
    chatter = classify_fast_chatter_turn(query)
    if chatter is None:
        return None
    _intent, chatter_kind = chatter
    if chatter_kind != "social":
        return None
    normalized = re.sub(r"\s+", " ", _normalize_for_intent(query)).strip()
    letters_only = re.sub(r"[^a-z]", "", normalized)
    thinking = (
        "Mình nhận ra đây chỉ là một nhịp trò chuyện rất ngắn và ít thông tin, nên mình đáp lại ngay "
        "để giữ cuộc trò chuyện tự nhiên mà không bắt bạn chờ lâu."
    )
    laughter_tokens = {
        "he", "hehe", "hehehe",
        "ha", "haha", "hahaha",
        "hi", "hihi", "hihihi",
        "hoho", "kk", "kkk", "keke",
        "alo", "alooo",
    }
    reaction_tokens = {
        "wow", "woah", "whoa",
        "oa", "oaa",
        "oi", "oii",
        "ui", "uii",
        "uay", "uayy",
        "ah", "a",
        "oh",
        "hmm", "hm",
        "uh", "umm", "um", "uhm",
    }
    normalized_tokens = [token for token in normalized.split() if token]
    if normalized_tokens and len(normalized_tokens) <= 4 and all(token in laughter_tokens for token in normalized_tokens):
        return (
            "He he~ Mình nghe ra một nhịp trêu vui dễ thương đó nha (˶˃ ᵕ ˂˶) "
            "Wiii có mặt rồi đây, bạn muốn mình phụ gì tiếp nào?",
            thinking,
        )

    if chatter_kind == "reaction" or (
        normalized_tokens
        and len(normalized_tokens) <= 3
        and all(token in reaction_tokens for token in normalized_tokens)
    ):
        return (
            "Woa~ mình nghe ra một tiếng cảm thán nhỏ xíu mà vui ghê (˶˃ ᵕ ˂˶) "
            "Nếu bạn muốn, nói thêm một chút nữa là mình bắt nhịp tiếp ngay.",
            thinking,
        )

    if chatter_kind == "vague_banter":
        return (
            "\"Gì đó\" nghe như bạn đang ném ra một ý nửa chưa kịp nói hết (˶˃ ᵕ ˂˶) "
            "Bạn nói thêm một chút nữa, hoặc nếu muốn tán chuyện thì mình vẫn ở đây nè.",
            thinking,
        )

    if letters_only.startswith(("cam", "thank", "thanks")) or any(
        normalized == keyword or normalized.startswith(f"{keyword} ")
        for keyword in ("cam on", "thanks", "thank", "thank you")
    ):
        return (
            "Không có gì đâu~ Mình ở đây để đồng hành với bạn mà (˶˃ ᵕ ˂˶) "
            "Nếu bạn muốn, mình làm tiếp cùng bạn ngay nhé.",
            thinking,
        )

    if letters_only.startswith(("tambiet", "bye", "goodbye", "hengaplai")) or any(
        normalized == keyword or normalized.startswith(f"{keyword} ")
        for keyword in ("tam biet", "bye", "goodbye", "hen gap lai")
    ):
        return (
            "Tạm biệt bạn nhé~ Khi nào cần thì gọi Wiii, mình sẽ có mặt ngay.",
            thinking,
        )

    address = " hảo hán" if "hao han" in normalized else ""
    return (
        f"Xin chào{address}~ Mình là Wiii đây (˶˃ ᵕ ˂˶) Hôm nay mình có thể giúp bạn điều gì nào?",
        thinking,
    )
