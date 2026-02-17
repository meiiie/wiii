# READY TO EXECUTE - REVIEWER TASK-007

**Copy toàn bộ prompt này vào Claude Code session mới và thực thi**

---

## Context

Bạn là **REVIEWER** agent. Nhiệm vụ của bạn là security review cho potential Cypher injection vulnerability.

**Project:** Maritime AI Tutor Service
**Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`

---

## TASK-007: Security Review - Cypher Injection

**Priority:** HIGH
**Goal:** Xác định và đánh giá rủi ro Cypher injection

---

## Vulnerability Location

**File:** `app/repositories/neo4j_knowledge_repository.py`
**Line:** ~930

**Suspicious Code:**
```python
cypher = f"""
MATCH (s:Entity {{id: $source_id}})
MATCH (t:Entity {{id: $target_id}})
MERGE (s)-[r:{relation_type}]->(t)  # <-- relation_type trong f-string!
SET r.confidence = $confidence,
    r.created_at = datetime()
RETURN r
"""
```

**Issue:** `relation_type` được chèn trực tiếp vào query string, không qua parameterization.

---

## STEP 1: Read the Vulnerable Code

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/neo4j_knowledge_repository.py
```

Tìm method `create_entity_relation` (khoảng line 920-950).

**Ghi lại:**
- Exact line numbers
- Full function signature
- Có validation nào không?

---

## STEP 2: Find All Callers

```bash
grep -rn "create_entity_relation" app/ --include="*.py"
```

**Với mỗi caller, cần xác định:**
1. File nào call?
2. `relation_type` đến từ đâu?
3. Có validation không?

---

## STEP 3: Trace relation_type Origin

**Likely callers:**
- `app/engine/multi_agent/agents/kg_builder_agent.py`
- `app/services/multimodal_ingestion_service.py`

Đọc từng file và trace nguồn gốc của `relation_type`:

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/kg_builder_agent.py
```

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/services/multimodal_ingestion_service.py
```

**Questions to answer:**
1. `relation_type` có đến từ user input không?
2. `relation_type` có đến từ LLM output không?
3. Có whitelist của valid relation types không?

---

## STEP 4: Exploitability Assessment

**Cypher Injection Example:**

Nếu attacker control được `relation_type`:
```
relation_type = "RELATES_TO}]->(x) DETACH DELETE x MERGE (s)-[r:HACKED"
```

Sẽ produce:
```cypher
MERGE (s)-[r:RELATES_TO}]->(x) DETACH DELETE x MERGE (s)-[r:HACKED]->(t)
```

**Impact:** Có thể delete toàn bộ nodes!

---

## STEP 5: Risk Assessment

Điền bảng sau:

| Factor | Rating | Notes |
|--------|--------|-------|
| Attack Vector | [Network/Adjacent/Local] | |
| Attack Complexity | [Low/High] | |
| Privileges Required | [None/Low/High] | |
| User Interaction | [None/Required] | |
| Scope | [Unchanged/Changed] | |
| Confidentiality Impact | [None/Low/High] | |
| Integrity Impact | [None/Low/High] | |
| Availability Impact | [None/Low/High] | |

---

## STEP 6: Recommendation

**Nếu VULNERABLE:**

```python
# Recommended Fix

# Define allowed relation types
ALLOWED_RELATION_TYPES = frozenset({
    "RELATES_TO",
    "PART_OF",
    "MENTIONS",
    "REFERENCES",
    "PREREQUISITE",
    "FOLLOWS",
    "CONTAINS",
    "DEFINES",
    "EXAMPLE_OF",
    "CONTRADICTS",
    "SUPPORTS",
})

def create_entity_relation(
    self,
    source_id: str,
    target_id: str,
    relation_type: str,
    confidence: float = 1.0
) -> Optional[Dict]:
    """Create relation between entities with validated relation type."""

    # SECURITY: Validate relation_type against whitelist
    if relation_type not in ALLOWED_RELATION_TYPES:
        logger.warning(f"Invalid relation type rejected: {relation_type}")
        raise ValueError(f"Invalid relation type: {relation_type}. "
                        f"Must be one of: {ALLOWED_RELATION_TYPES}")

    # Now safe to use in query
    cypher = f"""
    MATCH (s:Entity {{id: $source_id}})
    MATCH (t:Entity {{id: $target_id}})
    MERGE (s)-[r:{relation_type}]->(t)
    ...
    """
```

**Nếu NOT VULNERABLE:**

Document tại sao:
- relation_type luôn từ hardcoded list
- Không bao giờ từ user input
- LLM output được constrain

---

## Security Report Format

Tạo file: `.claude/reports/security-review-cypher-2025-02-05.md`

```markdown
# Security Review: Cypher Injection

**Date:** 2025-02-05
**Reviewer:** REVIEWER Agent
**Target:** neo4j_knowledge_repository.py:create_entity_relation()

## Executive Summary

**Severity:** [CRITICAL / HIGH / MEDIUM / LOW / INFO]
**Verdict:** [VULNERABLE / NOT VULNERABLE / NEEDS MITIGATION]
**CVSS Score:** [X.X] (if applicable)

## Vulnerability Details

### Location
- File: `app/repositories/neo4j_knowledge_repository.py`
- Method: `create_entity_relation()`
- Line: [exact line]
- Parameter: `relation_type`

### Description
[Describe the vulnerability]

## Data Flow Analysis

### Caller 1: kg_builder_agent.py
- **Source of relation_type:** [hardcoded / llm_output / user_input]
- **Validation present:** [yes / no]
- **Exploitable:** [yes / no]

### Caller 2: multimodal_ingestion_service.py
- **Source of relation_type:** [hardcoded / llm_output / user_input]
- **Validation present:** [yes / no]
- **Exploitable:** [yes / no]

## Exploitation Scenario

[If vulnerable, describe how it could be exploited]

## Risk Assessment

| Factor | Value |
|--------|-------|
| Attack Complexity | |
| Privileges Required | |
| Impact | |

## Recommendation

[Specific fix with code]

## Action Items

- [ ] Create DEVELOPER task for fix (if needed)
- [ ] Add to security test suite
- [ ] Review similar patterns in codebase
```

---

## Constraints

- CHỈ review, KHÔNG modify code
- Document tất cả findings
- Nếu vulnerable, create task cho DEVELOPER fix
- Be specific về risk level

---

## START NOW

Bắt đầu với:
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/neo4j_knowledge_repository.py
```

Tìm method `create_entity_relation`.
