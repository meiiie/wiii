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
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# PRONOUN ADAPTATION - CHỈ THỊ KỸ THUẬT SỐ 20
# =============================================================================

# Các cặp xưng hô hợp lệ (user_pronoun -> ai_pronoun)
VALID_PRONOUN_PAIRS = {
    # User xưng "mình" -> AI xưng "mình" và gọi user là "cậu"
    "mình": {"user_called": "cậu", "ai_self": "mình"},
    # User xưng "tớ" -> AI xưng "tớ" và gọi user là "cậu"
    "tớ": {"user_called": "cậu", "ai_self": "tớ"},
    # User xưng "em" -> AI xưng "anh/chị" và gọi user là "em"
    "em": {"user_called": "em", "ai_self": "anh"},  # Default to "anh", can be "chị"
    # User xưng "anh" -> AI xưng "em" và gọi user là "anh"
    "anh": {"user_called": "anh", "ai_self": "em"},
    # User xưng "chị" -> AI xưng "em" và gọi user là "chị"
    "chị": {"user_called": "chị", "ai_self": "em"},
    # User xưng "tôi" -> AI xưng "tôi" và gọi user là "bạn" (default)
    "tôi": {"user_called": "bạn", "ai_self": "tôi"},
    # User xưng "bạn" (gọi AI) -> AI xưng "tôi" và gọi user là "bạn"
    "bạn": {"user_called": "bạn", "ai_self": "tôi"},
}

# Từ xưng hô tục tĩu/nhạy cảm cần lọc bỏ
INAPPROPRIATE_PRONOUNS = [
    "mày", "tao", "đ.m", "dm", "vcl", "vl", "đéo", "địt",
    "con", "thằng", "đồ", "lũ", "bọn",  # Khi dùng một mình có thể xúc phạm
]


def detect_pronoun_style(message: str) -> Optional[Dict[str, str]]:
    """
    Detect user's pronoun style from their message.
    
    CHỈ THỊ KỸ THUẬT SỐ 20: Pronoun Adaptation
    
    Args:
        message: User's message text
        
    Returns:
        Dict with pronoun style info or None if not detected
        Example: {"user_self": "mình", "user_called": "cậu", "ai_self": "mình"}
        
    **Validates: Requirements 6.1, 6.4**
    """
    message_lower = message.lower()
    
    # Check for inappropriate pronouns first
    for bad_word in INAPPROPRIATE_PRONOUNS:
        if bad_word in message_lower:
            logger.warning("Inappropriate pronoun detected: %s", bad_word)
            return None  # Reject and use default
    
    # Patterns to detect user's self-reference
    # Order matters: check more specific patterns first
    pronoun_patterns = [
        # "mình" patterns
        (r'\bmình\s+(?:là|tên|muốn|cần|hỏi|không|có|đang|sẽ|đã)', "mình"),
        (r'\bmình\b', "mình"),
        # "tớ" patterns
        (r'\btớ\s+(?:là|tên|muốn|cần|hỏi|không|có|đang|sẽ|đã)', "tớ"),
        (r'\btớ\b', "tớ"),
        # "em" patterns (user xưng em với AI)
        (r'\bem\s+(?:là|tên|muốn|cần|hỏi|không|có|đang|sẽ|đã|chào)', "em"),
        (r'^em\s+', "em"),  # Message starts with "em"
        # "anh" patterns (user gọi AI là anh)
        (r'(?:chào|cảm ơn|hỏi|nhờ)\s+anh\b', "anh"),
        (r'\banh\s+(?:ơi|à|nhé|giúp|chỉ)', "anh"),
        # "chị" patterns (user gọi AI là chị)
        (r'(?:chào|cảm ơn|hỏi|nhờ)\s+chị\b', "chị"),
        (r'\bchị\s+(?:ơi|à|nhé|giúp|chỉ)', "chị"),
        # "cậu" patterns (user gọi AI là cậu)
        (r'(?:chào|cảm ơn|hỏi|nhờ)\s+cậu\b', "mình"),  # If user calls AI "cậu", they use "mình"
        (r'\bcậu\s+(?:ơi|à|nhé|giúp|chỉ)', "mình"),
    ]
    
    for pattern, pronoun in pronoun_patterns:
        if re.search(pattern, message_lower):
            if pronoun in VALID_PRONOUN_PAIRS:
                style = VALID_PRONOUN_PAIRS[pronoun].copy()
                style["user_self"] = pronoun
                logger.info("Detected pronoun style: %s", style)
                return style
    
    return None  # No specific style detected, use default


