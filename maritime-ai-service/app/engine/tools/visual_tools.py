"""
Rich Visual Widget Generator — Claude-level educational diagrams.
Sprint 229: Custom SVG/HTML visuals rendered inline in chat via ```widget blocks.

Generates self-contained HTML+CSS+SVG for:
  - comparison: Side-by-side visual comparison (like Standard vs Linear Attention)
  - process: Step-by-step flow with arrows
  - matrix: Color-coded grid visualization
  - architecture: Layered system diagram
  - concept: Central idea with radiating branches
  - infographic: Stats/icons/mixed content

Feature-gated by enable_chart_tools (shared with chart_tools).
"""

import logging
import functools
from typing import Any

from app.engine.tools.native_tool import tool
from pydantic import ValidationError
from app.engine.tools.visual_html_builders import (
    _DESIGN_CSS,
    _BUILDERS,
    _build_architecture_html,
    _build_chart_html,
    _build_comparison_html,
    _build_concept_html,
    _build_infographic_html,
    _build_map_lite_html,
    _build_matrix_html,
    _build_process_html,
    _build_timeline_html,
    _normalize_chart_spec,
    _wrap_html,
)
from app.engine.tools.visual_pendulum_scaffold import (
    _build_pendulum_simulation_scaffold,
    _looks_like_pendulum_simulation,
)
from app.engine.tools.visual_code_quality import (
    maybe_upgrade_code_studio_output_impl,
    postprocess_visual_html_impl,
    quality_score_visual_output_impl,
    resolve_code_html_impl,
    resolve_fallback_html_impl,
    validate_code_studio_output_impl,
)
from app.engine.tools.visual_group_planner import (
    build_bridge_infographic_spec_impl,
    build_takeaway_claim_impl,
    build_takeaway_infographic_spec_impl,
    collect_story_points_impl,
    estimate_query_figure_pressure_impl,
    estimate_spec_figure_pressure_impl,
    normalize_visual_query_text_impl,
    plan_auto_group_figure_budget_impl,
    should_auto_group_visual_request_impl,
    supports_auto_grouping_impl,
)
from app.engine.tools.visual_payload_runtime import (
    apply_runtime_patch_defaults_impl,
    build_artifact_handoff_impl,
    build_auto_grouped_payloads_impl,
    build_multi_figure_payloads_impl,
    coerce_visual_payload_data_impl,
    normalize_visual_payload_impl,
    parse_visual_payload_impl,
    parse_visual_payloads_impl,
)
from app.engine.tools.visual_scene_contract import (
    build_annotations_impl,
    build_controls_impl,
    build_runtime_manifest_impl,
    build_scene_impl,
    enrich_scene_contract_impl,
    infer_interaction_mode_impl,
    infer_patch_strategy_impl,
    infer_runtime_impl,
    infer_scene_render_surface_impl,
    infer_shell_variant_impl,
)
from app.engine.tools.visual_tool_runtime import (
    tool_create_visual_code_impl,
    tool_generate_visual_impl,
)
from app.engine.tools.visual_payload_models import VisualPayloadV1
from app.engine.tools.visual_surface_support import (
    clean_summary_text_impl,
    default_visual_claim_impl,
    default_visual_summary_impl,
    default_visual_title_impl,
    generate_figure_group_id_impl,
    generate_visual_session_id_impl,
    infer_chrome_mode_impl,
    infer_pedagogical_role_impl,
    log_visual_telemetry_impl,
    named_count_impl,
    resolve_renderer_kind_impl,
    sanitize_summary_candidate_impl,
    should_keep_structured_renderer_impl,
    slugify_fragment_impl,
    spec_text_impl,
)
from app.engine.tools.runtime_context import get_current_tool_runtime_context
from app.engine.tools.visual_runtime_metadata import (
    _get_runtime_visual_metadata_impl,
    _runtime_metadata_text_impl,
    _runtime_metadata_int_impl,
    _runtime_presentation_intent_impl,
    _runtime_renderer_contract_impl,
    _runtime_quality_profile_impl,
    _runtime_studio_lane_impl,
    _runtime_artifact_kind_impl,
    _runtime_code_studio_version_impl,
    _runtime_visual_user_query_impl,
    _runtime_preferred_render_surface_impl,
    _runtime_planning_profile_impl,
    _runtime_thinking_floor_impl,
    _runtime_critic_policy_impl,
    _runtime_living_expression_mode_impl,
    _metadata_text_impl,
)

logger = logging.getLogger(__name__)


