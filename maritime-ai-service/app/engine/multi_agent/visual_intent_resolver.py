"""Resolve visual delivery lanes for article figures, chart runtime, apps, and artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Literal


VisualMode = Literal["text", "mermaid", "template", "inline_html", "app"]
PresentationIntent = Literal["text", "article_figure", "chart_runtime", "code_studio_app", "artifact"]
StudioLane = Literal["app", "artifact", "widget"]
ArtifactKind = Literal["html_app", "code_widget", "search_widget", "document", "chart_widget"]
QualityProfile = Literal["draft", "standard", "premium"]
RendererContract = Literal["host_shell", "chart_runtime", "article_figure"]
ThinkingEffort = Literal["low", "medium", "high", "max"]
PreferredRenderSurface = Literal["svg", "canvas", "html", "video"]
PlanningProfile = Literal["article_svg", "chart_svg", "simulation_canvas", "artifact_html"]
CriticPolicy = Literal["none", "standard", "premium"]
LivingExpressionMode = Literal["subtle", "expressive"]

_QUALITY_PROFILE_ORDER: dict[str, int] = {
    "draft": 0,
    "standard": 1,
    "premium": 2,
}

_THINKING_EFFORT_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "max": 3,
}

_LEGACY_VISUAL_TOOL_NAMES = frozenset({
    "tool_generate_interactive_chart",
    "tool_generate_chart",
    "tool_generate_mermaid",
})

_VISUAL_PATCH_KEYWORDS = (
    "highlight",
    "focus on",
    "focus only",
    "bottleneck",
    "giu cung visual",
    "giu nguyen visual",
    "same visual",
    "same visual session",
    "keep the same visual",
    "reuse visual",
    "update visual",
    "patch visual",
    "modify visual",
    "change this visual",
    "annotate",
    "them annotation",
    "lam ro",
    "nhan manh",
    "chi show",
    "chi hien thi",
    "doi thanh 3 buoc",
    "doi thanh",
    "bien thanh",
    "thanh 3 buoc",
    "so do nay",
    "turn this into",
    "convert this visual",
    "filter",
    "loc theo",
    "zoom in",
    "giu app hien tai",
    "giu mini app hien tai",
    "giu widget hien tai",
    "keep the current app",
    "keep the same app",
    "keep the current widget",
    "keep the same widget",
    "update the app",
    "modify the app",
    "change the app",
    "change background",
    "change the background",
    "doi mau nen",
    "doi background",
    "them slider",
    "bo sung slider",
    "them dieu khien",
    "cap nhat app",
)

_VISUAL_PATCH_PREFIXES = (
    "giu ",
    "them ",
    "doi ",
    "sua ",
    "chinh sua ",
    "cap nhat ",
    "bo sung ",
    "nang cap ",
    "lam ro ",
    "highlight ",
    "annotate ",
    "make ",
    "change ",
    "update ",
    "modify ",
    "add ",
    "turn ",
)

_SIMULATION_PATCH_CUES = (
    "con lac",
    "pendulum",
    "vat ly",
    "physics",
    "trong luc",
    "ma sat",
    "keo tha",
    "drag",
    "goc lech",
    "van toc",
    "do thi thoi gian",
    "rule 15",
    "colregs",
    "tau",
    "ship",
)

_SIMULATION_APP_CUES = (
    "pendulum",
    "physics app",
    "physics simulation",
    "drag interaction",
    "drag physics",
    "gravity slider",
    "damping slider",
    "con lac",
    "vat ly",
    "keo tha",
)


_QUIZ_WIDGET_CUES = (
    "quiz widget",
    "quiz app",
    "interactive quiz",
    "quiz interactive",
    "trac nghiem tuong tac",
    "bai quiz tuong tac",
    "widget quiz",
    "html quiz",
    "mini quiz app",
)

_QUIZ_CREATION_CUES = (
    "tao",
    "lam",
    "dung",
    "xay",
    "soan",
    "thiet ke",
    "build",
    "create",
    "generate",
)

_QUIZ_REQUEST_CUES = (
    "quiz",
    "quizz",
    "trac nghiem",
    "bai quiz",
    "bo quiz",
)

_QUIZ_CREATION_RAW_CUES = (
    "tạo",
    "làm",
    "dựng",
    "xây",
    "soạn",
    "thiết kế",
    "build",
    "create",
    "generate",
)

_QUIZ_REQUEST_RAW_CUES = (
    "quiz",
    "quizz",
    "trắc nghiệm",
    "bài quiz",
    "bộ quiz",
)


def _looks_like_quiz_app_request(query: str, normalized: str) -> bool:
    if not query and not normalized:
        return False
    raw_lower = query.lower().strip()
    has_quiz_request = _contains_any(normalized, _QUIZ_REQUEST_CUES) or _contains_any(raw_lower, _QUIZ_REQUEST_RAW_CUES)
    has_creation_intent = _contains_any(normalized, _QUIZ_CREATION_CUES) or _contains_any(raw_lower, _QUIZ_CREATION_RAW_CUES)
    return has_quiz_request and has_creation_intent


def _looks_like_recipe_backed_simulation(normalized: str) -> bool:
    return _contains_any(normalized, _SIMULATION_APP_CUES + _SIMULATION_PATCH_CUES)


@dataclass(frozen=True)
class VisualIntentDecision:
    mode: VisualMode
    force_tool: bool = False
    visual_type: str | None = None
    reason: str = ""
    presentation_intent: PresentationIntent = "text"
    preferred_tool: str | None = None
    figure_budget: int = 1
    studio_lane: StudioLane | None = None
    artifact_kind: ArtifactKind | None = None
    quality_profile: QualityProfile = "standard"
    renderer_contract: RendererContract | None = None
    preferred_render_surface: PreferredRenderSurface = "svg"
    planning_profile: PlanningProfile = "article_svg"
    thinking_floor: ThinkingEffort = "medium"
    critic_policy: CriticPolicy = "standard"
    living_expression_mode: LivingExpressionMode = "expressive"
    renderer_kind_hint: str = ""


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower()).replace("đ", "d")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9\s/+.-]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _metadata_value(source: dict[str, Any] | None, *keys: str) -> str:
    if not isinstance(source, dict):
        return ""
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def merge_quality_profile(*values: Any) -> QualityProfile:
    best = ""
    best_rank = -1
    for value in values:
        candidate = str(value or "").strip().lower()
        rank = _QUALITY_PROFILE_ORDER.get(candidate)
        if rank is None:
            continue
        if rank > best_rank:
            best = candidate
            best_rank = rank
    return (best or "standard")  # type: ignore[return-value]


def merge_thinking_effort(base: str | None, recommended: str | None) -> str | None:
    base_value = str(base or "").strip().lower()
    recommended_value = str(recommended or "").strip().lower()

    if base_value not in _THINKING_EFFORT_ORDER:
        return recommended_value or None
    if recommended_value not in _THINKING_EFFORT_ORDER:
        return base_value
    if _THINKING_EFFORT_ORDER[recommended_value] > _THINKING_EFFORT_ORDER[base_value]:
        return recommended_value
    return base_value


def _looks_like_app_followup_patch(normalized: str) -> bool:
    if not normalized:
        return False
    if not detect_visual_patch_request(normalized):
        return False
    return _contains_any(
        normalized,
        (
            " app ",
            "app hien tai",
            "same app",
            "current app",
            "widget",
            "slider",
            "trong luc",
            "ma sat",
            "drag",
            "keo tha",
            "preview",
            "background",
            "mau nen",
            "code studio",
            "goc lech",
            "van toc",
            "pendulum",
            "con lac",
        ),
    )


def _infer_followup_simulation_type(normalized: str) -> str | None:
    return "simulation" if _contains_any(normalized, _SIMULATION_PATCH_CUES) else None


def detect_visual_patch_request(query: str) -> bool:
    """Return True when the query looks like a follow-up edit to an existing visual."""
    normalized = _normalize(query)
    if not normalized:
        return False
    if _contains_any(normalized, _VISUAL_PATCH_KEYWORDS):
        return True
    return normalized.startswith(_VISUAL_PATCH_PREFIXES)


def preferred_visual_tool_name() -> str:
    """Return the preferred rich visual tool for the current runtime mode."""
    return "tool_generate_visual"


def recommended_visual_thinking_effort(
    query: str,
    *,
    active_code_session: dict[str, Any] | None = None,
) -> ThinkingEffort | None:
    normalized = _normalize(query)
    if not normalized:
        return None

    visual_decision = resolve_visual_intent(query)
    session_quality = _metadata_value(
        active_code_session,
        "quality_profile",
        "qualityProfile",
    )
    session_lane = _metadata_value(
        active_code_session,
        "studio_lane",
        "studioLane",
    )
    session_artifact_kind = _metadata_value(
        active_code_session,
        "artifact_kind",
        "artifactKind",
    )
    effective_quality = merge_quality_profile(visual_decision.quality_profile, session_quality)
    recommended_floor: ThinkingEffort | None = visual_decision.thinking_floor

    if visual_decision.presentation_intent == "code_studio_app":
        if visual_decision.visual_type == "simulation":
            if _looks_like_recipe_backed_simulation(normalized):
                recommended_floor = merge_thinking_effort(recommended_floor, "high")  # type: ignore[assignment]
            else:
                recommended_floor = merge_thinking_effort(  # type: ignore[assignment]
                    recommended_floor,
                    "max" if effective_quality == "premium" else "high",
                )
            return recommended_floor
        if effective_quality == "premium":
            return merge_thinking_effort(recommended_floor, "max")  # type: ignore[return-value]
        if session_lane in {"app", "widget"} or visual_decision.studio_lane in {"app", "widget"}:
            return merge_thinking_effort(recommended_floor, "high")  # type: ignore[return-value]

    if visual_decision.presentation_intent == "artifact":
        artifact_kind = visual_decision.artifact_kind or session_artifact_kind
        if artifact_kind in {"html_app", "code_widget", "search_widget"}:
            return merge_thinking_effort(recommended_floor, "high")  # type: ignore[return-value]

    if visual_decision.presentation_intent == "chart_runtime":
        if effective_quality == "premium":
            return merge_thinking_effort(recommended_floor, "high")  # type: ignore[return-value]
        return recommended_floor

    if visual_decision.presentation_intent == "article_figure":
        if visual_decision.mode == "inline_html" or effective_quality == "premium":
            return merge_thinking_effort(recommended_floor, "high")  # type: ignore[return-value]
        return recommended_floor

    if visual_decision.presentation_intent == "artifact":
        return recommended_floor

    return recommended_floor if visual_decision.force_tool else None


def _resolve_preferred_tool(
    visual_decision: VisualIntentDecision,
) -> str | None:
    if visual_decision.preferred_tool:
        return visual_decision.preferred_tool
    if visual_decision.mode in {"template", "inline_html", "app"}:
        return preferred_visual_tool_name()
    if visual_decision.mode == "mermaid":
        return "tool_generate_mermaid"
    return None


def required_visual_tool_names(
    visual_decision: VisualIntentDecision,
) -> tuple[str, ...]:
    """Return the visual tool names that should remain available for an explicit intent."""
    if not visual_decision.force_tool:
        return ()

    tool_name = _resolve_preferred_tool(visual_decision)
    return (tool_name,) if tool_name else ()


def filter_tools_for_visual_intent(
    tools: list[Any],
    visual_decision: VisualIntentDecision,
    *,
    structured_visuals_enabled: bool,
) -> list[Any]:
    """Reduce drift toward legacy visual tools when structured intent is explicit."""
    if not structured_visuals_enabled:
        return tools

    allowed_names = set(
        required_visual_tool_names(visual_decision)
    )
    if not allowed_names:
        return tools

    filtered: list[Any] = []
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "")
        if tool_name in allowed_names:
            filtered.append(tool)
            continue
        if tool_name in _LEGACY_VISUAL_TOOL_NAMES:
            continue
        filtered.append(tool)

    return filtered


def resolve_visual_intent(query: str) -> VisualIntentDecision:
    """Classify a user request into the most suitable visual delivery mode."""
    return _resolve_visual_intent_core(query)


def _infer_figure_budget(
    normalized: str,
    *,
    visual_type: str | None,
    presentation_intent: PresentationIntent,
) -> int:
    if presentation_intent == "text":
        return 1

    if presentation_intent == "code_studio_app":
        return 1

    if presentation_intent == "artifact":
        return 1

    if presentation_intent == "chart_runtime":
        if _contains_any(normalized, ("explain in charts", "explain with charts", "giai thich", "step by step")):
            return 2
        return 1

    if presentation_intent == "article_figure":
        if _contains_any(
            normalized,
            (
                "explain in charts",
                "explain with charts",
                "step by step",
                "giai thich",
                "co che",
                "trade off",
                "benchmark",
                "kien truc",
            ),
        ):
            return 3 if visual_type in {"chart", "comparison", "architecture"} else 2
        if visual_type in {"comparison", "process", "architecture", "concept", "chart"}:
            return 2
    return 1


def _resolve_visual_intent_core(query: str) -> VisualIntentDecision:
    """Core classification logic (before code-gen upgrade)."""
    normalized = _normalize(query)
    if not normalized:
        return VisualIntentDecision(mode="text", reason="empty-query")

    if _contains_any(
        normalized,
        (
            "visual studio",
            "visual basic",
            "artifact repository",
        ),
    ):
        return VisualIntentDecision(mode="text", reason="false-positive-visual")

    if _contains_any(
        normalized,
        (
            "landing page",
            "website",
            "microsite",
            "web app",
            "html app",
            "html file",
            "file html",
            "excel file",
            "spreadsheet",
            "word file",
            "docx",
            "xlsx",
            "download file",
            "de nhung",
            "embed",
            "artifact",
            "react app",
        ),
    ):
        return VisualIntentDecision(
            mode="app",
            force_tool=True,
            reason="artifact-request",
            presentation_intent="artifact",
            preferred_tool="tool_create_visual_code",
            figure_budget=1,
            studio_lane="artifact",
            artifact_kind="html_app",
            quality_profile="premium",
            renderer_contract="host_shell",
            preferred_render_surface="html",
            planning_profile="artifact_html",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="subtle",
        )

    if _contains_any(
        normalized,
        (
            "mini app",
            "mini tool",
            "interactive tool",
            "dashboard",
            "dashboard app",
            "simulation",
            "simulate",
            "simulator",
            "mo phong",
            "mo phong vat ly",
            "keo tha",
            "drag and drop",
            "interactive table",
        ),
    ) or _contains_any(normalized, _QUIZ_WIDGET_CUES) or _looks_like_quiz_app_request(query, normalized) or (
        "app" in normalized
        and _contains_any(normalized, _SIMULATION_APP_CUES)
    ):
        visual_type = "simulation" if _contains_any(
            normalized,
            (
                "simulation",
                "simulate",
                "simulator",
                "mo phong",
                "mo phong vat ly",
                "keo tha",
                "drag and drop",
                "drag interaction",
                "pendulum",
                "physics",
                "con lac",
            ),
        ) else None
        return VisualIntentDecision(
            mode="app",
            force_tool=True,
            visual_type=visual_type,
            reason="app-request",
            presentation_intent="code_studio_app",
            preferred_tool="tool_create_visual_code",
            figure_budget=1,
            studio_lane="app",
            artifact_kind="html_app",
            quality_profile="premium" if visual_type == "simulation" else "standard",
            renderer_contract="host_shell",
            preferred_render_surface="canvas" if visual_type == "simulation" else "html",
            planning_profile="simulation_canvas" if visual_type == "simulation" else "artifact_html",
            thinking_floor="max" if visual_type == "simulation" else "high",
            critic_policy="premium" if visual_type == "simulation" else "standard",
            living_expression_mode="expressive" if visual_type == "simulation" else "subtle",
        )

    if _looks_like_app_followup_patch(normalized):
        visual_type = _infer_followup_simulation_type(normalized)
        return VisualIntentDecision(
            mode="app",
            force_tool=True,
            visual_type=visual_type,
            reason="app-followup-patch",
            presentation_intent="code_studio_app",
            preferred_tool="tool_create_visual_code",
            figure_budget=1,
            studio_lane="app",
            artifact_kind="html_app",
            quality_profile="premium" if visual_type == "simulation" else "standard",
            renderer_contract="host_shell",
            preferred_render_surface="canvas" if visual_type == "simulation" else "html",
            planning_profile="simulation_canvas" if visual_type == "simulation" else "artifact_html",
            thinking_floor="max" if visual_type == "simulation" else "high",
            critic_policy="premium" if visual_type == "simulation" else "standard",
            living_expression_mode="expressive" if visual_type == "simulation" else "subtle",
        )

    if _contains_any(
        normalized,
        (
            "flowchart",
            "timeline",
            "sequence diagram",
            "state diagram",
            "er diagram",
            "mindmap",
            "mind map",
            "so do",
        ),
    ):
        return VisualIntentDecision(
            mode="mermaid",
            force_tool=True,
            reason="diagram-request",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_mermaid",
            figure_budget=1,
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    if _contains_any(
        normalized,
        (
            "animated",
            "animation",
            "animate",
            "hero visual",
            "editorial visual",
            "storyboard",
            "bespoke visual",
            "visual walkthrough",
            "trinh bay dep",
            "trinh bay hien dai",
        ),
    ):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="concept",
            reason="bespoke-inline-html",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=2,
            quality_profile="premium",
            renderer_contract="article_figure",
            preferred_render_surface="html",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="premium",
            living_expression_mode="expressive",
        )

    if _contains_any(
        normalized,
        (
            "chart",
            "charts",
            "bar chart",
            "line chart",
            "pie chart",
            "doughnut chart",
            "radar chart",
            "trend",
            "xu huong",
            "thong ke",
            "bieu do",
            "phan bo",
            "du lieu so",
            "kpi",
            "explain in charts",
            "explain with charts",
        ),
    ):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="chart",
            reason="chart-runtime",
            presentation_intent="chart_runtime",
            preferred_tool="tool_generate_visual",
            figure_budget=_infer_figure_budget(
                normalized,
                visual_type="chart",
                presentation_intent="chart_runtime",
            ),
            quality_profile="premium" if _contains_any(normalized, ("benchmark", "kpi", "perplexity")) else "standard",
            renderer_contract="chart_runtime",
            preferred_render_surface="svg",
            planning_profile="chart_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="subtle",
            renderer_kind_hint="recharts",
        )

    if _contains_any(normalized, ("so sanh", "compare", "vs ", "khac nhau", "uu nhuoc diem")):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="comparison",
            reason="comparison",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=_infer_figure_budget(
                normalized,
                visual_type="comparison",
                presentation_intent="article_figure",
            ),
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    if _contains_any(normalized, ("quy trinh", "cac buoc", "step by step", "how it works", "process")):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="process",
            reason="process",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=_infer_figure_budget(
                normalized,
                visual_type="process",
                presentation_intent="article_figure",
            ),
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    if _contains_any(normalized, ("kien truc", "architecture", "he thong", "layer", "stack")):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="architecture",
            reason="architecture",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=_infer_figure_budget(
                normalized,
                visual_type="architecture",
                presentation_intent="article_figure",
            ),
            quality_profile="premium",
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="premium",
            living_expression_mode="expressive",
        )

    if _contains_any(normalized, ("ma tran", "matrix", "heatmap", "quadrant", "2x2")):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="matrix",
            reason="matrix",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=2,
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    if _contains_any(normalized, ("infographic", "tong quan nhanh", "facts at a glance", "highlights")):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="infographic",
            reason="infographic",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=2,
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    if _contains_any(
        normalized,
        (
            "concept map",
            "ban do khai niem",
            "khai niem bang so do",
            "explain visually",
            "visualize this concept",
            "truc quan hoa",
        ),
    ):
        return VisualIntentDecision(
            mode="inline_html",
            force_tool=True,
            visual_type="concept",
            reason="concept",
            presentation_intent="article_figure",
            preferred_tool="tool_generate_visual",
            figure_budget=2,
            renderer_contract="article_figure",
            preferred_render_surface="svg",
            planning_profile="article_svg",
            thinking_floor="high",
            critic_policy="standard",
            living_expression_mode="expressive",
        )

    return VisualIntentDecision(mode="text", reason="plain-text")
