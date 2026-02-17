# Implementation Plan: Memory Isolation & Context Protection

## Phase 1: Database Schema Update

- [x] 1. Update chat_history table schema

  - [x] 1.1 Create migration script for is_blocked column


    - Add is_blocked BOOLEAN DEFAULT FALSE
    - Add block_reason TEXT (nullable)
    - Create index on is_blocked


    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ] 1.2 Update ChatMessage dataclass
    - Add is_blocked: bool = False
    - Add block_reason: Optional[str] = None
    - _Requirements: 1.1_

- [x] 2. Checkpoint - Verify schema migration

  - Ensure all tests pass, ask the user if questions arise.



## Phase 2: Repository Layer Updates



- [ ] 3. Update ChatHistoryRepository
  - [ ] 3.1 Update save_message() to support is_blocked
    - Add is_blocked parameter (default False)
    - Add block_reason parameter (optional)
    - Update SQL INSERT to include new columns
    - _Requirements: 1.1, 1.3, 1.4_
  - [ ] 3.2 Update get_recent_messages() to filter blocked
    - Add include_blocked parameter (default False)
    - Update SQL SELECT to filter WHERE is_blocked = FALSE
    - Ensure sliding window counts only non-blocked messages
    - _Requirements: 2.1, 2.2, 2.3_


  - [ ]* 3.3 Write property test for blocked message filtering
    - **Property 1: Blocked Messages Never Enter Context**


    - **Validates: Requirements 2.1, 2.2**

- [x] 4. Checkpoint - Verify repository updates


  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: ChatService Integration

- [ ] 5. Update ChatService to save blocked messages
  - [ ] 5.1 Save blocked message with flag when Guardian blocks
    - Call save_message with is_blocked=True
    - Include block_reason from GuardianDecision
    - Do NOT call semantic memory storage
    - _Requirements: 1.1, 1.2, 3.1, 3.2_
  - [ ] 5.2 Update history retrieval to exclude blocked
    - Pass include_blocked=False to get_recent_messages
    - Ensure context building uses clean history
    - _Requirements: 2.1, 2.2_
  - [ ]* 5.3 Write property test for semantic memory protection
    - **Property 2: Blocked Messages Never Enter Vector DB**
    - **Validates: Requirements 3.1, 3.2**

- [ ] 6. Checkpoint - Verify ChatService integration
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Verification & Testing

- [ ] 7. End-to-end verification
  - [ ] 7.1 Test blocked message flow
    - Send blocked message, verify saved with is_blocked=True
    - Send follow-up message, verify blocked content not in context
    - Verify blocked content not in semantic_memories table
    - _Requirements: 1.1, 2.1, 3.1_
  - [ ] 7.2 Test admin visibility
    - Query chat_history with include_blocked=True
    - Verify blocked messages visible with reasons
    - _Requirements: 4.1, 4.2_
  - [ ]* 7.3 Write property test for blocked message logging
    - **Property 3: Blocked Messages Are Logged**
    - **Validates: Requirements 1.1, 4.1**

- [ ] 8. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
