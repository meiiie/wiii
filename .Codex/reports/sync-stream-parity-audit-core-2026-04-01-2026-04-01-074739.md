# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-01T07:47:39.096529`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-065017.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-072108.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-core-2026-04-01-composite-2026-04-01-074739.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-core-2026-04-01-2026-04-01-074739.json`

## Summary
- `turn_count`: 8
- `stream_missing_visible_thinking`: 0
- `stream_thinner_than_sync`: 0
- `parity_close`: 4
- `stream_richer_than_sync`: 1
- `both_missing_visible_thinking`: 1

## Lane Breakdown
- `direct`: turns=4, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `memory_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `tutor_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=0, stream_richer=1

## Findings
- `direct` / `direct_origin_bong` / `bong_followup`: parity_close (sync=388, stream=309, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=4)
- `direct` / `direct_origin_bong` / `origin`: both_missing_visible_thinking (sync=0, stream=0, sync_status=fail, stream_status=fail)
  stream_failures=['missing_visible_thinking']
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `emotion_direct` / `sadness`: parity_close (sync=170, stream=137, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `hard_math_direct` / `hilbert_operator`: sync_missing_visible_thinking (sync=0, stream=2615, sync_status=fail, stream_status=pass)
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=114)
- `memory_agent` / `memory_name_roundtrip` / `recall_name`: parity_close (sync=876, stream=804, sync_status=pass, stream_status=pass)
  stream_events(thinking=13, tool_call=0, tool_result=0, action_text=0, answer=2)
- `memory_agent` / `memory_name_roundtrip` / `store_name`: parity_close (sync=1058, stream=1080, sync_status=pass, stream_status=pass)
  stream_events(thinking=16, tool_call=0, tool_result=0, action_text=0, answer=3)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_explain`: stream_richer_than_sync (sync=256, stream=827, sync_status=pass, stream_status=pass)
  stream_events(thinking=25, tool_call=1, tool_result=1, action_text=0, answer=30)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_visual`: sync_missing_visible_thinking (sync=0, stream=643, sync_status=pass, stream_status=pass)
  stream_events(thinking=23, tool_call=1, tool_result=1, action_text=0, answer=14)
