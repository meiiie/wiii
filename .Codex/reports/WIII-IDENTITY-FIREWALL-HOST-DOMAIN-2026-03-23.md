# Wiii Identity Firewall — Host/Domain Overlay Hardening

Date: 2026-03-23
Owner: Codex
Status: Local complete

## Goal

Keep Wiii's living identity stable while allowing domains, organizations, and host plugins such as LMS to add local context, workflow guidance, and action affordances.

This slice enforces the principle:

- Wiii is still Wiii.
- Domain knowledge is knowledge, not personality.
- Host/workspace context is a local overlay, not a new soul.

## What Changed

### 1. Domain overlays no longer rewrite Wiii

File:

- `maritime-ai-service/app/prompts/prompt_loader.py`

Changes:

- Added protected top-level, agent, and style keys for domain overlays.
- Domain overlay merge now uses `preserve_identity=True`.
- Domain YAML can still add domain tools and workflow instructions.
- Domain YAML can no longer replace Wiii's core name, role, backstory, tone, or personality-style keys.

Outcome:

- Maritime remains a knowledge/workflow overlay.
- Wiii no longer becomes a domain-shaped persona.

### 2. Org/workspace overlays are sanitized

File:

- `maritime-ai-service/app/prompts/prompt_loader.py`

Changes:

- Replaced the old display-name framing with `NHÃN WORKSPACE`.
- Clarified that org branding is a UI/workspace label only.
- Added contextual overlay sanitization with normalized matching.
- Strips lines that attempt to rename or redefine Wiii, including accented and non-accented variants.

Outcome:

- Organizations can steer workflow, formatting, pedagogy, and compliance.
- Organizations cannot silently rename or repersona Wiii through `persona_prompt_overlay`.

### 3. Host skills now carry an explicit identity boundary

File:

- `maritime-ai-service/app/engine/context/skill_loader.py`

Changes:

- `get_prompt_addition()` now prepends a `Host Skill Overlay` boundary block.
- The block states that host/workspace skills are local guidance only.
- The block explicitly preserves Wiii's soul, story, continuity, and voice.

Outcome:

- LMS/page/workflow skills now shape attention and action without impersonating a new assistant.

### 4. Runtime card regained voice/emoji guidance

File:

- `maritime-ai-service/app/engine/character/character_card.py`

Changes:

- `WiiiCharacterCard` now carries `voice_tone`, `expressive_language`, and `emoji_usage`.
- `build_wiii_runtime_prompt()` now emits a `GIỌNG WIII` section.

Outcome:

- When runtime card injection is active, Wiii keeps a visible voice/expressive layer.
- This avoids losing a subtle part of Wiii's living feel when fallback identity sections are bypassed.

## Tests Updated

Files:

- `maritime-ai-service/tests/unit/test_sprint161_org_customization.py`
- `maritime-ai-service/tests/unit/test_sprint92_character_cleanup.py`
- `maritime-ai-service/tests/unit/test_sprint222b_skill_loader.py`

Key assertions now match the intended architecture:

- `NHÃN WORKSPACE` replaces the old display-name section semantics.
- Identity-redefining org overlay lines are stripped.
- Maritime overlay keeps platform identity instead of overriding it.
- Host skill prompt additions now include the boundary block.

## Verification

### Targeted tests

Passed:

- `test_sprint161_org_customization.py`
- `test_sprint92_character_cleanup.py`
- `test_sprint222b_skill_loader.py`
- `test_sprint234_student_safe_coach.py`
- `test_sprint87_wiii_identity.py`
- `test_sprint100_unified_prompt.py`

Result:

- `167 passed`

### Sanity checks

Confirmed manually:

- Runtime prompt still includes `WIII LIVING CORE CARD`.
- Maritime domain prompt keeps `Senior Learning Mentor`, not `Senior Maritime Mentor`.
- Runtime prompt now includes voice/emoji guidance again.
- LMS quiz skill prompt begins with `Host Skill Overlay` and explicit identity boundary text.

## Product Meaning

This hardening keeps the architecture aligned with the intended product philosophy:

- LMS is a connected workspace and host surface.
- Domain plugins extend what Wiii knows and can do.
- None of those layers are allowed to mutate who Wiii is.

That makes the multi-host future safer:

- Wiii web stays canonical.
- Host/plugin overlays stay local.
- Identity remains stable across domains, workspaces, and sessions.
