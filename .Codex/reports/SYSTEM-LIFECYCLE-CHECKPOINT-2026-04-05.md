# System Lifecycle Checkpoint

Date: 2026-04-05

## Why this checkpoint exists

This repository has accumulated a large, coordinated local checkpoint across backend, desktop, runtime policy, eval harnesses, and live debugging artifacts.

This document summarizes the current system shape before commit/push so the branch has one stable operator-facing narrative instead of many isolated reports.

## What is now structurally in place

### 1. Thinking lifecycle authority

- Visible thinking now has a dedicated lifecycle authority instead of being stitched from ad-hoc deltas.
- `sync` and `stream` both consume the same lifecycle source.
- HTML viewer, parity audit, and golden eval scripts now read from that same authority.

Key outcomes:

- `stream` is no longer systematically thinner than `sync`.
- final snapshot rescue is explicit and measurable.
- tutor/direct/memory lanes can be debugged via one lifecycle model.

### 2. Provider + model as real sockets

- Request-level `provider` and `model` now travel farther through the real runtime path instead of being silently dropped.
- Runtime metadata, failover state, and model-switch UX are now surfaced more honestly in both `sync` and `stream`.

Key outcomes:

- provider failures no longer disappear behind generic answers as often.
- model-switch prompting is grounded in actual runtime observations.
- provider/runtime audit and chat behavior are closer to each other.

### 3. Embedding runtime is no longer single-vendor

- Semantic memory, hybrid retrieval, ingestion, CRAG, HyDE, and related retrieval paths have been moved onto a shared embedding authority.
- The system now supports multi-socket embedding backends with selectability and runtime policy.
- Same-space guardrails and shadow migration tooling are in place.

Key outcomes:

- memory/retrieval no longer depends exclusively on Gemini embeddings.
- fail-open behavior is safer when embeddings fail.
- canonical embedding space can be audited and migrated deliberately.

### 4. Vision runtime is capability-aware

- Vision handling is now split by capability instead of pretending OCR and general vision are the same task.
- `ocr_extract`, `visual_describe`, and `grounded_visual_answer` now sit behind a shared runtime authority with policy, selectability, and audit.
- OCR specialist vs fallback roles are now visible to operators.

Key outcomes:

- local general vision can run through Ollama.
- OCR lane can prefer specialist contracts while still degrading cleanly.
- vision runtime state is now observable instead of opaque.

### 5. Tutor live path is no longer rail-empty

- Tutor live metadata is authoritative.
- Tutor continuation after tool usage now has a safe fallback path derived from distilled tool signals.
- Live tutor stream now emits real `thinking_delta` events again instead of only `thinking_start/end`.

Key outcomes:

- `rule15_explain` regained visible thinking in both `sync` and `stream`.
- `rule15_visual` regained live post-tool thinking.
- remaining tutor issue is quality polish, not missing plumbing.

## Current truth by subsystem

### Chat core

- Core chat lifecycle now has endpoint-level E2E coverage for direct, memory, RAG, tutor, and failover-focused flows.
- Failover and model-switch behavior is significantly more truthful than before.

### RAG + memory

- Retrieval and semantic memory have been moved away from one-provider dependence.
- Write paths now fail open more safely when embeddings are unavailable.
- Remaining work is mostly quality and coverage, not basic architecture.

### Vision + OCR

- Vision runtime authority exists.
- Vision policy by capability exists.
- Vision live probe and runtime observation audit exist.

### Frontend

- Desktop stream/finalize behavior has been updated to respect lifecycle and model/provider runtime state more accurately.
- Admin/runtime views now show more of the truth about provider health and lane fit.

## What is still not done

### 1. Some lanes still need quality polish

- Tutor visual continuation is alive but still somewhat metadata-shaped.
- Memory thinking can still sound narrator-like in some turns.
- Some lanes remain functionally correct but stylistically not yet at the best Wiii level.

### 2. Full-system E2E closure is not complete

- Chat core has meaningful E2E coverage.
- But multimodal/product/code-studio full-path end-to-end closure is not yet one final unified suite.

### 3. Live upstream variability still matters

- Provider health, quotas, latency, and upstream behavior still affect observed quality.
- The system is more resilient now, but not independent from external runtime conditions.

## Practical conclusion

The system is no longer in the old state where:

- visible thinking depended on one brittle path,
- embeddings depended on one vendor,
- vision was treated as one undifferentiated capability,
- or stream behavior quietly drifted from sync without good observability.

At this checkpoint, the architecture is much closer to a professional multi-socket runtime with explicit lifecycle authorities.

The remaining work is primarily:

- quality refinement,
- broader E2E closure,
- and operator/runtime hardening,

not rebuilding the foundations again.
