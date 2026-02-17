# Implementation Plan

## Phase 1: Enhanced Prompt System

- [ ] 1. Cải thiện Persona YAML và PromptLoader


  - [x] 1.1 Thêm VariationPool vào tutor.yaml và assistant.yaml



    - Thêm section `variation_phrases` với các opening phrases, transitions
    - Thêm `empathy_patterns` để detect user frustration
    - _Requirements: 1.1, 1.2, 7.1_
  - [x] 1.2 Implement EnhancedPromptLoader class





    - Extend PromptLoader với `detect_empathy_needed()` method
    - Implement `get_variation_phrases()` method
    - Add `recent_phrases` tracking parameter
    - _Requirements: 1.2, 7.1, 7.3_
  - [x]* 1.3 Write property test for empathy detection


    - **Property 1: Empathy Detection Accuracy**
    - **Validates: Requirements 1.2**

  - [ ]* 1.4 Write property test for opening phrase variation
    - **Property 17: Opening Phrase Variation**
    - **Validates: Requirements 7.1**

- [ ] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: New Tools Implementation

- [ ] 3. Implement tool_start_quiz
  - [ ] 3.1 Create tool function with Tutor Agent integration
    - Connect to existing TutorAgent class
    - Handle session creation and phase management
    - Return formatted quiz question
    - _Requirements: 3.1, 3.2_
  - [ ]* 3.2 Write property test for quiz tool invocation
    - **Property 7: Quiz Tool Invocation**
    - **Validates: Requirements 3.1**
  - [ ]* 3.3 Write property test for phase transitions
    - **Property 8: Tutor Phase Transitions**
    - **Validates: Requirements 3.2**

- [ ] 4. Implement tool_suggest_topics
  - [ ] 4.1 Create tool function for topic suggestions
    - Query user's learning history from Semantic Memory
    - Generate personalized topic recommendations
    - Include reasoning for each suggestion
    - _Requirements: 5.2_

- [ ] 5. Implement tool_compare_rules
  - [ ] 5.1 Create tool function for rule comparison
    - Parse input rules (comma-separated)
    - Query Knowledge Base for each rule
    - Format side-by-side comparison table
    - _Requirements: 5.3_

- [ ] 6. Implement tool_explain_term
  - [ ] 6.1 Create tool function for term explanation
    - Query Knowledge Base for term definition
    - Include Vietnamese translation
    - Add practical maritime examples
    - _Requirements: 5.4, 2.4_
  - [ ]* 6.2 Write property test for term translation
    - **Property 6: Term Translation Consistency**
    - **Validates: Requirements 2.4**

- [ ] 7. Register new tools in Unified Agent
  - [ ] 7.1 Update TOOLS list in unified_agent.py
    - Add all 4 new tools to TOOLS list
    - Update `_init_llm_with_tools()` to bind new tools
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ]* 7.2 Write property test for tool registration
    - **Property 14: Tool Registration**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Enhanced Tool Descriptions

- [ ] 9. Update existing tool descriptions
  - [ ] 9.1 Enhance tool_maritime_search description
    - Add detailed WHEN TO CALL / WHEN NOT TO CALL sections
    - Add priority level and keyword examples
    - _Requirements: 6.1, 6.3_
  - [ ] 9.2 Enhance tool_save_user_info description
    - Specify exact patterns for fact extraction
    - Add examples of triggering phrases
    - _Requirements: 6.2_
  - [ ]* 9.3 Write property test for greeting no-search rule
    - **Property 16: Greeting No-Search Rule**
    - **Validates: Requirements 6.4**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Response Processor

- [ ] 11. Implement ResponseLengthController
  - [ ] 11.1 Create query complexity estimator
    - Count words, detect complexity keywords ("chi tiết", "giải thích")
    - Return "simple" or "complex" classification
    - _Requirements: 2.1, 2.2_
  - [ ] 11.2 Implement length adjustment logic
    - Truncate long responses for simple queries
    - Expand short responses for complex queries
    - _Requirements: 2.1, 2.2_
  - [ ]* 11.3 Write property test for response length
    - **Property 4: Response Length Appropriateness**
    - **Validates: Requirements 2.1, 2.2**

- [ ] 12. Implement VariationChecker
  - [ ] 12.1 Create VariationTracker class
    - Track recent opening phrases per session
    - Track name usage count
    - Implement `should_use_name()` method
    - _Requirements: 1.3, 7.2_
  - [ ] 12.2 Implement variation checking logic
    - Detect repetitive patterns
    - Suggest alternative phrases from VariationPool
    - _Requirements: 7.1, 7.3_
  - [ ]* 12.3 Write property test for name usage frequency
    - **Property 2: Name Usage Frequency**
    - **Validates: Requirements 1.3, 7.2**
  - [ ]* 12.4 Write property test for no greeting repetition
    - **Property 3: No Greeting Repetition in Follow-ups**
    - **Validates: Requirements 1.4**

