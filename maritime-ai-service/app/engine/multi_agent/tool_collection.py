"""Tool collection and selection helpers for multi-agent graph.

Extracted from graph.py — collects available tools based on query intent,
user role, and domain context.
"""

from __future__ import annotations

from importlib import import_module
import logging
from typing import Any, Optional

from app.core.config import settings
from app.engine.multi_agent.state import AgentState
logger = logging.getLogger(__name__)


def _load_attr(module_name: str, attr_name: str):
    """Load a helper lazily to reduce static tool-collection coupling."""
    return getattr(import_module(module_name), attr_name)


def _normalize_for_intent(query: str) -> str:
    return _load_attr("app.engine.multi_agent.direct_intent", "_normalize_for_intent")(query)


def _needs_web_search(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_web_search")(query)


def _needs_datetime(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_datetime")(query)


def _needs_news_search(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_news_search")(query)


def _needs_legal_search(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_legal_search")(query)


def _needs_analysis_tool(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_analysis_tool")(query)


def _needs_lms_query(query: str) -> bool:
    return _load_attr("app.engine.multi_agent.direct_intent", "_needs_lms_query")(query)


def _needs_direct_knowledge_search(query: str) -> bool:
    return _load_attr(
        "app.engine.multi_agent.direct_intent",
        "_needs_direct_knowledge_search",
    )(query)


def _infer_direct_thinking_mode(
    query: str,
    state: Optional[AgentState] = None,
    tool_names: list[str] | None = None,
) -> str:
    return _load_attr(
        "app.engine.multi_agent.direct_reasoning",
        "_infer_direct_thinking_mode",
    )(query, state or {}, tool_names or [])


def _should_strip_visual_tools_from_direct(query: str, visual_decision) -> bool:
    return _load_attr(
        "app.engine.multi_agent.direct_intent",
        "_should_strip_visual_tools_from_direct",
    )(query, visual_decision)


def resolve_visual_intent(query: str):
    return _load_attr(
        "app.engine.multi_agent.visual_intent_resolver",
        "resolve_visual_intent",
    )(query)


def filter_tools_for_visual_intent(tools, visual_decision, *, structured_visuals_enabled: bool):
    return _load_attr(
        "app.engine.multi_agent.visual_intent_resolver",
        "filter_tools_for_visual_intent",
    )(
        tools,
        visual_decision,
        structured_visuals_enabled=structured_visuals_enabled,
    )


def detect_visual_patch_request(query: str) -> bool:
    return _load_attr(
        "app.engine.multi_agent.visual_intent_resolver",
        "detect_visual_patch_request",
    )(query)


def merge_quality_profile(base_profile, override_profile):
    return _load_attr(
        "app.engine.multi_agent.visual_intent_resolver",
        "merge_quality_profile",
    )(base_profile, override_profile)


def _log_visual_telemetry(event_name: str, **kwargs) -> None:
    return _load_attr(
        "app.engine.multi_agent.visual_events",
        "_log_visual_telemetry",
    )(event_name, **kwargs)


def filter_tools_for_role(tools, user_role: str):
    return _load_attr(
        "app.engine.tools.runtime_context",
        "filter_tools_for_role",
    )(tools, user_role)


def _should_strip_visual_tools_for_analytical_text_turn(
    query: str,
    visual_decision,
    *,
    thinking_mode: str,
) -> bool:
    """Keep analytical text turns on text/data tools unless visual intent is explicit."""
    if not str(thinking_mode or "").strip().lower().startswith("analytical_"):
        return False
    return getattr(visual_decision, "presentation_intent", "text") == "text"

def _collect_direct_tools(query: str, user_role: str = "student", state: Optional[AgentState] = None):
    """Collect tools for direct response node and determine forced calling.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        tuple: (tools_list, llm_with_tools_factory, llm_auto_factory, force_tools)
            - tools_list: List of available tools
            - force_tools: Whether to force tool calling (intent detected)
    """
    _direct_tools = []
    try:
        if settings.enable_character_tools:
            get_character_tools = _load_attr(
                "app.engine.character.character_tools",
                "get_character_tools",
            )
            _direct_tools = get_character_tools()
    except Exception as _e:
        logger.debug("[DIRECT] Character tools unavailable: %s", _e)

    # WAVE-001: code_execution, browser_sandbox removed from direct.
    # These capabilities now live exclusively in code_studio_agent.
    # Boundary enforced at tool-binding level (LLM-first, not keyword).

    try:
        tool_current_datetime = _load_attr(
            "app.engine.tools.utility_tools",
            "tool_current_datetime",
        )
        tool_web_search = _load_attr(
            "app.engine.tools.web_search_tools",
            "tool_web_search",
        )
        tool_search_news = _load_attr(
            "app.engine.tools.web_search_tools",
            "tool_search_news",
        )
        tool_search_legal = _load_attr(
            "app.engine.tools.web_search_tools",
            "tool_search_legal",
        )
        tool_search_maritime = _load_attr(
            "app.engine.tools.web_search_tools",
            "tool_search_maritime",
        )
        _direct_tools = [
            *_direct_tools, tool_current_datetime,
            tool_web_search, tool_search_news,
            tool_search_legal, tool_search_maritime,
        ]
    except Exception as _e:
        logger.debug("[DIRECT] Utility/web search tools unavailable: %s", _e)

    # Knowledge search is opt-in only for explicit retrieval turns.
    if _needs_direct_knowledge_search(query):
        try:
            tool_knowledge_search = _load_attr(
                "app.engine.tools.rag_tools",
                "tool_knowledge_search",
            )
            _direct_tools.append(tool_knowledge_search)
        except Exception as _e:
            logger.debug("[DIRECT] Knowledge search tool unavailable: %s", _e)

    # P3 Agent-as-Tool: RAG knowledge delegation.
    # When tool_knowledge_search is NOT already bound, provide the agent-level
    # delegation tool so the LLM can still query domain knowledge when needed.
    _bound_tool_names = {
        str(getattr(t, "name", "") or getattr(t, "__name__", ""))
        for t in _direct_tools
    }
    if "tool_knowledge_search" not in _bound_tool_names:
        try:
            tool_rag_knowledge = _load_attr(
                "app.engine.tools.agent_tools",
                "RAG_KNOWLEDGE_TOOL",
            )
            _direct_tools.append(tool_rag_knowledge)
        except Exception as _e:
            logger.debug("[DIRECT] RAG agent tool unavailable: %s", _e)

    # Sprint 175: LMS tools (role-aware)
    try:
        if settings.enable_lms_integration:
            get_all_lms_tools = _load_attr(
                "app.engine.tools.lms_tools",
                "get_all_lms_tools",
            )
            _direct_tools.extend(get_all_lms_tools(role="student"))
    except Exception as _e:
        logger.debug("[DIRECT] LMS tools unavailable: %s", _e)

    try:
        if getattr(settings, "enable_host_actions", False) and state is not None:
            raw_caps = state.get("host_capabilities") or ((state.get("context") or {}).get("host_capabilities") or {})
            capabilities_tools = raw_caps.get("tools") if isinstance(raw_caps, dict) else []
            if capabilities_tools:
                generate_host_action_tools = _load_attr(
                    "app.engine.context.action_tools",
                    "generate_host_action_tools",
                )

                _direct_tools.extend(
                    generate_host_action_tools(
                        capabilities_tools,
                        user_role,
                        event_bus_id=state.get("_event_bus_id") or state.get("session_id") or "",
                        approval_context={
                            "query": query,
                            "host_action_feedback": ((state.get("context") or {}).get("host_action_feedback") or {}),
                        },
                    )
                )
    except Exception as _e:
        logger.debug("[DIRECT] Host action tools unavailable: %s", _e)

    # Structured visuals re-enable lightweight inline diagram/chart tools for direct,
    # but keep heavy artifact/file generation inside code_studio_agent.
    if getattr(settings, "enable_structured_visuals", False):
        try:
            get_chart_tools = _load_attr(
                "app.engine.tools.chart_tools",
                "get_chart_tools",
            )

            _direct_tools.extend(get_chart_tools())
        except Exception as _e:
            logger.debug("[DIRECT] Chart tools unavailable: %s", _e)

    # Sprint 229d: Re-add visual tools to direct agent so it can generate
    # rich visuals (comparison, process, quiz, etc.) without routing to code_studio.
    # This fixes the issue where direct agent writes raw JSON in widget blocks.
    try:
        get_visual_tools = _load_attr(
            "app.engine.tools.visual_tools",
            "get_visual_tools",
        )

        _direct_tools.extend(get_visual_tools())
    except Exception as _e:
        logger.debug("[DIRECT] Visual tools unavailable: %s", _e)

    visual_decision = resolve_visual_intent(query)
    thinking_mode = _infer_direct_thinking_mode(query, state, [])
    normalized_query = _normalize_for_intent(query)
    _prefers_code_execution_lane = any(
        token in normalized_query
        for token in (
            "python",
            "code python",
            "chay python",
            "chay code",
            "viet code",
            "doan code",
            "sandbox",
            "pandas",
            "xlsx",
            "excel bang python",
            "matplotlib",
        )
    )
    _direct_tools = filter_tools_for_role(_direct_tools, user_role)
    _direct_tools = filter_tools_for_visual_intent(
        _direct_tools,
        visual_decision,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )
    if _should_strip_visual_tools_from_direct(query, visual_decision):
        _direct_tools = [
            tool for tool in _direct_tools
            if str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "")
            not in {
                "tool_create_visual_code",
                "tool_generate_visual",
                "tool_generate_mermaid",
                "tool_generate_interactive_chart",
            }
        ]
    if _should_strip_visual_tools_for_analytical_text_turn(
        query,
        visual_decision,
        thinking_mode=thinking_mode,
    ):
        _direct_tools = [
            tool for tool in _direct_tools
            if str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "")
            not in {
                "tool_create_visual_code",
                "tool_generate_visual",
                "tool_generate_mermaid",
                "tool_generate_interactive_chart",
            }
        ]
    # Clear inline article/chart requests should stay tightly on the visual lane.
    # If there is no competing web/legal/news/datetime/LMS intent, bind only the
    # preferred visual tool so the first tool call is deterministic and the
    # direct lane does not waste latency on unrelated tool options.
    if (
        visual_decision.force_tool
        and visual_decision.preferred_tool
        and visual_decision.presentation_intent in {"article_figure", "chart_runtime"}
        and not (
            _needs_web_search(query)
            or _needs_datetime(query)
            or _needs_news_search(query)
            or _needs_legal_search(query)
            or _needs_lms_query(query)
        )
    ):
        preferred_name = visual_decision.preferred_tool
        preferred_tools = [
            tool
            for tool in _direct_tools
            if str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "") == preferred_name
        ]
        if preferred_tools:
            _direct_tools = preferred_tools
    _needs_visual_tool = (
        not _prefers_code_execution_lane
        and
        visual_decision.force_tool
        and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}
        and (
            visual_decision.presentation_intent in {"article_figure", "chart_runtime"}
            or not _needs_analysis_tool(query)
        )
    )
    if _needs_visual_tool:
        _log_visual_telemetry(
            "visual_requested",
            mode=visual_decision.mode,
            visual_type=visual_decision.visual_type,
            user_role=user_role,
            query=query[:180],
        )
    force_tools = bool(_direct_tools) and (
        _needs_web_search(query) or _needs_datetime(query)
        or _needs_news_search(query) or _needs_legal_search(query)
        or _needs_lms_query(query) or _needs_visual_tool
    )

    # Agent handoff tool (Phase 3)
    if settings.enable_agent_handoffs:
        try:
            from app.engine.multi_agent.handoff_tools import handoff_to_agent
            _direct_tools.append(handoff_to_agent)
        except Exception:
            pass

    return _direct_tools, force_tools


def _collect_code_studio_tools(query: str, user_role: str = "student"):
    """Collect tools for the code studio capability lane."""
    _tools = []

    try:
        if settings.enable_code_execution and user_role == "admin":
            get_code_execution_tools = _load_attr(
                "app.engine.tools.code_execution_tools",
                "get_code_execution_tools",
            )

            _tools.extend(get_code_execution_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Code execution tools unavailable: %s", _e)

    try:
        get_chart_tools = _load_attr(
            "app.engine.tools.chart_tools",
            "get_chart_tools",
        )

        _tools.extend(get_chart_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Chart tools unavailable: %s", _e)

    try:
        get_visual_tools = _load_attr(
            "app.engine.tools.visual_tools",
            "get_visual_tools",
        )

        _tools.extend(get_visual_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Visual tools unavailable: %s", _e)

    try:
        get_output_generation_tools = _load_attr(
            "app.engine.tools.output_generation_tools",
            "get_output_generation_tools",
        )

        _tools.extend(get_output_generation_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Output generation tools unavailable: %s", _e)

    try:
        if (
            user_role == "admin"
            and settings.enable_browser_agent
            and settings.enable_privileged_sandbox
            and settings.sandbox_provider == "opensandbox"
            and settings.sandbox_allow_browser_workloads
        ):
            get_browser_sandbox_tools = _load_attr(
                "app.engine.tools.browser_sandbox_tools",
                "get_browser_sandbox_tools",
            )

            _tools.extend(get_browser_sandbox_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Browser sandbox tools unavailable: %s", _e)

    visual_decision = resolve_visual_intent(query)
    _tools = filter_tools_for_role(_tools, user_role)
    _tools = filter_tools_for_visual_intent(
        _tools,
        visual_decision,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )

    # Clear app/artifact requests should not drift across a broad tool bundle.
    # Once the resolver has locked a preferred tool for the studio lane, we
    # narrow the bound tools to that target so the first tool call is
    # deterministic and faster to emit in streaming.
    if (
        visual_decision.force_tool
        and visual_decision.preferred_tool
        and visual_decision.presentation_intent in {"code_studio_app", "artifact"}
    ):
        preferred_name = visual_decision.preferred_tool
        preferred_tools = [
            tool
            for tool in _tools
            if str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "") == preferred_name
        ]
        if preferred_tools:
            _tools = preferred_tools

    force_tools = bool(_tools)
    return _tools, force_tools


def _needs_browser_snapshot(query: str) -> bool:
    """Detect requests that should prefer the browser sandbox over plain web search."""
    lowered = query.lower()
    normalized = _normalize_for_intent(query)
    has_url = "http://" in lowered or "https://" in lowered or "www." in lowered
    screenshot_signal = any(
        signal in normalized
        for signal in (
            "anh chup man hinh",
            "chup man hinh",
            "screenshot",
            "browser sandbox",
            "duyet web",
            "xem trang",
            "mo trang",
            "open page",
        )
    )
    inspect_signal = has_url and any(
        signal in normalized
        for signal in (
            "mo",
            "open",
            "ghe qua",
            "vao",
            "noi gi",
            "hien thi gi",
            "render",
            "trang do",
        )
    )
    return screenshot_signal or inspect_signal


def _direct_required_tool_names(query: str, user_role: str = "student") -> list[str]:
    """Return must-have direct tools inferred from the current query."""
    required: list[str] = []
    normalized = _normalize_for_intent(query)
    visual_decision = resolve_visual_intent(query)

    if _needs_datetime(query):
        required.append("tool_current_datetime")
    if _needs_news_search(query):
        required.append("tool_search_news")
    if _needs_legal_search(query):
        required.append("tool_search_legal")
    if _needs_web_search(query):
        if any(
            signal in normalized
            for signal in ("imo", "shipping", "maritime", "hang hai", "vinamarine", "cuc hang hai")
        ):
            required.append("tool_search_maritime")
        else:
            required.append("tool_web_search")
    if _needs_direct_knowledge_search(query):
        required.append("tool_knowledge_search")
    # WAVE-001: browser_snapshot and execute_python removed from direct.
    # These capabilities now live exclusively in code_studio_agent.

    if visual_decision.force_tool and not _needs_analysis_tool(query):
        _structured = getattr(settings, "enable_structured_visuals", False)
        if visual_decision.mode == "mermaid" and _structured:
            required.append("tool_generate_mermaid")
        elif visual_decision.preferred_tool:
            required.append(visual_decision.preferred_tool)
        elif _structured:
            # Structured mode: ALL visual intents → multi-figure tool
            required.append("tool_generate_visual")

    deduped: list[str] = []
    for tool_name in required:
        if tool_name not in deduped:
            deduped.append(tool_name)
    return deduped


def _code_studio_required_tool_names(query: str, user_role: str = "student") -> list[str]:
    """Return must-have tools inferred for the code studio capability."""
    normalized = _normalize_for_intent(query)
    required: list[str] = []
    visual_decision = resolve_visual_intent(query)

    if any(token in normalized for token in ("html", "landing page", "website", "web app", "microsite")):
        required.append("tool_generate_html_file")

    if any(token in normalized for token in ("excel", "xlsx", "spreadsheet")):
        required.append("tool_generate_excel_file")

    if any(token in normalized for token in ("word", "docx", "report", "memo", "proposal")):
        required.append("tool_generate_word_document")

    if user_role == "admin" and settings.enable_code_execution and _needs_analysis_tool(query):
        required.append("tool_execute_python")

    if (
        user_role == "admin"
        and settings.enable_browser_agent
        and settings.enable_privileged_sandbox
        and settings.sandbox_provider == "opensandbox"
        and settings.sandbox_allow_browser_workloads
        and _needs_browser_snapshot(query)
    ):
        required.append("tool_browser_snapshot_url")

    if visual_decision.force_tool and visual_decision.preferred_tool:
        required.append(visual_decision.preferred_tool)
        deduped: list[str] = []
        for tool_name in required:
            if tool_name not in deduped:
                deduped.append(tool_name)
        return deduped

    if visual_decision.force_tool:
        _structured = getattr(settings, "enable_structured_visuals", False)
        _llm_code_gen = getattr(settings, "enable_llm_code_gen_visuals", False)
        if visual_decision.mode == "mermaid" and _structured:
            required.append("tool_generate_mermaid")
        elif _structured and _llm_code_gen:
            if visual_decision.presentation_intent in {"article_figure", "chart_runtime"}:
                required.append("tool_generate_visual")
            else:
                required.append("tool_create_visual_code")
        elif _structured:
            required.append("tool_generate_visual")

    deduped: list[str] = []
    for tool_name in required:
        if tool_name not in deduped:
            deduped.append(tool_name)
    return deduped


def _build_visual_tool_runtime_metadata(state: dict, query: str) -> dict[str, Any] | None:
    """Provide visual intent metadata and patch defaults to the tool runtime layer."""
    visual_decision = resolve_visual_intent(query)
    metadata: dict[str, Any] = {}

    if visual_decision.force_tool and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}:
        metadata.update({
            "visual_user_query": query,
            "visual_intent_mode": visual_decision.mode,
            "visual_intent_reason": visual_decision.reason,
            "visual_force_tool": True,
            "presentation_intent": visual_decision.presentation_intent,
            "figure_budget": visual_decision.figure_budget,
            "quality_profile": visual_decision.quality_profile,
            "preferred_render_surface": visual_decision.preferred_render_surface,
            "planning_profile": visual_decision.planning_profile,
            "thinking_floor": visual_decision.thinking_floor,
            "critic_policy": visual_decision.critic_policy,
            "living_expression_mode": visual_decision.living_expression_mode,
        })
        if visual_decision.visual_type:
            metadata["visual_requested_type"] = visual_decision.visual_type
        if visual_decision.preferred_tool:
            metadata["preferred_visual_tool"] = visual_decision.preferred_tool
        if visual_decision.studio_lane:
            metadata["studio_lane"] = visual_decision.studio_lane
        if visual_decision.artifact_kind:
            metadata["artifact_kind"] = visual_decision.artifact_kind
        if visual_decision.renderer_contract:
            metadata["renderer_contract"] = visual_decision.renderer_contract
        if visual_decision.renderer_kind_hint:
            metadata["renderer_kind_hint"] = visual_decision.renderer_kind_hint

    if not detect_visual_patch_request(query):
        return metadata or None

    visual_ctx = ((state.get("context") or {}).get("visual_context") or {})
    if not isinstance(visual_ctx, dict):
        visual_ctx = {}

    preferred_session_id = str(visual_ctx.get("last_visual_session_id") or "").strip()
    preferred_visual_type = str(visual_ctx.get("last_visual_type") or "").strip()

    if not preferred_session_id:
        active_items = visual_ctx.get("active_inline_visuals")
        if isinstance(active_items, list):
            for item in active_items:
                if not isinstance(item, dict):
                    continue
                preferred_session_id = str(item.get("visual_session_id") or item.get("session_id") or "").strip()
                preferred_visual_type = preferred_visual_type or str(item.get("type") or "").strip()
                if preferred_session_id:
                    break

    code_studio_ctx = ((state.get("context") or {}).get("code_studio_context") or {})
    if not isinstance(code_studio_ctx, dict):
        code_studio_ctx = {}

    active_code_session = code_studio_ctx.get("active_session")
    if not isinstance(active_code_session, dict):
        active_code_session = {}
    requested_code_view = str(code_studio_ctx.get("requested_view") or "").strip().lower()
    if requested_code_view not in {"code", "preview"}:
        requested_code_view = ""

    prefers_code_studio_session = visual_decision.presentation_intent in {"code_studio_app", "artifact"}
    preferred_code_session_id = str(active_code_session.get("session_id") or "").strip()
    preferred_code_lane = str(active_code_session.get("studio_lane") or "").strip()
    preferred_code_artifact_kind = str(active_code_session.get("artifact_kind") or "").strip()
    preferred_code_quality = str(
        active_code_session.get("quality_profile")
        or active_code_session.get("qualityProfile")
        or ""
    ).strip()
    try:
        preferred_code_active_version = max(0, int(active_code_session.get("active_version") or 0))
    except Exception:
        preferred_code_active_version = 0

    if prefers_code_studio_session and preferred_code_session_id:
        preferred_session_id = preferred_code_session_id
        if preferred_code_lane:
            metadata["studio_lane"] = preferred_code_lane
        if preferred_code_artifact_kind:
            metadata["artifact_kind"] = preferred_code_artifact_kind
        metadata["quality_profile"] = merge_quality_profile(
            metadata.get("quality_profile"),
            preferred_code_quality,
        )
        if preferred_code_active_version > 0:
            metadata["code_studio_version"] = preferred_code_active_version + 1
        if requested_code_view:
            metadata["requested_view"] = requested_code_view

    if not preferred_session_id:
        return metadata or None

    metadata.update({
        "preferred_visual_operation": "patch",
        "preferred_visual_session_id": preferred_session_id,
        "preferred_visual_patch_hint": "followup-patch",
    })
    if prefers_code_studio_session:
        metadata["preferred_code_studio_session_id"] = preferred_session_id
    if preferred_visual_type:
        metadata["preferred_visual_type"] = preferred_visual_type

    # C3: Conversational editing — inject last visual HTML so LLM can modify
    last_visual_html = str(visual_ctx.get("last_visual_html") or "").strip()
    if not last_visual_html:
        # Try to find HTML from active visuals state_summary
        for item in (visual_ctx.get("active_inline_visuals") or []):
            if isinstance(item, dict) and str(item.get("visual_session_id", "")) == preferred_session_id:
                last_visual_html = str(item.get("state_summary") or "").strip()
                break
    if last_visual_html:
        metadata["last_visual_html"] = last_visual_html[:50000]  # cap at 50k chars

    return metadata or None


