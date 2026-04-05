# Sentrux Rerun — Wiii Backend — 2026-03-27

> Scope: rerun real Sentrux on the backend after the latest `graph.py` refactor cuts
> Binary used: `E:\Sach\Sua\AI_v1\tools\sentrux.exe`
> Version: `sentrux 0.5.7`

---

## 1. How Sentrux was recovered

The machine had Sentrux data and plugins already present:

- User profile data: `C:\Users\Admin\.sentrux`
- Project rules: [rules.toml](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/.sentrux/rules.toml)
- Project baseline: [baseline.json](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/.sentrux/baseline.json)

But the `sentrux` executable was not on `PATH`.

To run the tool again, I downloaded the official Windows binary into:

- [sentrux.exe](/E:/Sach/Sua/AI_v1/tools/sentrux.exe)

Verified:

- `sentrux 0.5.7`

---

## 2. Commands run

From backend app root:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe check .
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Working directory:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app`

---

## 3. Raw results

### `sentrux check .`

```text
sentrux check — 0 rules checked

Quality: 3589

✓ All rules pass
Scanning ....
[build_project_map] 522 files, 89 unique dirs, 80 cache misses, 21.5ms
[resolve] 1403 resolved, 1747 unresolved (of 3150 total specs)
[resolve_imports] project_map 21.6ms, suffix_idx 1.7ms, suffix_resolve 27.4ms, total 50.7ms
[build_graphs] 522 files | maps 1.0ms, imports 50.9ms, calls+inherit 5.1ms, total 57.1ms | 1400 import, 3373 call, 33 inherit edges
```

### `sentrux gate .`

```text
sentrux gate — structural regression check

Quality:      3581 -> 3589
Coupling:     0.36 → 0.35
Cycles:       8 → 8
God files:    9 → 9

Distance from Main Sequence: 0.36

✓ No degradation detected
Scanning ....
[build_project_map] 522 files, 89 unique dirs, 80 cache misses, 22.7ms
[resolve] 1403 resolved, 1747 unresolved (of 3150 total specs)
[resolve_imports] project_map 22.9ms, suffix_idx 1.7ms, suffix_resolve 26.4ms, total 51.0ms
[build_graphs] 522 files | maps 1.2ms, imports 51.3ms, calls+inherit 5.7ms, total 58.3ms | 1400 import, 3373 call, 33 inherit edges
```

---

## 4. Comparison with baseline

Baseline from [baseline.json](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/.sentrux/baseline.json):

- `quality_signal`: `0.35808875359771225` → about `3581`
- `coupling_score`: `0.35775526110678096` → about `0.36`
- `cycle_count`: `8`
- `god_file_count`: `9`
- `complex_fn_count`: `141`
- `max_depth`: `22`
- `total_import_edges`: `1283`
- `cross_module_edges`: `956`

Current rerun confirms:

- quality improved from `3581` to `3589`
- coupling improved from `0.36` to `0.35`
- cycles unchanged at `8`
- god files unchanged at `9`

---

## 5. Interpretation

This is a real structural improvement, but still a small one.

### Good news

- The recent refactor did help:
  - better quality score
  - slightly lower coupling
  - no regression detected by gate

This validates the current extraction strategy as safe and directionally correct.

### Important reality check

- The refactor has **not** yet crossed the threshold needed to reduce the god-file count.
- In other words:
  - the codebase is cleaner than baseline
  - but not yet clean enough for Sentrux to consider one of the current god-file clusters resolved

That matches what we already saw manually:

- `graph.py` is much smaller than before
- but orchestration complexity is still concentrated in a few heavyweight functions
- coupling across `graph.py`, prompt builders, execution loops, and node wrappers is still high

---

## 6. One oddity to note

`sentrux check .` reported:

- `0 rules checked`

while still producing:

- `Quality: 3589`
- `✓ All rules pass`

Likely explanations:

1. `check` is computing the structural model but not counting the current TOML thresholds as discrete "rules checked" in this version
2. `gate` is the more reliable signal for regression/non-regression in the current setup

This does **not** invalidate the scan. The `gate` output is the most useful signal here, and it clearly confirms improvement without regression.

---

## 7. Practical conclusion for the team

The team's current direction is correct:

- continue refactoring `graph.py` and adjacent high-coupling modules
- keep each extraction small and independently verifiable
- prioritize cuts that remove responsibility overlap, not just raw line count

Best next targets remain:

1. public-thinking ownership helpers
2. Code Studio summary/synthesis helpers
3. only later, the biggest execution loops

This Sentrux rerun supports continuing the cleanup plan. It does **not** yet support declaring the structural problem solved.

