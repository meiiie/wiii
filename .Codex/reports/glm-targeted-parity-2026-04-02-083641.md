# Wiii Sync vs Stream Parity Audit

- Generated: `2026-04-02T08:36:41.476700`
- Base report: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-082132.json`
- Overlays:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-082935.json`
  - `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-02-083207.json`
- Composite report: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-targeted-parity-composite-2026-04-02-083641.json`
- Parity JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\glm-targeted-parity-2026-04-02-083641.json`

## Summary
- `turn_count`: 4
- `stream_missing_visible_thinking`: 2
- `stream_thinner_than_sync`: 0
- `parity_close`: 0
- `stream_richer_than_sync`: 0
- `both_missing_visible_thinking`: 1
- `avg_processing_time.sync`: 81.489
- `avg_processing_time.stream`: 94.203
- `provider_counts.sync`: {'zhipu': 4}
- `provider_counts.stream`: {'zhipu': 3}
- `model_counts.sync`: {'glm-5': 4}
- `model_counts.stream`: {'glm-5': 3}
- `failover_reason_counts`: {'rate_limit': 4, 'timeout': 1}
- `failover_route_counts`: {'google->google': 4, 'google->zhipu': 5}

## Lane Breakdown
- `direct`: turns=4, stream_missing=2, stream_thinner=0, parity_close=0, stream_richer=0

## Findings
- `direct` / `direct_origin_bong` / `bong_followup`: both_missing_visible_thinking (sync=0, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=zhipu, sync_time=87.366, stream_time=112.2552330493927)
  stream_failures=['missing_visible_thinking']
  sync_failover=['google->google', 'google->zhipu'] stream_failover=['google->google', 'google->zhipu']
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=4)
- `direct` / `direct_origin_bong` / `origin`: stream_missing_visible_thinking (sync=199, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=zhipu, sync_time=84.091, stream_time=25.005276918411255)
  stream_failures=['missing_visible_thinking']
  sync_failover=['google->google', 'google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=2)
- `direct` / `emotion_direct` / `sadness`: stream_missing_visible_thinking (sync=190, stream=0, sync_status=pass, stream_status=fail, sync_provider=zhipu, stream_provider=None, sync_time=83.322, stream_time=None)
  stream_failures=['missing_answer', 'agent_mismatch:none']
  sync_failover=['google->zhipu'] stream_failover=[]
  stream_events(thinking=0, tool_call=0, tool_result=0, action_text=0, answer=0)
- `direct` / `hard_math_direct` / `hilbert_operator`: sync_missing_visible_thinking (sync=0, stream=834, sync_status=fail, stream_status=pass, sync_provider=zhipu, stream_provider=zhipu, sync_time=71.175, stream_time=145.34778141975403)
  sync_failures=['missing_visible_thinking']
  sync_failover=[] stream_failover=['google->google', 'google->zhipu']
  stream_events(thinking=3, tool_call=0, tool_result=0, action_text=0, answer=96)
