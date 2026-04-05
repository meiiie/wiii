# Graph Refactor Round 19 — LLM Runtime Audit Service

> Date: 2026-03-28
> Scope: Continue structural cleanup only
> Goal: Pull snapshot/discovery shaping out of `llm_runtime_audit_service.py` while keeping module-level patch seams stable

---

## 1. Summary

This round targeted one more near-threshold file:

- `app/services/llm_runtime_audit_service.py`

The service had several pure-ish helper functions for:

- selected model resolution
- metadata hint application
- degraded-state refresh
- discovery snapshot persistence shaping

These were good candidates for extraction because the public module still needed to preserve the same function names for tests that patch them directly.

---

## 2. Files Added

1. `app/services/llm_runtime_audit_snapshot_support.py`

---

## 3. Files Modified

1. `app/services/llm_runtime_audit_service.py`

---

## 4. What Moved

Into `llm_runtime_audit_snapshot_support.py`:

- `get_selected_models_impl`
- `lookup_selected_model_metadata_impl`
- `apply_metadata_hints_impl`
- `refresh_degraded_state_impl`
- `record_runtime_discovery_snapshot_impl`

What stayed in `llm_runtime_audit_service.py`:

- public wrapper names used by tests and callers
- persistence boundary
- live probe logic
- provider capability probe orchestration

---

## 5. Compatibility Strategy

This service has multiple tests that patch functions by exact module path, for example:

- `_get_selected_models`
- `_get_current_audit_payload`
- `record_runtime_discovery_snapshot`

To keep that contract stable:

- the original function names remain in `llm_runtime_audit_service.py`
- wrappers delegate into the new support module
- tests can still patch the same import paths as before

---

## 6. Line Count

- `llm_runtime_audit_service.py`: `920 -> 813`

This pulls the file below the 900-line threshold.

---

## 7. Verification

### Compile

Passed:

- `app/services/llm_runtime_audit_service.py`
- `app/services/llm_runtime_audit_snapshot_support.py`

### Passed test batches

1. Audit/runtime service batch
   - `tests/unit/test_llm_runtime_audit_service.py`
   - `tests/unit/test_admin_llm_runtime.py`
   - `tests/unit/test_llm_runtime_metadata.py`
   - `tests/unit/test_llm_runtime_policy_service.py`
   - Result: `15 passed`

### Unrelated branch-local failure observed

The broader runtime profile batch surfaced an unrelated failure:

- `tests/unit/test_llm_runtime_profiles.py::test_get_runtime_provider_preset_for_openrouter`

Observed mismatch:

- expected: `("openrouter", "ollama", "google")`
- actual: `("openrouter", "google", "zhipu", "ollama")`

This appears to be preset/config drift, not a regression caused by snapshot helper extraction.

---

## 8. Sentrux

Latest gate result after this round:

- `Quality: 3581 -> 3597`
- `Coupling: 0.36 -> 0.33`
- `Cycles: 8 -> 8`
- `God files: 9 -> 4`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

---

## 9. Why This Helps Future Thinking Work

This round does not change Wiii thinking directly.

It does help by:

1. reducing the size of a central runtime policy file
2. isolating state-shaping logic from live probe orchestration
3. keeping patch seams explicit for tests and future runtime policy changes

That makes later debugging around provider/runtime metadata less entangled with the rest of the admin runtime surface.

---

## 10. Best Next Refactor Targets

Highest-value remaining structural targets:

1. `app/engine/multi_agent/graph.py`
2. `app/engine/multi_agent/graph_streaming.py`
3. `app/engine/multi_agent/direct_execution.py`
4. `app/core/config/_settings.py`

Still avoid unless handled as a dedicated stabilization task:

1. `app/engine/tools/visual_tools.py`