CORE_STRUCTURED_VISUAL_TYPES = (
    "comparison",
    "process",
    "matrix",
    "architecture",
    "concept",
    "infographic",
    "chart",
    "timeline",
    "map_lite",
)

def _default_visual_title(visual_type: str) -> str:
    return default_visual_title_impl(visual_type)


def _generate_figure_group_id(visual_type: str) -> str:
    return generate_figure_group_id_impl(visual_type)


def _clean_summary_text(value: Any) -> str:
    return clean_summary_text_impl(value)


def _spec_text(spec: dict[str, Any], *keys: str) -> str:
    return spec_text_impl(spec, keys, clean_summary_text=_clean_summary_text)


def _named_count(items: Any) -> int:
    return named_count_impl(items)


def _sanitize_summary_candidate(value: str, visual_type: str, title: str) -> str:
    return sanitize_summary_candidate_impl(
        value,
        visual_type,
        title,
        clean_summary_text=_clean_summary_text,
    )

def _default_visual_summary(visual_type: str, title: str, spec: dict[str, Any] | None = None) -> str:
    return default_visual_summary_impl(
        visual_type,
        title,
        spec,
        default_visual_title=_default_visual_title,
        spec_text=_spec_text,
        clean_summary_text=_clean_summary_text,
        named_count=_named_count,
    )

def _infer_pedagogical_role(
    visual_type: str,
    spec: dict[str, Any],
    provided: str = "",
) -> str:
    return infer_pedagogical_role_impl(visual_type, spec, provided)

def _infer_chrome_mode(
    renderer_kind: str,
    shell_variant: str,
    provided: str = "",
) -> str:
    return infer_chrome_mode_impl(renderer_kind, shell_variant, provided)

def _default_visual_claim(
    visual_type: str,
    title: str,
    summary: str,
    spec: dict[str, Any],
) -> str:
    return default_visual_claim_impl(
        visual_type,
        title,
        summary,
        spec,
        clean_summary_text=_clean_summary_text,
        spec_text=_spec_text,
    )

def _llm_first_visual_codegen_enabled() -> bool:
    from app.core.config import get_settings

    return bool(getattr(get_settings(), "enable_llm_code_gen_visuals", False))


def _should_keep_structured_renderer(requested: str = "") -> bool:
    return should_keep_structured_renderer_impl(
        requested,
        runtime_presentation_intent=_runtime_presentation_intent,
        runtime_metadata_text=_runtime_metadata_text,
    )

_supports_auto_grouping = supports_auto_grouping_impl
_collect_story_points = functools.partial(
    collect_story_points_impl,
    clean_summary_text=_clean_summary_text,
    spec_text=_spec_text,
)
_build_takeaway_infographic_spec = functools.partial(
    build_takeaway_infographic_spec_impl,
    collect_story_points=_collect_story_points,
    named_count=_named_count,
)
_build_takeaway_claim = functools.partial(build_takeaway_claim_impl)
_normalize_visual_query_text = normalize_visual_query_text_impl
_estimate_query_figure_pressure = functools.partial(
    estimate_query_figure_pressure_impl,
    normalize_visual_query_text=_normalize_visual_query_text,
)
_estimate_spec_figure_pressure = functools.partial(
    estimate_spec_figure_pressure_impl,
    named_count=_named_count,
)
_plan_auto_group_figure_budget = functools.partial(
    plan_auto_group_figure_budget_impl,
    supports_auto_grouping=_supports_auto_grouping,
    get_runtime_visual_metadata=lambda: _get_runtime_visual_metadata(),
    estimate_query_figure_pressure=lambda query: _estimate_query_figure_pressure(query),
    estimate_spec_figure_pressure=lambda visual_type, spec: _estimate_spec_figure_pressure(visual_type, spec),
)
_build_bridge_infographic_spec = functools.partial(
    build_bridge_infographic_spec_impl,
    build_takeaway_infographic_spec=_build_takeaway_infographic_spec,
    collect_story_points=_collect_story_points,
)
_should_auto_group_visual_request = functools.partial(
    should_auto_group_visual_request_impl,
    plan_auto_group_figure_budget=_plan_auto_group_figure_budget,
)


def _log_visual_telemetry(event_name: str, **fields: Any) -> None:
    """Structured logger hook for visual pipeline telemetry."""
    log_visual_telemetry_impl(event_name, logger=logger, fields=fields or None)

def _slugify_fragment(value: str) -> str:
    return slugify_fragment_impl(value)

