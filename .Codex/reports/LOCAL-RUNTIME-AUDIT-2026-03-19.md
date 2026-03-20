# Local Runtime Audit - 2026-03-19

## Scope
- Audit local runtime behavior for:
  - thinking quality
  - routing correctness
  - progress honesty
  - inline visual vs Code Studio flow
- Compare:
  - `127.0.0.1:8000` current local server actually serving the UI
  - `127.0.0.1:8010` clean `.venv` backend with latest feature flags enabled

## Important Environment Finding
- `127.0.0.1:8000` was served by a stale global Python process, not the latest `.venv` backend from the repo.
- For reliable validation of current code, a clean backend was started on `127.0.0.1:8010`.
- Some earlier CLI smoke tests were also skewed by Windows PowerShell mojibake for Vietnamese literals.
- Reliable Vietnamese tests must use Unicode-safe input, otherwise routing can look wrong for fake reasons.

## What Looks Good Now

### 1. Article figure lane is fundamentally working
- Prompt: `Explain Kimi linear attention in charts`
- Latest backend (`:8010`) routed to `direct`
- Tool: `tool_generate_visual`
- Output: inline visual (`visual_open`) with `presentation_intent=chart_runtime`
- Time to `done`: ~40-55s

This means the main `SVG/inline figure` direction is alive and functioning.

### 2. Explicit chart request is correct on the latest backend
- Prompt: `Vẽ biểu đồ so sánh tốc độ các loại tàu container`
- Latest backend (`:8010`) routed to `direct`
- Tool: `tool_generate_visual`
- Output: inline chart visual
- Time to `done`: ~36s

This is the right lane.

### 3. Quiz-as-app request is correct on the latest backend
- Prompt: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
- Latest backend (`:8010`) routed to `code_studio_agent`
- Tool: `tool_create_visual_code`
- Output: Code Studio app + `code_open` + `visual_open`
- Time to `done`: ~198s

So the app-shaped interpretation is now correct when the request text is passed cleanly.

### 4. Progress honesty is much better than before
- Long Code Studio runs now emit staged status updates:
  - `Minh dang phan tich yeu cau ky thuat...`
  - `... len ke hoach code... (da 20s)`
  - `... viet ma nguon... (da 40s)`
  - `... toi uu logic... (da 60s)`
  - `... hoan thien chi tiet...`

This is a major improvement over silent waiting.

## What Is Still Not Good Enough

### 1. Thinking is still too long and too literary
- Many turns still emit visible thinking that feels:
  - over-warm
  - repetitive
  - partially performative
  - too close to hidden planning instead of short public progress
- This is especially visible in:
  - article figure prompts
  - quiz app prompts
  - follow-up simulation prompts

The system is more alive now, but not yet disciplined enough.

### 2. Follow-up simulation continuity is still weak
- Chain tested on latest backend (`:8010`):
  1. `Explain Kimi linear attention in charts`
  2. `Wiii tạo mô phỏng cho mình được chứ?`
- Result:
  - routes to Code Studio quickly
  - but does **not** anchor to the just-discussed Kimi topic strongly enough
  - instead returns a clarification-style response:
    - `câu này chưa nêu rõ hiện tượng nào...`

This means living continuity is not yet doing the job users expect.

### 3. Article figures are still too small in pedagogical ambition
- `Explain ... in charts` currently succeeded as a single inline figure flow.
- It did not reliably become the desired `2-3 figure explanatory arc`.
- So routing is improved, but pedagogy depth is still below target.

### 4. Quiz app quality is correct in lane, but too slow
- ~198s to `done` is acceptable only if the result is premium.
- The current result is better than before, but still not yet premium enough to justify the wait every time.
- Long latency is acceptable in principle, but quality must clearly match the cost.

### 5. Current UI server target can still mislead testing
- If the desktop/browser is still pointed at stale `:8000`, local testing may not reflect the actual latest backend code.
- This can create false regression reports.

## Judgment
- Overall state: `pretty good, but not maxed out`
- Routing is **better than before**
- Progress transparency is **meaningfully better**
- The system is **not sick or silently hanging in the same way as before**
- But it is **not yet at top-tier living quality**

## Priority Recommendations
1. Trim public thinking aggressively.
2. Strengthen follow-up continuity from article -> simulation.
3. Push explanatory article visuals toward multi-figure pedagogy, not single figure success.
4. Raise Code Studio quality bar so 2-3 minute waits feel earned.
5. Standardize local test target so frontend does not accidentally hit stale backend processes.
