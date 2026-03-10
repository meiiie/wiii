# Wave Task

Wave: WAVE-002
Owner: architect
Status: RUNNING
Priority: HIGH

## Objective

Harden Code Studio capability: chart/html/python intents produce real artifact outputs, delivery-first answers, fail-fast on terminal sandbox errors.

## Scope In

- chart tool priority guidance (execute_python → PNG vs Mermaid → SVG)
- delivery contract completeness for html/chart intents
- regression tests for required_tool_names paths (html, excel, word, python)
- regression test for delivery_contract chart content

## Scope Out

- new chart rendering infrastructure
- FE artifact display changes
- WAVE-003 document studio

## Acceptance Criteria

- [ ] code/chart/html intents route to `code_studio_agent` (verified WAVE-001)
- [ ] delivery-first answers enforced via contract + sanitizer
- [ ] chart requests: LLM gets explicit priority — execute_python→PNG when available, Mermaid fallback for structures
- [ ] terminal sandbox failures fail fast (no retry loop)
- [ ] regression suite covers html/excel/word/python required_tool_names paths

## Likely Files

- `maritime-ai-service/app/engine/multi_agent/graph.py` (`_build_code_studio_tools_context`)
- `maritime-ai-service/tests/unit/test_sprint154_tech_debt.py`

## Required Evidence

- implementation report
- pytest results for targeted tests