def _generate_visual_session_id(visual_type: str) -> str:
    return generate_visual_session_id_impl(visual_type, slugify_fragment=_slugify_fragment)

_build_scene = build_scene_impl
_build_controls = build_controls_impl
_build_annotations = build_annotations_impl
_infer_interaction_mode = infer_interaction_mode_impl


def _infer_renderer_kind(visual_type: str, spec: dict[str, Any], requested: str = "") -> str:
    candidate = requested.strip()
    if candidate in {"template", "inline_html", "app"}:
        return candidate
    if any(isinstance(spec.get(key), str) and str(spec.get(key)).strip() for key in ("html", "markup", "custom_html", "template_html")):
        return "inline_html"
    if _runtime_presentation_intent() in {"article_figure", "chart_runtime"}:
        return "inline_html" if _llm_first_visual_codegen_enabled() else "template"

    # Code-gen route: explanatory types with HTML builders → inline_html iframe
    from app.core.config import get_settings
    if getattr(get_settings(), "enable_code_gen_visuals", False):
        if visual_type in _BUILDERS:
            return "inline_html"

    return "template"


_infer_runtime = infer_runtime_impl


def _resolve_renderer_kind(visual_type: str, spec: dict[str, Any], requested: str = "") -> str:
    return resolve_renderer_kind_impl(
        visual_type,
        spec,
        requested,
        should_keep_structured_renderer=_should_keep_structured_renderer,
        runtime_presentation_intent=_runtime_presentation_intent,
        llm_first_visual_codegen_enabled=_llm_first_visual_codegen_enabled,
    )

_infer_renderer_kind = _resolve_renderer_kind


_infer_shell_variant = infer_shell_variant_impl
_infer_patch_strategy = infer_patch_strategy_impl
_resolve_code_html = resolve_code_html_impl


_validate_code_studio_output = validate_code_studio_output_impl
_postprocess_visual_html = postprocess_visual_html_impl
_quality_score_visual_output = quality_score_visual_output_impl
_maybe_upgrade_code_studio_output = maybe_upgrade_code_studio_output_impl
_infer_scene_render_surface = infer_scene_render_surface_impl
_enrich_scene_contract = enrich_scene_contract_impl
_resolve_fallback_html = resolve_fallback_html_impl
_build_runtime_manifest = build_runtime_manifest_impl