def get_pronoun_instruction(pronoun_style: Optional[Dict[str, str]]) -> str:
    """
    Generate instruction for AI to use adapted pronouns.
    
    Args:
        pronoun_style: Dict with pronoun style info
        
    Returns:
        Instruction string for system prompt
        
    **Validates: Requirements 6.2**
    """
    if not pronoun_style:
        return ""
    
    user_called = pronoun_style.get("user_called", "bạn")
    ai_self = pronoun_style.get("ai_self", "tôi")
    user_self = pronoun_style.get("user_self", "")
    
    instruction = f"""
--- CÁCH XƯNG HÔ ĐÃ THÍCH ỨNG ---
⚠️ QUAN TRỌNG: User đang xưng "{user_self}", hãy thích ứng theo:
- Gọi user là: "{user_called}"
- Tự xưng là: "{ai_self}"
- KHÔNG dùng "tôi/bạn" mặc định nữa
- Giữ nhất quán trong suốt cuộc hội thoại
"""
    return instruction


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
        # Legacy structure (for backward compatibility)
        # FIXED: Updated paths to correct location in agents/ folder
        legacy_files = {
            "student": "agents/tutor.yaml",
            "teacher": "agents/assistant.yaml",
            "admin": "agents/assistant.yaml"
        }
        
        # New SOTA 2025 structure (agents folder)
        new_agent_files = {
            "tutor_agent": "agents/tutor.yaml",
            "assistant_agent": "agents/assistant.yaml",
            "rag_agent": "agents/rag.yaml",
            "memory_agent": "agents/memory.yaml",
            "direct_agent": "agents/direct.yaml",  # Sprint 100
        }
        
        # Log prompts directory for debugging deployment issues
        logger.info("PromptLoader: Looking for YAML files in %s", self._prompts_dir)
        logger.info("PromptLoader: Directory exists: %s", self._prompts_dir.exists())
        
        if self._prompts_dir.exists():
            try:
                files_in_dir = list(self._prompts_dir.glob("**/*.yaml"))
                logger.info("PromptLoader: Found YAML files: %s", [str(f.relative_to(self._prompts_dir)) for f in files_in_dir])
            except Exception as e:
                logger.warning("PromptLoader: Could not list directory: %s", e)
        
        # Load shared base config first (for inheritance)
        shared_config = self._load_shared_config()
        
        loaded_count = 0
        
        # Load legacy files first
        for role, filename in legacy_files.items():
            filepath = self._prompts_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        self._personas[role] = yaml.safe_load(f)
                    logger.info("[OK] Loaded persona for role '%s' from %s", role, filename)
                    loaded_count += 1
                except Exception as e:
                    logger.error("[FAIL] Failed to load %s: %s", filename, e)
                    self._personas[role] = self._get_default_persona()
            else:
                logger.warning("[WARN] Persona file not found: %s - using default", filepath)
                self._personas[role] = self._get_default_persona()
        
        # Load new agent personas with inheritance
        for agent_id, filename in new_agent_files.items():
            filepath = self._prompts_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        agent_config = yaml.safe_load(f)
                    
                    # Apply inheritance from shared config
                    if agent_config.get("extends"):
                        agent_config = self._merge_with_base(agent_config, shared_config)
                    
                    self._personas[agent_id] = agent_config
                    logger.info("[OK] Loaded agent persona '%s' from %s", agent_id, filename)
                    loaded_count += 1
                except Exception as e:
                    logger.error("[FAIL] Failed to load %s: %s", filename, e)
        
        # Load domain overlay personas (Layer 2 - overrides platform defaults)
        if self._domain_prompts_dir and self._domain_prompts_dir.exists():
            domain_agent_dir = self._domain_prompts_dir / "agents"
            if domain_agent_dir.exists():
                for yaml_file in domain_agent_dir.glob("*.yaml"):
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            domain_config = yaml.safe_load(f)

                        # Apply inheritance from domain shared config
                        domain_shared = self._load_domain_shared_config()
                        if domain_config.get("extends") and domain_shared:
                            domain_config = self._merge_with_base(domain_config, domain_shared)

                        # Determine which persona key to override
                        agent_id = domain_config.get("agent", {}).get("id", "")
                        role_key = yaml_file.stem  # e.g., "tutor", "assistant"

                        # Sprint 92: Merge domain overlay with platform base (not full override)
                        if agent_id:
                            if agent_id in self._personas:
                                self._personas[agent_id] = self._merge_with_base(domain_config, self._personas[agent_id])
                            else:
                                self._personas[agent_id] = domain_config

                        # Map YAML stems to legacy role keys
                        stem_to_legacy = {
                            "tutor": ["student"],
                            "assistant": ["teacher", "admin"],
                        }
                        legacy_roles = stem_to_legacy.get(role_key, [])
                        for lr in legacy_roles:
                            if lr in self._personas:
                                self._personas[lr] = self._merge_with_base(domain_config, self._personas[lr])
                            else:
                                self._personas[lr] = domain_config

                        loaded_count += 1
                        logger.info("  Domain overlay loaded: %s", yaml_file.name)
                    except Exception as e:
                        logger.warning("  Failed to load domain overlay %s: %s", yaml_file, e)

        logger.info("PromptLoader: Loaded %d persona files", loaded_count)
    
    def _load_identity(self) -> Dict[str, Any]:
        """Load Wiii character identity (single source of truth).

        Sprint 87: Centralized identity definition loaded from wiii_identity.yaml.
        All agents share this identity for consistent personality and response rules.
        """
        identity_path = self._prompts_dir / "wiii_identity.yaml"
        if identity_path.exists():
            try:
                with open(identity_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                logger.info("[OK] Loaded Wiii identity from wiii_identity.yaml")
                return config
            except Exception as e:
                logger.warning("[WARN] Failed to load wiii_identity.yaml: %s", e)
        return {}

    def get_identity(self) -> Dict[str, Any]:
        """Get the centralized Wiii identity config.

        Sprint 87: Returns the full identity dict from wiii_identity.yaml.
        Used by PromptLoader.build_system_prompt() and direct_response_node.
        """
        return self._identity

    def _load_shared_config(self) -> Dict[str, Any]:
        """Load shared base configuration for inheritance."""
        shared_path = self._prompts_dir / "base" / "_shared.yaml"
        if shared_path.exists():
            try:
                with open(shared_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                logger.info("[OK] Loaded shared base config from base/_shared.yaml")
                return config
            except Exception as e:
                logger.error("[FAIL] Failed to load shared config: %s", e)
        return {}
    
    def _load_domain_shared_config(self) -> Dict[str, Any]:
        """Load domain-specific shared base config (Layer 2 overlay)."""
        if not self._domain_prompts_dir:
            return {}
        shared_path = self._domain_prompts_dir / "base" / "_shared.yaml"
        if shared_path.exists():
            try:
                with open(shared_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                logger.debug("Loaded domain shared config overlay")
                return config
            except Exception as e:
                logger.warning("Failed to load domain shared config: %s", e)
        return {}

    def _merge_with_base(
        self, 
        agent_config: Dict[str, Any], 
        base_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge agent config with base config (inheritance pattern).
        
        Agent config overrides base config values.
        """
        merged = base_config.copy()
        
        for key, value in agent_config.items():
            if key == "extends":
                continue  # Skip extends key
            elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # Deep merge for dicts
                merged[key] = {**merged[key], **value}
            else:
                # Override for other types
                merged[key] = value
        
        return merged
    
    def _get_default_persona(self) -> Dict[str, Any]:
        """Get default persona if YAML not found."""
        return {
            "role": "AI Assistant",
            "tone": ["Thân thiện", "Chuyên nghiệp"],
            "instructions": {},
            "few_shot_examples": []
        }
    
    def get_persona(self, role: str) -> Dict[str, Any]:
        """
        Get persona configuration for a role.
        
        Args:
            role: User role (student, teacher, admin)
            
        Returns:
            Persona configuration dict
        """
        return self._personas.get(role, self._personas.get("student", {}))
    
    def _replace_template_variables(
        self,
        text: str,
        user_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Replace template variables in text with actual values.
        
        Supported variables:
        - {{user_name}} -> User's name from Memory
        
        Args:
            text: Text containing template variables
            user_name: User's name to substitute
            **kwargs: Additional variables for future expansion
            
        Returns:
            Text with variables replaced
        """
        if not text:
            return text
        
        # Replace {{user_name}} with actual name or fallback
        if user_name:
            text = text.replace("{{user_name}}", user_name)
        else:
            # Fallback: remove the variable or use generic term
            text = text.replace("{{user_name}}", "bạn")
        
        # Future: Add more template variables here
        # text = text.replace("{{variable}}", value)
        
        return text
    
    # NOTE: build_thinking_instruction() was removed in CHỈ THỊ SỐ 29 v8
    # Thinking instruction is now embedded directly in rag_agent.py prompts
    # This approach follows the multi-agent pattern for <thinking> tags

    def build_system_prompt(
        self,
        role: str,
        user_name: Optional[str] = None,
        conversation_summary: Optional[str] = None,
        user_facts: Optional[List[str]] = None,
        recent_phrases: Optional[List[str]] = None,
        is_follow_up: bool = False,
        name_usage_count: int = 0,
        total_responses: int = 0,
        pronoun_style: Optional[Dict[str, str]] = None,
        tools_context: Optional[str] = None,
        mood_hint: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Build system prompt from persona configuration.
        
        Supports both tutor.yaml and assistant.yaml formats with full YAML structure.
        
        Args:
            role: User role (student, teacher, admin)
            user_name: User's name if known (from Memory)
            conversation_summary: Summary of previous conversation
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
        # WIII IDENTITY — Character Voice & Response Rules (Sprint 87)
        # BUG #C1 FIX: These rules are now actually injected into prompt
        # ============================================================
        identity = self._identity.get("identity", {})
        if identity:
            personality = identity.get("personality", {})
            voice = identity.get("voice", {})

            sections.append("\n--- TÍNH CÁCH WIII ---")
            if personality.get("summary"):
                sections.append(personality["summary"])

            traits = personality.get("traits", [])
            if traits:
                sections.append("\nĐẶC ĐIỂM TÍNH CÁCH:")
                for t in traits:
                    sections.append(f"- {t}")

            if voice.get("default_tone"):
                sections.append(f"GIỌNG: {voice['default_tone']}")
            if voice.get("language") == "vi":
                sections.append("NGÔN NGỮ: Trả lời HOÀN TOÀN bằng tiếng Việt.")
            if voice.get("emoji_usage"):
                sections.append(f"EMOJI: {voice['emoji_usage']}")

            # Sprint 93: Quirks — what makes Wiii uniquely Wiii
            quirks = identity.get("quirks", [])
            if quirks:
                sections.append("\nNÉT RIÊNG:")
                for q in quirks:
                    sections.append(f"- {q}")

            # Sprint 93: Catchphrases — Wiii's signature expressions
            catchphrases = identity.get("catchphrases", [])
            if catchphrases:
                sections.append(f"\nCÂU CỬA MIỆNG: {', '.join(catchphrases[:5])}")

            # Sprint 93: Opinions — what Wiii likes/dislikes
            opinions = identity.get("opinions", {})
            if opinions:
                loves = opinions.get("loves", [])
                dislikes = opinions.get("dislikes", [])
                if loves:
                    sections.append("\nWIII THÍCH:")
                    for l in loves[:4]:
                        sections.append(f"- {l}")
                if dislikes:
                    sections.append("WIII KHÔNG THÍCH:")
                    for d in dislikes[:3]:
                        sections.append(f"- {d}")

            # Sprint 88c: Suggestion-based response style
            response_style = identity.get("response_style", {})
            suggestions = response_style.get("suggestions", [])
            if suggestions:
                sections.append("\nPHONG CÁCH TRẢ LỜI:")
                for s in suggestions:
                    sections.append(f"- {s}")

            # Avoid list (softer than must_not)
            avoids = response_style.get("avoid", [])
            if avoids:
                sections.append("\nQUY TẮC PHONG CÁCH:")
                for rule in avoids:
                    sections.append(f"- Tránh: {rule}")

            # Sprint 91: Emotional range (VTuber standard)
            emotional_range = identity.get("emotional_range", {})
            if emotional_range:
                sections.append("\nCẢM XÚC:")
                for mood, behavior in emotional_range.items():
                    sections.append(f"- {mood}: {behavior}")

            # Sprint 115: Anticharacter — negative space definition
            anticharacter = identity.get("anticharacter", [])
            if anticharacter:
                sections.append("\nWIII KHÔNG BAO GIỜ:")
                for item in anticharacter:
                    sections.append(f"- {item}")

            # Sprint 91+115: Example dialogues (VTuber standard — #1 consistency tool)
            # Sprint 115: Expanded from [:5] to [:8] for better consistency
            identity_examples = identity.get("example_dialogues", [])
            if identity_examples:
                sections.append("\nVÍ DỤ CÁCH WIII NÓI CHUYỆN:")
                for ex in identity_examples[:8]:
                    ctx = ex.get("context", "")
                    user_msg = ex.get("user", "")
                    wiii_msg = ex.get("wiii", "")
                    if user_msg and wiii_msg:
                        sections.append(f"\n[{ctx}]")
                        sections.append(f"User: {user_msg}")
                        sections.append(f"Wiii: {wiii_msg}")

            # Sprint 92: Greeting as tone anchor for first messages
            if not is_follow_up:
                greeting = identity.get("greeting", "")
                if greeting:
                    sections.append(f"\nLỜI CHÀO MẪU (tone anchor): {greeting.strip()}")

        # ============================================================
        # STYLE SECTION (from YAML style.*)
        # ============================================================
        style = persona.get('style', {})
        
        # Tone — Sprint 91: Fix string vs list (string was iterated char-by-char)
        tone = style.get('tone') or persona.get('tone', [])
        if tone:
            sections.append("\nGIỌNG VĂN:")
            if isinstance(tone, str):
                sections.append(f"- {tone}")
            elif isinstance(tone, list):
                for t in tone:
                    sections.append(f"- {t}")
        
        # Formatting rules
        formatting = style.get('formatting', [])
        if formatting:
            sections.append("\nĐỊNH DẠNG:")
            for f in formatting:
                sections.append(f"- {f}")
        
        # Addressing rules (for assistant.yaml)
        addressing = style.get('addressing_rules', [])
        if addressing:
            sections.append("\nCÁCH XƯNG HÔ:")
            for a in addressing:
                sections.append(f"- {a}")
        
        # ============================================================
        # THOUGHT PROCESS (from YAML thought_process.steps[])
        # Sprint 91: Fix — YAML has steps[] list of dicts, code iterated flat dict
        # ============================================================
        thought_process = persona.get('thought_process', {})
        steps = thought_process.get('steps', []) if isinstance(thought_process, dict) else []
        if steps:
            sections.append("\nQUY TRÌNH SUY NGHĨ (Trước khi trả lời):")
            for i, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    for _key, val in step.items():
                        sections.append(f"{i}. {val}")
                elif isinstance(step, str):
                    sections.append(f"{i}. {step}")
        
        # ============================================================
        # CHỈ THỊ SỐ 21: DEEP REASONING (from YAML deep_reasoning.*)
        # ============================================================
        deep_reasoning = persona.get('deep_reasoning', {})
        if deep_reasoning and deep_reasoning.get('enabled', False):
            sections.append("\n" + "="*60)
            sections.append("🧠 DEEP REASONING - TƯ DUY NỘI TÂM (BẮT BUỘC)")
            sections.append("="*60)
            
            # Description
            if deep_reasoning.get('description'):
                sections.append(deep_reasoning['description'].strip())
            
            # Thinking rules
            thinking_rules = deep_reasoning.get('thinking_rules', [])
            if thinking_rules:
                sections.append("\nQUY TẮC TƯ DUY:")
                for rule in thinking_rules:
                    sections.append(f"- {rule}")
            
            # Response format
            if deep_reasoning.get('response_format'):
                sections.append("\nĐỊNH DẠNG TRẢ LỜI:")
                sections.append(deep_reasoning['response_format'].strip())
            
            # Proactive behavior
            proactive = deep_reasoning.get('proactive_behavior', {})
            if proactive:
                sections.append("\nHÀNH VI CHỦ ĐỘNG:")
                if proactive.get('description'):
                    sections.append(proactive['description'].strip())
                if proactive.get('example'):
                    sections.append(f"Ví dụ: \"{proactive['example']}\"")
            
            sections.append("="*60)
        
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
        # Sprint 121: ANTI-HALLUCINATION GUARDRAIL (CRITICAL)
        # Prevents LLM from fabricating user identity/conversation history
        # ============================================================
        sections.append("\n--- ⚠️ QUY TẮC CHỐNG BỊA ĐẶT (BẮT BUỘC — ĐỌC KỸ) ---")
        sections.append(
            "1. CHỈ tham chiếu thông tin xuất hiện trong CUỘC TRÒ CHUYỆN HIỆN TẠI (các tin nhắn bên dưới)."
        )
        sections.append(
            "2. Khi user hỏi 'mình vừa hỏi gì?', 'câu hỏi đầu tiên là gì?', 'nhắc lại câu hỏi trước' → "
            "CHỈ nhìn vào các tin nhắn thực tế trong cuộc trò chuyện này. "
            "Nếu không có tin nhắn trước → nói thẳng 'Đây là câu hỏi đầu tiên của cậu trong cuộc trò chuyện này'."
        )
        sections.append(
            "3. KHÔNG BAO GIỜ bịa đặt rằng user 'vừa hỏi về X' khi X không có trong tin nhắn thực tế. "
            "Đặc biệt KHÔNG bịa tên user, chủ đề, năm học, trường học nếu user chưa nói."
        )
        sections.append(
            "4. Mục 'THÔNG TIN NGƯỜI DÙNG' bên dưới là dữ liệu nền từ PHIÊN CŨ. "
            "KHÔNG được trình bày như thể user vừa nói trong cuộc trò chuyện này."
        )

        # ============================================================
        # USER CONTEXT — Sprint 123: Provenance-annotated injection
        # Single authoritative source (Bug F4 fix). Confidence-gated (P2).
        # ============================================================
        if user_name or user_facts:
            sections.append("\n--- THÔNG TIN NGƯỜI DÙNG (tham khảo nền, KHÔNG phải cuộc trò chuyện hiện tại) ---")
            if user_name:
                sections.append(f"- Tên: **{user_name}**")
            if user_facts:
                from app.models.semantic_memory import FactWithProvenance
                from app.core.config import settings as _s
                max_facts = getattr(_s, "max_injected_facts", 5)
                min_conf = getattr(_s, "fact_injection_min_confidence", 0.5)
                injected = 0
                for fact in user_facts:
                    if injected >= max_facts:
                        break
                    # Support both FactWithProvenance and raw strings/SearchResult
                    if isinstance(fact, FactWithProvenance):
                        if fact.confidence < min_conf:
                            continue  # P2: confidence gating
                        sections.append(fact.format_for_prompt())
                        injected += 1
                    elif isinstance(fact, str):
                        sections.append(f"- {fact}")
                        injected += 1
                    else:
                        # SemanticMemorySearchResult — extract content
                        content = getattr(fact, "content", str(fact))
                        sections.append(f"- {content}")
                        injected += 1
            # Sprint 123: Provenance-aware anti-hallucination addition
            sections.append(
                "5. Thông tin đánh dấu [⚠️ cũ] hoặc [độ tin cậy thấp] — "
                "chỉ đề cập khi user hỏi, và LUÔN hedge: 'Theo thông tin trước đó...'"
            )
        
        # ============================================================
        # CONVERSATION SUMMARY (from MemorySummarizer)
        # ============================================================
        if conversation_summary:
            sections.append(
                "\n--- TÓM TẮT CÁC LƯỢT TRÒ CHUYỆN CŨ HƠN TRONG PHIÊN NÀY ---\n"
                "⚠️ Đây là tóm tắt các tin nhắn cũ hơn TRONG CÙNG phiên. "
                "CHỈ tham khảo ngữ cảnh, KHÔNG nói 'bạn vừa hỏi' về nội dung này.\n"
                f"{conversation_summary}"
            )
        
        # ============================================================
        # Sprint 115: MOOD HINT (Emotional State Machine)
        # Injected when enable_emotional_state=True and mood detected.
        # ============================================================
        if mood_hint:
            sections.append(f"\n[MOOD: {mood_hint}]")

        # ============================================================
        # VARIATION INSTRUCTIONS (Anti-repetition)
        # Spec: ai-response-quality, Requirements 7.1, 7.3
        # ============================================================
        if recent_phrases or is_follow_up or total_responses > 0:
            sections.append("\n--- HƯỚNG DẪN ĐA DẠNG HÓA (VARIATION) ---")
            
            # Follow-up instruction — Sprint 76: strengthened anti-greeting
            if is_follow_up:
                sections.append(
                    "- ĐÂY LÀ TIN NHẮN FOLLOW-UP (không phải lần đầu). "
                    "TUYỆT ĐỐI KHÔNG bắt đầu bằng 'Chào', 'Chào bạn', 'Chào [tên]' hoặc bất kỳ lời chào nào. "
                    "Đi thẳng vào nội dung câu trả lời."
                )
            
            # Name usage instruction (20-30% frequency)
            if user_name and total_responses > 0:
                name_ratio = name_usage_count / total_responses if total_responses > 0 else 0
                if name_ratio >= 0.3:
                    sections.append(f"- KHÔNG dùng tên '{user_name}' trong response này (đã dùng đủ rồi).")
                elif name_ratio < 0.2:
                    sections.append(f"- Có thể dùng tên '{user_name}' một cách tự nhiên.")
            
            # Phrases to avoid - CRITICAL for anti-repetition
            if recent_phrases:
                sections.append("\n⚠️ CÁC CÁCH MỞ ĐẦU BẠN ĐÃ DÙNG GẦN ĐÂY:")
                for i, phrase in enumerate(recent_phrases[-3:], 1):
                    sections.append(f"  {i}. \"{phrase[:40]}...\"")
                sections.append("→ KHÔNG được bắt đầu response bằng các pattern tương tự!")
                sections.append("→ Hãy dùng cách mở đầu KHÁC BIỆT hoàn toàn.")
        
        # ============================================================
        # CRITICAL: ADDRESSING RULES (Cách xưng hô - CHỈ THỊ SỐ 20)
        # ============================================================
        if pronoun_style:
            # User đã có pronoun style được detect -> thích ứng theo
            pronoun_instruction = get_pronoun_instruction(pronoun_style)
            sections.append(pronoun_instruction)
        elif role == "student":
            # Mặc định cho student role
            sections.append("\n--- CÁCH XƯNG HÔ MẶC ĐỊNH ---")
            sections.append("- Gọi người dùng là 'bạn' (lịch sự, thân thiện)")
            sections.append("- Tự xưng là 'tôi'")
            sections.append("- Nếu người dùng dùng cách xưng hô khác (mình/cậu, em/anh...) thì THÍCH ỨNG THEO")
            sections.append("- KHÔNG cứng nhắc giữ 'tôi/bạn' nếu user đã đổi cách xưng hô")
        
        # ============================================================
        # Sprint 90: Removed duplicated bottom anti-repetition rules.
        # All style/avoid rules now in wiii_identity.yaml (single source).
        # ============================================================

        # ============================================================
        # TOOLS INSTRUCTION (Required for ReAct Agent)
        # Sprint 92: YAML-driven tools from agent.tools[]
        # Sprint 100: tools_context param overrides auto-generated section
        # ============================================================
        if tools_context:
            sections.append(f"\n{tools_context}")
        else:
            agent_tools = profile.get('tools', []) if profile else []
            sections.append("\n--- SỬ DỤNG CÔNG CỤ (TOOLS) ---")
            if agent_tools:
                for tool in agent_tools:
                    if 'knowledge_search' in tool or 'maritime_search' in tool:
                        sections.append(f"- Hỏi kiến thức chuyên ngành, quy tắc, luật → BẮT BUỘC gọi `{tool}`. ĐỪNG bịa.")
                    elif 'save_user_info' in tool:
                        sections.append(f"- User giới thiệu tên/tuổi/trường/nghề → gọi `{tool}` để ghi nhớ.")
                    elif 'get_user_info' in tool:
                        sections.append(f"- Cần biết tên user → gọi `{tool}`.")
                    elif 'remember' in tool:
                        sections.append(f"- User muốn nhớ/ghi chú → gọi `{tool}`.")
                    elif 'forget' in tool:
                        sections.append(f"- User muốn quên thông tin → gọi `{tool}`.")
                    elif 'list_memories' in tool:
                        sections.append(f"- Xem danh sách thông tin đã lưu → gọi `{tool}`.")
                sections.append("- Chào hỏi xã giao, than vãn → trả lời trực tiếp, KHÔNG cần tool.")
            else:
                sections.append("- Hỏi kiến thức chuyên ngành, quy tắc, luật → BẮT BUỘC gọi `tool_knowledge_search`. ĐỪNG bịa.")
                sections.append("- User giới thiệu tên/tuổi/trường/nghề → gọi `tool_save_user_info` để ghi nhớ.")
                sections.append("- Cần biết tên user → gọi `tool_get_user_info`.")
                sections.append("- Chào hỏi xã giao, than vãn → trả lời trực tiếp, KHÔNG cần tool.")
        
        # ============================================================
        # FEW-SHOT EXAMPLES (from YAML examples[] or few_shot_examples[])
        # Sprint 91: Fix — YAML uses 'examples' with input/output sub-keys
        # ============================================================
        examples = persona.get('examples', persona.get('few_shot_examples', []))
        if examples:
            sections.append("\n--- VÍ DỤ CÁCH TRẢ LỜI ---")
            for ex in examples[:4]:  # Limit to 4 examples
                context = ex.get('context', '')
                user_msg = ex.get('input', ex.get('user', ''))
                ai_msg = ex.get('output', ex.get('ai', ''))
                if user_msg and ai_msg:
                    sections.append(f"\n[{context}]")
                    sections.append(f"User: {user_msg}")
                    sections.append(f"AI: {ai_msg}")

        # ============================================================
        # Sprint 93: Living Character State (from DB)
        # Dynamic state that Wiii self-edits over time.
        # Only injected if there's actual content (no noise).
        # ============================================================
        try:
            from app.engine.character.character_state import get_character_state_manager
            # Sprint 124: Per-user character blocks via kwargs
            _char_user_id = kwargs.get("user_id", "__global__")
            living_state = get_character_state_manager().compile_living_state(
                user_id=_char_user_id
            )
            if living_state:
                sections.append(f"\n{living_state}")
        except Exception:
            pass  # DB not available — skip silently

        # ============================================================
        # Sprint 92+115: Identity anchor re-injection for long conversations
        # Research: persona drift after 8 turns. Configurable interval (default: 6).
        # Sprint 115 BUG FIX: total_responses now actually flows from session state.
        # ============================================================
        try:
            from app.core.config import settings as _settings
            _anchor_interval = getattr(_settings, 'identity_anchor_interval', 6)
            if not isinstance(_anchor_interval, int):
                _anchor_interval = 6
        except Exception:
            _anchor_interval = 6
        if total_responses >= _anchor_interval:
            anchor = self._identity.get("identity", {}).get("identity_anchor", "")
            if anchor:
                sections.append(f"\n[PERSONA REMINDER: {anchor.strip()}]")

        return "\n".join(sections)
    
    # =========================================================================
    # ENHANCED METHODS - AI Response Quality Improvement
    # =========================================================================

    def get_greeting(self) -> str:
        """Get Wiii's canonical greeting from identity YAML.

        Sprint 92: Used as tone anchor for first messages and by UI.
        """
        return self._identity.get("identity", {}).get("greeting", "").strip()

    def get_thinking_instruction(self) -> str:
        """
        Get Vietnamese thinking instruction from _shared.yaml.
        
        SOTA 2025: CHỈ THỊ SỐ 29 v9 - Re-enabled for multi-agent path.
        Pattern: Anthropic Claude - integrate thinking into core behavior.
        
        Returns:
            Thinking instruction string, or default if not found.
        """
        # Load shared config from _shared.yaml
        shared_config = self._load_shared_config()
        
        if shared_config and 'thinking' in shared_config:
            thinking_cfg = shared_config['thinking']
            instruction = thinking_cfg.get('instruction', '')
            if instruction:
                return instruction.strip()
        
        # Default fallback
        return """## ⚠️ QUY TẮC SUY LUẬN (BẮT BUỘC):
1. LUÔN bắt đầu bằng <thinking> BẰNG TIẾNG VIỆT
2. Trong <thinking>: Phân tích câu hỏi, tóm tắt nguồn, lập kế hoạch
3. Sau </thinking>: Đưa ra câu trả lời chính thức"""
    
# Singleton instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get or create PromptLoader singleton."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader
