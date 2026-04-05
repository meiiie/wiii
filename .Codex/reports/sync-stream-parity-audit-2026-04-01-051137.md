# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-01T05:11:37.031255`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-030533.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-042657.json`
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-043218.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-composite-2026-04-01-051137.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-01-051137.json`

## Summary
- `turn_count`: 8
- `stream_missing_visible_thinking`: 0
- `stream_thinner_than_sync`: 1
- `parity_close`: 5
- `stream_richer_than_sync`: 0
- `both_missing_visible_thinking`: 1

## Lane Breakdown
- `direct`: turns=5, stream_missing=0, stream_thinner=1, parity_close=3, stream_richer=0
- `memory_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `tutor_agent`: turns=1, stream_missing=0, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `direct` / `direct_origin_bong` / `bong_followup`: parity_close (sync=334, stream=237, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=6)
- `direct` / `direct_origin_bong` / `origin`: parity_close (sync=762, stream=695, sync_status=pass, stream_status=pass)
  stream_events(thinking=6, tool_call=0, tool_result=0, action_text=0, answer=4)
- `direct` / `emotion_direct` / `sadness`: stream_thinner_than_sync (sync=410, stream=275, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=5)
- `direct` / `hard_math_direct` / `hilbert_operator`: parity_close (sync=2565, stream=2285, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=91)
- `direct` / `tutor_rule15_visual` / `rule15_visual`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=fail)
  stream_failures=['missing_visible_thinking', 'missing_tool_trace']
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=16)
- `memory_agent` / `memory_name_roundtrip` / `recall_name`: parity_close (sync=977, stream=926, sync_status=pass, stream_status=pass)
  stream_events(thinking=13, tool_call=0, tool_result=0, action_text=0, answer=4)
- `memory_agent` / `memory_name_roundtrip` / `store_name`: parity_close (sync=1049, stream=1218, sync_status=pass, stream_status=pass)
  stream_events(thinking=16, tool_call=0, tool_result=0, action_text=0, answer=6)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_explain`: sync_missing_visible_thinking (sync=0, stream=667, sync_status=fail, stream_status=pass)
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=21, tool_call=1, tool_result=1, action_text=0, answer=27)
