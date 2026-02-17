# Implementation Plan

## Insight Memory Engine v0.5 - CHỈ THỊ 23 CẢI TIẾN

- [x] 1. Database Schema Updates




  - [ ] 1.1 Add new columns to semantic_memories table
    - Add insight_category, sub_topic, last_accessed, evolution_notes columns

    - Create migration script
    - _Requirements: 4.1, 4.2, 3.3_
  - [x] 1.2 Create indexes for efficient queries




    - Index on (user_id, last_accessed DESC)
    - Index on (user_id, insight_category)
    - _Requirements: 3.3, 4.3_

- [x] 2. Insight Data Models




  - [ ] 2.1 Create InsightCategory enum and Insight model
    - Define 5 categories: learning_style, knowledge_gap, goal_evolution, habit, preference

    - Add evolution_notes field for tracking changes
    - _Requirements: 4.1_
  - [ ]* 2.2 Write property test for insight model validation
    - **Property 1: Insight Format Validation**
    - **Validates: Requirements 1.4, 5.1, 5.2**

- [x] 3. InsightExtractor Component




  - [ ] 3.1 Create InsightExtractor class with new extraction prompt
    - Implement behavioral-focused prompt (not atomic facts)

    - Include examples for learning_style, knowledge_gap, goal_evolution
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 3.2 Implement extract_insights method

    - Parse LLM response into Insight objects
    - Assign categories based on content
    - _Requirements: 1.1, 4.1_
  - [ ]* 3.3 Write unit tests for InsightExtractor
    - Test prompt building
    - Test response parsing
    - _Requirements: 1.4, 1.5_

- [x] 4. InsightValidator Component



  - [-] 4.1 Create InsightValidator class

    - Implement MIN_INSIGHT_LENGTH = 20 validation

    - Implement is_behavioral() check
    - _Requirements: 5.1, 5.2_
  - [x] 4.2 Implement duplicate detection

    - Use semantic similarity to find duplicates
    - Return existing insight for merge
    - _Requirements: 5.3_
  - [ ] 4.3 Implement contradiction detection
    - Detect conflicting insights on same topic
    - Return existing insight for evolution update
    - _Requirements: 5.4_
  - [ ]* 4.4 Write property test for duplicate merge
    - **Property 7: Duplicate Merge**
    - **Validates: Requirements 5.3**



  - [-]* 4.5 Write property test for contradiction evolution

    - **Property 8: Contradiction Evolution**

    - **Validates: Requirements 5.4**

- [x] 5. MemoryConsolidator Component

  - [ ] 5.1 Create MemoryConsolidator class
    - Define CONSOLIDATION_THRESHOLD = 40
    - Define TARGET_COUNT = 30

    - _Requirements: 2.1, 2.3_
  - [ ] 5.2 Implement consolidation prompt
    - Build prompt to merge duplicates, update changes, remove unimportant
    - Target 30 core items from 40+ inputs
    - _Requirements: 2.2, 2.4_
  - [ ] 5.3 Implement consolidate() method
    - Call LLM for rewrite
    - Parse response and update database
    - Handle failures with FIFO fallback
    - _Requirements: 2.2, 2.3, 2.5_
  - [ ]* 5.4 Write property test for consolidation trigger
    - **Property 2: Consolidation Trigger**
    - **Validates: Requirements 2.1, 2.3**

- [x] 6. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.


- [ ] 7. Enhanced SemanticMemoryEngine
  - [ ] 7.1 Add last_accessed tracking
    - Update timestamp on every retrieval
    - Add _update_last_accessed() method
    - _Requirements: 3.3_
  - [ ] 7.2 Implement hard limit enforcement
    - Block insertions when count >= 50
    - Trigger consolidation automatically
    - _Requirements: 3.1_
  - [ ] 7.3 Implement FIFO fallback with preservation
    - Delete oldest by last_accessed
    - Preserve memories accessed within 7 days
    - _Requirements: 3.2, 3.4_
  - [ ] 7.4 Implement category-prioritized retrieval
    - Prioritize knowledge_gap and learning_style
    - Keep only most recent per sub-topic
    - _Requirements: 4.3, 4.4_
  - [ ]* 7.5 Write property test for hard limit
    - **Property 3: Hard Limit Enforcement**
    - **Validates: Requirements 3.1**
  - [ ]* 7.6 Write property test for last_accessed update
    - **Property 4: Last Accessed Update**
    - **Validates: Requirements 3.3**
  - [ ]* 7.7 Write property test for recent memory preservation
    - **Property 5: Recent Memory Preservation**
    - **Validates: Requirements 3.4**
  - [ ]* 7.8 Write property test for category assignment
    - **Property 6: Category Assignment**
    - **Validates: Requirements 4.1, 4.2**

- [x] 8. Integration with ChatService

  - [x] 8.1 Update _store_semantic_interaction_async

    - Use InsightExtractor instead of old fact extraction
    - Pass conversation history for context
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 8.2 Update retrieve_context for category prioritization
    - Prioritize knowledge_gap and learning_style in context

    - Update last_accessed on retrieval
    - _Requirements: 4.3, 3.3_

- [x] 9. Checkpoint - Ensure all tests pass



  - Ensure all tests pass, ask the user if questions arise.






- [ ] 10. Documentation and Deployment
  - [ ] 10.1 Update SEMANTIC_MEMORY_V04_GUIDE.md to v0.5
    - Document new Insight Engine features
    - Add examples of behavioral insights
    - _Requirements: All_
  - [ ] 10.2 Update README.md
    - Add Insight Memory Engine section
    - Document new API behavior
    - _Requirements: All_

- [ ] 11. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
