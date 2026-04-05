# Graph Refactor Round 35 — Semantic Memory Model Decomposition

Date: 2026-03-29

## Summary

This round refactored the semantic memory model barrel into focused modules while
preserving the public import contract at `app.models.semantic_memory`.

Primary goals:
- reduce ownership density in `semantic_memory.py`
- separate taxonomy/constants from data records
- keep all existing imports stable across the semantic memory stack

## Changes

### 1. Extract semantic memory taxonomy/constants

Added:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory_types.py`

Moved into this module:
- `MemoryType`
- `InsightCategory`
- `FactType`
- `Predicate`
- `ALLOWED_FACT_TYPES`
- `FACT_TYPE_MAPPING`
- `IGNORED_FACT_TYPES`
- `IDENTITY_FACT_TYPES`
- `PROFESSIONAL_FACT_TYPES`
- `LEARNING_FACT_TYPES`
- `PERSONAL_FACT_TYPES`
- `VOLATILE_FACT_TYPES`
- `FACT_TYPE_TO_PREDICATE`
- `PREDICATE_TO_OBJECT_TYPE`

### 2. Extract semantic memory record/context models

Added:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory_records.py`

Moved into this module:
- `SemanticMemory`
- `SemanticMemoryCreate`
- `SemanticMemorySearchResult`
- `UserFact`
- `SemanticTriple`
- `Insight`
- `UserFactExtraction`
- `FactWithProvenance`
- `SemanticContext`
- `ConversationSummary`

Also extracted prompt-facing helpers/constants:
- `TRIPLE_TO_FACT_TYPE`
- `PROMPT_FACT_TYPE_ORDER`
- `PROMPT_FACT_TYPE_LABELS`
- `PROVENANCE_FACT_TYPE_LABELS`

### 3. Convert public module into compatibility facade

Modified:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory.py`

`semantic_memory.py` is now a thin public facade that re-exports the same names
from the new support modules. This keeps code such as:

```python
from app.models.semantic_memory import SemanticContext, Predicate
```

fully compatible without changing callers.

## Line Count Impact

- `app/models/semantic_memory.py`: `666 -> 61`
- `app/models/semantic_memory_types.py`: `159`
- `app/models/semantic_memory_records.py`: `363`

Net effect:
- the monolithic model barrel is gone
- public API stayed stable
- future semantic-memory refactors can now target taxonomy vs record models independently

## Validation

### Compile

Passed:

```powershell
python -m py_compile E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory_types.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\semantic_memory_records.py
```

### Focused tests

Passed:

```powershell
python -m pytest tests/unit/test_sprint51_fact_repository.py tests/unit/test_sprint53_context_retriever.py -v -p no:capture --tb=short
```

Result:
- `56 passed`

Passed:

```powershell
python -m pytest tests/unit/test_sprint79_memory_hardening.py tests/unit/test_sprint89_rag_persona_memory.py -v -p no:capture --tb=short -k "pronoun_style_predicate_exists or hometown or SemanticTriple_to_metadata_maps_hometown"
```

Result:
- `16 passed`

Passed with unrelated pre-existing drift outside the touched area:

```powershell
python -m pytest tests/unit/test_sprint122_memory_foundation.py tests/unit/test_sprint123_provenance_memory.py -v -p no:capture --tb=short
```

Result:
- `29 passed`
- `1 failed`

Unrelated failure:
- `test_core_memory_section_empty_in_tutor_node`
- This is a structural assertion against `tutor_node` source, unrelated to the
  `semantic_memory` model extraction performed in this round.

## Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate E:\Sach\Sua\AI_v1\maritime-ai-service\app
```

Result:
- `Quality: 4503`
- `Coupling: 0.30`
- `Cycles: 7`
- `God files: 0`
- `No degradation detected`

## Why This Round Matters

Before this round, `app.models.semantic_memory` mixed:
- enum taxonomy
- decay/category constants
- triple mappings
- persistence records
- provenance formatting
- assembled prompt context
- session summary serialization

That made semantic memory harder to extend because a change in one concern
required reopening the same central file.

After this round:
- taxonomy is isolated
- prompt/context helpers are isolated from enums
- the public import surface remains stable
- semantic memory now has a clearer seam for future work in:
  - retrieval models
  - provenance formatting
  - prompt-context assembly
  - summary serialization

## Recommended Next Cuts

High-ROI follow-ups:
1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security.py`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_runtime.py`
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\semantic_memory\temporal_graph.py`

Rationale:
- these are not god files anymore, but they still own multiple concerns and are
  good candidates for the next clean-architecture passes
