# Intent Identity and Exactly-Once Effects (research surface)

Status: active research surface, v0.3, 2026-09-19. Not submitted anywhere.

This directory holds the v0.3 development release of the study "Exactly-Once
Effects for Re-Planning LLM Agents: A Reduction, a Retention Hazard, and an
Evidence Contract" (previously "Intent Identity and Exactly-Once Effects for
Non-Deterministic LLM Agents", v0.2). It is research groundwork for the Wiii
tool-execution contract; nothing here is wired into the runtime yet.

## What is here

| Path | Content |
| --- | --- |
| `paper/main.tex`, `paper/main.pdf` | Manuscript v0.3 (IEEEtran, 8 pages). |
| `REPORT_VI_v0.3.md` | Vietnamese research report for the project owner. |
| `EVIDENCE_SUMMARY_v0.3.json` | Machine-readable summary of every number in the paper. |
| `PROVIDER_CONTRACTS.md` | Quoted, dated facts from official provider documentation used as evidence. |
| `artifact/` | Independent stdlib-only Python re-implementation, experiments, raw results. |

## Reproduce

```bash
cd docs/research/intent-identity/artifact
python3 run_all.py          # ~10 min on one core; regenerates results/
python3 run_all.py quick    # skips the process-crash studies
python3 -m unittest discover -s tests -v
```

Build the paper with any LaTeX engine that has IEEEtran and TikZ; the
committed PDF was produced with Tectonic 0.15.

## Relationship to v0.2

The v0.2 artifact was not available to this session; the v0.3 artifact was
written from the v0.2 manuscript's specification. It reproduces every v0.2
finite-domain count exactly (D1: 186,674 cases, 130,348 group-key duplicates
split 16 / 1,308 / 129,024; E1: 65,535 families, 1,048,560 checks, 941
nonempty frontiers; E3 closed form to n = 10) and the I1/I2 pass counts
(240/240, 24/24). Model-checker state counts differ from v0.2 because the
encoding differs; the mutant witnesses have the same shape.

## What v0.3 adds

- A strengthened reference `R+` that consults its own ledger; it ties the
  verifier `V` call-for-call, sharpening the v0.2 null result.
- Retention-bounded provider profile `P_D(T)`, a necessary-and-sufficient
  same-key-retry condition using only the controller's hold timestamp, and
  exhaustive, model-checked and process-level evidence that every same-key
  policy duplicates after the window while the retention-aware controller does
  not (D1-TTL, M1 mutant, I4).
- An in-flight takeover study across `P_D` / `P_F` / `P_O` with naive vs
  profile-aware recovery (I3), separating sink dedup, fence-then-fresh-key and
  the explicit `unresolved` state.
- Semantics-determined belief families (independent / atomic / prefix /
  exact-k) with closed forms verified by an exact oracle (E4).
- A measured finding that reservation-resolved concurrency races never reach
  sink deduplication (I2: 0 of 96 sink calls deduplicated).

## Relevance to Wiii

`docs/architecture/WIII_WORKBENCH_IDENTITY_AND_ACP.md` states that after
`continuityLevel: recovered`, interrupted mutations remain `unknown outcome`
and are not retried. That is the `P_O`-aware behaviour in this study: safe,
not complete. The study shows which additional contract fields a Wiii tool
adapter would need to declare for the controller to do better without losing
safety: the provider's idempotency window `T`, whether an evidence lookup or
a fence exists, and the batch processing class. `specs/941-neko-durable-runtime`
user story 3 (retry by request ID without duplicate side effects) is the
controller-internal `P_D` case; this study concerns the external-provider
boundary beyond it.

## Boundaries

No live LLM, no commercial provider call, no paid inference, no submission.
Provider facts are quoted from documentation on the access date and may
change. Characterizations of the 2026 arXiv preprints cited in the paper are
carried from the v0.2 literature audit and must be re-verified by a human
before any submission.
