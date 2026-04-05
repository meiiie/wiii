# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-02T01:06:01.385463`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-214818.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-224938.json`
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-233642.json`
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-003817.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-02-lifecycle-v1-composite-2026-04-02-010601.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-02-lifecycle-v1-2026-04-02-010601.json`

## Summary
- `turn_count`: 18
- `stream_missing_visible_thinking`: 1
- `stream_thinner_than_sync`: 0
- `parity_close`: 8
- `stream_richer_than_sync`: 2
- `both_missing_visible_thinking`: 4

## Lane Breakdown
- `code_studio_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `direct`: turns=9, stream_missing=0, stream_thinner=0, parity_close=3, stream_richer=2
- `memory_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `product_search_agent`: turns=1, stream_missing=0, stream_thinner=0, parity_close=1, stream_richer=0
- `tutor_agent`: turns=4, stream_missing=1, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `code_studio_agent` / `code_studio_rule15_sim` / `rule15_sim`: parity_close (sync=208, stream=418, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=3, tool_result=3, action_text=2, answer=34)
- `code_studio_agent` / `code_studio_rule15_sim` / `rule15_sim_annotation`: parity_close (sync=290, stream=582, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=1, tool_result=1, action_text=0, answer=7)
- `direct` / `casual_followup_micro` / `hehe`: parity_close (sync=156, stream=367, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=7)
- `direct` / `casual_followup_micro` / `oke`: parity_close (sync=210, stream=262, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=5)
- `direct` / `direct_origin_bong` / `bong_followup`: stream_richer_than_sync (sync=549, stream=814, sync_status=pass, stream_status=pass)
  stream_events(thinking=5, tool_call=0, tool_result=0, action_text=0, answer=3)
- `direct` / `direct_origin_bong` / `origin`: stream_richer_than_sync (sync=22, stream=756, sync_status=pass, stream_status=pass)
  stream_events(thinking=6, tool_call=0, tool_result=0, action_text=0, answer=4)
- `direct` / `emotion_direct` / `sadness`: parity_close (sync=159, stream=161, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `hard_math_direct` / `hilbert_operator`: both_missing_visible_thinking (sync=0, stream=0, sync_status=fail, stream_status=fail)
  stream_failures=['missing_visible_thinking']
  sync_failures=['missing_visible_thinking']
  stream_events(thinking=0, tool_call=1, tool_result=1, action_text=0, answer=90)
- `direct` / `product_search_audio` / `headphone_compare`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=pass)
  stream_events(thinking=0, tool_call=1, tool_result=1, action_text=0, answer=19)
- `direct` / `search_current_events` / `oil_compress`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=pass)
  stream_events(thinking=0, tool_call=1, tool_result=1, action_text=0, answer=25)
- `direct` / `search_current_events` / `oil_today`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=pass)
  stream_events(thinking=0, tool_call=1, tool_result=1, action_text=0, answer=57)
- `memory_agent` / `memory_name_roundtrip` / `recall_name`: parity_close (sync=697, stream=825, sync_status=pass, stream_status=pass)
  stream_events(thinking=13, tool_call=0, tool_result=0, action_text=0, answer=2)
- `memory_agent` / `memory_name_roundtrip` / `store_name`: parity_close (sync=1098, stream=1054, sync_status=pass, stream_status=pass)
  stream_events(thinking=16, tool_call=0, tool_result=0, action_text=0, answer=4)
- `product_search_agent` / `product_search_audio` / `headphone_search`: parity_close (sync=233, stream=6911, sync_status=fail, stream_status=pass)
  sync_failures=['agent_mismatch:rag']
  stream_events(thinking=204, tool_call=9, tool_result=9, action_text=0, answer=82)
- `tutor_agent` / `lookup_grounded_rule15` / `rule15_lookup`: sync_missing_visible_thinking (sync=0, stream=255, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=1, tool_result=1, action_text=0, answer=34)
- `tutor_agent` / `lookup_grounded_rule15` / `rule16_followup`: sync_missing_visible_thinking (sync=0, stream=719, sync_status=pass, stream_status=pass)
  stream_events(thinking=22, tool_call=1, tool_result=1, action_text=0, answer=38)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_explain`: stream_missing_visible_thinking (sync=304, stream=0, sync_status=pass, stream_status=fail)
  stream_failures=['missing_visible_thinking']
  stream_events(thinking=2, tool_call=1, tool_result=1, action_text=0, answer=39)
- `tutor_agent` / `tutor_rule15_visual` / `rule15_visual`: sync_missing_visible_thinking (sync=0, stream=677, sync_status=pass, stream_status=pass)
  stream_events(thinking=23, tool_call=1, tool_result=1, action_text=0, answer=14)
