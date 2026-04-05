# Healthy-First Routing + Answer Streaming

Date: 2026-03-24
Owner: Codex LEADER

## Summary

- Auto mode now prefers providers that are currently `selectable` from persisted runtime audit truth before considering any degraded fallback.
- Explicit provider pinning remains strict: if the user selects `zhipu`, the runtime does not loop back through `google`.
- Direct and Code Studio answer streaming now keep provider scratchpad private. Visible thinking stays Wiii-owned, while `answer_delta` carries the real streamed answer tokens.
- Direct lane metadata now reports the actual execution provider/model instead of returning a vague `provider=auto`.

## Why This Change

Recent official guidance points in the same direction:

- Anthropic recommends reducing latency by streaming meaningful progress early rather than blocking on hidden work.
- Anthropic fine-grained tool streaming confirms that streaming should be capability-aware, not blindly enabled for every provider.
- OpenAI background mode reinforces that long-running work should avoid brittle foreground waits and use explicit runtime state.
- Vercel AI Gateway documents timeouts and failover as safety rails, not as the primary selection policy.
- Zhipu documents `stream=true` for realtime chat/code flows; live measurement on this runtime showed `glm-4.5-air` is the better delivery model while `glm-5` remains better suited to creative/deep lanes.

## Implementation

### Healthy-first auto routing

- `LLMPool._resolve_auto_primary_provider()` now tries:
  1. `choose_best_runtime_provider(... allow_degraded_fallback=False)`
  2. only if that fails, `allow_degraded_fallback=True`
- `AgentConfigRegistry._resolve_auto_provider()` follows the same two-step rule.

Result:

- If `google` is known-busy and `zhipu` is selectable, auto goes straight to `zhipu`.
- Degraded providers are used only as a last resort when no selectable provider exists.

### Answer token streaming

- `_stream_openai_compatible_answer_with_route()` no longer forwards raw provider `reasoning_content` into the UI for `direct` and `code_studio_agent`.
- Direct lane heartbeat now stops as soon as the first answer token arrives, so thinking and answer no longer overlap awkwardly.
- Response state now captures the actual provider/model chosen by the bound LLM for direct/code-studio execution lanes.

## Live Verification

Runtime truth after refresh:

- `google`: `disabled / busy`
- `zhipu`: `selectable`, `selected_model=glm-4.5-air`
- `ollama`: `disabled / host_down`

Measured direct stream (`message="wow"`):

- `provider=auto`
  - `thinking_start ~1.77s`
  - `answer first token ~12.12s`
  - metadata: `provider=zhipu`, `model=glm-4.5-air`
- `provider=zhipu`
  - `thinking_start ~0.26s`
  - `answer first token ~8.22s`

Measured raw provider latency outside Wiii orchestration:

- `glm-4.5-air`: first answer token ~4.9s
- `glm-5`: first answer token ~33.2s
- `glm-4.7-flash`: first answer token ~68.6s

Conclusion:

- Current best Zhipu split for this runtime is:
  - delivery/general: `glm-4.5-air`
  - creative/code: `glm-5`

## Remaining Issue

Code Studio answer streaming is now real in the final delivery phase, but the slowest part is still upstream planning/tool execution.

Live smoke with `Tạo mô phỏng con lắc bằng canvas`:

- `tool_call/code_open` started around `~92.9s`
- first final answer token around `~113.9s`
- total stream around `~151s`

This is no longer a silent-dead-zone problem, but it is still a quality/performance issue in the Code Studio planning lane.

## Next Recommendation

If we continue this branch, the next high-value step is not more retry/failover logic. It is:

1. profile and compact the Code Studio planning prompt,
2. reduce unnecessary structured/tool rounds before `tool_create_visual_code`,
3. keep Wiii-owned thinking visible while the creative lane works.

## Sources

- Anthropic streaming: https://platform.claude.com/docs/en/build-with-claude/streaming
- Anthropic fine-grained tool streaming: https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming
- Anthropic reduce latency: https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency
- OpenAI background mode: https://developers.openai.com/api/docs/guides/background
- Vercel provider timeouts: https://vercel.com/docs/ai-gateway/models-and-providers/provider-timeouts
- Zhipu GLM-5 guide: https://docs.z.ai/guides/llm/glm-5
- Zhipu chat completions: https://docs.z.ai/api-reference/llm/chat-completion
