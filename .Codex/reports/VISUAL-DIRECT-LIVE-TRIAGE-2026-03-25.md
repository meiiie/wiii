# Visual Direct Live Triage - 2026-03-25

## Scope
- Local runtime issue observed on `http://localhost:1420`
- Prompt family: `Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây`
- Goal: determine whether the failure was caused by stale build/rebuild needs or live backend logic

## Verdict
- This was **not** a frontend rebuild problem.
- `localhost:1420` is Vite dev mode, so frontend code changes do not require a production rebuild.
- Backend Python changes are mounted live into `wiii-app`; a container restart is sufficient after code edits.
- The failure came from **live runtime logic**, specifically in the direct visual lane.

## Findings
1. `direct` visual/chart turns could reach `tool_web_search` and then time out on the follow-up LLM call that should produce `tool_generate_visual`.
2. The timeout was the default `25s` first-response budget, which is too short for the chart/visual follow-up round.
3. This caused the flow to fall back to the generic phrase:
   - `Mình là Wiii! Bạn muốn tìm hiểu gì hôm nay?`
4. Streamed ASCII smoke confirmed the visual path now reaches:
   - `tool_web_search`
   - `tool_generate_visual`
   - `visual_open`
   - `visual_commit`
5. There is still a separate open issue around prompt/model truth:
   - Some paths still show execution metadata as `gemini-3.1-flash-lite-preview`
   - A shell-driven Unicode reproduction can still degrade text into `?`, so terminal-based Unicode smoke is not a reliable proxy for browser UTF-8 behavior.

## Code Changes
- `maritime-ai-service/app/engine/multi_agent/graph.py`
  - direct visual/tool rounds now use:
    - `structured` timeout for the initial visual tool-planning call
    - `background` timeout for follow-up calls when a chart/article figure still needs to be committed
  - direct lane now records execution target later in the tool round, instead of only at the first bind step
- `maritime-ai-service/tests/unit/test_sprint154_tech_debt.py`
  - regression test updated to assert the timeout profile sequence:
    - `structured`
    - `background`
    - `background`
  - regression test also checks that execution metadata can advance to the deeper visual model target

## Verification
- `docker exec wiii-app python -m pytest /app/tests/unit/test_sprint154_tech_debt.py -k "visual_intent_keeps_forcing_followup_until_visual_tool_emits" -q -p no:capture`
  - result: `1 passed`
- `python -m py_compile ...graph.py ...test_sprint154_tech_debt.py`
  - result: pass
- Live SSE smoke with ASCII prompt:
  - confirmed `visual_open` and `visual_commit`

## Still Open
1. Model badge / execution metadata can still drift from the true runtime model in some sync responses.
2. Auto-provider/runtime truth is still not fully aligned with `/llm/status` when providers are degraded or capability-gated.
3. Terminal-driven Unicode smoke can still be misleading on Windows because the shell layer may inject replacement characters before Python sees the string.

## Local Test Guidance
- Backend restart is enough after backend code edits:
  - `docker restart wiii-app`
- Frontend rebuild is not required for Vite dev:
  - hard refresh `http://localhost:1420` with `Ctrl+F5`
