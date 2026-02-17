# 📋 BÁO CÁO TRẢ LỜI: CHIẾN LƯỢC QUẢN LÝ BỘ NHỚ DÀI HẠN

**Người gửi:** Team AI Backend (Kiro)
**Người nhận:** Project Manager / Architect
**Ngày:** 07/12/2025
**Chủ đề:** Trả lời câu hỏi về Semantic Memory v0.3

---

## 1. TRẢ LỜI CÁC CÂU HỎI VỀ HIỆN TRẠNG

### 1.1 Dạng lưu trữ: Raw Chunks hay Atomic Facts?

**Trả lời: ATOMIC FACTS (Facts cô đọng)**

Hệ thống hiện tại đã implement theo hướng **Atomic Facts**:

```python
# File: app/engine/semantic_memory.py - Line 230-260
def _build_fact_extraction_prompt(self, message: str) -> str:
    """Build prompt for fact extraction."""
    return f"""Analyze the following message and extract any personal facts about the user.
Return a JSON array of facts. Each fact should have:
- fact_type: one of [name, preference, goal, background, weak_area, strong_area, interest, learning_style]
- value: the actual fact
- confidence: confidence score from 0.0 to 1.0

Examples of facts to extract:
- User's name ("Tôi là Minh" -> name: "Minh")
- Learning goals ("Tôi muốn học về COLREGs" -> goal: "học về COLREGs")
- Professional background ("Tôi là thuyền trưởng" -> background: "thuyền trưởng")
"""
```

**Ví dụ thực tế:**
- Input: "Tôi là Minh, sinh viên năm 3 Hàng hải, muốn học COLREGs"
- Output (3 facts riêng biệt):
  - `{fact_type: "name", value: "Minh", confidence: 0.95}`
  - `{fact_type: "background", value: "sinh viên năm 3 Hàng hải", confidence: 0.9}`
  - `{fact_type: "goal", value: "học COLREGs", confidence: 0.85}`

---

### 1.2 Cơ chế ghi đè (Update/Deduplication)

**Trả lời: CÓ - Deduplication by fact_type**

Hệ thống đã implement **Deduplication theo fact_type**:

```python
# File: app/repositories/semantic_memory_repository.py - Line 230-270
def _deduplicate_facts(
    self,
    facts: List[SemanticMemorySearchResult]
) -> List[SemanticMemorySearchResult]:
    """
    Deduplicate facts by fact_type, keeping the most recent one.
    
    For each fact_type (name, job, preference, etc.), keeps only the
    fact with the highest created_at timestamp.
    """
    seen_types: dict[str, SemanticMemorySearchResult] = {}
    
    for fact in facts:
        fact_type = fact.metadata.get("fact_type", "unknown")
        
        if fact_type not in seen_types:
            seen_types[fact_type] = fact
        else:
            existing = seen_types[fact_type]
            if fact.created_at > existing.created_at:
                seen_types[fact_type] = fact  # Ghi đè bằng cái mới hơn
    
    return list(seen_types.values())
```

**Ví dụ thực tế:**
- Tháng trước: User nói "Tôi tên Nam" → Lưu `{fact_type: "name", value: "Nam"}`
- Tháng này: User nói "À nhầm, tôi tên Bắc" → Lưu `{fact_type: "name", value: "Bắc"}`
- Khi retrieve: Chỉ trả về `{fact_type: "name", value: "Bắc"}` (cái mới nhất)

**⚠️ LƯU Ý:** Hiện tại chỉ **deduplicate khi retrieve**, KHÔNG xóa cái cũ trong database. Cả "Nam" và "Bắc" đều tồn tại trong DB, nhưng chỉ "Bắc" được trả về.

---

### 1.3 Giới hạn (Limits)

**Trả lời: CÓ GIỚI HẠN - Nhưng chưa implement Eviction Policy**

Hiện tại có các giới hạn:

```python
# File: app/engine/semantic_memory.py
DEFAULT_USER_FACTS_LIMIT = 10  # Chỉ lấy 10 facts gần nhất khi retrieve

# File: app/repositories/semantic_memory_repository.py
def get_user_facts(self, user_id: str, limit: int = 20, deduplicate: bool = True):
    # Fetch limit * 3 để có đủ data cho deduplication
    limit = limit * 3 if deduplicate else limit
```

**⚠️ VẤN ĐỀ:** 
- Chưa có **Eviction Policy** (FIFO hoặc LRU)
- Database có thể phình to vô hạn
- Chỉ giới hạn khi **retrieve**, không giới hạn khi **store**

---

