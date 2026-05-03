# Wiii AI — Chaos Testing Harness

Phase 20 of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Reproducible failure scenarios so an oncall can verify circuit breakers, fallback chains, and the Phase 19 durable event log behave correctly under provider degradation **before** it happens in prod.

## Install

```bash
pip install pytest httpx
```

Chaos pytest scenarios are **not** in `requirements.txt` — this is an ops dependency. Install on the workstation running the chaos suite, not the app server. The scenarios speak HTTP to a real Wiii instance (local docker compose by default).

## Quickstart

```bash
# Boot a local Wiii stack with the canary gate open + native runtime on
export WIII_HOST=http://localhost:8000
export WIII_API_KEY=test-key
export WIII_ORG_ID=chaos-canary  # must be in native_runtime_org_allowlist

cd chaos
pytest scenarios/ -v
```

Each scenario:

1. **Sets up** a deterministic fault (env var override, monkey-patched provider, fake tool).
2. **Drives** load against the runtime via HTTP.
3. **Asserts** the system responded the way the SLO doc says it should.
4. **Tears down** so the next scenario starts clean.

## Scenarios shipped today

| File                                | What it asserts                                                          |
|-------------------------------------|--------------------------------------------------------------------------|
| `scenarios/test_chatservice_exception.py` | ChatService raises mid-turn → native_dispatch still emits the `assistant_message` event with `status=error` (Phase 19 contract). Both `RuntimeError` and `TimeoutError` paths covered. 5-consecutive-failure case verifies counter aggregation. |
| `scenarios/test_repeated_native_runs_record_metrics.py` | 50 successful turns → `runtime.native_dispatch.runs{status="success"}` counter + duration histogram populate correctly via Phase 13 façade. Mixed success/error sequence verifies the status label keeps buckets distinct. |
| `scenarios/test_subagent_runner_under_chaos.py` | SubagentRunner.run with the ChatService bridge under provider failure → parent log gets exactly two bookend events (`subagent_started` + `subagent_completed` with `status=error`), no leak of child's working messages. 5-failure loop verifies isolation holds under sustained pressure. |

These tests **do not** reach an external LLM provider — they monkey-patch `get_chat_service()` at the seam, so they run in seconds + cost zero tokens.

## Scenarios deferred (TODO, separate phase)

| Scenario                            | Why deferred                                                             |
|-------------------------------------|--------------------------------------------------------------------------|
| LLM provider 5xx → failover chain   | Needs a hook inside `LLMPool` that doesn't exist yet. Adding it is a runtime change, not an ops harness change. |
| Provider timeout → circuit breaker  | Same reason. The pool's circuit breaker behavior is currently only verified by unit tests with mocks. |
| Postgres pool exhaustion            | Needs a real Postgres + asyncpg manipulation; better as an integration test in `tests/integration/`. |
| Real network chaos (TCP RST, jitter)| Needs a kernel-level tool (Toxiproxy, iptables); out of scope for Python pytest. |

## Adding a new scenario

1. Identify a real failure mode you want to defend against (incident postmortem, oncall observation, SLO breach hypothesis).
2. Decide which boundary you'll inject the fault at (HTTP layer, ChatService method, provider client).
3. Write a pytest file under `scenarios/` that follows the same pattern as the existing four.
4. Make sure the assertion checks observable behavior (HTTP status, durable log content, metrics counter), not implementation detail.

## What this harness does NOT do

- **Real network chaos** (TCP RST, packet loss, latency injection). That needs a kernel-level tool (Toxiproxy, iptables); out of scope for Python pytest.
- **Multi-region failover.** Wiii is single-region today.
- **Postgres failure modes.** Connection pool exhaustion has its own runbook (Phase 18 SLO doc); the chaos harness will pick this up later.
- **Browser-agent / scraping chaos.** Those have their own subsystems.

## Relationship to other harnesses

- **Load test (`loadtest/`)**: how much can the system take? Volume, throughput, tail latency.
- **Chaos test (`chaos/`)**: does the system degrade gracefully? Failure shape, recovery, error budget impact.

Run them on different cadences. Load tests before each canary expansion. Chaos tests after every change to the failover or circuit-breaker code paths.
