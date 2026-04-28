"""
Prompt Loader - Load persona configuration from YAML files.

CHỈ THỊ KỸ THUẬT SỐ 16: HUMANIZATION
- Tách biệt persona ra file YAML
- Few-shot prompting để dạy AI nói chuyện tự nhiên
- Hỗ trợ role-based prompting (student vs teacher/admin)

CHỈ THỊ KỸ THUẬT SỐ 20: PRONOUN ADAPTATION
- Phát hiện cách xưng hô từ user (mình/cậu, tớ/cậu, anh/em, chị/em)
- AI thích ứng xưng hô theo user
- Lọc bỏ xưng hô tục tĩu/nhạy cảm

**Feature: wiii**
**Spec: CHỈ THỊ KỸ THUẬT SỐ 16, 20**
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from app.prompts.prompt_context_utils import (
    INAPPROPRIATE_PRONOUNS,
    VALID_PRONOUN_PAIRS,
    build_response_language_instruction,
    build_time_context,
    detect_pronoun_style,
    get_pronoun_instruction,
)
from app.prompts.prompt_page_context import format_page_context_for_prompt_impl as format_page_context_for_prompt
from app.prompts.prompt_persona_runtime import (
    _get_default_persona_impl,
    _load_domain_shared_config_impl,
    _load_identity_impl,
    _load_personas_impl,
    _load_shared_config_impl,
    _replace_template_variables_impl,
    get_persona_impl,
)
from app.prompts.prompt_runtime_tail import (
    append_identity_anchor,
    append_org_persona_overlay,
    append_personality_mode,
    get_greeting_from_identity,
    get_thinking_instruction_from_shared_config,
)
from app.prompts.prompt_section_builders import (
    append_identity_fallback_sections,
    append_style_sections,
    append_tools_examples_and_living_sections,
    append_truth_user_and_session_sections,
    append_variation_and_addressing_sections,
)

logger = logging.getLogger(__name__)
_prompt_loader: "PromptLoader | None" = None

class PromptLoader:
    """
    Load and manage persona configurations from YAML files.
    
    Usage:
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
    """
    
    def __init__(self, prompts_dir: Optional[str] = None, domain_prompts_dir: Optional[str] = None):
        """
        Initialize PromptLoader.

        Supports two-layer prompt inheritance:
          Layer 1: Platform base (app/prompts/) — cross-domain rules
          Layer 2: Domain overlay (app/domains/{domain}/prompts/) — domain personas

        Args:
            prompts_dir: Path to platform prompts directory. Defaults to app/prompts/
            domain_prompts_dir: Path to domain-specific prompts (optional overlay)
        """
        if prompts_dir:
            self._prompts_dir = Path(prompts_dir)
        else:
            # Default: app/prompts/
            self._prompts_dir = Path(__file__).parent

        self._domain_prompts_dir: Optional[Path] = None
        if domain_prompts_dir:
            self._domain_prompts_dir = Path(domain_prompts_dir)

        self._personas: Dict[str, Dict[str, Any]] = {}
        self._identity: Dict[str, Any] = self._load_identity()
        self._load_personas()
    
    def _load_personas(self) -> None:
        """Load all persona YAML files with inheritance support."""
        self._personas = _load_personas_impl(
            self._prompts_dir,
            self._domain_prompts_dir,
        )

    def _load_identity(self) -> Dict[str, Any]:
        """Load Wiii character identity (single source of truth)."""
        return _load_identity_impl(self._prompts_dir)

    def get_identity(self) -> Dict[str, Any]:
        """Get the centralized Wiii identity config.

        Sprint 87: Returns the full identity dict from wiii_identity.yaml.
        Used by PromptLoader.build_system_prompt() and direct_response_node.
        """
        return self._identity

    def _load_shared_config(self) -> Dict[str, Any]:
        """Load shared base configuration for inheritance."""
        return _load_shared_config_impl(self._prompts_dir)

    def _load_domain_shared_config(self) -> Dict[str, Any]:
        """Load domain-specific shared base config (Layer 2 overlay)."""
        return _load_domain_shared_config_impl(self._domain_prompts_dir)

    def _get_default_persona(self) -> Dict[str, Any]:
        """Get default persona if YAML not found."""
        return _get_default_persona_impl()

    def get_persona(self, role: str) -> Dict[str, Any]:
        """Get persona configuration for a role."""
        return get_persona_impl(self._personas, role)

    def _replace_template_variables(
        self,
        text: str,
        user_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """Replace template variables in text with actual values."""
        return _replace_template_variables_impl(
            text,
            user_name=user_name,
            **kwargs,
        )

    def build_system_prompt(
        self,
        role: str,
        user_name: Optional[str] = None,
        conversation_summary: Optional[str] = None,
        core_memory_block: Optional[str] = None,
        user_facts: Optional[List[str]] = None,
        recent_phrases: Optional[List[str]] = None,
        is_follow_up: bool = False,
        name_usage_count: int = 0,
        total_responses: int = 0,
        pronoun_style: Optional[Dict[str, str]] = None,
        tools_context: Optional[str] = None,
        mood_hint: Optional[str] = None,
        personality_mode: Optional[str] = None,
        response_language: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Build system prompt from persona configuration.
        
        Supports both tutor.yaml and assistant.yaml formats with full YAML structure.
        
        Args:
            role: User role (student, teacher, admin)
            user_name: User's name if known (from Memory)
            conversation_summary: Summary of previous conversation
            core_memory_block: Structured long-term memory block compiled for this user
            user_facts: List of known facts about user
            recent_phrases: List of recently used opening phrases (for variation)
            is_follow_up: True if this is a follow-up message (not first in session)
            name_usage_count: Number of times user's name has been used
            total_responses: Total number of responses in session
            pronoun_style: Dict with adapted pronoun style (CHỈ THỊ SỐ 20)
            tools_context: Optional pre-built tools section (replaces auto-generated).
                Sprint 100: Used by direct_agent for detailed tool hints + knowledge limits.

        Returns:
            Complete system prompt string with template variables replaced
            
        **Validates: Requirements 1.2, 7.1, 7.3, 6.2**
        """
        persona = self.get_persona(role)
        
        # Build prompt sections
        sections = []
        
        # ============================================================
        # Sprint 90: Removed duplicated anti-"À," rules from top section.
        # These rules now live ONLY in wiii_identity.yaml "avoid" list,
        # injected once via the WIII IDENTITY section below.
        # Follow-up anti-greeting is handled in VARIATION section.
        # ============================================================

        # ============================================================
        # PROFILE SECTION (from YAML agent.* or profile.*)
        # Sprint 91: Fix key mapping — YAML uses 'agent', code expected 'profile'
        # ============================================================
        profile = persona.get('agent', persona.get('profile', {}))
        if profile:
            profile_name = profile.get('name', 'Wiii')
            profile_role = profile.get('role', 'Assistant')
            sections.append(f"Bạn là **{profile_name}** - {profile_role}.")

            if profile.get('goal'):
                sections.append(f"MỤC TIÊU: {profile['goal']}")

            if profile.get('backstory'):
                sections.append(f"\n{profile['backstory'].strip()}")
        else:
            # Fallback for old format
            role_name = persona.get('role', 'AI Assistant')
            sections.append(f"Bạn là {role_name}.")
            if persona.get('description'):
                sections.append(persona['description'])
        
        # ============================================================
        # TIME CONTEXT — Current Vietnamese datetime for natural greetings
        # Injected early so all downstream sections can reference time.
        # ============================================================
        try:
            _time_ctx = build_time_context()
            sections.append(f"\n--- THỜI GIAN ---\n{_time_ctx}")
        except Exception:
            pass  # Clock not available — skip silently

        sections.append(f"\n{build_response_language_instruction(response_language)}")

        # ============================================================
        # WIII CHARACTER CARD — unified runtime contract
        # Inspired by AIRI-style "character card as architecture":
        # identity + soul + living state + current mood are compiled into
        # one contract block so Wiii keeps the same self across all flows.
        # ============================================================
        identity = self._identity.get("identity", {})
        runtime_card_prompt = ""
        try:
            from app.engine.character.character_card import build_wiii_runtime_prompt

            runtime_card_prompt = build_wiii_runtime_prompt(
                user_id=kwargs.get("user_id", "__global__"),
                organization_id=kwargs.get("organization_id"),
                mood_hint=mood_hint,
                personality_mode=personality_mode,
            )
        except Exception:
            runtime_card_prompt = ""

        if runtime_card_prompt:
            sections.append(f"\n{runtime_card_prompt}")
        elif identity:
            append_identity_fallback_sections(
                sections,
                identity=identity,
                is_follow_up=is_follow_up,
            )

        # ============================================================
        # STYLE SECTION (from YAML style.*)
        # ============================================================
        append_style_sections(sections, persona=persona)
        
        # ============================================================
        # DIRECTIVES SECTION (from YAML directives.*)
        # Sprint 91: Fix — YAML uses 'must'/'avoid', code expected 'dos'/'donts'
        # ============================================================
        directives = persona.get('directives', {})
        if directives:
            must_rules = directives.get('must', directives.get('dos', []))
            if must_rules:
                sections.append("\nNÊN LÀM:")
                for rule in must_rules:
                    rule = self._replace_template_variables(rule, user_name)
                    sections.append(f"- {rule}")

            avoid_rules = directives.get('avoid', directives.get('must_not', directives.get('donts', [])))
            if avoid_rules:
                sections.append("\nTRÁNH:")
                for rule in avoid_rules:
                    sections.append(f"- {rule}")
        
        # Instructions (legacy format)
        instructions = persona.get('instructions', {})
        if instructions:
            sections.append("\nQUY TẮC ỨNG XỬ:")
            for category, rules in instructions.items():
                if isinstance(rules, list):
                    for rule in rules:
                        sections.append(f"- {rule}")

        # ============================================================
        # Sprint 227 + 230: VISUAL-FIRST RESPONSE (from YAML visual.*)
        # Three tiers: Mermaid + Charts + Structured/Fallback visuals
        # ============================================================
        visual = persona.get('visual', {})
        if visual:
            from app.core.config import get_settings

            settings = get_settings()
            structured_visuals_enabled = bool(getattr(settings, "enable_structured_visuals", False))
            sections.append("\n--- TRỰC QUAN HÓA (Visual-First) ---")
            philosophy = visual.get('philosophy', '')
            if philosophy:
                sections.append(philosophy)

            # Tier 1: Mermaid diagrams
            mermaid_cfg = visual.get('mermaid', {})
            if mermaid_cfg:
                mermaid_when = mermaid_cfg.get('when_to_use', [])
                if mermaid_when:
                    sections.append("\n📊 SƠ ĐỒ MERMAID (```mermaid code block):")
                    for item in mermaid_when:
                        sections.append(f"- {item}")

            # Tier 2: Interactive charts (Chart.js)
            chart_cfg = visual.get('chart', {})
            if chart_cfg:
                chart_when = chart_cfg.get('when_to_use', [])
                if chart_when:
                    sections.append("\n📈 BIỂU ĐỒ TƯƠNG TÁC (tool_generate_interactive_chart → ```widget):")
                    for item in chart_when:
                        sections.append(f"- {item}")

            # Tier 3: Rich educational visuals (Sprint 229)
            rich_cfg = visual.get('rich_visual', {})
            if rich_cfg:
                rich_when = rich_cfg.get('when_to_use', [])
                if rich_when:
                    if structured_visuals_enabled:
                        sections.append("\n🎨 VISUAL RUNTIME V3 (tool_generate_visual → SSE visual):")
                    else:
                        sections.append("\n🎨 RICH VISUAL GIÁO DỤC (tool_generate_visual → SSE visual):")
                    for item in rich_when:
                        sections.append(f"- {item}")
                rich_rules = rich_cfg.get('rules', [])
                if rich_rules:
                    sections.append("Quy tắc:")
                    for r in rich_rules:
                        sections.append(f"- {r}")
                if structured_visuals_enabled:
                    sections.append("- Chon renderer_kind=template cho visual giao duc chuan; inline_html cho custom editorial visual; app cho simulation/mini tool.")
                    sections.append("- Sau khi gọi tool_generate_visual: KHÔNG copy payload JSON vào answer. Viết narrative + takeaway, frontend sẽ render visual.")
                    sections.append("- Dùng tool_create_visual_code cho visual custom (code-gen).")

            # Legacy: widget section (backward compat with Sprint 228)
            widget_cfg = visual.get('widget', {})
            if widget_cfg and not chart_cfg and not rich_cfg:
                widget_when = widget_cfg.get('when_to_use', [])
                if widget_when:
                    sections.append("\n🎯 WIDGET TƯƠNG TÁC (```widget code block):")
                    for item in widget_when:
                        sections.append(f"- {item}")
                widget_rules = widget_cfg.get('rules', [])
                if widget_rules:
                    sections.append("Quy tắc widget:")
                    for r in widget_rules:
                        sections.append(f"- {r}")

            # Legacy flat when_to_use (backward compat with Sprint 227 format)
            flat_when = visual.get('when_to_use', [])
            if flat_when and not mermaid_cfg:
                sections.append("\nKhi nào dùng sơ đồ thay vì text:")
                for item in flat_when:
                    sections.append(f"- {item}")

            # Guidelines (applies to both tiers)
            guidelines = visual.get('guidelines', [])
            if guidelines:
                sections.append("\nNguyên tắc chung:")
                for g in guidelines:
                    sections.append(f"- {g}")

        append_truth_user_and_session_sections(
            sections,
            user_name=user_name,
            core_memory_block=core_memory_block,
            user_facts=user_facts,
            conversation_summary=conversation_summary,
            mood_hint=mood_hint,
            kwargs=kwargs,
            logger=logger,
            format_page_context_for_prompt=format_page_context_for_prompt,
        )

        # ============================================================
        # VARIATION INSTRUCTIONS (Anti-repetition)
        # Spec: ai-response-quality, Requirements 7.1, 7.3
        # Sprint 203: Natural conversation mode replaces anti-instructions
        #             with positive phase-aware framing (Anthropic pattern)
        # ============================================================
        append_variation_and_addressing_sections(
            sections,
            recent_phrases=recent_phrases,
            is_follow_up=is_follow_up,
            total_responses=total_responses,
            user_name=user_name,
            name_usage_count=name_usage_count,
            pronoun_style=pronoun_style,
            role=role,
            kwargs=kwargs,
            get_pronoun_instruction=get_pronoun_instruction,
        )
        
        # ============================================================
        # Sprint 90: Removed duplicated bottom anti-repetition rules.
        # All style/avoid rules now in wiii_identity.yaml (single source).
        # ============================================================

        # ============================================================
        # TOOLS INSTRUCTION (Required for ReAct Agent)
        # Sprint 92: YAML-driven tools from agent.tools[]
        # Sprint 100: tools_context param overrides auto-generated section
        # ============================================================
        append_tools_examples_and_living_sections(
            sections,
            tools_context=tools_context,
            profile=profile,
            persona=persona,
            runtime_card_prompt=runtime_card_prompt,
            kwargs=kwargs,
        )

        # ============================================================
        # Sprint 92+115: Identity anchor re-injection for long conversations
        # Research: persona drift after 8 turns. Configurable interval (default: 6).
        # Sprint 115 BUG FIX: total_responses now actually flows from session state.
        # ============================================================
        append_identity_anchor(
            sections,
            identity=self._identity,
            total_responses=total_responses,
        )

        # ============================================================
        # Sprint 161: ORG PERSONA OVERLAY — "Không Gian Riêng"
        # Injected AFTER all other sections to take precedence.
        # Pattern: Salesforce metadata-driven, Botpress per-org persona.
        # ============================================================
        append_org_persona_overlay(
            sections,
            organization_id=kwargs.get("organization_id"),
        )

        # ============================================================
        # Sprint 174: PERSONALITY MODE — Soul vs Professional
        # When personality_mode="soul", inject soul prompt + casual tone
        # even if enable_living_agent=False. This gives Messenger/Zalo
        # a warm, companion-like Wiii without requiring full living agent.
        # ============================================================
        append_personality_mode(
            sections,
            personality_mode=personality_mode,
        )

        return "\n".join(sections)
    
    # =========================================================================
    # ENHANCED METHODS - AI Response Quality Improvement
    # =========================================================================

    def get_greeting(self) -> str:
        """Get Wiii's canonical greeting from identity YAML."""
        return get_greeting_from_identity(self._identity)

    def get_thinking_instruction(self) -> str:
        """Get Vietnamese thinking instruction from `_shared.yaml`."""
        shared_config = self._load_shared_config()
        return get_thinking_instruction_from_shared_config(shared_config)


def get_prompt_loader() -> "PromptLoader":
    """Compatibility wrapper around the shared PromptLoader singleton."""
    global _prompt_loader
    if _prompt_loader is not None:
        return _prompt_loader
    _prompt_loader = PromptLoader()
    return _prompt_loader
