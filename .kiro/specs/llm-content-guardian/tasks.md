# Implementation Plan: LLM Content Guardian

## Phase 1: Core Guardian Agent

- [x] 1. Create GuardianAgent class
  - [x] 1.1 Create guardian_agent.py with base structure
    - Create GuardianAgent class with LLM and fallback initialization
    - Define GuardianDecision and PronounValidationResult dataclasses
    - Add GuardianConfig for configuration
    - _Requirements: 1.1, 2.1_
  - [x] 1.2 Implement validate_message() method
    - Build Guardian prompt template
    - Call LLM and parse JSON response
    - Handle ALLOW/BLOCK/FLAG decisions
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ]* 1.3 Write property test for contextual content filtering
    - **Property 2: Contextual Content Filtering**
    - **Validates: Requirements 2.2, 2.3**

- [x] 2. Checkpoint - Verify GuardianAgent base works



  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Pronoun Request Validation

- [x] 3. Implement pronoun request validation
  - [x] 3.1 Implement validate_pronoun_request() method
    - Detect pronoun request patterns in message
    - Call LLM to validate appropriateness
    - Return PronounValidationResult with approved/rejected pronouns
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 3.2 Integrate with existing pronoun detection
    - Update detect_pronoun_style() to call GuardianAgent for complex requests
    - Handle "gọi tôi là X" patterns
    - _Requirements: 1.2, 1.4_
  - [ ]* 3.3 Write property test for pronoun request validation
    - **Property 1: Pronoun Request Validation**
    - **Validates: Requirements 1.2, 1.3**

- [x] 4. Checkpoint - Verify pronoun validation works
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Fallback and Optimization

- [x] 5. Implement fallback mechanism
  - [x] 5.1 Add timeout handling for LLM calls
    - Set 2-second timeout for LLM validation
    - Fallback to rule-based Guardrails on timeout
    - Log fallback events
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 5.2 Implement _should_skip_llm() method
    - Define skip patterns (simple greetings)
    - Return ALLOW immediately for skip patterns
    - _Requirements: 5.3_
  - [ ]* 5.3 Write property test for fallback mechanism
    - **Property 3: Fallback Mechanism**
    - **Validates: Requirements 3.1, 3.2**
  - [ ]* 5.4 Write property test for LLM skip optimization
    - **Property 5: LLM Skip Optimization**
    - **Validates: Requirements 5.3**

- [x] 6. Checkpoint - Verify fallback works
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Caching and Performance

- [x] 7. Implement decision caching
  - [x] 7.1 Add cache for repeated message patterns
    - Implement simple in-memory cache with TTL
    - Hash message content for cache key
    - Return cached decision without LLM call
    - _Requirements: 5.2_
  - [x] 7.2 Add latency tracking
    - Track LLM call latency
    - Include in GuardianDecision
    - _Requirements: 5.4_
  - [ ]* 7.3 Write property test for decision caching
    - **Property 6: Decision Caching**
    - **Validates: Requirements 5.2**

- [x] 8. Checkpoint - Verify caching works
  - Ensure all tests pass, ask the user if questions arise.




## Phase 5: Integration with ChatService

- [x] 9. Integrate GuardianAgent into ChatService
  - [x] 9.1 Wire GuardianAgent into process_message()
    - Initialize GuardianAgent in ChatService.__init__()
    - Call validate_message() before UnifiedAgent
    - Handle BLOCK/FLAG decisions
    - _Requirements: 2.1, 2.3, 2.4_
  - [x] 9.2 Update pronoun handling to use GuardianAgent
    - Replace hardcoded INAPPROPRIATE_PRONOUNS with GuardianAgent
    - Store approved custom pronouns in SessionState
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [ ]* 9.3 Write property test for custom pronoun lifecycle
    - **Property 4: Custom Pronoun Lifecycle**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 10. Checkpoint - Verify integration works


  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: End-to-End Testing

- [x] 11. Integration testing with real scenarios
  - [x] 11.1 Test custom pronoun requests
    - "Gọi tôi là công chúa" → approved ✅
    - "Gọi tôi là đ.m" → rejected ✅
    - "Gọi tôi là thuyền trưởng" → approved ✅
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 11.2 Test contextual content filtering
    - "Cướp biển trong hàng hải" → allowed ✅
    - "Mày là đồ ngu" → blocked ✅
    - "Rule về piracy" → allowed ✅
    - _Requirements: 2.2, 2.3_
  - [x] 11.3 Test fallback scenarios
    - Simulate LLM timeout → fallback works ✅
    - Simulate LLM error → fallback works ✅
    - _Requirements: 3.1, 3.2_

- [x] 12. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
