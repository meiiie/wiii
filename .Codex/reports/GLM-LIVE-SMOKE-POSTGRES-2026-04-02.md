# GLM Live Smoke With Postgres - 2026-04-02

## Setup
- Brought local Postgres back up with:
  - `docker compose up -d postgres`
- Verified:
  - `localhost:5433` reachable
  - `wiii-postgres` healthy

## Artifacts
- [glm-targeted-live-smoke-2026-04-02-045832.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-targeted-live-smoke-2026-04-02-045832.json)
- [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Coverage
- `tutor_rule15_visual`
  - `rule15_explain`
  - `rule15_visual`
- `direct_origin_bong`
  - `origin`
  - `bong_followup`
- `emotion_direct`
  - `sadness`

## Summary
```json
{
  "session_count": 3,
  "turn_count": 5,
  "transport_count": 10,
  "passed_transport_count": 7,
  "failed_transport_count": 3,
  "stream_duplicate_answer_count": 0,
  "stream_visible_thinking_turns": 4,
  "stream_tool_trace_turns": 2
}
```

## Current truth
- `emotion_direct / sadness`
  - sync and stream both healthy
  - visible thinking present on both
  - `provider=zhipu`, `model=glm-5`
- `direct_origin_bong / origin`
  - stream is healthy and visibly better than sync
  - sync still misses visible thinking
- `direct_origin_bong / bong_followup`
  - sync passed
  - stream still misses visible thinking
- `tutor_rule15_visual`
  - both stream turns returned `200`
  - stream now shows visible thinking and tool trace
  - sync still misses visible thinking on `rule15_explain`

## Performance
- One lightweight direct sync turn (`mình buồn quá`, `provider=zhipu`) completed in about `29.67s`.
- Full targeted batch above took about `404s` for:
  - `5 turns`
  - `10 transports` (`sync + stream`)

Practical reading:
- GLM path is now working.
- It is not broken anymore.
- But it is still **slow** for deep/full chat smoke.

## Interpretation
- The biggest blocker was not failover anymore; it was local Postgres being down.
- Once Postgres came back, the same GLM-pinned runtime started producing real chat results again.
- Stream quality is now meaningful to inspect in HTML.
- Remaining issues are lane-quality issues, not total-runtime collapse.

## About `fallbackModel`
Right now, a Claude Code style `fallbackModel` idea looks more useful as a **latency optimization** than as a reliability rescue.

Why:
- reliability is already much better after:
  - failover taxonomy
  - selectability bootstrap fix
  - Postgres restoration
- but latency on GLM full turns is still high

So if we adopt a `fallbackModel` pattern next, the best framing is:
- same-provider fast model for lighter turns
- same-provider stronger model only for hard turns
- not as a replacement for Wiii’s multi-provider pool

## Best next target
- Fix `stream missing visible thinking` for `bong_followup`
- Fix `sync missing visible thinking` for tutor/direct origin parity
- Then evaluate whether Zhipu tiering / same-provider model fallback is worth implementing for speed
