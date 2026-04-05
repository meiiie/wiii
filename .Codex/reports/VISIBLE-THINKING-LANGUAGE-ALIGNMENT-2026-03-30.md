# Visible Thinking Language Alignment - 2026-03-30

## Muc tieu

Them mot lop alignment rat mong cho visible thinking:

- khong quay lai authored public renderer cu
- khong viet ho thinking
- chi can ngon ngu hien thi cua native thought theo `response_language` cua turn

## Da sua

### 1. Thin helper cho visible thinking

File:
- `maritime-ai-service/app/engine/reasoning/public_thinking_language.py`

Them / hoan thien:
- `should_align_visible_thinking_language(...)`
- `align_visible_thinking_language(...)`

Hanh vi:
- neu thought da cung ngon ngu voi turn -> giu nguyen
- neu thought lech ngon ngu va co `llm` -> goi mot translation/alignment pass rat mong
- prompt alignment chi cho phep:
  - giu nguyen y
  - giu nhip suy nghi
  - giu thu tu / paragraph neu co
  - khong them y moi
  - khong bien thanh answer

### 2. Wire vao tutor live path

File:
- `maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py`

Da doi:
- native thought surface trong stream di qua alignment truoc khi emit `thinking_delta`
- fallback sync `thinking_content` cua tutor di qua cung alignment helper
- van giu sanitize public thinking de chan private/meta markers

Authority hien tai:
- model-owned thought -> sanitize -> language align (chi neu lech) -> surface

### 3. Don tutor fallback cu

File:
- `maritime-ai-service/app/engine/multi_agent/agents/tutor_surface.py`

Da bo:
- tutor public-plan fallback functions khong con dung tren live path
- sync authored tutor thinking fallback

## Export reasoning package

File:
- `maritime-ai-service/app/engine/reasoning/__init__.py`

Da export:
- `align_visible_thinking_language`
- `should_align_visible_thinking_language`

## Tests

Files:
- `maritime-ai-service/tests/unit/test_public_thinking_language.py`
- `maritime-ai-service/tests/unit/test_tutor_agent_node.py`
- `maritime-ai-service/tests/unit/test_response_language_policy.py`
- `maritime-ai-service/tests/unit/test_public_thinking_renderer.py`

Ket qua:
- focused suite 1: `42 passed`
- focused suite 2: `57 passed`

## Live status

Kiem tra runtime local:
- `http://localhost:1420` -> `200`
- `http://localhost:8000/api/v1/health/live` -> `200`

Ghi chu:
- da co backend + frontend song
- probe HTTP sync voi prompt `Giải thích Quy tắc 15 COLREGs` bi timeout o local run nay, nen chua chot live content sample moi bang endpoint that
- unit tests da khoa duoc hanh vi alignment

## Current truth

Patch nay chua “viet lai” thinking.

No chi lam dung 1 viec:
- neu visible native thought cua tutor bi troi sang tieng Anh trong khi turn da resolve la tieng Viet
- system se can thought do ve tieng Viet truoc khi surface

Day la native-thinking-first + language-contract-following, khong quay lai simulated authored gray rail.
