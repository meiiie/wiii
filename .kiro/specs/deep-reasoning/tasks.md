# Implementation Plan: Deep Reasoning & Smart Context Engine (CHỈ THỊ 21)

- [x] 1. Update Context Window Size


  - [x] 1.1 Increase chat history limit to 50 messages


    - Update `get_recent_messages()` default limit from 10 to 50
    - Update ChatService to use new limit
    - _Requirements: 2.1, 5.3_
  - [x]* 1.2 Write property test for context window size


    - **Property 3: Context Window Size Limit**


    - **Validates: Requirements 2.1**

- [ ] 2. Implement ConversationAnalyzer
  - [ ] 2.1 Create ConversationAnalyzer class
    - Create `app/engine/conversation_analyzer.py`
    - Implement `analyze()` method for conversation context
    - Implement `detect_incomplete_explanation()` method
    - Implement `extract_topic()` method for maritime topics
    - Implement `is_continuation_request()` method
    - _Requirements: 3.1, 3.4, 3.5_
  - [ ]* 2.2 Write property test for incomplete topic detection
    - **Property 5: Incomplete Topic Detection**
    - **Validates: Requirements 3.1, 3.4, 3.5**
  - [x]* 2.3 Write unit tests for ConversationAnalyzer

    - Test detect_incomplete_explanation with various inputs


    - Test extract_topic with maritime content
    - Test is_continuation_request with Vietnamese phrases
    - _Requirements: 3.1, 3.4, 3.5_


- [x] 3. Update Prompts for Deep Reasoning

  - [ ] 3.1 Update assistant.yaml with Deep Reasoning instructions
    - Add `<thinking>` section instructions
    - Add self-correction examples
    - Add context checking instructions

    - Add strategy planning examples
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_


  - [ ] 3.2 Add few-shot examples for Deep Reasoning
    - Add example with maritime context (Rule 15, tàu cá)
    - Add example with proactive continuation

    - _Requirements: 1.5, 3.2, 3.3_

- [ ] 4. Checkpoint - Verify prompts and analyzer
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Integrate Deep Reasoning into ChatService
  - [ ] 5.1 Add ConversationAnalyzer to ChatService
    - Initialize ConversationAnalyzer in ChatService
    - Call analyze() before processing message


    - Pass context analysis to UnifiedAgent

    - _Requirements: 3.1, 3.4_
  - [ ] 5.2 Update UnifiedAgent for Deep Reasoning
    - Add deep_reasoning_config parameter

    - Inject proactive context into prompt


    - Handle thinking tags in response
    - _Requirements: 1.1, 3.2_
  - [ ]* 5.3 Write property test for thinking tags presence
    - **Property 1: Thinking Tags Presence**
    - **Validates: Requirements 1.1, 1.5, 4.1**

  - [ ]* 5.4 Write property test for response format order
    - **Property 2: Response Format Order**
    - **Validates: Requirements 4.2, 4.3**

- [ ] 6. Implement Proactive Continuation
  - [ ] 6.1 Add proactive continuation logic
    - Detect when should_offer_continuation is true
    - Inject continuation offer into response
    - _Requirements: 3.2, 3.3_
  - [ ]* 6.2 Write property test for proactive continuation
    - **Property 6: Proactive Continuation Offer**
    - **Validates: Requirements 3.2**

- [ ] 7. Implement Deep Reasoning Toggle
  - [ ] 7.1 Add configuration for deep reasoning
    - Create DeepReasoningConfig dataclass
    - Add enable/disable toggle
    - _Requirements: 4.4_
  - [x]* 7.2 Write property test for disabled mode

    - **Property 7: Deep Reasoning Disabled Mode**


    - **Validates: Requirements 4.4**


- [ ] 8. Checkpoint - Verify Deep Reasoning integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Response Parser (Frontend Support)
  - [ ] 9.1 Create ThinkingTagParser utility
    - Parse `<thinking>` section from response
    - Extract thinking content and final answer


    - Handle malformed responses gracefully
    - _Requirements: 6.1, 6.5_
  - [ ]* 9.2 Write property test for thinking tags well-formed
    - **Property 8: Thinking Tags Well-Formed**
    - **Validates: Requirements 4.5**
  - [ ]* 9.3 Write property test for frontend parsing round-trip
    - **Property 11: Frontend Parsing Round-Trip**
    - **Validates: Requirements 6.1**
  - [ ]* 9.4 Write property test for frontend error resilience
    - **Property 12: Frontend Error Resilience**
    - **Validates: Requirements 6.5**

- [ ] 10. Hybrid Memory Integration
  - [ ] 10.1 Update prompt building with user facts
    - Query Vector DB for user facts at request start
    - Inject user facts into system prompt
    - _Requirements: 5.1, 5.2_
  - [ ] 10.2 Implement facts priority logic
    - Prioritize Vector DB facts over conversation-extracted facts
    - _Requirements: 5.4_
  - [ ]* 10.3 Write property test for user facts injection
    - **Property 9: User Facts Injection**
    - **Validates: Requirements 5.2**
  - [ ]* 10.4 Write property test for Vector DB facts priority
    - **Property 10: Vector DB Facts Priority**
    - **Validates: Requirements 5.4**

- [ ] 11. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