@tool
def tool_generate_visual(
    visual_type: str = "chart",
    spec_json: str = "{}",
    title: str = "",
    summary: str = "",
    subtitle: str = "",
    visual_session_id: str = "",
    operation: str = "open",
    renderer_kind: str = "",
    shell_variant: str = "",
    patch_strategy: str = "",
    narrative_anchor: str = "",
    runtime_manifest_json: str = "",
    code_html: str = "",
) -> str:
    """Tạo biểu đồ hoặc minh họa inline trong chat.

    Wiii dùng tool này để tạo visual giúp người đọc hiểu nhanh hơn.
    Visual hiện trực tiếp trong chat — không cần mở app khác.

    CÁCH DÙNG ĐƠN GIẢN NHẤT:
    - Chỉ cần gửi code_html (HTML fragment) — đây là param duy nhất cần thiết
    - visual_type và spec_json tự động có default, không bắt buộc
    - Ví dụ: tool_generate_visual(code_html="<style>...</style><div>...</div>")

    Example specs for rich output:

    architecture:
      {"layers": [
        {"name": "API Gateway", "description": "Nhận request từ client, xác thực, rate limiting", "components": ["Auth", "Rate Limiter", "Router"]},
        {"name": "Service Layer", "description": "Xử lý business logic, orchestrate giữa các service", "components": ["UserService", "OrderService", "PaymentService"]},
        {"name": "Data Layer", "description": "Lưu trữ và truy vấn dữ liệu", "components": ["PostgreSQL", "Redis Cache", "S3"]}
      ]}

    comparison:
      {"left": {"title": "Monolith", "subtitle": "Kiến trúc truyền thống", "highlight": "Đơn giản triển khai, khó scale", "items": ["Single codebase", "Shared database", "Tight coupling"]},
       "right": {"title": "Microservices", "subtitle": "Kiến trúc phân tán", "highlight": "Scale linh hoạt, phức tạp vận hành", "items": ["Independent services", "Own database", "Loose coupling"]}}

    process:
      {"steps": [
        {"title": "Request đến", "description": "Client gửi HTTP request tới API Gateway", "icon": "1", "signals": ["HTTP/HTTPS", "REST/GraphQL"]},
        {"title": "Xác thực", "description": "Gateway kiểm tra JWT token và quyền truy cập", "icon": "2", "signals": ["JWT", "RBAC"]},
        {"title": "Xử lý", "description": "Service xử lý business logic và trả kết quả", "icon": "3", "signals": ["Business Logic", "Response"]}
      ]}

    code_html:
      HTML/CSS trực tiếp cho visual. Font: system-ui. Background: transparent.
      Xen kẽ 5 màu gradient: #D97757 (cam), #85CDCA (mint), #FFD166 (vàng), #C9B1FF (tím), #E8A87C (cam nhạt).
      Title nhỏ (15px font-weight:600). Label rộng (min-width:160px, word-wrap).
      Mỗi bar có giá trị số bên phải.

      Ví dụ horizontal bar chart (labels rộng, có value, xen kẽ màu):
        code_html='<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:transparent;color:#333}.root{max-width:640px;padding:16px 0}.title{font-size:15px;font-weight:600;margin-bottom:4px}.sub{font-size:13px;color:#999;margin-bottom:20px}.rows{display:flex;flex-direction:column;gap:12px}.row{display:flex;align-items:center;gap:12px}.lbl{min-width:160px;max-width:200px;font-size:13px;color:#555;text-align:right;font-weight:500;word-wrap:break-word}.track{flex:1;height:28px;background:#f5f2ef;border-radius:6px;overflow:hidden}.fill{height:100%;border-radius:6px}.val{font-size:12px;font-weight:600;color:#555;min-width:52px}</style><div class="root"><div class="title">Yếu tố ảnh hưởng giá dầu 2024</div><div class="sub">Mức độ tác động (%), nguồn: IEA World Energy Outlook</div><div class="rows"><div class="row"><div class="lbl">Căng thẳng địa chính trị</div><div class="track"><div class="fill" style="width:95%;background:linear-gradient(90deg,#D97757,#e89a7c)"></div></div><div class="val">95%</div></div><div class="row"><div class="lbl">Chính sách cắt giảm OPEC+</div><div class="track"><div class="fill" style="width:82%;background:linear-gradient(90deg,#85CDCA,#a8ddd8)"></div></div><div class="val">82%</div></div><div class="row"><div class="lbl">Nhu cầu tiêu thụ toàn cầu</div><div class="track"><div class="fill" style="width:78%;background:linear-gradient(90deg,#FFD166,#ffe09a)"></div></div><div class="val">78%</div></div><div class="row"><div class="lbl">Rủi ro gián đoạn chuỗi cung ứng</div><div class="track"><div class="fill" style="width:65%;background:linear-gradient(90deg,#C9B1FF,#ddd0ff)"></div></div><div class="val">65%</div></div><div class="row"><div class="lbl">Tăng trưởng năng lượng tái tạo</div><div class="track"><div class="fill" style="width:45%;background:linear-gradient(90deg,#E8A87C,#f0c4a8)"></div></div><div class="val">45%</div></div></div></div>'
    """
    return tool_generate_visual_impl(
        visual_type=visual_type,
        spec_json=spec_json,
        title=title,
        summary=summary,
        subtitle=subtitle,
        visual_session_id=visual_session_id,
        operation=operation,
        renderer_kind=renderer_kind,
        shell_variant=shell_variant,
        patch_strategy=patch_strategy,
        narrative_anchor=narrative_anchor,
        runtime_manifest_json=runtime_manifest_json,
        code_html=code_html,
        core_structured_visual_types=CORE_STRUCTURED_VISUAL_TYPES,
        resolve_code_html=_resolve_code_html,
        build_multi_figure_payloads=_build_multi_figure_payloads,
        builders=_BUILDERS,
        logger=logger,
        runtime_metadata_text=_runtime_metadata_text,
        should_keep_structured_renderer=_should_keep_structured_renderer,
        resolve_renderer_kind=_resolve_renderer_kind,
        apply_runtime_patch_defaults=_apply_runtime_patch_defaults,
        build_auto_grouped_payloads=_build_auto_grouped_payloads,
        resolve_fallback_html=_resolve_fallback_html,
        normalize_visual_payload=_normalize_visual_payload,
        log_visual_telemetry=_log_visual_telemetry,
    )


