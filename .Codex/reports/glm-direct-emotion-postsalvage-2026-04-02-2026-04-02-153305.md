# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-02T15:33:05.509525`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-152013.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-152953.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-direct-emotion-postsalvage-2026-04-02-composite-2026-04-02-153305.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-direct-emotion-postsalvage-2026-04-02-2026-04-02-153305.json`

## Summary
- `turn_count`: 3
- `stream_missing_visible_thinking`: 1
- `stream_thinner_than_sync`: 0
- `parity_close`: 0
- `stream_richer_than_sync`: 1
- `both_missing_visible_thinking`: 0
- `avg_processing_time.sync`: 106.16
- `avg_processing_time.stream`: 131.125
- `provider_counts.sync`: {'zhipu': 3}
- `provider_counts.stream`: {'zhipu': 2}
- `model_counts.sync`: {'glm-5': 3}
- `model_counts.stream`: {'glm-5': 2}
- `failover_reason_counts`: {'rate_limit': 3, 'timeout': 1}
- `failover_route_counts`: {'google->google': 3, 'google->zhipu': 4}

## Lane Breakdown
- `direct`: turns=3, stream_missing=1, stream_thinner=0, parity_close=0, stream_richer=1

## Findings
- `direct` / `direct_origin_bong` / `bong_followup`: sync_missing_visible_thinking (sync=0, stream=84, sync_status=pass, stream_status=pass, sync_provider=zhipu, stream_provider=zhipu, sync_time=68.913, stream_time=102.8123722076416)
  sync_failover=[] stream_failover=['google->google', 'google->zhipu']
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=6)
- `direct` / `direct_origin_bong` / `origin`: stream_richer_than_sync (sync=249, stream=410, sync_status=pass, stream_status=pass, sync_provider=zhipu, stream_provider=zhipu, sync_time=160.389, stream_time=159.43790316581726)
  sync_failover=['google->google', 'google->zhipu'] stream_failover=['google->google', 'google->zhipu']
  stream_events(thinking=4, tool_call=0, tool_result=0, action_text=0, answer=7)
- `direct` / `emotion_direct` / `sadness`: stream_missing_visible_thinking (sync=133, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=None, sync_time=89.177, stream_time=None)
  stream_failures=['missing_answer', 'agent_mismatch:none']
  sync_failover=['google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=0)
