# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-02T02:26:43.557003`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-02-lifecycle-v1-composite-2026-04-02-010601.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-020638.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-02-followup-composite-2026-04-02-022643.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\sync-stream-parity-audit-2026-04-02-followup-2026-04-02-022643.json`

## Summary
- `turn_count`: 18
- `stream_missing_visible_thinking`: 0
- `stream_thinner_than_sync`: 1
- `parity_close`: 7
- `stream_richer_than_sync`: 2
- `both_missing_visible_thinking`: 6

## Lane Breakdown
- `code_studio_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `direct`: turns=8, stream_missing=0, stream_thinner=0, parity_close=3, stream_richer=2
- `memory_agent`: turns=2, stream_missing=0, stream_thinner=0, parity_close=2, stream_richer=0
- `rag_agent`: turns=2, stream_missing=0, stream_thinner=1, parity_close=0, stream_richer=0
- `tutor_agent`: turns=4, stream_missing=0, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `code_studio_agent` / `code_studio_rule15_sim` / `rule15_sim`: parity_close (sync=208, stream=208, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=3, tool_result=3, action_text=2, answer=34)
- `code_studio_agent` / `code_studio_rule15_sim` / `rule15_sim_annotation`: parity_close (sync=290, stream=290, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=1, tool_result=1, action_text=0, answer=7)
- `direct` / `casual_followup_micro` / `hehe`: parity_close (sync=156, stream=221, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=7)
- `direct` / `casual_followup_micro` / `oke`: parity_close (sync=210, stream=187, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=5)
- `direct` / `direct_origin_bong` / `bong_followup`: stream_richer_than_sync (sync=549, stream=814, sync_status=pass, stream_status=pass)
  stream_events(thinking=5, tool_call=0, tool_result=0, action_text=0, answer=3)
- `direct` / `direct_origin_bong` / `origin`: stream_richer_than_sync (sync=22, stream=756, sync_status=pass, stream_status=pass)
  stream_events(thinking=6, tool_call=0, tool_result=0, action_text=0, answer=4)
- `direct` / `emotion_direct` / `sadness`: parity_close (sync=159, stream=161, sync_status=pass, stream_status=pass)
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `product_search_audio` / `headphone_compare`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=pass)
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=1)
- `direct` / `search_current_events` / `oil_compress`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=pass)
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=1)
- `direct` / `tutor_rule15_visual` / `rule15_visual`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=fail)
  stream_failures=['missing_visible_thinking', 'missing_tool_trace']
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=1)
- `memory_agent` / `memory_name_roundtrip` / `recall_name`: parity_close (sync=697, stream=825, sync_status=pass, stream_status=pass)
  stream_events(thinking=13, tool_call=0, tool_result=0, action_text=0, answer=2)
- `memory_agent` / `memory_name_roundtrip` / `store_name`: parity_close (sync=1098, stream=1054, sync_status=pass, stream_status=pass)
  stream_events(thinking=16, tool_call=0, tool_result=0, action_text=0, answer=4)
- `rag_agent` / `product_search_audio` / `headphone_search`: both_missing_visible_thinking (sync=0, stream=0, sync_status=fail, stream_status=fail)
  stream_failures=['missing_tool_trace', 'agent_mismatch:rag_agent']
  sync_failures=['agent_mismatch:rag']
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=2)
- `rag_agent` / `tutor_rule15_visual` / `rule15_explain`: stream_thinner_than_sync (sync=79, stream=54, sync_status=fail, stream_status=fail)
  stream_failures=['agent_mismatch:rag_agent']
  sync_failures=['agent_mismatch:rag']
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=1)
- `tutor_agent` / `hard_math_direct` / `hilbert_operator`: both_missing_visible_thinking (sync=0, stream=0, sync_status=fail, stream_status=fail)
  stream_failures=['missing_visible_thinking', 'agent_mismatch:tutor_agent']
  sync_failures=['missing_visible_thinking', 'agent_mismatch:tutor']
  stream_events(thinking=2, tool_call=0, tool_result=0, action_text=0, answer=2)
- `tutor_agent` / `lookup_grounded_rule15` / `rule15_lookup`: sync_missing_visible_thinking (sync=0, stream=255, sync_status=pass, stream_status=pass)
  stream_events(thinking=11, tool_call=1, tool_result=1, action_text=0, answer=34)
- `tutor_agent` / `lookup_grounded_rule15` / `rule16_followup`: sync_missing_visible_thinking (sync=0, stream=719, sync_status=pass, stream_status=pass)
  stream_events(thinking=22, tool_call=1, tool_result=1, action_text=0, answer=38)
- `tutor_agent` / `search_current_events` / `oil_today`: both_missing_visible_thinking (sync=0, stream=0, sync_status=fail, stream_status=fail)
  stream_failures=['missing_tool_trace', 'agent_mismatch:tutor_agent']
  sync_failures=['agent_mismatch:tutor']
  stream_events(thinking=2, tool_call=0, tool_result=0, action_text=0, answer=2)
