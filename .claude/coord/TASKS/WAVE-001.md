# Wave Task

Wave: WAVE-001
Owner: architect
Status: READY
Priority: HIGH

## Objective

Establish clean capability boundaries so `direct` no longer owns code, document, or browser responsibilities.

## Scope In

- define routing boundary for `wiii-code-studio`
- define routing boundary for `wiii-document-studio`
- define routing boundary for `wiii-browser-research`
- preserve current role policy for admin-only sandbox/code paths

## Scope Out

- final FE styling polish
- broad prompt tuning outside the affected capabilities
- non-essential refactors unrelated to routing and ownership

## Acceptance Criteria

- [ ] `direct` path is no longer the owner of code/document/browser capabilities
- [ ] capability ownership is explicit in routing and documented in implementation notes
- [ ] admin-only sandbox policy still holds after routing changes
- [ ] smoke evidence is attached for at least one routed code path

## Likely Files

- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/app/engine/reasoning/skills/...`
- `maritime-ai-service/app/prompts/agents/...`

## Required Evidence

- implementation report
- raw SSE trace for one code-studio request
- screenshot or terminal evidence showing routed ownership

## Handoff Notes

Keep changes minimal and routing-focused. Do not bundle FE polish into this wave.

