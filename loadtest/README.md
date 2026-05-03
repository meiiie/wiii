# Wiii AI — Load Testing Harness

Phase 17 of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Locust scenarios for `/api/v1/chat`, `/v1/chat/completions`, and
`/v1/messages` so canary rollouts can compare p50/p99 against a known
baseline before flipping `enable_native_runtime` for an org.

## Install

```bash
pip install locust
```

Locust is intentionally **not** in `requirements.txt` — this is an ops
dependency, not a runtime one. Install it on the load-generator box, not
on the app server.

## Quickstart

```bash
export WIII_HOST=http://localhost:8000
export WIII_API_KEY=test-key
export WIII_USER_ID=loadtest-1

# Headless: 50 users, ramp 5/s, run 2 minutes
locust -f loadtest/locustfile.py --headless \
    -u 50 -r 5 -t 2m --host $WIII_HOST

# Web UI: open http://localhost:8089 to drive interactively
locust -f loadtest/locustfile.py --host $WIII_HOST
```

Locust prints a per-endpoint summary on shutdown:

```
Type     Name                         # reqs   # fails  Avg   Min   Max  | p50  p95  p99
POST     /api/v1/chat                  1240        0    312    87  1842  | 240  890 1480
POST     /v1/chat/completions           620        0     11     3    44  |   8   24   38
POST     /v1/messages                   210        0     12     3    51  |   8   26   45
```

(503 responses from the edge endpoints when `enable_native_runtime` is
off are treated as **success** by the harness — see notes below.)

## Profiles

Set `WIII_LOAD_PROFILE` to focus traffic:

| Profile       | Endpoints exercised                                | Use for                              |
|---------------|-----------------------------------------------------|--------------------------------------|
| `smoke` (default) | all 3, weighted 2:3:1                          | quick sanity check + warmup          |
| `edge_only`   | `/v1/chat/completions` + `/v1/messages`             | canary regression vs baseline        |
| `legacy_only` | `/api/v1/chat`                                      | baseline before flipping the canary  |

## Comparing canary against baseline

1. **Capture baseline** before flipping the canary:

   ```bash
   WIII_LOAD_PROFILE=legacy_only \
   locust -f loadtest/locustfile.py --headless \
       -u 100 -r 10 -t 5m --host $WIII_HOST \
       --csv reports/baseline
   ```

2. **Add the canary org** to `native_runtime_org_allowlist` (Phase 14).

3. **Hit the edge endpoints** with the canary org's API key and
   `WIII_ORG_ID` set:

   ```bash
   WIII_LOAD_PROFILE=edge_only WIII_ORG_ID=canary-org \
   locust -f loadtest/locustfile.py --headless \
       -u 100 -r 10 -t 5m --host $WIII_HOST \
       --csv reports/canary
   ```

4. **Compare** `reports/baseline_stats.csv` and `reports/canary_stats.csv`.
   The acceptance bar (proposed): canary p99 ≤ 1.5× baseline p99 and
   error rate ≤ baseline error rate + 0.5%.

## Why 503 counts as success

When `enable_native_runtime=False` and the caller's org is not in the
allowlist, the edge endpoints return `503 Service Unavailable` with a
structured body — that's the documented "feature not enabled" response,
not a server fault. The harness treats 503 as a successful negative
response so a smoke run against a fresh dev box doesn't go red just
because the runtime is off. To validate the **gate itself** is working,
look at the response code distribution in Locust's web UI rather than
the pass/fail summary.

## Environment variables

| Variable           | Default                | Notes                                |
|--------------------|------------------------|--------------------------------------|
| `WIII_HOST`        | `http://localhost:8000` | `--host` on the CLI overrides       |
| `WIII_API_KEY`     | `test-key`             | sent as `X-API-Key`                  |
| `WIII_USER_ID`     | `loadtest-locust`      | sent as `X-User-ID`                  |
| `WIII_ORG_ID`      | unset                  | sent as `X-Organization-ID` if set   |
| `WIII_LOAD_PROFILE`| `smoke`                | see profiles table above             |

## What this harness does NOT do

- **Chaos / fault injection.** Provider failover, DB blips, network
  jitter. Those need a separate harness (Phase 19 — TBD).
- **Realistic conversation flow.** Each task is a single-turn prompt.
  Multi-turn session pinning is a follow-up.
- **Cost tracking.** Token counts are server-side; Locust only sees
  HTTP latency. Pull token metrics from `/metrics` (Phase 16) during
  the run if you need cost-per-turn estimates.
