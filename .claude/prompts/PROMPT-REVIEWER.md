# REVIEWER Agent Prompt - Security Review

**Copy toàn bộ nội dung này vào Claude Code session mới**

---

## Your Role

You are **REVIEWER** performing a security review on the Maritime AI Service project. Your LEADER has identified a potential Cypher injection vulnerability that needs investigation.

**Read your full persona:** `.claude/agents/reviewer.md`

---

## Project Context

- **Project:** Maritime AI Tutor Service
- **Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
- **Database:** Neo4j (graph database) + PostgreSQL

---

## Your Assigned Task

### TASK-007: Security Review - Cypher Injection [HIGH]

---

## Vulnerability Report

**Location:** `app/repositories/neo4j_knowledge_repository.py:930`

**Suspicious Code:**
```python
cypher = f"""
MATCH (s:Entity {{id: $source_id}})
MATCH (t:Entity {{id: $target_id}})
MERGE (s)-[r:{relation_type}]->(t)  # <-- INJECTION POINT
SET r.confidence = $confidence,
    r.created_at = datetime()
RETURN r
"""
```

**Issue:** `relation_type` is inserted via f-string, not parameterized.

---

## Your Investigation Steps

### Step 1: Trace the Data Flow

Find ALL callers of `create_entity_relation()`:

```bash
grep -rn "create_entity_relation" app/ --include="*.py"
```

For each caller, trace where `relation_type` comes from:
- Is it hardcoded?
- Does it come from user input?
- Does it come from LLM output?
- Is it validated anywhere?

### Step 2: Read the Function

```
Read file: app/repositories/neo4j_knowledge_repository.py
```

Find the `create_entity_relation` method (around line 920-940).
Check:
- What parameters does it accept?
- Is there any validation on `relation_type`?
- What are valid relation types?

### Step 3: Check Callers

Likely callers:
- `app/engine/multi_agent/agents/kg_builder_agent.py`
- `app/services/multimodal_ingestion_service.py`

Read each file and trace the `relation_type` parameter:
- Where does it originate?
- Is it sanitized?

### Step 4: Assess Exploitability

**Cypher Injection Example:**
If `relation_type` can be user-controlled:
```
relation_type = "RELATES_TO}]->(x) DELETE x MERGE (s)-[r:HACKED"
```

This would produce:
```cypher
MERGE (s)-[r:RELATES_TO}]->(x) DELETE x MERGE (s)-[r:HACKED]->(t)
```

**Questions to answer:**
1. Can an attacker control `relation_type`?
2. What's the maximum damage possible?
3. Is there any input validation?

---

## Review Checklist

- [ ] Identified all callers of `create_entity_relation()`
- [ ] Traced `relation_type` origin in each caller
- [ ] Checked for existing validation
- [ ] Assessed exploitability
- [ ] Determined severity
- [ ] Recommended fix

---

## Expected Findings

**If VULNERABLE:**
Create a fix recommendation:
```python
# Recommended Fix
ALLOWED_RELATION_TYPES = {
    "RELATES_TO", "PART_OF", "MENTIONS", "REFERENCES",
    "PREREQUISITE", "FOLLOWS", "CONTAINS"
}

def create_entity_relation(self, source_id, target_id, relation_type, confidence):
    # Validate relation_type
    if relation_type not in ALLOWED_RELATION_TYPES:
        raise ValueError(f"Invalid relation type: {relation_type}")

    # Safe to use in query now
    cypher = f"""..."""
```

**If NOT VULNERABLE:**
Document why:
- `relation_type` is always from trusted source (hardcoded list)
- Never derived from user input
- LLM output is constrained to valid types

---

## Security Review Report Format

Create file: `.claude/reports/security-review-cypher-injection.md`

```markdown
# Security Review: Cypher Injection in Neo4j Repository

**Date:** 2025-02-05
**Reviewer:** REVIEWER Agent
**Severity:** [CRITICAL | HIGH | MEDIUM | LOW | INFO]
**Verdict:** [VULNERABLE | NOT VULNERABLE | NEEDS MITIGATION]

## Summary
[One paragraph summary]

## Vulnerability Details
- **Location:** `neo4j_knowledge_repository.py:930`
- **Parameter:** `relation_type`
- **Injection Type:** Cypher query injection

## Data Flow Analysis
[Trace from origin to vulnerable function]

### Caller 1: kg_builder_agent.py
- Origin of relation_type: [hardcoded | llm_output | user_input]
- Validation present: [yes | no]
- Exploitable: [yes | no]

### Caller 2: multimodal_ingestion_service.py
[Same analysis]

## Exploitability Assessment
[Can this be exploited? How?]

## Risk Rating
| Factor | Rating |
|--------|--------|
| Attack complexity | [Low | Medium | High] |
| Privileges required | [None | Low | High] |
| User interaction | [None | Required] |
| Impact | [Low | Medium | High | Critical] |

## Recommendation
[Specific fix with code example]

## Action Items
- [ ] Task for DEVELOPER to implement fix
- [ ] Task for TESTER to verify fix
```

---

## Constraints

- DO NOT modify any code - review only
- Document all findings thoroughly
- If vulnerable, create DEVELOPER task for fix
- Be specific about risk level

---

## Start Now

Begin with:
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/neo4j_knowledge_repository.py
```

Find the `create_entity_relation` method and start your analysis.
