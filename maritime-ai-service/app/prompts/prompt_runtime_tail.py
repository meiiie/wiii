"""Tail-end runtime helpers for PromptLoader.

These helpers keep late-stage prompt decorations out of the main loader file
without changing the prompt contract seen by callers.
"""

from __future__ import annotations

from typing import Any, Optional

from app.prompts.prompt_overlay_guard import sanitize_contextual_overlay_text


def append_identity_anchor(
    sections: list[str],
    *,
    identity: dict[str, Any],
    total_responses: int,
) -> None:
    try:
        from app.core.config import settings as _settings

        anchor_interval = getattr(_settings, "identity_anchor_interval", 6)
        if not isinstance(anchor_interval, int):
            anchor_interval = 6
    except Exception:
        anchor_interval = 6

    if total_responses >= anchor_interval:
        anchor = identity.get("identity", {}).get("identity_anchor", "")
        if anchor:
            sections.append(f"\n[PERSONA REMINDER: {anchor.strip()}]")


def append_org_persona_overlay(
    sections: list[str],
    *,
    organization_id: Optional[str],
) -> None:
    if not organization_id:
        return

    try:
        from app.core.org_settings import get_effective_settings

        org_settings = get_effective_settings(organization_id)

        brand = org_settings.branding
        if brand.chatbot_name != "Wiii":
            sections.append(
                f"\n--- NHAN WORKSPACE ---\n"
                f"Workspace hien tai hien thi tro ly duoi nhan **{brand.chatbot_name}** trong UI. "
                "Giu nguyen danh tinh loi, ten, story, va continuity cua Wiii; "
                "chi coi day la nhan giao dien cua to chuc hoac host."
            )

        ai_overlay = org_settings.ai_config.persona_prompt_overlay
        if ai_overlay:
            clean_overlay = sanitize_contextual_overlay_text(ai_overlay)
            if clean_overlay:
                sections.append(
                    "\n--- HUONG DAN TO CHUC ---\n"
                    "Day la preference theo workspace hoac to chuc cho turn hien tai. "
                    "Khong duoc doi ten, doi soul, doi story, hoac thay nhan cach loi cua Wiii. "
                    "Chi ap dung cac chi dan lien quan den workflow, compliance, pedagogy, formatting, "
                    "hoac cach ho tro trong workspace nay.\n"
                    f"{clean_overlay}"
                )
    except Exception:
        pass


def append_personality_mode(
    sections: list[str],
    *,
    personality_mode: Optional[str],
) -> None:
    if personality_mode != "soul":
        return

    try:
        from app.engine.personality_mode import get_soul_mode_instructions

        sections.append(get_soul_mode_instructions())

        from app.core.config import settings as _pm_settings

        if not getattr(_pm_settings, "enable_living_agent", False):
            try:
                from app.engine.living_agent.soul_loader import compile_soul_prompt

                soul_prompt = compile_soul_prompt()
                if soul_prompt:
                    sections.append(f"\n{soul_prompt}")
            except Exception:
                pass
    except Exception:
        pass


def get_greeting_from_identity(identity: dict[str, Any]) -> str:
    return identity.get("identity", {}).get("greeting", "").strip()


def get_thinking_instruction_from_shared_config(shared_config: dict[str, Any]) -> str:
    if shared_config and "thinking" in shared_config:
        thinking_cfg = shared_config["thinking"]
        instruction = thinking_cfg.get("instruction", "")
        if instruction:
            return instruction.strip()

    return """## NGUYEN TAC SUY LUAN:
1. Neu model co native thinking, hay de native thinking dan duong cho cau tra loi. Chi dung <thinking>...</thinking> khi model khong co native thinking.
2. Trong <thinking>, tap trung vao dieu de nham, dieu kien ap dung, diem neo lap luan, muc can doi, hoac dieu gi con chua chac.
3. KHONG lap dan y cau tra loi. KHONG ban ve loi chao, emoji, formatting, schema, hay "gio den phan cau tra loi".
4. KHONG viet nhap cau tra loi cho user trong <thinking>. Thinking chi duoc la dong suy tu noi tam, khong phai mini-answer.
5. Sau <thinking>, moi dua ra cau tra loi chinh thuc."""