@tool
def tool_create_visual_code(
    code_html: str,
    title: str = "",
    subtitle: str = "",
    visual_session_id: str = "",
) -> str:
    """Create Code Studio app/widget/artifact markup for host-governed runtimes.

    Use this only for `code_studio_app` or `artifact` lanes such as simulations,
    quiz widgets, search/code widgets, mini tools, and embeddable HTML apps.
    Ordinary explanatory figures and chart runtime outputs should stay on
    `tool_generate_visual`.
    """
    return tool_create_visual_code_impl(
        code_html=code_html,
        title=title,
        subtitle=subtitle,
        visual_session_id=visual_session_id,
        runtime_presentation_intent=_runtime_presentation_intent,
        runtime_studio_lane=_runtime_studio_lane,
        runtime_artifact_kind=_runtime_artifact_kind,
        runtime_metadata_text=_runtime_metadata_text,
        runtime_quality_profile=_runtime_quality_profile,
        runtime_code_studio_version=_runtime_code_studio_version,
        maybe_upgrade_code_studio_output=_maybe_upgrade_code_studio_output,
        validate_code_studio_output=_validate_code_studio_output,
        quality_score_visual_output=_quality_score_visual_output,
        wrap_html=_wrap_html,
        apply_runtime_patch_defaults=_apply_runtime_patch_defaults,
        normalize_visual_payload=_normalize_visual_payload,
        log_visual_telemetry=_log_visual_telemetry,
        logger=logger,
    )

tool_create_visual_code.description = (
    "Create app/widget/artifact UI with raw HTML/CSS/SVG/JS for Code Studio. "
    "Use only for code_studio_app or artifact lanes such as simulation, quiz, "
    "search/code widget, mini tool, or HTML app. Do not use as the default path "
    "for ordinary explanatory visuals or normal charts when tool_generate_visual is sufficient."
)


def get_visual_tools() -> list:
    """Return list of rich visual tools. Feature-gated by enable_chart_tools."""
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "enable_chart_tools", False):
        return []

    tools = []
    if getattr(settings, "enable_structured_visuals", False):
        tools.append(tool_generate_visual)
    # tool_create_visual_code: tool riêng cho LLM code-gen visuals
    if getattr(settings, "enable_llm_code_gen_visuals", False):
        tools.append(tool_create_visual_code)
    return tools
def _get_runtime_visual_metadata() -> dict[str, Any]:
    return _get_runtime_visual_metadata_impl(get_current_tool_runtime_context)


def _runtime_metadata_text(key: str, default: str = "") -> str:
    return _runtime_metadata_text_impl(key, default, _get_runtime_visual_metadata)


def _runtime_metadata_int(key: str, default: int = 0) -> int:
    return _runtime_metadata_int_impl(key, default, _get_runtime_visual_metadata)


def _runtime_presentation_intent() -> str:
    return _runtime_presentation_intent_impl(_runtime_metadata_text)


def _runtime_renderer_contract() -> str:
    return _runtime_renderer_contract_impl(_runtime_metadata_text)


def _runtime_quality_profile() -> str:
    return _runtime_quality_profile_impl(_runtime_metadata_text)


def _runtime_studio_lane() -> str:
    return _runtime_studio_lane_impl(_runtime_metadata_text)


def _runtime_artifact_kind() -> str:
    return _runtime_artifact_kind_impl(_runtime_metadata_text)


def _runtime_code_studio_version() -> int:
    return _runtime_code_studio_version_impl(_runtime_metadata_int)


def _runtime_visual_user_query() -> str:
    return _runtime_visual_user_query_impl(_runtime_metadata_text)


def _runtime_preferred_render_surface() -> str:
    return _runtime_preferred_render_surface_impl(_runtime_metadata_text)


def _runtime_planning_profile() -> str:
    return _runtime_planning_profile_impl(_runtime_metadata_text)


def _runtime_thinking_floor() -> str:
    return _runtime_thinking_floor_impl(_runtime_metadata_text)


def _runtime_critic_policy() -> str:
    return _runtime_critic_policy_impl(_runtime_metadata_text)


def _runtime_living_expression_mode() -> str:
    return _runtime_living_expression_mode_impl(_runtime_metadata_text)


def _metadata_text(metadata: dict[str, Any] | None, key: str, default: str = "") -> str:
    return _metadata_text_impl(metadata, key, default)


