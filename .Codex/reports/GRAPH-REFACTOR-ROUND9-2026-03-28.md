# Graph Refactor Round 9

> Date: 2026-03-28
> Scope: Reduce orchestration god files further without touching thinking behavior yet
> Status: Completed and verified

---

## 1. What changed

This round focused on three low-risk structural cuts:

1. `supervisor.py`
- Removed the local wrapper layer around `supervisor_surface` helpers.
- Switched to direct import aliasing for routing/surface helpers.
- Result: the file stopped carrying a second naming/indirection layer that added size without ownership value.

2. `direct_execution.py`
- Extracted wait-surface helpers into `app/engine/multi_agent/direct_wait_surface.py`.
- Kept `direct_execution.py` as a compatibility re-export surface because `graph.py` still imports these helper names.
- Result: direct execution keeps orchestration/streaming logic while wait-copy generation is separated.

3. `llm_pool.py`
- Extracted the public convenience facade into `app/engine/llm_pool_public.py`.
- Re-exported the public API back through `llm_pool.py` so existing imports stay unchanged.
- Preserved monkeypatch/test seams by making the public facade read compatibility symbols from the `llm_pool` module object.

---

## 2. Files added

1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_wait_surface.py`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\llm_pool_public.py`

---

## 3. Files modified

1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_execution.py`
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\llm_pool.py`

---

## 4. Line-count impact

Key files after this round:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py` → `879`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_execution.py` → `939`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\llm_pool.py` → `997`

This round pushed all three of these files below the 1000-line mark.

---

## 5. Verification

### Compile

Passed:

```powershell
python -m py_compile `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\llm_pool.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\llm_pool_public.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_execution.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_wait_surface.py
```

### Tests

Passed:

```powershell
python -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_graph_routing.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_supervisor_agent.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_llm_failover.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_llm_pool_multi.py `
  -v -p no:capture --tb=short
```

Result:

- `173 passed`

---

## 6. Sentrux

Latest gate:

- `Quality: 3581 -> 3587`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

Interpretation:

- The project is structurally healthier than the earlier baseline.
- This round did not remove dependency cycles yet.
- It did continue reducing line-heavy ownership concentration in the core runtime path.

---

## 7. Important compatibility note

During the `llm_pool` facade extraction, tests initially failed because timeout/failover tests monkeypatch symbols on the `llm_pool` module itself. The fix was:

- keep `llm_pool_public.py` as the thin facade
- but make it resolve runtime compatibility values through the `llm_pool` module object
- keep the imported failover/timeout symbols present on `llm_pool.py`

This preserves the old test seam while still shrinking the main file.

---

## 8. Why this matters for future thinking work

The immediate goal was not to improve thinking quality directly.

The value of this round is architectural:

- fewer wrapper layers in `supervisor.py`
- less mixed ownership in `direct_execution.py`
- a cleaner split between provider internals and public LLM access in `llm_pool.py`

That makes future `thinking` repairs easier because the public-reasoning path is now less entangled with provider/failover facade code.

---

## 9. Best next cuts

Highest-ROI next steps:

1. `prompt_loader.py`
- still above 1000 lines
- best candidate for section-builder extraction from `build_system_prompt()`

2. `visual_tools.py`
- still the largest god file
- safest first seam is HTML/template builder extraction

3. `graph_streaming.py`
- continue reducing stream/bus/surface merge ownership

4. `fact_repository.py` or `product_search_node.py`
- both are large and likely contain separable query/helper seams

---

## 10. Verdict

Round 9 is a successful clean-architecture pass:

- no behavior regressions in the focused test surface
- no Sentrux degradation
- three more core files moved below the 1000-line threshold
- future refactors can now target prompt/runtime/tool layers with clearer seams