- [ ] 13. Implement SuggestedQuestionsGenerator
  - [ ] 13.1 Create suggestion generation logic
    - Extract topics from current response
    - Generate 2-3 follow-up questions
    - Consider user's weak areas if available
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 13.2 Integrate with API response
    - Add suggested_questions to InternalChatResponse
    - Ensure API returns suggestions in response
    - _Requirements: 8.5_
  - [ ]* 13.3 Write property test for suggested questions
    - **Property 18: Suggested Questions Generation**
    - **Validates: Requirements 8.1, 8.5**

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 5: Memory Utilization Improvements

- [ ] 15. Enhance Semantic Memory retrieval
  - [ ] 15.1 Improve user facts retrieval for returning users
    - Prioritize recent and high-importance facts
    - Include facts in context for all responses
    - _Requirements: 4.1, 4.4_
  - [ ]* 15.2 Write property test for user facts retrieval
    - **Property 11: User Facts Retrieval**
    - **Validates: Requirements 4.1**

- [ ] 16. Improve fact extraction
  - [ ] 16.1 Enhance fact extraction patterns
    - Add more Vietnamese patterns for name, profession, school
    - Improve confidence scoring
    - _Requirements: 4.2_
  - [ ]* 16.2 Write property test for fact extraction
    - **Property 12: Fact Extraction from Personal Info**
    - **Validates: Requirements 4.2**

- [ ] 17. Verify summarization trigger
  - [ ] 17.1 Ensure summarization works at threshold
    - Verify token counting accuracy
    - Test summarization trigger logic
    - _Requirements: 4.3_
  - [ ]* 17.2 Write property test for summarization trigger
    - **Property 13: Summarization Trigger**
    - **Validates: Requirements 4.3**

- [ ] 18. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: Quiz/Assessment Integration

- [ ] 19. Integrate Tutor Agent with Unified Agent
  - [ ] 19.1 Wire TutorAgent into tool_start_quiz
    - Create quiz session management
    - Handle phase transitions
    - _Requirements: 3.1, 3.2_
  - [ ] 19.2 Implement quiz answer evaluation
    - Connect to TutorAgent.process_response()
    - Handle correct/incorrect answers
    - Provide hints for wrong answers
    - _Requirements: 3.3_
  - [ ]* 19.3 Write property test for quiz evaluation
    - **Property 9: Quiz Evaluation Correctness**
    - **Validates: Requirements 3.3**

- [ ] 20. Implement mastery tracking
  - [ ] 20.1 Add mastery achievement logic
    - Check score ≥ 80% AND questions ≥ 3
    - Set mastery_achieved flag
    - Record achievement in Learning Profile
    - _Requirements: 3.4_
  - [ ] 20.2 Implement struggling user support
    - Detect low scores (< 50% after 3 questions)
    - Offer additional explanations
    - Suggest topic review
    - _Requirements: 3.5_
  - [ ]* 20.3 Write property test for mastery achievement
    - **Property 10: Mastery Achievement**
    - **Validates: Requirements 3.4**

- [ ] 21. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 7: Citation and Logging

- [ ] 22. Ensure citation inclusion
  - [ ] 22.1 Verify RAG responses include citations
    - Check tool_maritime_search returns sources
    - Format citations in response
    - _Requirements: 2.3_
  - [ ]* 22.2 Write property test for citation inclusion
    - **Property 5: Citation Inclusion**
    - **Validates: Requirements 2.3**

- [ ] 23. Implement tool usage logging
  - [ ] 23.1 Add logging to all tool invocations
    - Log tool name, arguments, result summary
    - Include timestamp and session_id
    - _Requirements: 5.5_
  - [ ]* 23.2 Write property test for tool logging
    - **Property 15: Tool Usage Logging**
    - **Validates: Requirements 5.5**

- [ ] 24. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 8: Integration and Wiring

- [ ] 25. Wire all components into ChatService
  - [ ] 25.1 Integrate EnhancedPromptLoader
    - Replace existing PromptLoader usage
    - Pass variation tracking data
    - _Requirements: 1.1, 1.2, 7.1_
  - [ ] 25.2 Integrate ResponseProcessor
    - Add post-processing step after agent response
    - Include suggested questions in API response
    - _Requirements: 2.1, 2.2, 8.1, 8.5_
  - [ ] 25.3 Update API response schema
    - Ensure suggested_questions field is populated
    - Include variation metadata for debugging
    - _Requirements: 8.5_

- [ ] 26. Final Integration Testing
  - [ ] 26.1 End-to-end test: Student conversation flow
    - Test greeting → knowledge question → follow-up → quiz
    - Verify persona, variation, and memory work together
    - _Requirements: All_
  - [ ] 26.2 End-to-end test: Teacher/Admin conversation flow
    - Test professional tone and honorifics
    - Verify assistant.yaml persona is applied
    - _Requirements: 1.5_

- [ ] 27. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
