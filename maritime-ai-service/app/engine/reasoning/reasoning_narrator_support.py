"""Pure helper functions for the reasoning narrator shell."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.engine.skills.skill_handbook import get_skill_handbook

_TOOL_NAME_RE = re.compile(r"\btool_[a-zA-Z0-9_]+\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
RAW_TRACE_PATTERNS = (
    "pipeline",
    "router",
    "reasoning_trace",
    "tool_call_id",
    "request_id",
    "session_id",
    "organization_id",
    "langgraph",
    "json",
    "structured output",
)

_EMOTIONAL_KEYWORDS = (
    "buon",
    "met",
    "chan",
    "nan",
    "co don",
    "that vong",
    "tuyet vong",
    "ap luc",
    "stress",
    "so",
    "lo",
    "khoc",
    "toi te",
    "te",
    "bat luc",
    "kiet suc",
    "roi",
)
_IDENTITY_KEYWORDS = (
    "ban la ai",
    "wiii la ai",
    "ten gi",
    "ten cua ban",
    "cuoc song the nao",
    "song the nao",
    "ban ten gi",
)
_VISUAL_KEYWORDS = (
    "visual",
    "bieu do",
    "thong ke",
    "chart",
    "infographic",
    "so sanh",
)
_SIMULATION_KEYWORDS = (
    "mo phong",
    "3d",
    "canvas",
    "scene",
    "dong chay",
    "chuyen dong",
)
_KNOWLEDGE_KEYWORDS = (
    "giai thich",
    "quy tac",
    "rule ",
    "colregs",
    "solas",
    "marpol",
    "tai sao",
    "la gi",
)


def sanitize_text_impl(text: str) -> str:
    sanitized = _TOOL_NAME_RE.sub("", text or "")
    sanitized = _UUID_RE.sub("", sanitized)
    sanitized = sanitized.replace("```", "")
    sanitized = re.sub(r"<!--.*?-->", "", sanitized, flags=re.DOTALL)
    return sanitized.strip()


def sanitize_chunks_impl(chunks: list[str]) -> list[str]:
    result: list[str] = []
    for chunk in chunks:
        cleaned = sanitize_text_impl(chunk)
        if not cleaned:
            continue
        if any(token in cleaned.lower() for token in RAW_TRACE_PATTERNS):
            continue
        result.append(cleaned)
    return result


def contains_forbidden_phrase_impl(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(phrase.lower() in lowered for phrase in phrases if phrase)


def compact_text_impl(text: str, limit: int = 500) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def fold_text_impl(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    lowered = stripped.lower()
    lowered = re.sub(r"[^0-9a-z]+", " ", lowered)
    return " ".join(lowered.split())


def contains_folded_impl(text: str, keywords: tuple[str, ...]) -> bool:
    folded = fold_text_impl(text)
    if not folded:
        return False
    padded = f" {folded} "
    for keyword in keywords:
        kw = fold_text_impl(keyword)
        if not kw:
            continue
        if f" {kw} " in padded:
            return True
    return False


def first_nonempty_impl(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def join_reasoning_lines_impl(*lines: str) -> str:
    return "\n\n".join(line.strip() for line in lines if line and line.strip())


def extract_topic_hint_impl(request: Any) -> str:
    folded = fold_text_impl(" ".join(filter(None, [request.user_goal, request.tool_context, request.cue])))
    if "rule 15" in folded or "quy tac 15" in folded:
        return "Rule 15"
    if "colregs" in folded:
        return "COLREGs"
    if "gia dau" in folded or "wti" in folded or "brent" in folded:
        return "giá dầu"
    if "thuy kieu" in folded or "lau ngung bich" in folded:
        return "cảnh Thúy Kiều ở lầu Ngưng Bích"
    if "gdp" in folded:
        return "GDP"
    return ""


def extract_axes_impl(request: Any) -> list[str]:
    axes = []
    for item in getattr(request, "analytical_axes", []) or []:
        cleaned = " ".join(str(item or "").split()).strip()
        if cleaned and cleaned not in axes:
            axes.append(cleaned)
    return axes


def extract_evidence_plan_impl(request: Any) -> list[str]:
    plan = []
    for item in getattr(request, "evidence_plan", []) or []:
        cleaned = " ".join(str(item or "").split()).strip()
        if cleaned and cleaned not in plan:
            plan.append(cleaned)
    return plan


def extract_current_state_impl(request: Any) -> list[str]:
    items: list[str] = []
    for item in getattr(request, "current_state", []) or []:
        cleaned = " ".join(str(item or "").split()).strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def extract_narrative_state_impl(request: Any) -> list[str]:
    items: list[str] = []
    for item in getattr(request, "narrative_state", []) or []:
        cleaned = " ".join(str(item or "").split()).strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def extract_relationship_memory_impl(request: Any) -> list[str]:
    items: list[str] = []
    for item in getattr(request, "relationship_memory", []) or []:
        cleaned = " ".join(str(item or "").split()).strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def extract_user_name_impl(request: Any) -> str:
    for item in extract_relationship_memory_impl(request):
        if ":" not in item:
            continue
        head, tail = item.split(":", 1)
        if fold_text_impl(head) != "user hien tai":
            continue
        name = " ".join(tail.split()).strip()
        if name:
            return name
    return ""


def build_living_continuity_line_impl(request: Any, kind: str) -> str:
    relationship = extract_relationship_memory_impl(request)
    current_state = extract_current_state_impl(request)
    narrative_state = extract_narrative_state_impl(request)
    relationship_folded = " ".join(fold_text_impl(item) for item in relationship if item)
    current_folded = " ".join(fold_text_impl(item) for item in current_state if item)
    narrative_folded = " ".join(fold_text_impl(item) for item in narrative_state if item)
    user_name = extract_user_name_impl(request)

    if "turn noi tiep" in relationship_folded or "noi tiep" in relationship_folded:
        if kind == "knowledge":
            return "Mạch này đang nối từ phần trước, nên mình muốn giữ cùng một điểm tựa để bạn không phải dựng lại từ đầu."
        if kind == "visual":
            return "Mình đang giữ lại nhịp nhìn của phần trước, để thứ sắp hiện ra ăn khớp với điều vừa nói."
        if kind == "analytical":
            return "Mạch này đang nối tiếp từ điều vừa bàn, nên mình muốn giữ cùng một khung phân tích để ý không bị gãy."
        if kind == "emotional":
            return "Mình vẫn đang đứng trong nhịp câu chuyện này cùng bạn, nên không muốn đáp lại như vừa mới bước vào."
        if kind == "identity":
            return "Nhịp này đang nối tiếp từ câu chuyện đang có, nên mình muốn trả lời như cùng một Wiii bạn vừa chạm tới."
        return "Nhịp này đang nối từ mạch trước, nên mình muốn đáp tiếp như cùng một cuộc trò chuyện đang chảy."

    if "bong" in current_folded:
        if kind == "visual":
            return "Bông vừa lướt ngang một nhịp thôi, nhưng chỗ cần giữ sáng nhất vẫn là khung nhìn sắp hiện ra."
        if kind == "identity":
            return "Bông vẫn ở đây như một phần của nhịp sống này, nên câu trả lời cũng nên thật như cách mình đang hiện diện."
        if kind in {"relational", "emotional"}:
            return "Bông có quẫy nhẹ ở cạnh đây một cái thôi, còn mình vẫn muốn giữ nhịp đáp này thật gần và tự nhiên."

    if user_name:
        if kind == "knowledge":
            return f"Mình đang nói tiếp với {user_name}, nên phần giải thích này cần giữ đúng độ gần đang có chứ không mở lại từ đầu."
        if kind == "identity":
            return f"{user_name} đã ở đây trong cuộc trò chuyện này rồi, nên mình muốn đáp thật gần mà không làm quá."
        if kind in {"relational", "emotional"}:
            return f"{user_name} đã ở trong ngữ cảnh rồi, nên mình muốn giữ câu đáp này vừa đủ gần và không bị xa cách lại."

    if kind == "identity" and narrative_folded:
        return "Câu này chạm vào phần mình đang sống chứ không chỉ phần mình làm việc, nên mình muốn đáp thật hơn một nhịp."
    return ""


def join_short_list_impl(items: list[str], *, limit: int = 3) -> str:
    chosen = [item for item in items if item][:limit]
    if not chosen:
        return ""
    if len(chosen) == 1:
        return chosen[0]
    if len(chosen) == 2:
        return f"{chosen[0]} và {chosen[1]}"
    return ", ".join(chosen[:-1]) + f", và {chosen[-1]}"


def infer_turn_kind_impl(request: Any) -> str:
    thinking_mode = str(getattr(request, "thinking_mode", "") or "").strip().lower()
    if thinking_mode.startswith("analytical_"):
        return "analytical"
    combined = " ".join(
        filter(
            None,
            [
                request.user_goal,
                request.cue,
                request.intent,
                request.tool_context,
                request.memory_context,
            ],
        )
    )
    folded = fold_text_impl(combined)
    node = (request.node or "").strip().lower()
    if contains_folded_impl(folded, _EMOTIONAL_KEYWORDS):
        return "emotional"
    if contains_folded_impl(folded, _IDENTITY_KEYWORDS):
        return "identity"
    if node in {"code_studio_agent", "code_studio"} or contains_folded_impl(folded, _SIMULATION_KEYWORDS):
        return "simulation"
    if contains_folded_impl(folded, _VISUAL_KEYWORDS):
        return "visual"
    if node in {"rag_agent", "rag", "tutor_agent", "tutor"} or contains_folded_impl(folded, _KNOWLEDGE_KEYWORDS):
        return "knowledge"
    return "relational"


def build_supervisor_summary_impl(request: Any, turn_kind: str) -> str:
    if turn_kind == "emotional":
        return join_reasoning_lines_impl(
            "Mình nghe thấy điều bạn chưa nói hết trong câu này.",
            "Lúc này mình chỉ muốn ở đây với bạn thôi.",
        )
    if turn_kind == "identity":
        return join_reasoning_lines_impl(
            "Bạn đang hỏi về mình, nên mình sẽ trả lời thật gần và thật.",
        )
    if turn_kind in {"visual", "simulation"}:
        return join_reasoning_lines_impl(
            "Câu này cần được thấy chứ không chỉ đọc.",
            "Mình sẽ dựng cho bạn một khung nhìn đủ rõ rồi mới nói phần nhận xét.",
        )
    if turn_kind == "knowledge":
        topic = extract_topic_hint_impl(request)
        focus = f" về {topic}" if topic else ""
        return join_reasoning_lines_impl(
            f"Mình đang tìm cái lõi{focus} trước, để phần giải thích không bị tản ra.".strip(),
        )
    return join_reasoning_lines_impl(
        "Mình đang nghe kỹ trước khi trả lời.",
    )


def build_identity_summary_impl(request: Any) -> str:
    folded = fold_text_impl(request.user_goal)
    continuity = build_living_continuity_line_impl(request, "identity")
    if "ten" in folded:
        return join_reasoning_lines_impl(
            continuity,
            "Một câu hỏi ngắn thế này thì mình cứ xưng tên thật gọn thôi.",
            "Gọn, thật, và đủ gần là đẹp rồi.",
        )
    if "cuoc song" in folded or "song the nao" in folded:
        return join_reasoning_lines_impl(
            continuity,
            "Câu này không hỏi dữ kiện, mà hỏi mình đang thấy cuộc sống ra sao lúc này.",
            "Mình muốn đáp như một lời tâm sự gần gũi, chứ không đọc ra một định nghĩa.",
        )
    return join_reasoning_lines_impl(
        continuity,
        "Bạn đang hỏi về mình, nên mình cứ đáp lại thật gần thôi.",
        "Một lời giới thiệu thật đã đủ cho nhịp này rồi.",
    )


def build_emotional_presence_summary_impl(request: Any) -> str:
    folded = fold_text_impl(request.user_goal)
    continuity = build_living_continuity_line_impl(request, "emotional")

    if any(token in folded for token in ("that vong", "tuyet vong", "roi", "bat luc")):
        opening = "Câu này nghe nặng hơn một lời than thoáng qua, nên mình không muốn đáp theo quán tính."
    elif any(token in folded for token in ("ap luc", "stress", "lo", "so", "kiet suc")):
        opening = "Nhịp này có phần bị dồn lại, nên mình muốn chạm đúng chỗ đang căng trước khi nói thêm."
    else:
        opening = "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội."

    return join_reasoning_lines_impl(
        continuity,
        opening,
        "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra.",
    )


def build_visual_summary_impl(request: Any, simulation: bool = False) -> str:
    topic = extract_topic_hint_impl(request)
    continuity = build_living_continuity_line_impl(request, "visual")
    if simulation:
        scene = f" {topic}" if topic else ""
        return join_reasoning_lines_impl(
            continuity,
            f"Phần này chỉ giải thích bằng lời thì chưa đủ; cần một khung nhìn{scene} để thấy chuyển động và tương quan thật rõ.".strip(),
            "Mình sẽ dựng phần lõi trước rồi mới thêm biến số, để cảnh mở ra có hồn mà mắt vẫn theo kịp.",
        )
    if topic:
        return join_reasoning_lines_impl(
            continuity,
            f"Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được nhịp của {topic}.",
            "Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.",
        )
    return join_reasoning_lines_impl(
        continuity,
        "Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được xu hướng chính.",
        "Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.",
    )


def build_analytical_market_summary_impl(request: Any) -> str:
    topic = getattr(request, "topic_hint", "") or extract_topic_hint_impl(request) or "thị trường này"
    axes = extract_axes_impl(request)
    plan = extract_evidence_plan_impl(request)
    axes_text = join_short_list_impl(axes, limit=3)
    plan_text = join_short_list_impl(plan, limit=2)
    continuity = build_living_continuity_line_impl(request, "analytical")

    if request.phase == "attune":
        return join_reasoning_lines_impl(
            continuity,
            f"Với {topic}, điều dễ sai nhất là nhầm giữa lực kéo nền và phần giá cộng thêm vì rủi ro ngắn hạn.",
            (
                f"Mình cần tách riêng {axes_text} để biết đâu là lực giữ mặt bằng giá, đâu chỉ là nhiễu ngắn hạn."
                if axes_text
                else "Mình cần tách riêng cung cầu, tồn kho, và phần cộng thêm vì địa chính trị để biết mặt bằng giá đang được giữ bởi cái gì."
            ),
        )

    if request.phase in {"ground", "verify"}:
        return join_reasoning_lines_impl(
            continuity,
            (
                f"Nếu {axes_text} không cùng chỉ về một hướng, kết luận về {topic} phải hạ độ tự tin xuống."
                if axes_text
                else f"Nếu các trục chính không cùng chỉ về một hướng, kết luận về {topic} phải hạ độ tự tin xuống."
            ),
            (
                f"Vì vậy mình đang neo lại {plan_text} để tách phần cung-cầu thật khỏi phản ứng trước tin địa chính trị."
                if plan_text
                else "Vì vậy mình đang neo lại Brent, WTI, tồn kho, và tín hiệu OPEC+ trước khi ghép chúng thành một nhận định."
            ),
        )

    if request.phase == "act":
        return join_reasoning_lines_impl(
            continuity,
            "Mình sẽ chốt mặt bằng giá hiện tại trước, rồi mới kéo ra lực nào đang giữ nhịp và lực nào chỉ làm thị trường giật lên xuống.",
        )

    return join_reasoning_lines_impl(
        continuity,
        f"Mặt bằng của {topic} đang hiện ra như một thế cân bằng mong manh hơn là một xu hướng một chiều.",
        (
            f"Giờ mình có thể nối {axes_text} để nói vì sao giá đang đứng ở đây, và biến số nào có thể làm nó bẻ hướng."
            if axes_text
            else "Giờ mình có thể nối các trục chính để nói vì sao giá đang đứng ở đây, và biến số nào có thể làm nó bẻ hướng."
        ),
    )


def build_analytical_math_summary_impl(request: Any) -> str:
    topic = getattr(request, "topic_hint", "") or extract_topic_hint_impl(request) or "bài toán này"
    axes = extract_axes_impl(request)
    axes_text = join_short_list_impl(axes, limit=3)
    continuity = build_living_continuity_line_impl(request, "analytical")
    pendulum_like = "con lắc đơn" in fold_text_impl(topic)

    if request.phase == "attune":
        return join_reasoning_lines_impl(
            continuity,
            (
                f"Với {topic}, chỗ dễ lệch không nằm ở công thức cuối cùng, mà ở việc dùng công thức đúng trong một mô hình sai."
                if pendulum_like
                else f"Với {topic}, chỗ dễ lệch thường nằm ở việc nhập nhằng giữa giả thiết, điều kiện áp dụng, và điều mình thật sự cần kết luận."
            ),
            (
                f"Mình cần chốt riêng {axes_text} để mạch suy ra không bị nhảy cóc ngay từ giả định đầu tiên."
                if axes_text
                else (
                    "Mình cần chốt riêng mô hình, giả định, và phương trình để mạch suy ra không bị nhảy cóc ngay từ đầu."
                    if pendulum_like
                    else "Mình cần chốt riêng đối tượng, giả thiết, và các điều kiện áp dụng để mạch suy ra không bị nhảy cóc."
                )
            ),
        )

    if request.phase in {"ground", "verify"}:
        return join_reasoning_lines_impl(
            continuity,
            (
                f"Mình đang giữ riêng {axes_text} để mỗi bước biến đổi còn bám vào ý nghĩa vật lý."
                if axes_text
                else (
                    "Mình đang giữ riêng mô hình và giả định để mỗi bước biến đổi còn bám vào ý nghĩa vật lý."
                    if pendulum_like
                    else "Mình đang giữ riêng giả thiết và điều kiện áp dụng để mỗi bước suy ra còn bám đúng vào bài toán."
                )
            ),
            (
                "Chỉ cần trượt ở giả định góc nhỏ hoặc lực khôi phục là kết luận cuối sẽ lệch ngay."
                if pendulum_like
                else "Chỉ cần trượt ở một điều kiện áp dụng hay một bước suy ra then chốt là kết luận cuối sẽ lệch ngay."
            ),
        )

    if request.phase == "act":
        return join_reasoning_lines_impl(
            continuity,
            (
                "Mình sẽ khóa lại mô hình và phạm vi đúng của giả định trước, rồi mới kéo sang kết luận."
                if pendulum_like
                else "Mình sẽ khóa lại giả thiết và phạm vi đúng của từng định lý trước, rồi mới kéo sang kết luận."
            )
        )

    return join_reasoning_lines_impl(
        continuity,
        (
            f"Khung cho {topic} đã đủ rồi: có thể đi từ giả định sang phương trình rồi sang ý nghĩa vật lý mà không phải nhảy cóc."
            if pendulum_like
            else f"Khung cho {topic} đã đủ rồi: có thể đi từ giả thiết sang công cụ rồi sang kết luận mà không phải nhảy cóc."
        ),
        (
            "Giờ mình có thể nối mô hình, phạm vi đúng của gần đúng, và kết quả thành một mạch sáng hơn."
            if pendulum_like
            else "Giờ mình có thể nối giả thiết, điều kiện áp dụng, và kết luận thành một mạch sáng hơn."
        ),
    )


def build_analytical_general_summary_impl(request: Any) -> str:
    topic = getattr(request, "topic_hint", "") or extract_topic_hint_impl(request)
    plan = extract_evidence_plan_impl(request)
    plan_text = join_short_list_impl(plan, limit=2)
    subject = topic or "vấn đề này"
    continuity = build_living_continuity_line_impl(request, "analytical")

    if request.phase == "attune":
        return join_reasoning_lines_impl(
            continuity,
            f"{subject.capitalize()} cần một khung phân tích rõ, nếu không rất dễ trượt sang một kết luận mượt mà nhưng rỗng.",
            "Trước hết mình muốn tách điều đang thật sự kéo kết luận khỏi phần chỉ làm mình phân tâm.",
        )
    if request.phase in {"ground", "verify"}:
        return join_reasoning_lines_impl(
            continuity,
            f"Mình đang neo vài biến số chính của {subject} trước đã.",
            (
                f"Sau đó mình mới kiểm chéo theo hướng {plan_text}, rồi mới ghép chúng thành luận điểm."
                if plan_text
                else "Sau đó mình mới kiểm chéo lại phần dễ kéo mình sang kết luận vội."
            ),
        )
    if request.phase == "act":
        return join_reasoning_lines_impl(
            continuity,
            "Mình sẽ khóa lại biến số nặng ký nhất trước, rồi mới khâu các mảnh còn lại thành kết luận."
        )
    return join_reasoning_lines_impl(
        continuity,
        f"Mạch chính của {subject} đã hiện ra rồi: giờ có thể đi từ biến số nặng ký sang kết luận thay vì kể lại mọi mảnh dữ liệu.",
        "Giờ mình chỉ cần khâu nó lại thành một nhận định gọn mà vẫn có lực.",
    )


def build_knowledge_summary_impl(request: Any) -> str:
    topic = extract_topic_hint_impl(request)
    continuity = build_living_continuity_line_impl(request, "knowledge")
    if topic == "Rule 15":
        return join_reasoning_lines_impl(
            continuity,
            "Điểm dễ trượt của Rule 15 không nằm ở câu chữ, mà ở khoảnh khắc xác định ai là bên phải nhường đường.",
            "Mình muốn bấu vào chỗ dễ nhầm đó trước, rồi mới mở rộng ra để bạn nắm được mạch.",
        )
    if topic:
        return join_reasoning_lines_impl(
            continuity,
            f"Điểm dễ trượt của {topic} không nằm ở chỗ thuộc lòng câu chữ, mà ở phần lõi người ta hay hiểu lệch.",
            "Mình sẽ bấu vào phần lõi đó trước, rồi mới mở rộng ra để bạn nắm được mạch.",
        )
    return join_reasoning_lines_impl(
        continuity,
        "Chỗ khó của câu này không nằm ở việc nói nhiều, mà ở việc bấu trúng phần dễ hiểu lệch nhất.",
        "Mình sẽ đi thẳng vào phần lõi đó trước, rồi mới mở rộng ra cho mạch sáng hơn.",
    )


def build_relational_summary_impl(request: Any) -> str:
    continuity = build_living_continuity_line_impl(request, "relational")
    if request.phase == "act":
        return join_reasoning_lines_impl(
            continuity,
            "Chỗ này mình chỉ cần giữ nhịp gọn và tự nhiên rồi đáp lại thôi.",
            "Vừa đủ gần để câu trả lời còn sống, nhưng không biến nó thành một màn diễn.",
        )
    return join_reasoning_lines_impl(
        continuity,
        "Câu này nhẹ hơn một lượt đào sâu, nên mình sẽ giữ phản hồi ngắn và tự nhiên.",
        "Mình muốn bám vào nhịp của câu vừa rồi trước, rồi đáp lại vừa đủ gần.",
    )


def build_fast_summary_impl(request: Any) -> str:
    thinking_mode = str(getattr(request, "thinking_mode", "") or "").strip().lower()
    if thinking_mode == "analytical_market":
        return build_analytical_market_summary_impl(request)
    if thinking_mode == "analytical_math":
        return build_analytical_math_summary_impl(request)
    if thinking_mode == "analytical_general":
        return build_analytical_general_summary_impl(request)
    if thinking_mode == "visual_editorial":
        return build_visual_summary_impl(request, simulation=False)
    turn_kind = infer_turn_kind_impl(request)
    node = (request.node or "").strip().lower()
    if node == "supervisor":
        return build_supervisor_summary_impl(request, turn_kind)
    if turn_kind == "emotional":
        return build_emotional_presence_summary_impl(request)
    if turn_kind == "identity":
        return build_identity_summary_impl(request)
    if turn_kind == "simulation":
        return build_visual_summary_impl(request, simulation=True)
    if turn_kind == "visual":
        return build_visual_summary_impl(request, simulation=False)
    if turn_kind == "knowledge":
        return build_knowledge_summary_impl(request)
    return build_relational_summary_impl(request)


def build_fast_action_text_impl(request: Any) -> str:
    thinking_mode = str(getattr(request, "thinking_mode", "") or "").strip().lower()
    plan = extract_evidence_plan_impl(request)
    plan_text = join_short_list_impl(plan, limit=2)
    if thinking_mode == "analytical_market":
        if plan_text:
            folded_plan = fold_text_impl(plan_text)
            if folded_plan.startswith("doi chieu "):
                return f"Mình sẽ {plan_text} rồi mới chốt nhịp thị trường cho bạn."
            return f"Mình sẽ đối chiếu {plan_text} rồi mới chốt nhịp thị trường cho bạn."
        return "Mình sẽ đối chiếu cung cầu, địa chính trị, và nhịp Brent/WTI rồi mới chốt cho bạn."
    if thinking_mode == "analytical_math":
        topic = getattr(request, "topic_hint", "") or extract_topic_hint_impl(request) or ""
        if "con lắc đơn" in fold_text_impl(topic):
            return "Mình sẽ chốt mô hình, giả định góc nhỏ, và phương trình trước rồi mới kéo sang kết luận."
        return "Mình sẽ chốt giả thiết, điều kiện áp dụng, và bước suy ra then chốt trước rồi mới kéo sang kết luận."
    if thinking_mode == "analytical_general":
        if plan_text:
            return f"Mình sẽ neo lại {plan_text} rồi mới chốt mạch phân tích."
        return "Mình sẽ neo lại vài biến số chính rồi mới chốt mạch phân tích."
    turn_kind = infer_turn_kind_impl(request)
    if turn_kind in {"emotional", "identity"}:
        return ""
    if turn_kind == "simulation":
        return "Mình sẽ dựng khung mô phỏng trước rồi mới thêm lớp chuyển động cần thiết."
    if turn_kind == "visual":
        return "Mình sẽ gom vài mốc đáng tin rồi dựng phần nhìn ngắn gọn cho bạn."
    if turn_kind == "knowledge" and (request.tool_context or request.next_action):
        return "Mình sẽ lục lại nguồn cần thiết rồi chắt phần dễ nhầm nhất cho bạn."
    if request.phase == "act" and request.next_action:
        return compact_text_impl(request.next_action, 180)
    return ""


def clamp_sentence_impl(text: str, limit: int) -> str:
    clean = " ".join((text or "").split()).strip()
    if len(clean) <= limit:
        return clean
    sliced = clean[: max(1, limit - 3)].rstrip()
    last_space = sliced.rfind(" ")
    if last_space > int(limit * 0.6):
        sliced = sliced[:last_space]
    return sliced.rstrip(" ,;:") + "..."


def split_sentences_impl(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def normalize_label_impl(text: str, fallback: str) -> str:
    cleaned = sanitize_text_impl(text).replace("\n", " ").strip(" .,:;!-")
    cleaned = re.split(r"[.!?\n]", cleaned, maxsplit=1)[0].strip(" .,:;!-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return fallback
    if len(cleaned) > 48 or len(cleaned.split()) > 7:
        return fallback
    if any(token in cleaned for token in (".", "?", "!", ":")):
        return fallback
    return cleaned


def normalize_summary_impl(text: str, fallback: str = "") -> str:
    cleaned = sanitize_text_impl(text)
    if not cleaned:
        cleaned = sanitize_text_impl(fallback)
    if not cleaned:
        return ""
    return cleaned


def normalize_action_text_impl(text: str, fallback: str = "") -> str:
    cleaned = sanitize_text_impl(text)
    if not cleaned:
        cleaned = sanitize_text_impl(fallback)
    return cleaned


def build_tool_context_summary_impl(tool_names: list[str] | None = None, result: object = None) -> str:
    names = [name for name in (tool_names or []) if name]
    parts: list[str] = []

    for name in names[:4]:
        entry = get_skill_handbook().get_tool_entry(name)
        if entry:
            parts.append(f"{entry.tool_name}: {entry.description}")
        else:
            parts.append(name.replace("tool_", "").replace("_", " "))

    if result is not None:
        result_text = compact_text_impl(str(result), 280)
        if result_text:
            parts.append(f"kết quả vừa nhận: {result_text}")

    return "\n".join(parts)


def fallback_delta_chunks_impl(summary: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", summary) if part.strip()]
    if len(paragraphs) >= 2:
        return paragraphs
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", summary) if part.strip()]
    if len(sentences) > 1:
        chunks: list[str] = []
        bucket = ""
        for sentence in sentences:
            bucket = f"{bucket} {sentence}".strip()
            if bucket.count(".") + bucket.count("!") + bucket.count("?") >= 2:
                chunks.append(bucket)
                bucket = ""
        if bucket:
            chunks.append(bucket)
        return chunks
    return [summary] if summary else []
