# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-01T08:48:14.853330`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-072108.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-082736.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-composite-2026-04-01-084814.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-01-084814.json`

## Summary
- `turn_count`: 6
- `stream_missing_visible_thinking`: 0
- `stream_thinner_than_sync`: 0
- `parity_close`: 3
- `stream_richer_than_sync`: 0
- `both_missing_visible_thinking`: 0

## Lane Breakdown
- `direct`: turns=2, stream_missing=0, stream_thinner=0, parity_close=1, stream_richer=0
- `memory_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `tutor_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `direct` / `emotion_direct` / `sadness`: parity_close (sync=170, stream=137, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `hard_math_direct` / `hilbert_operator`: sync_missing_visible_thinking (sync=0, stream=2615, sync_status=fail, stream_status=pass)
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=114)
- `memory_agent` / `memory_name_roundtrip` / `recall_name`: parity_close (sync=876, stream=804, sync_status=pass, stream_status=pass)
  stream_events(thinking=13, tool_call=0, tool_result=0, action_text=0, answer=2)
- `memory_agent` / `memory_name_roundtrip` / `store_name`: parity_close (sync=1058, stream=1080, sync_status=pass, stream_status=pass)
  stream_events(thinking=16, tool_call=0, tool_result=0, action_text=0, answer=3)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_explain`: sync_missing_visible_thinking (sync=0, stream=309, sync_status=fail, stream_status=pass)
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=12, tool_call=1, tool_result=1, action_text=0, answer=36)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_visual`: sync_missing_visible_thinking (sync=0, stream=758, sync_status=pass, stream_status=pass)
  stream_events(thinking=25, tool_call=1, tool_result=1, action_text=0, answer=14)
