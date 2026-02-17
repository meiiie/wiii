# Implementation Plan

## Phase 1: Memory Capping & True Deduplication

- [x] 1. Update FactType enum and validation




  - [ ] 1.1 Update FactType enum in semantic_memory.py models
    - Add new types: role, level


    - Keep backward compatibility mapping for deprecated types
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ] 1.2 Implement _validate_fact_type() method in SemanticMemoryEngine
    - Case-insensitive comparison
    - Return normalized type or None if invalid
    - Map deprecated types to new types




    - _Requirements: 4.1, 4.2, 4.3_
  - [x]* 1.3 Write property test for fact type validation

    - **Property 5: Fact Type Validation**
    - **Validates: Requirements 4.1, 4.2, 4.3**


- [ ] 2. Implement Repository methods for upsert and capping
  - [ ] 2.1 Implement find_fact_by_type() in SemanticMemoryRepository
    - Query by user_id and fact_type from metadata

    - Return existing fact or None
    - _Requirements: 2.1, 2.2_
  - [ ] 2.2 Implement update_fact() in SemanticMemoryRepository
    - Update content, embedding, metadata, updated_at
    - Preserve original ID and created_at
    - _Requirements: 2.2, 2.4_




  - [ ] 2.3 Implement delete_oldest_facts() in SemanticMemoryRepository
    - Delete N oldest USER_FACT entries by created_at
    - Return count of deleted facts
    - _Requirements: 1.2_
  - [ ] 2.4 Implement get_all_user_facts() in SemanticMemoryRepository
    - Return all USER_FACT entries for user
    - Order by created_at DESC
    - _Requirements: 3.1_
  - [ ]* 2.5 Write property test for FIFO eviction
    - **Property 6: FIFO Eviction Order**




    - **Validates: Requirements 1.2**


- [ ] 3. Implement Upsert logic in SemanticMemoryEngine
  - [ ] 3.1 Implement store_user_fact_upsert() method
    - Validate fact_type

    - Check if fact exists using find_fact_by_type()
    - If exists: call update_fact()
    - If not: call save_memory()
    - _Requirements: 2.1, 2.2, 2.3, 2.4_


  - [ ]* 3.2 Write property test for upsert uniqueness
    - **Property 2: Upsert Uniqueness**
    - **Validates: Requirements 2.1, 2.2, 2.3**




  - [x]* 3.3 Write property test for timestamp update

    - **Property 3: Timestamp Update on Upsert**
    - **Validates: Requirements 2.4**

- [x] 4. Implement Memory Capping

  - [ ] 4.1 Add MAX_USER_FACTS constant (50) to SemanticMemoryEngine
    - _Requirements: 1.1_
  - [x] 4.2 Implement _enforce_memory_cap() method


    - Count USER_FACT entries for user
    - If count > MAX_USER_FACTS: delete oldest
    - Log deletions for audit




    - _Requirements: 1.1, 1.2, 1.3, 1.4_


  - [x] 4.3 Integrate memory cap into store_user_fact_upsert()


    - Call _enforce_memory_cap() after storing
    - _Requirements: 1.1, 1.2_
  - [x]* 4.4 Write property test for memory capping invariant





    - **Property 1: Memory Capping Invariant**
    - **Validates: Requirements 1.1, 1.2, 1.3**



- [ ] 5. Checkpoint - Make sure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Memory Management API

- [ ] 6. Create Memory API endpoint
  - [ ] 6.1 Create app/api/v1/memories.py router
    - Define MemoryItem and MemoryListResponse models
    - _Requirements: 3.1, 3.2_
  - [ ] 6.2 Implement GET /api/v1/memories/{user_id} endpoint
    - Call get_all_user_facts() from repository
    - Transform to MemoryListResponse format
    - Handle empty case (return empty array)
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ] 6.3 Add authentication to memories endpoint
    - Use existing verify_api_key dependency
    - Return 401 for unauthorized requests
    - _Requirements: 3.4_
  - [ ] 6.4 Register memories router in main.py
    - _Requirements: 3.1_
  - [ ]* 6.5 Write property test for API response completeness
    - **Property 4: API Response Completeness**
    - **Validates: Requirements 3.1, 3.2**

- [ ] 7. Update existing fact extraction to use new upsert
  - [ ] 7.1 Update _extract_and_store_facts() to use store_user_fact_upsert()
    - Replace save_memory() calls with store_user_fact_upsert()
    - _Requirements: 2.1_
  - [ ] 7.2 Update tool_save_user_info to use store_user_fact_upsert()
    - Ensure tools also use upsert logic
    - _Requirements: 2.1_

- [ ] 8. Final Checkpoint - Make sure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Documentation & Cleanup

- [ ] 9. Update documentation
  - [ ] 9.1 Update README.md with Semantic Memory v0.4 changes
    - Document Memory Capping (50 facts limit)
    - Document Upsert behavior
    - Document new API endpoint
    - _Requirements: All_
  - [ ] 9.2 Update SEMANTIC_MEMORY_V03_GUIDE.md to v0.4
    - Rename to SEMANTIC_MEMORY_V04_GUIDE.md
    - Add new features documentation
    - _Requirements: All_
