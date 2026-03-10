# Wave Task

Wave: WAVE-004
Owner: architect
Status: RUNNING
Priority: HIGH

## Objective

Refactor Wiii's interleaved reasoning presentation so the UI clearly separates thinking, tool execution, answer, and artifact. Remove duplicated summary/body/action layers and eliminate the heavy rounded-rectangle thinking feel.

## Scope In

- reasoning rail information architecture cleanup
- collapse/expand behavior for thinking steps
- reduce duplicated content between header, summary, preview, body, and action bridge
- tool execution strip alignment with the reasoning rail
- answer/artifact composition after reasoning
- Playwright smoke for live and settled reasoning states

## Scope Out

- backend SSE protocol redesign
- new capability agents beyond already-approved waves
- artifact panel redesign outside chat lane

## Acceptance Criteria

- [ ] a turn visually separates `thinking`, `tool execution`, `answer`, and `artifact`
- [ ] no duplicated summary/body/action_text layers for the same reasoning step
- [ ] completed turns collapse cleanly without losing readability
- [ ] live turns expand only the active step and settle into a cleaner historical state
- [ ] tool-heavy turns do not look like a log viewer or stacked rounded cards
- [ ] smoke evidence includes `live`, `after_done`, and `after_settle`

## Likely Files

- `wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx`
- `wiii-desktop/src/components/chat/ThinkingBlock.tsx`
- `wiii-desktop/src/components/chat/ActionText.tsx`
- `wiii-desktop/src/components/chat/ToolExecutionStrip.tsx`
- `wiii-desktop/src/components/chat/MessageBubble.tsx`
- `wiii-desktop/src/components/chat/MessageList.tsx`
- `wiii-desktop/src/styles/globals.css`
- `.claude/scripts/*playwright*`

## Required Evidence

- screenshot `live`
- screenshot `after_done`
- screenshot `after_settle`
- FE test/build results
- short UI smoke summary
