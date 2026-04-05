# Direct Origin Stream Depth Step — 2026-04-01

## Goal

Keo `direct selfhood/origin` stream visible thinking sau hon va co hon, nhung khong quay lai template gia.

## What Changed

- Tang selfhood visible-thinking supplement trong:
  - `app/engine/multi_agent/direct_prompts.py`
- Siet normalizer cua direct visible thinking trong:
  - `app/engine/multi_agent/direct_execution.py`
- Them turn-filter cho golden harness:
  - `scripts/probe_wiii_golden_eval.py`

## Key Fixes

1. Giup selfhood/origin turn duoc khuyen khich lo ra `2-4` cau/nhiep that hon.
2. Loai bo preamble/meta khong thuoc thought that:
   - `Reflecting on the Response`
   - `here's my take on those thoughts, tailored for an expert audience`
   - `The Birth of Wiii: A Personal Reflection`
   - `I will attempt a few kaomoji...`
   - `Day la cach minh thu tom tat lai... nham den doi tuong chuyen gia...`
3. Them `--turn-ids` vao golden eval de probe dung mot turn thay vi ca session.

## Tests

Focused suites:

- `test_direct_execution_streaming.py`
- `test_direct_prompts_identity_contract.py`
- `test_public_thinking_language.py`
- `test_wiii_golden_eval_scripts.py`

Status:

- `38 passed`

## Live Artifacts

Fresh targeted run:

- `wiii-golden-eval-2026-04-01-152709.json`
- `golden-stream-direct_origin_bong-origin-2026-04-01-152709.txt`
- `golden-sync-direct_origin_bong-origin-2026-04-01-152709.json`

Deterministic normalization preview from that live raw:

- `direct-origin-normalize-preview-2026-04-01.md`

## Current Truth

- Chieu sau cua `origin` stream da quay lai.
- Stream visible thinking da co than, co The Wiii Lab, co Bong, va co nhiep hoi tu than ro hon truoc.
- Van con mot lop meta/preamble moi tu provider/translator o live raw 15:27, nhung da duoc them rule strip trong code sau artifact do.
- Sync hien van bat on theo run: co run rat dep, co run fallback rong. Vi vay stream dang tro thanh authority thuc te hon cho selfhood/origin.

## Next Likely Step

- Rerun lai targeted `origin` sau patch marker moi de cap nhat HTML/viewer tu artifact sach hon.
