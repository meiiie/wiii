# WAVE-003 Report: Document Studio Capability

Wave: WAVE-003
Author: claude-code
Status: REVIEW_NEEDED
Completed: 2026-03-10T13:00:00+07:00

## Summary

Fixed the core Document Studio bug: `_extract_code_studio_artifact_names` only parsed the `tool_execute_python` "Artifacts:" text format, so xlsx/docx/html tool results (JSON format) were invisible to the synthesis layer. This caused text-only fallback even when file generation succeeded.

Three functions patched. Eleven new regressions added. Full suite 61/61 green.

## Root Cause

`output_generation_tools` return JSON:
```json
{"filename": "report.docx", "format": "docx", "file_url": "...", ...}
```
`tool_execute_python` returns text:
```
Artifacts:
- chart.png (image/png) -> /workspace/...
```
`_extract_code_studio_artifact_names` only parsed the text format, so docx/xlsx/html filenames never reached `_ensure_code_studio_delivery_lede` or `_build_code_studio_synthesis_observations`.

## Files Changed

| File | Change |
|------|--------|
| `app/engine/multi_agent/graph.py` | `_extract_code_studio_artifact_names()`: Added Path 1 — JSON parsing for output_generation_tools. Tries `json.loads(result)` → extracts `"filename"` key → validates extension in `{.html,.htm,.xlsx,.docx}`. Falls through to existing line-based parse on failure. |
| `app/engine/multi_agent/graph.py` | Added `_DOCUMENT_STUDIO_TOOLS` frozenset constant and `_DOCUMENT_STUDIO_EXTENSIONS` for clean tool set membership checks. |
| `app/engine/multi_agent/graph.py` | Added `_is_document_studio_tool_error()`: Parses JSON result and returns True if `"error"` key present. |
| `app/engine/multi_agent/graph.py` | `_build_code_studio_synthesis_observations()`: Added Path B — for document studio tools with JSON result, emits human-readable "Da tao file XLSX that: `filename`" observation instead of raw JSON first-line. JSON error results emit error observation. |
| `app/engine/multi_agent/graph.py` | `_is_terminal_code_studio_tool_error()`: Extended to also catch document studio JSON error responses via `_is_document_studio_tool_error()`. |
| `tests/unit/test_sprint154_tech_debt.py` | Added `TestDocumentStudioWave003` (11 tests): artifact extraction from xlsx/docx/html JSON, error JSON yielding nothing, synthesis observations for all formats, terminal error detection, delivery lede prepend. |

## Architecture Notes

- **No text-only fallback**: Once `_extract_code_studio_artifact_names` sees the docx/xlsx filename, `_ensure_code_studio_delivery_lede` prepends the delivery lede automatically. The sanitizer then emits the artifact note.
- **Fail-fast for document errors**: JSON `{"error": "..."}` from any document tool now terminates the code_studio loop immediately via `_is_terminal_code_studio_tool_error`.
- **Synthesis observations readable**: LLM sees "Da tao file DOCX that: `wiii-doc_20260310.docx` — san sang tai xuong hoac mo ngay." instead of raw JSON.
- **Backwards compatible**: The original line-based parse for `tool_execute_python` is unchanged (Path 2 fallback).

## Regression Suite

```
TestDocumentStudioWave003 — 11/11 PASSED
  test_extract_artifact_names_from_excel_json ✅
  test_extract_artifact_names_from_word_json ✅
  test_extract_artifact_names_from_html_json ✅
  test_extract_artifact_names_json_error_yields_nothing ✅
  test_synthesis_observations_include_excel_artifact ✅
  test_synthesis_observations_include_word_artifact ✅
  test_synthesis_observations_note_document_error ✅
  test_is_document_studio_tool_error_detects_json_error ✅
  test_is_document_studio_tool_error_not_for_success ✅
  test_is_terminal_error_catches_document_studio_json_error ✅
  test_delivery_lede_added_when_docx_artifact_present ✅

Full test_sprint154_tech_debt.py: 61/61 PASSED (no regressions from WAVE-001/002/003)
```

## Acceptance Criteria Status

- [x] docx/xlsx/html tool results are parsed by `_extract_code_studio_artifact_names`
- [x] synthesis observations include document studio artifacts (human-readable, not raw JSON)
- [x] no text-only fallback when generate_word/excel/html succeeds (lede prepended automatically)
- [x] regression tests cover all three output_generation_tools formats (11 tests)

## Recommendation

WAVE-003 ready for architect review. All acceptance criteria met.
