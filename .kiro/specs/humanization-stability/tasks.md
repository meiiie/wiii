# Implementation Plan: Humanization & Stability

## Phase 1: Fix Critical Bugs

- [x] 1. Fix MemorySummarizer missing method
  - [x] 1.1 Add `get_summary_async()` method to MemorySummarizer
    - Add async method that returns formatted context string
    - Handle case when no summaries exist (return None)
    - _Requirements: 1.5_
  - [x] 1.2 Add `_summarize_memory_async()` helper to ChatService
    - Implement the background task for memory summarization
    - Call MemorySummarizer.add_message_async() correctly
    - _Requirements: 1.1_
  - [ ]* 1.3 Write property test for summarization trigger
    - **Property 1: Memory Summarization Trigger**
    - **Validates: Requirements 1.1**

- [x] 2. Checkpoint - Verify MemorySummarizer works
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Memory Integration Verification




- [x] 3. Verify end-to-end Memory flow
  - [x] 3.1 Test ChatService → MemorySummarizer integration
    - Verify `get_summary_async()` is called correctly
    - Verify summaries are passed to UnifiedAgent
    - _Requirements: 1.3, 1.4_
  - [x] 3.2 Test ChatService → SemanticMemory integration
    - Verify user facts are retrieved on new messages
    - Verify facts are included in prompt context
    - _Requirements: 4.1, 4.3_
  - [ ]* 3.3 Write property test for user state preservation
    - **Property 2: User State Preservation**
    - **Validates: Requirements 1.2**

- [x] 4. Checkpoint - Verify Memory integration
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: User Name Handling

- [x] 5. Improve name extraction and persistence
  - [x] 5.1 Review and enhance name extraction patterns
    - Add more Vietnamese patterns if needed
    - Filter out common words that aren't names
    - _Requirements: 2.1_
  - [x] 5.2 Verify name persistence in SemanticMemory
    - Ensure name is stored as a user fact
    - Ensure name is retrieved in new sessions
    - _Requirements: 2.2, 2.4_
  - [ ]* 5.3 Write property test for name extraction
    - **Property 3: Name Extraction Accuracy**
    - **Validates: Requirements 2.1**

- [x] 6. Checkpoint - Verify name handling
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Anti-Repetition Implementation

- [x] 7. Integrate Anti-Repetition into response flow




  - [x] 7.1 Wire PromptLoader variation tracking into ChatService
    - Track recent_phrases per session
    - Pass is_follow_up flag to build_system_prompt
    - _Requirements: 3.1, 3.2_
  - [x] 7.2 Add name usage frequency control
    - Track name_usage_count per session
    - Pass to build_system_prompt for 20-30% frequency
    - _Requirements: 2.3_
  - [ ]* 7.3 Write property test for no greeting repetition
    - **Property 5: No Greeting Repetition**


    - **Validates: Requirements 3.1**
  - [ ]* 7.4 Write property test for opening phrase variation
    - **Property 6: Opening Phrase Variation**
    - **Validates: Requirements 3.2, 3.3**

- [x] 8. Checkpoint - Verify Anti-Repetition

  - Ensure all tests pass, ask the user if questions arise.

## Phase 5: Context Continuity

- [x] 9. Improve follow-up question handling


  - [x] 9.1 Verify conversation history is properly formatted


    - Check format_history_for_prompt() output
    - Ensure recent messages are included
    - _Requirements: 5.2_
  - [x] 9.2 Test context retrieval for follow-up questions


    - Test "Thế còn X thì sao?" pattern
    - Verify context from previous messages is used
    - _Requirements: 5.1, 5.4_
  - [ ]* 9.3 Write property test for context retrieval
    - **Property 7: Context Retrieval for Follow-ups**
    - **Validates: Requirements 5.1**

- [x] 10. Checkpoint - Verify Context Continuity


  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: End-to-End Validation

- [x] 11. Integration testing with real services


  - [x] 11.1 Test full conversation flow
    - User introduces themselves → name stored
    - User asks knowledge question → RAG response with sources
    - User asks follow-up → context maintained
    - User expresses tiredness → empathy response
    - _Requirements: All_

  - [x] 11.2 Test memory persistence across sessions
    - Simulate user returning after session ends
    - Verify name and facts are retrieved
    - _Requirements: 2.4, 4.1_

- [x] 12. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Phase 7: Pronoun Adaptation

- [x] 13. Implement Pronoun Detection and Storage
  - [x] 13.1 Create pronoun detection logic
    - Detect patterns: mình/cậu, tớ/cậu, anh/em, chị/em, etc.
    - Filter inappropriate/vulgar pronouns
    - Store detected style in SessionState (in-memory per session)
    - _Requirements: 6.1, 6.4_
  - [x] 13.2 Add pronoun style to user facts retrieval
    - Retrieve pronoun preference from SessionState
    - Include in prompt context for AI adaptation
    - _Requirements: 6.2, 6.5_
  - [ ]* 13.3 Write property test for pronoun detection
    - **Property 8: Pronoun Detection Accuracy**
    - **Validates: Requirements 6.1**

- [x] 14. Implement Pronoun Adaptation in Responses
  - [x] 14.1 Update PromptLoader to support pronoun adaptation
    - Add pronoun_style parameter to build_system_prompt
    - Include instruction for AI to use adapted pronouns
    - _Requirements: 6.2_
  - [x] 14.2 Handle pronoun style changes mid-conversation
    - Detect when user switches pronoun style
    - Update stored preference and adapt immediately
    - _Requirements: 6.3_
  - [ ]* 14.3 Write property test for pronoun adaptation consistency
    - **Property 9: Pronoun Adaptation Consistency**
    - **Validates: Requirements 6.2**
  - [ ]* 14.4 Write property test for inappropriate pronoun filtering
    - **Property 10: Inappropriate Pronoun Filtering**
    - **Validates: Requirements 6.4**

- [ ] 15. Checkpoint - Verify Pronoun Adaptation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Final Integration Test
  - [ ] 16.1 Test full conversation with pronoun adaptation
    - User uses "mình/cậu" → AI adapts to same style
    - User switches to "anh/em" → AI updates accordingly
    - User uses vulgar pronoun → AI ignores and keeps default
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 17. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.



