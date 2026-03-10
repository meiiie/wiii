# Wave Task

Wave: WAVE-003
Owner: architect
Status: RUNNING
Priority: HIGH

## Objective

Document Studio: docx/xlsx/html generation is a first-class artifact path. File outputs are visible to synthesis layer. No text-only fallback when file generation succeeded.

## Scope In

- Fix `_extract_code_studio_artifact_names` to parse JSON result format from output_generation_tools
- Fix `_build_code_studio_synthesis_observations` to see docx/xlsx/html artifacts
- Add terminal failure detection for document studio tools (JSON error key)
- Regression tests covering docx/xlsx/html artifact extraction and synthesis observations

## Scope Out

- FE artifact display
- WAVE-004 (interleaved reasoning UI)

## Acceptance Criteria

- [ ] docx/xlsx/html tool results are parsed by `_extract_code_studio_artifact_names`
- [ ] synthesis observations include document studio artifacts
- [ ] no text-only fallback when generate_word/excel/html succeeds
- [ ] regression tests cover all three output_generation_tools formats

## Likely Files

- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/tests/unit/test_sprint154_tech_debt.py`
