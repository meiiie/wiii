# Wiii AI Runtime — Service Level Objectives

**Version:** 1.0
**Effective date:** 2026-05-03
**Owner:** runtime team
**Review cadence:** monthly + after every incident postmortem

Phase 18 of the runtime migration epic
([#207](https://github.com/meiiie/wiii/issues/207)).

This document is the contract between the Wiii AI runtime and its
consumers (LMS, desktop app, channel gateways, MCP clients). It covers
**chat completion** traffic — the single highest-volume surface. Other
surfaces (knowledge ingestion, admin dashboards, eval recorders) are
out of scope for v1; they get their own SLOs once the chat surface is
stable.

## Why these numbers

The targets below come from three sources:

1. **Pre-Phase-9 production observations** of `/api/v1/chat` over the
   last 30 days (aggregated client-side via the LMS dashboard).
2. **Anthropic-published latency numbers** for OpenAI-compatible
   chat-completion APIs (Sonnet, Haiku) in March 2026.
3. **The acceptance bar** the team agreed to before flipping the
   `enable_native_runtime` canary: native runtime must not regress
   beyond 1.5× the legacy path's p99.

The numbers are **deliberately tight enough to catch regressions** and
**deliberately loose enough to be defensible** under realistic provider
variance. Tightening happens after we have a month of post-canary data.

## Definitions

- **Availability** — fraction of HTTP requests answered by the runtime
  (not by an upstream load balancer error page) with status `<500` over
  a rolling 30-day window. Excludes documented 503 responses from
  feature-gated endpoints (Phase 14 canary).
- **Latency p50 / p95 / p99** — server-side measurement, from receipt of
  the request body to the first byte of the streamed response. Pulled
  from the Phase 13 metrics façade (`edge.*.duration_ms` histograms,
  `runtime.subagent.duration_ms` for Task delegations).
- **Error rate** — fraction of HTTP responses with status `>=500`,
  measured server-side, excluding 503 from feature gates. Computed over
  a 5-minute rolling window for alerting; 30-day window for the SLO.

## Targets — chat completion

| Surface                    | Availability | p50      | p95      | p99      | Error rate |
|----------------------------|--------------|----------|----------|----------|------------|
| `POST /api/v1/chat`        | **99.9%**    | ≤ 800 ms | ≤ 2.5 s  | ≤ 5.0 s  | ≤ 0.5%     |
| `POST /v1/chat/completions`| **99.9%**    | ≤ 800 ms | ≤ 2.5 s  | ≤ 5.0 s  | ≤ 0.5%     |
| `POST /v1/messages`        | **99.9%**    | ≤ 800 ms | ≤ 2.5 s  | ≤ 5.0 s  | ≤ 0.5%     |

**Notes:**

- p99 envelope is generous because RAG retrieval + multi-step tool calls
  can legitimately take ≥ 3 s on cold cache. Sub-second p50 stays the
  user-experience target.
- Streaming TTFB (time to first byte) gets its own target once the
  Phase 13 metrics include a dedicated histogram. Today, the
  `edge.*.duration_ms` numbers measure full request duration including
  SSE flush.

## Targets — subagent isolation (Phase 12)

| Metric                                         | Target          |
|------------------------------------------------|-----------------|
| `runtime.subagent.duration_ms` p99              | ≤ 8.0 s         |
| `runtime.subagent.runs{status="error"}` rate    | ≤ 1% of total   |
| `runtime.subagent.runs{status="max_steps_exceeded"}` rate | ≤ 0.5% of total |

Subagents are bounded by `subagent_default_max_steps=10` (config).
Higher latency budget because a subagent typically does 3-8 LLM calls
in sequence.

## Targets — replay regression net (Phase 11b)

| Metric                                         | Target          |
|------------------------------------------------|-----------------|
| Nightly replay job success rate (last 30 days) | ≥ 28 / 30 days  |
| Records flagged as regression per nightly run  | ≤ 1% of replays |

A failing nightly replay job doesn't page on-call directly — it lands
as an artifact + dashboard tile. The on-call only gets paged if the
failure persists across **two consecutive nights** (operational
debounce).

## Error budget

A 99.9% availability target gives **43.2 minutes of budgeted downtime
per month**. The team consumes the budget on intentional changes
(deploys, canary rollouts, schema migrations). When the budget is
exhausted in a given month:

- All non-critical changes pause until the next month boundary.
- Postmortem is required for any single incident that consumed > 25%
  of the monthly budget (≥ 11 minutes downtime).
- The next month's SLO review must explicitly justify the budget
  spend or tighten the target.

## Alerting thresholds

These are the **paging thresholds**, not the SLO targets. They fire
faster than the 30-day SLO window so on-call can intervene before
budget is consumed.

| Symptom                                              | Window     | Threshold | Severity |
|------------------------------------------------------|------------|-----------|----------|
| `error rate >= 5xx` on any chat surface              | 5 minutes  | ≥ 2%      | P1 page  |
| `p99 latency` on any chat surface                    | 5 minutes  | ≥ 8 s     | P2 page  |
| Subagent error rate                                  | 15 minutes | ≥ 5%      | P2 page  |
| Postgres connection pool exhausted                   | 1 minute   | ≥ 3 occurrences | P1 page  |
| Provider failover triggered                          | 5 minutes  | ≥ 5 events | P3 ticket |
| Two consecutive nightly replay failures              | n/a        | n/a       | P2 page  |

## On-call playbook entries

Each row below maps to a written runbook in `docs/runtime/runbooks/`.
The runbooks ship with the structure + decision tree; they will get
sharper as the team responds to first-time incidents and carries
specific findings back into them.

| Symptom                              | Runbook                                            |
|--------------------------------------|----------------------------------------------------|
| 5xx surge on chat surface            | [`runbooks/chat-5xx-surge.md`](runbooks/chat-5xx-surge.md)         |
| p99 latency spike                    | [`runbooks/chat-latency-spike.md`](runbooks/chat-latency-spike.md) |
| Subagent error rate spike            | [`runbooks/subagent-errors.md`](runbooks/subagent-errors.md)       |
| Postgres pool exhaustion             | [`runbooks/db-pool-exhaustion.md`](runbooks/db-pool-exhaustion.md) |
| Provider failover storm              | [`runbooks/provider-failover.md`](runbooks/provider-failover.md)   |
| Nightly replay double-failure        | [`runbooks/replay-regression.md`](runbooks/replay-regression.md)   |

## What is NOT in scope for v1

- **Per-org SLAs.** Once `native_runtime_org_allowlist` has > 5 orgs,
  per-org error rate becomes meaningful. Until then everyone shares
  the global rollup.
- **Streaming TTFB.** Needs a dedicated metric (Phase 13 collects
  full-request duration only). Add when streaming becomes the
  dominant traffic shape.
- **Cost-per-turn SLOs.** Token cost lives in provider invoices, not
  on the data plane. Pulled in via the Phase 16 `/metrics` endpoint
  once the team adds a token-counting collector.

## Review log

| Date       | Reviewer | Change                                   |
|------------|----------|------------------------------------------|
| 2026-05-03 | runtime  | v1 — initial draft, derived from Phase 9-17 work |
