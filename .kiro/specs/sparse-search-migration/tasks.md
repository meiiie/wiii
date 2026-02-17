# Implementation Plan

## Sparse Search Migration to PostgreSQL

- [x] 1. Database Schema Migration
  - [x] 1.1 Create Alembic migration for search_vector column




    - Add `search_vector` column of type `tsvector` to `knowledge_embeddings` table
    - Create GIN index `idx_knowledge_search_vector` on `search_vector`
    - Create trigger function `update_search_vector()` to auto-generate tsvector
    - Create trigger `trg_update_search_vector` on INSERT/UPDATE
    - Populate existing rows with `to_tsvector('simple', content)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 1.2 Write property test for tsvector auto-generation
    - **Property 4: Tsvector auto-generation on insert**
    - **Validates: Requirements 2.4**

- [x] 2. Implement PostgreSQL-based SparseSearchRepository

  - [x] 2.1 Create new SparseSearchRepository class using PostgreSQL
    - Use shared database connection pool from `app.core.database`
    - Implement `_build_tsquery()` method for query building
    - Implement `_extract_numbers()` for number boosting
    - Implement `search()` method using `ts_rank` and `@@` operator
    - Implement `is_available()` to check PostgreSQL connectivity
    - Maintain same interface as Neo4j version (SparseSearchResult dataclass)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 2.2 Write property test for search result structure
    - **Property 1: Search results contain required fields**
    - **Validates: Requirements 3.4, 4.3, 6.2**

  - [ ]* 2.3 Write property test for result ordering
    - **Property 2: Results are ranked by score descending**
    - **Validates: Requirements 3.1**


- [x] 3. Implement Number Boosting and Vietnamese Support
  - [x] 3.1 Implement number boosting logic
    - Extract numbers from query using regex
    - Boost results containing matching numbers in content
    - Re-sort results after boosting
    - _Requirements: 3.3_

  - [x]* 3.2 Write property test for number boosting

    - **Property 3: Number boosting increases score**
    - **Validates: Requirements 3.3**

  - [x] 3.3 Implement Vietnamese text handling
    - Use 'simple' configuration for tsvector (language-agnostic)
    - Handle Vietnamese stop words in query building
    - _Requirements: 3.2_


  - [ ]* 3.4 Write property test for Vietnamese search
    - **Property 6: Vietnamese text search returns results**
    - **Validates: Requirements 3.2**

- [x] 4. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.


- [x] 5. Update HybridSearchService Integration


  - [x] 5.1 Update HybridSearchService to use PostgreSQL SparseSearchRepository
    - Replace Neo4j SparseSearchRepository import with PostgreSQL version
    - Verify RRF reranking works with new sparse results
    - _Requirements: 5.1_

  - [x] 5.2 Implement graceful fallback on sparse search failure
    - Catch exceptions from sparse search
    - Return dense-only results when sparse fails
    - Log warning but don't fail the request
    - _Requirements: 1.3, 1.4_



  - [ ]* 5.3 Write property test for graceful fallback
    - **Property 5: Graceful fallback on sparse search failure**
    - **Validates: Requirements 1.3, 1.4, 5.4**

- [x] 6. Update Health Checks and Remove Neo4j RAG Dependency


  - [x] 6.1 Update health check to report PostgreSQL sparse search status
    - Modify `check_knowledge_graph_health()` or add new sparse search health
    - Report based on PostgreSQL connectivity, not Neo4j
    - _Requirements: 5.2_

  - [x] 6.2 Make Neo4j optional for RAG functionality
    - RAG should work without Neo4j connection
    - Keep Neo4j health check for future Learning Graph
    - Update startup to not fail if Neo4j unavailable
    - _Requirements: 5.3, 5.4_


- [x] 7. Backward Compatibility and Cleanup
  - [x] 7.1 Verify backward compatibility
    - Ensure SparseSearchRepository exposes same interface
    - Verify HybridSearchService works without code changes
    - Run existing integration tests

    - _Requirements: 6.1, 6.3_

  - [ ]* 7.2 Run existing hybrid search tests
    - Verify all existing tests pass
    - _Requirements: 6.4_

  - [x] 7.3 Update documentation
    - Update README to reflect PostgreSQL-only RAG
    - Document Neo4j is reserved for future Learning Graph
    - _Requirements: 5.3_

- [x] 8. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
