# Wiii Backend-Frontend Visual Contract Note

Date: 2026-03-17
Author: Codex backend

## Scope

Clarify current backend behavior for:

- `tool_create_visual_code`
- `tool_generate_visual`
- `renderer_kind`
- `fallback_html`
- chart/runtime vs Code Studio routing

## Answers for frontend team

### 1. What does `tool_create_visual_code` send as `renderer_kind`?

It does **not** send `template`.

Current behavior in `maritime-ai-service/app/engine/tools/visual_tools.py`:

- `studio_lane in {"app", "widget"}` -> `renderer_kind="app"`
- `studio_lane == "artifact"` -> `renderer_kind="inline_html"`

This is enforced in `tool_create_visual_code()` around lines 2758-2768.

### 2. Is `fallback_html` populated?

Yes.

`tool_create_visual_code()` always wraps or preserves the generated HTML and passes it into
`fallback_html=final_html` before payload normalization.

This happens around lines 2780-2813 in `visual_tools.py`.

### 3. After the current backend behavior, will `visual_open` carry `renderer_kind="inline_html"` + full `fallback_html`?

Only for the **artifact lane**.

- `code_studio_app` / `widget` lane -> `renderer_kind="app"` + full `fallback_html`
- `artifact` lane -> `renderer_kind="inline_html"` + full `fallback_html`

Therefore, if frontend sees:

- `renderer_kind="template"`
- `data-visual-status="committed"`
- `0 iframes`

that payload is almost certainly **not** from `tool_create_visual_code`.

It is instead coming from the structured lane, typically `tool_generate_visual`.

## Routing confirmation

The prompt:

`Ve bieu do so sanh toc do cac loai tau container`

currently resolves to:

- `presentation_intent="chart_runtime"`
- `preferred_tool="tool_generate_visual"`
- not Code Studio

This is now locked by test in:

- `maritime-ai-service/tests/unit/test_visual_intent_resolver.py`

## Recommendation

Do **not** rewrite backend to force ordinary chart/article requests through `tool_create_visual_code` just to get an iframe.

That would violate the current Wiii lane policy:

- `article_figure` / `chart_runtime` -> `tool_generate_visual`
- `code_studio_app` / `artifact` -> `tool_create_visual_code`

If frontend sees a blank structured/template visual, the next debugging target should be:

- the structured payload contents from `tool_generate_visual`
- or frontend rendering/styling for the template lane

not `tool_create_visual_code`.

## Verification

Backend tests run after this note:

- `python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q` -> `21 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q` -> `80 passed`
