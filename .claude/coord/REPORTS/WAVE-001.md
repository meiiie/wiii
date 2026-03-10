# WAVE-001 Report: Capability Boundary

Wave: WAVE-001
Author: claude-code
Status: REVIEW_NEEDED
Completed: 2026-03-10T12:10:00+07:00
Updated: 2026-03-10T12:25:00+07:00

## Summary

Established clean capability boundaries so `direct` no longer owns code, document, or browser responsibilities. These capabilities now live exclusively in `code_studio_agent`. Boundary is enforced at two levels:

1. **Tool-binding level (hard boundary)**: Removed code_execution, browser_sandbox, chart_tools, and output_generation_tools from `_collect_direct_tools()`. Even if routing fails, direct physically cannot execute these capabilities.
2. **LLM routing prompt (soft boundary)**: Added `CODE_STUDIO_AGENT` to Agent Mapping in `ROUTING_PROMPT_TEMPLATE` with explicit Vietnamese description + 6 routing examples. Updated `DIRECT` description to explicitly state it does NOT create files, run code, or draw charts.

Approach follows **LLM-first routing** per Anthropic/LangGraph SOTA — no keyword expansion, tool-level enforcement + prompt-based routing descriptions.

## Files Changed

| File | Change |
|------|--------|
| `app/engine/multi_agent/graph.py` | Removed code_execution, browser_sandbox, chart_tools, output_generation_tools from `_collect_direct_tools()`. Removed browser/code tool hints from `_build_direct_tools_context()`. Removed browser_snapshot and execute_python from `_direct_required_tool_names()`. |
| `app/engine/multi_agent/supervisor.py` | Added CODE_STUDIO_AGENT to Agent Mapping in `ROUTING_PROMPT_TEMPLATE`. Updated DIRECT description with explicit boundary statement. Added 6 routing examples for code/chart/document/browser requests. (Note: routing prompt lives in `supervisor.py` as a Python string constant, not in a YAML file.) |
| `tests/unit/test_sprint154_tech_debt.py` | Updated `TestDirectAnalysisTools` tests to assert new boundary: direct no longer forces tools for Python queries, direct no longer requires execute_python. Added positive regression `test_code_studio_collects_execute_python_for_admin` confirming code_studio_agent owns Python execution. |

## Architecture Notes

- **LLM-first, not keyword-first**: Supervisor LLM decides routing based on context understanding. Keywords are fallback guardrails only (`CODE_STUDIO_KEYWORDS` unchanged).
- **Soft boundary location**: `ROUTING_PROMPT_TEMPLATE` constant in `app/engine/multi_agent/supervisor.py` (not a YAML file).
- **Tool-level hard boundary**: `_collect_direct_tools()` no longer imports or returns code/document/browser tools. `_collect_code_studio_tools()` unchanged — already has all needed tools.
- **Admin-only sandbox policy preserved**: `_collect_code_studio_tools()` still gates code_execution and browser_sandbox behind `user_role == "admin"` checks.
- **`_needs_browser_snapshot` and `_needs_analysis_tool` functions retained**: Still used by `_code_studio_required_tool_names()` and code studio inference functions. Only removed from `_direct_required_tool_names()`.

## Smoke / Verification

### Test 1: Code request → code_studio_agent (live SSE)
```
Request: "Write Python code to calculate factorial"
Role: admin
Result: ✅ Routed to code_studio_agent
Evidence: SSE event id=7 content="Chuyển sang Code Studio", id=10 node="code_studio_agent"
```

### Test 2: Social greeting → direct (live SSE)
```
Request: "Xin chao ban"
Role: student
Result: ✅ Routed to direct
Evidence: SSE event id=10 node="direct", supervisor action="Chuyển sang Suy nghĩ câu trả lời"
```

### Test 3: Regression suite (pytest)
```
tests/unit/test_sprint154_tech_debt.py::TestDirectAnalysisTools — 5/5 PASSED
  test_force_tools_for_python_query — direct does NOT force tools for Python queries
  test_python_query_requires_execute_python — direct does NOT require execute_python
  test_code_studio_collects_execute_python_for_admin — code_studio DOES collect execute_python (positive regression)
  test_student_query_does_not_collect_execute_python — student direct has no execute_python
  test_student_query_does_not_require_execute_python — student direct requires nothing for Python queries
```

### Compilation
```
py_compile graph.py: OK
py_compile supervisor.py: OK
```

## Evidence

- SSE trace for code request shows `"node": "code_studio_agent"` (not `"direct"`)
- SSE trace for social request shows `"node": "direct"` (unchanged behavior)
- Backend started successfully with no import errors
- All 5 regression tests in `TestDirectAnalysisTools` pass

## Known Issues

- `_needs_browser_snapshot()` and `_needs_analysis_tool()` helper functions still exist in graph.py (used by code_studio paths). Not dead code, but could be confusing without context.
- Chart/document requests from non-admin users: code_studio_agent still binds chart_tools and output_generation_tools regardless of role (only code_execution and browser_sandbox are admin-gated).

## Acceptance Criteria Status

- [x] `direct` path is no longer the owner of code/document/browser capabilities
- [x] capability ownership is explicit in routing and documented in implementation notes
- [x] admin-only sandbox policy still holds after routing changes
- [x] smoke evidence is attached for at least one routed code path

## Recommendation

WAVE-001 ready for re-review. All acceptance criteria met. Regression suite aligned with new boundary. Report file reference corrected (supervisor.py, not supervisor.yaml).
