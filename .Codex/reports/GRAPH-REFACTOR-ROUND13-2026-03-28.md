# Graph Refactor Round 13 — Browser Adapter + Product Search Surface

> Date: 2026-03-28
> Scope: Reduce god-file pressure in browser scraping and product-search agent paths
> Goal: Keep runtime behavior stable while extracting prompt/mapping logic away from orchestration shells

---

## 1. Summary

This round focused on two bounded seams that were large enough to block future change but isolated enough to refactor safely:

1. `browser_base.py`
2. `product_search_node.py`

Both were cut using a "compatibility shell" approach:

- existing public names stayed available
- implementation moved into dedicated helper modules
- focused regression suites stayed green

---

## 2. Browser Adapter Extraction

### Files

- Modified: `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\search_platforms\adapters\browser_base.py`
- New: `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\search_platforms\adapters\browser_product_mapping.py`

### What moved

The following pure mapping / extraction logic moved out of `browser_base.py`:

- JSON array extraction from LLM output
- free-text price extraction
- attachment image walking
- GraphQL product scanning
- marketplace/group-post product normalization
- intercepted/LLM item → `ProductSearchResult` mapping

### Design note

`browser_base.py` now acts more clearly as:

- Playwright runtime shell
- interception flow coordinator
- search adapter interface

while `browser_product_mapping.py` owns:

- data-shaping
- extraction heuristics
- backward-compatible normalization rules

### Compatibility

Backward-compatible names were preserved via re-export / staticmethod delegation so old tests importing from `browser_base.py` still work.

### Size impact

- `browser_base.py`: `1223 -> 712` lines

---

## 3. Product Search Surface Extraction

### Files

- Modified: `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\product_search_node.py`
- New: `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\product_search_surface.py`

### What moved

The following prompt/surface concerns moved out of `product_search_node.py`:

- `_SYSTEM_PROMPT`
- `_DEEP_SEARCH_PROMPT`
- `_iteration_label()`
- `_iteration_phase()`
- `_render_product_search_narration()`

### Design note

`product_search_node.py` now leans more toward:

- node orchestration
- tool loop execution
- state handling

while `product_search_surface.py` owns:

- prompt contract
- narration helpers
- iteration-phase surface logic

This is a strong architectural cut because it separates "how the node behaves" from "how the node frames and narrates its work".

### Size impact

- `product_search_node.py`: `951 -> 806` lines

---

## 4. Verification

### Compile

Passed:

- `browser_base.py`
- `browser_product_mapping.py`
- `product_search_node.py`
- `product_search_surface.py`

### Tests

Passed:

- `tests/unit/test_sprint156_network_interception.py` → `55 passed`
- `tests/unit/test_sprint152_browser_scraping.py`
- `tests/unit/test_sprint157b_deep_scanning.py` → combined browser batch `78 passed`
- `tests/unit/test_product_search_tools.py`
- `tests/unit/test_sprint150_deep_search.py`
- `tests/unit/test_sprint200_visual_search.py` → combined product-search batch `121 passed`

---

## 5. Sentrux

Latest gate:

- `Quality: 3581 -> 3593`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- `Distance from Main Sequence: 0.36`
- Verdict: `No degradation detected`

Important note:

- The round improved structure and kept the system green.
- It did **not** reduce the reported `god files` count below `7`, so more cuts are still needed.

---

## 6. Current Largest Files

Top remaining pressure points after this round:

1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py` — `2429`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings.py` — `1491`
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin.py` — `1314`
4. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py` — `1241`
5. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py` — `1210`
6. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation.py` — `1179`

---

## 7. Recommended Next Cuts

Highest ROI next:

1. `tutor_node.py`
2. `graph.py`
3. `prompt_loader.py`
4. `chat_orchestrator.py`

Reason:

- these files still sit on core orchestration / prompt / response paths
- reducing them will make the later thinking refactor much easier and safer
- they are closer to the eventual "public reasoning ownership" work than config/admin files

---

## 8. Verdict

This round was successful.

- large files were reduced materially
- behavior stayed stable
- compatibility seams were preserved
- architecture is cleaner than before

The project is not "done refactoring", but it is measurably easier to evolve than at the start of this session.
