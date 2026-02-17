# Implementation Plan

## API Transparency & Thinking Feature

- [x] 1. Add ToolUsageInfo schema and update ChatResponseMetadata




  - [ ] 1.1 Add ToolUsageInfo model to schemas.py
    - Create `ToolUsageInfo` Pydantic model with `name` and `description` fields
    - Add proper Field descriptions and validation
    - _Requirements: 1.3_
  - [x]* 1.2 Write property test for ToolUsageInfo schema

    - **Property 3: Tool entries contain required fields**
    - **Validates: Requirements 1.3**
  - [ ] 1.3 Update ChatResponseMetadata to include tools_used field
    - Add `tools_used: List[ToolUsageInfo]` with default empty list
    - Ensure backward compatibility with existing API consumers
    - _Requirements: 1.1, 1.4, 3.2_




  - [ ]* 1.4 Write property test for ChatResponseMetadata tools_used
    - **Property 1: API response always contains valid tools_used array**
    - **Validates: Requirements 1.1, 1.4**

- [ ] 2. Update SYSTEM_PROMPT with mandatory thinking rules
  - [x] 2.1 Add thinking rules section to SYSTEM_PROMPT in unified_agent.py




    - Add explicit instructions requiring `<thinking>` when calling tool_maritime_search
    - Include examples of proper thinking format
    - Specify that thinking is optional for non-RAG responses
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 2.2 Write property test for RAG responses include thinking tag
    - **Property 4: RAG responses include thinking tag**


    - **Validates: Requirements 2.1**





- [ ] 3. Wire tools_used through the response pipeline
  - [ ] 3.1 Update chat.py to format tools_used for API response
    - Extract tools_used from internal response metadata
    - Convert to ToolUsageInfo objects with descriptive text
    - Add helper function `_get_tool_description()` for human-readable descriptions



    - _Requirements: 1.1, 1.2, 1.3_
  - [ ]* 3.2 Write property test for empty tools_used on non-tool responses
    - **Property 2: Empty tools_used for non-tool responses**
    - **Validates: Requirements 1.2**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Integration testing and backward compatibility verification
  - [ ] 5.1 Update test_deployed_flow.py to verify new fields
    - Add checks for tools_used in API response
    - Add checks for thinking tag in RAG responses
    - Verify backward compatibility of existing fields
    - _Requirements: 3.1, 3.3_
  - [ ]* 5.2 Write property test for backward compatibility
    - **Property 5: Backward compatibility maintained**
    - **Validates: Requirements 3.1, 3.3**

- [ ] 6. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