### 1.4 Truy xuất (Retrieval)

**Trả lời: TOP-K FACTS + SEMANTIC SEARCH**

```python
# File: app/engine/semantic_memory.py - Line 80-120
async def retrieve_context(
    self,
    user_id: str,
    query: str,
    search_limit: int = DEFAULT_SEARCH_LIMIT,  # 5
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,  # 0.7
    include_user_facts: bool = True,
    deduplicate_facts: bool = True
) -> SemanticContext:
    """
    Retrieve relevant context for a query.
    """
    # 1. Semantic search cho memories liên quan đến query
    relevant_memories = self._repository.search_similar(
        user_id=user_id,
        query_embedding=query_embedding,
        limit=search_limit,  # Top-5
        threshold=similarity_threshold,  # >= 0.7 similarity
        memory_types=[MemoryType.MESSAGE, MemoryType.SUMMARY]
    )
    
    # 2. Lấy user facts (deduplicated)
    user_facts = self._repository.get_user_facts(
        user_id=user_id,
        limit=self.DEFAULT_USER_FACTS_LIMIT,  # 10
        deduplicate=deduplicate_facts
    )
```

**Kết luận:** Không lấy tất cả, chỉ lấy:
- **Top-5 memories** liên quan đến query (similarity >= 0.7)
- **Top-10 user facts** (deduplicated by fact_type)

---

## 2. ĐÁNH GIÁ SO VỚI TIÊU CHUẨN NGÀNH

| Tiêu chí | Qwen/OpenAI | Maritime AI (v0.3) | Đánh giá |
|----------|-------------|-------------------|----------|
| **Dạng lưu trữ** | Discrete Items | Atomic Facts ✅ | **PASS** |
| **Deduplication** | Có (by type) | Có (khi retrieve) ⚠️ | **PARTIAL** |
| **Giới hạn số lượng** | 50-100 items | Không giới hạn ❌ | **FAIL** |
| **Eviction Policy** | FIFO/LRU | Chưa có ❌ | **FAIL** |
| **User Management UI** | Có (xem/xóa) | Chưa có ❌ | **FAIL** |
| **Token Budget** | Cố định | Không cố định ⚠️ | **PARTIAL** |

---

## 3. ĐỀ XUẤT CẢI TIẾN (ROADMAP)

### Phase 1: Memory Capping (Ưu tiên cao)

```python
# Đề xuất thêm vào semantic_memory.py
MAX_USER_FACTS = 50  # Giới hạn 50 facts per user

async def _enforce_memory_cap(self, user_id: str):
    """Xóa facts cũ nhất khi vượt quá giới hạn."""
    count = self._repository.count_user_memories(user_id, MemoryType.USER_FACT)
    
    if count > MAX_USER_FACTS:
        # Xóa (count - MAX_USER_FACTS) facts cũ nhất
        self._repository.delete_oldest_facts(
            user_id=user_id,
            count=count - MAX_USER_FACTS
        )
```

### Phase 2: True Deduplication (Xóa cái cũ khi lưu cái mới)

```python
async def store_user_fact(self, user_id: str, fact_content: str, fact_type: str, ...):
    # 1. Tìm fact cùng type đã tồn tại
    existing = self._repository.find_fact_by_type(user_id, fact_type)
    
    # 2. Nếu có, UPDATE thay vì INSERT
    if existing:
        self._repository.update_fact(existing.id, fact_content)
    else:
        self._repository.save_memory(...)
```

### Phase 3: Memory Management API

```python
# Thêm endpoints mới
GET  /api/v1/memories/{user_id}           # Xem danh sách memories
DELETE /api/v1/memories/{user_id}/{id}    # Xóa 1 memory cụ thể
PUT  /api/v1/memories/{user_id}/{id}      # Sửa 1 memory
```

---

## 4. KẾT LUẬN

| Câu hỏi | Trả lời |
|---------|---------|
| Đang lưu Raw hay Facts? | **Facts cô đọng** ✅ |
| Có ghi đè/hợp nhất không? | **Có (khi retrieve)** ⚠️ |
| Có giới hạn không? | **Chưa có eviction** ❌ |
| Lấy tất cả hay Top-K? | **Top-K** ✅ |

**Đánh giá tổng thể:** Hệ thống đã đi đúng hướng (Atomic Facts + Deduplication), nhưng cần bổ sung:
1. **Memory Capping** (50 items limit)
2. **True Deduplication** (xóa cái cũ khi lưu cái mới)
3. **Memory Management API** (cho Frontend)

---

*Báo cáo bởi Team AI Backend (Kiro) - 07/12/2025*
