# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-02T15:55:29.802897`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-154620.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-152953.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-direct-emotion-mixed-latest-2026-04-02-composite-2026-04-02-155529.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-direct-emotion-mixed-latest-2026-04-02-2026-04-02-155529.json`

## Summary
- `turn_count`: 3
- `stream_missing_visible_thinking`: 3
- `stream_thinner_than_sync`: 0
- `parity_close`: 0
- `stream_richer_than_sync`: 0
- `both_missing_visible_thinking`: 0
- `avg_processing_time.sync`: 114.863
- `avg_processing_time.stream`: 72.786
- `provider_counts.sync`: {'zhipu': 3}
- `provider_counts.stream`: {'zhipu': 2}
- `model_counts.sync`: {'glm-5': 3}
- `model_counts.stream`: {'glm-5': 2}
- `failover_reason_counts`: {'rate_limit': 2, 'timeout': 1}
- `failover_route_counts`: {'google->google': 2, 'google->zhipu': 3}

## Lane Breakdown
- `direct`: turns=3, stream_missing=3, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `direct` / `direct_origin_bong` / `bong_followup`: stream_missing_visible_thinking (sync=84, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=zhipu, sync_time=112.912, stream_time=73.95664978027344)
  stream_failures=['missing_visible_thinking']
  sync_failover=['google->google', 'google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `direct_origin_bong` / `origin`: stream_missing_visible_thinking (sync=519, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=zhipu, sync_time=142.499, stream_time=71.6143536567688)
  stream_failures=['missing_visible_thinking']
  sync_failover=['google->google', 'google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `emotion_direct` / `sadness`: stream_missing_visible_thinking (sync=133, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=None, sync_time=89.177, stream_time=None)
  stream_failures=['missing_answer', 'agent_mismatch:none']
  sync_failover=['google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=0)
