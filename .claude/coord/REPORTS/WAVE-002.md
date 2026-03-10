# WAVE-002 Report: Code Studio Capability

Wave: WAVE-002
Author: claude-code
Status: REVIEW_NEEDED
Completed: 2026-03-10T12:45:00+07:00

## Summary

Hardened Code Studio capability contracts: chart tool priority guidance, HTML delivery contract, required_tool_names regression coverage. All four acceptance criteria now verified.

## Files Changed

| File | Change |
|------|--------|
| `app/engine/multi_agent/graph.py` | `_build_code_studio_tools_context()`: Rewrote to add explicit chart tool priority — when execute_python is available (admin), tools context says "UU TIEN dung tool_execute_python voi matplotlib để luu PNG that". Mermaid tools labeled as "Du phong" (fallback). Added NGUYEN TAC UU TIEN section with per-intent routing rules (chart→PNG, html→generate_html_file, excel→generate_excel_file, word→generate_word_document). |
| `app/engine/multi_agent/graph.py` | `_build_code_studio_delivery_contract()`: Added `is_html_request` detection (html/landing page/website/trang web) and corresponding delivery contract line. Chart line now mentions PNG + SVG fallback. |
| `tests/unit/test_sprint154_tech_debt.py` | Added `TestCodeStudioWave002` (8 tests): required_tool_names for html/excel/word/python, delivery contract chart/html lines, tools_context priority with/without execute_python. |

## Architecture Notes

- **Chart tool priority (LLM-first)**: `_build_code_studio_tools_context()` now explicitly tells the LLM which tool to call for charts based on runtime capability — no keyword routing, the priority description guides LLM decision.
- **Two chart paths**:
  - Admin + enable_code_execution=True → `tool_execute_python` with matplotlib → PNG artifact (real file)
  - Student or no code_execution → `tool_generate_mermaid/chart` → Mermaid SVG (FE-rendered)
- **Delivery contract** is query-aware: chart requests get chart guidance, HTML requests get HTML guidance. Both appended to system prompt in `_build_direct_system_messages()`.
- **Terminal fail-fast** (unchanged from prior implementation): `_is_terminal_code_studio_tool_error()` detects "tool unavailable" / "opensandbox execution failed + network connectivity error" and breaks the loop immediately.
- **Routing** (verified WAVE-001): code/chart/html intents already route to code_studio_agent via supervisor LLM.

## Smoke / Verification

### Routing (from WAVE-001 smoke — still valid)
```
Request: "Write Python code to calculate factorial"
Result: ✅ Routed to code_studio_agent (SSE node="code_studio_agent")
```

### Regression suite
```
tests/unit/test_sprint154_tech_debt.py::TestCodeStudioWave002 — 8/8 PASSED
  test_html_query_requires_generate_html_file ✅
  test_excel_query_requires_generate_excel_file ✅
  test_word_query_requires_generate_word_document ✅
  test_python_query_code_studio_requires_execute_python_for_admin ✅
  test_delivery_contract_chart_request_includes_chart_guidance ✅
  test_delivery_contract_html_request_includes_html_guidance ✅
  test_code_studio_tools_context_chart_priority_with_execute_python ✅
  test_code_studio_tools_context_mermaid_fallback_without_execute_python ✅

Full test_sprint154_tech_debt.py suite: 50/50 PASSED (no regressions from WAVE-001 or WAVE-002)
```

### Compilation
```
py_compile graph.py: OK
```

## Known Issues

- Chart PNG output via tool_execute_python requires admin role + enable_code_execution=True + running sandbox. In local dev, sandbox is not configured, so only Mermaid SVG path is available for all users.
- `enable_chart_tools` feature flag still controls whether Mermaid tools are even loaded (default False). In production, this flag must be True for chart fallback to work for non-admin users.

## Acceptance Criteria Status

- [x] code/chart/html intents route to `code_studio_agent` (verified WAVE-001, still holds)
- [x] delivery-first answers enforced via contract + sanitizer
- [x] chart requests: LLM gets explicit priority — execute_python→PNG when available, Mermaid fallback for structures
- [x] terminal sandbox failures fail fast (no retry loop — pre-existing, covered by TestCodeStudioTerminalFailures)
- [x] regression suite covers html/excel/word/python required_tool_names paths (8 new tests)

## Recommendation

WAVE-002 ready for architect review. All acceptance criteria met.
