# Same-Provider Fallback Benchmark — 2026-04-02

## Summary
- Added a conservative same-provider model fallback layer before cross-provider failover.
- Scope:
  - only for `deep` turns
  - only when provider has distinct `advanced` and base models
  - current targets:
    - `google`: advanced -> base
    - `zhipu`: `glm-5` -> `glm-4.5-air`
    - `openai/openrouter`: advanced -> base
- This keeps Wiii's multi-provider pool as the final safety net, while borrowing Claude Code's practical `fallbackModel` idea inside one provider.

## Code Changes
- New helper:
  - `maritime-ai-service/app/engine/llm_same_provider_runtime.py`
- Integrated into pool:
  - `maritime-ai-service/app/engine/llm_pool.py`
- Integrated into failover runtime:
  - `maritime-ai-service/app/engine/llm_failover_runtime.py`
- Tests:
  - `maritime-ai-service/tests/unit/test_llm_failover.py`

## Unit Test Status
- `36 passed`

## Benchmark Artifacts
- `.Codex/reports/same-provider-fallback-benchmark-2026-04-02-072057.json`
- `.Codex/reports/same-provider-fallback-benchmark-origin-2026-04-02-072503.json`
- `.Codex/reports/same-provider-benchmark-origin-baseline-2026-04-02-072552.json`
- `.Codex/reports/same-provider-fallback-benchmark-extra-2026-04-02-072352.json`

## Measured Results

### Raw model latency (Zhipu)
- `glm-4.5-air`, moderate, prompt `Mình buồn quá.`
  - `8.478s`
- `glm-5`, deep, hard-math prompt
  - `99.233s`

### Same-provider fallback on medium selfhood turn
- Baseline `glm-5` direct invoke:
  - prompt: `Wiii được sinh ra thế nào? Hãy kể ngắn gọn nhưng có hồn.`
  - `22.677s`
- Same turn with failover policy:
  - provider=`zhipu`
  - primary=`glm-5`
  - timeout=`3.0s`
  - same-provider fallback=`glm-4.5-air`
  - completed in `9.163s`
  - emitted failover event:
    - `fallback_scope = "same_provider_model"`
    - `from_model = "glm-5"`
    - `to_model = "glm-4.5-air"`

### Same-provider fallback on very hard analytical turn
- provider=`zhipu`
- primary=`glm-5`
- timeout=`3.0s` or `6.0s`
- same-provider fallback triggered
- but `glm-4.5-air` still did not finish under the remaining practical latency envelope
- result: same-provider fallback alone was **not enough** for this class of prompt

## Interpretation
- Same-provider fallback is valuable for:
  - selfhood/origin
  - medium-deep direct turns
  - cases where the advanced model is slower than necessary
- Same-provider fallback is **not** a complete substitute for:
  - cross-provider failover
  - lane-level reasoning-depth control
  - timeout policy tuning for very hard prompts

## Recommendation
- Keep the new same-provider fallback layer enabled as an intermediate step.
- Keep multi-provider pool as the final safety net.
- Do **not** replace Wiii's multi-provider design with a pure `fallbackModel` architecture.
- Next tuning target should be:
  - per-lane timeout/SLA policy for deep turns
  - especially `hard_math`, `search/product` heavy turns, and other long analytical workloads