_build_artifact_handoff = functools.partial(
    build_artifact_handoff_impl,
    default_visual_title=_default_visual_title,
    clean_summary_text=_clean_summary_text,
)
_normalize_visual_payload = functools.partial(
    normalize_visual_payload_impl,
    payload_class=VisualPayloadV1,
    default_visual_title=_default_visual_title,
    sanitize_summary_candidate=_sanitize_summary_candidate,
    default_visual_summary=_default_visual_summary,
    resolve_renderer_kind=_resolve_renderer_kind,
    infer_runtime=_infer_runtime,
    infer_shell_variant=_infer_shell_variant,
    infer_patch_strategy=_infer_patch_strategy,
    infer_pedagogical_role=_infer_pedagogical_role,
    infer_chrome_mode=_infer_chrome_mode,
    clean_summary_text=_clean_summary_text,
    default_visual_claim=_default_visual_claim,
    build_controls=_build_controls,
    build_scene=_build_scene,
    build_annotations=_build_annotations,
    metadata_text=_metadata_text,
    runtime_presentation_intent=_runtime_presentation_intent,
    runtime_renderer_contract=_runtime_renderer_contract,
    runtime_quality_profile=_runtime_quality_profile,
    runtime_studio_lane=_runtime_studio_lane,
    runtime_artifact_kind=_runtime_artifact_kind,
    runtime_preferred_render_surface=_runtime_preferred_render_surface,
    infer_scene_render_surface=_infer_scene_render_surface,
    runtime_planning_profile=_runtime_planning_profile,
    runtime_thinking_floor=_runtime_thinking_floor,
    runtime_critic_policy=_runtime_critic_policy,
    runtime_living_expression_mode=_runtime_living_expression_mode,
    get_runtime_visual_metadata=_get_runtime_visual_metadata,
    build_artifact_handoff=_build_artifact_handoff,
    enrich_scene_contract=_enrich_scene_contract,
    generate_visual_session_id=_generate_visual_session_id,
    generate_figure_group_id=_generate_figure_group_id,
    infer_interaction_mode=_infer_interaction_mode,
    build_runtime_manifest=_build_runtime_manifest,
)
_coerce_visual_payload_data = functools.partial(
    coerce_visual_payload_data_impl,
    build_controls=_build_controls,
    generate_visual_session_id=_generate_visual_session_id,
    resolve_renderer_kind=_resolve_renderer_kind,
    infer_shell_variant=_infer_shell_variant,
    infer_patch_strategy=_infer_patch_strategy,
    generate_figure_group_id=_generate_figure_group_id,
    infer_pedagogical_role=_infer_pedagogical_role,
    infer_chrome_mode=_infer_chrome_mode,
    clean_summary_text=_clean_summary_text,
    default_visual_claim=_default_visual_claim,
    default_visual_title=_default_visual_title,
    infer_runtime=_infer_runtime,
    build_scene=_build_scene,
    build_annotations=_build_annotations,
    infer_interaction_mode=_infer_interaction_mode,
    build_runtime_manifest=_build_runtime_manifest,
)
_apply_runtime_patch_defaults = functools.partial(
    apply_runtime_patch_defaults_impl,
    get_runtime_context=get_current_tool_runtime_context,
)
_build_multi_figure_payloads = functools.partial(
    build_multi_figure_payloads_impl,
    generate_figure_group_id=_generate_figure_group_id,
    builders=_BUILDERS,
    logger=logger,
    resolve_renderer_kind=_resolve_renderer_kind,
    resolve_fallback_html=_resolve_fallback_html,
    normalize_visual_payload=_normalize_visual_payload,
)
_build_auto_grouped_payloads = functools.partial(
    build_auto_grouped_payloads_impl,
    plan_auto_group_figure_budget=_plan_auto_group_figure_budget,
    infer_pedagogical_role=_infer_pedagogical_role,
    sanitize_summary_candidate=_sanitize_summary_candidate,
    default_visual_summary=_default_visual_summary,
    generate_figure_group_id=_generate_figure_group_id,
    default_visual_claim=_default_visual_claim,
    collect_story_points=_collect_story_points,
    build_bridge_infographic_spec=_build_bridge_infographic_spec,
    build_takeaway_claim=_build_takeaway_claim,
    normalize_visual_payload=_normalize_visual_payload,
)
parse_visual_payloads = functools.partial(
    parse_visual_payloads_impl,
    payload_class=VisualPayloadV1,
    build_multi_figure_payloads=_build_multi_figure_payloads,
    coerce_visual_payload_data=_coerce_visual_payload_data,
    validation_error_cls=ValidationError,
)
parse_visual_payload = functools.partial(
    parse_visual_payload_impl,
    parse_visual_payloads=parse_visual_payloads,
)

