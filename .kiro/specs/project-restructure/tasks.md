# Implementation Plan

## P0: Scripts/Tests Reorganization

- [x] 1. Create test directory structure
  - [x] 1.1 Verify tests/e2e/ directory exists (create if not)
  - [x] 1.2 Verify tests/integration/ directory exists (create if not)
  - [x] 1.3 Verify tests/unit/ directory exists (create if not)
  - [x] 1.4 Verify tests/property/ directory exists (already has property tests)
  - _Requirements: 1.1_

- [x] 2. Move E2E test files from scripts/ to tests/e2e/


  - Move files: test_chat_e2e.py, test_humanization_e2e.py, test_pronoun_adaptation_e2e.py, test_memory_persistence_e2e.py
  - Move production tests: test_*_production*.py (deep_reasoning, guardian, insight_engine, managed_memory, api)
  - _Requirements: 1.2_


- [x] 3. Move integration test files from scripts/ to tests/integration/

  - Move guardian tests: test_guardian_agent.py, test_guardian_integration.py, test_guardian_model.py
  - Move search/api tests: test_hybrid_search.py, test_langgraph_api.py, test_neon_migration.py
  - Move cross-session: test_cross_session_memory.py
  - _Requirements: 1.3_


- [x] 4. Move remaining unit test files from scripts/ to tests/unit/

  - Move classifier: test_intent_classifier.py
  - Move memory tests: test_semantic_memory*.py, test_memory_*.py (non-e2e), test_insight_*.py (non-production)
  - Move remaining: test_*.py files not categorized above
  - _Requirements: 1.4_


- [x] 5. Organize scripts subdirectories



  - [x] 5.1 Create scripts/migrations/ and move: add_is_blocked_column.sql, create_*.sql, upgrade_*.sql



  - [x] 5.2 Create scripts/data/ and move: import_colregs.py, reingest_with_embeddings.py
  - [x] 5.3 Create scripts/utils/ and move: check_*.py, verify_all_systems.py
  - _Requirements: 1.5, 1.6, 1.7_

- [ ]* 6. Write property test for test discovery
  - **Property 2: Test Discovery Completeness**
  - **Validates: Requirements 1.1, 5.1**

- [x] 7. Checkpoint P0 - Verify test discovery


  - Ensure all tests pass, ask the user if questions arise.
  - Run: pytest tests/ --collect-only
  - _Requirements: 5.1_

## P1: Legacy Code Removal (QUYẾT ĐỊNH: LOẠI BỎ FALLBACK)

**✅ QUYẾT ĐỊNH:** Loại bỏ fallback, giữ code sạch với UnifiedAgent là agent duy nhất.


- [x] 8. Loại bỏ legacy imports và fallback logic trong chat_service.py


  - [x] 8.1 Xóa import: `from app.engine.agents.chat_agent import ChatAgent`





  - [x] 8.2 Xóa import: `from app.engine.graph import AgentOrchestrator, AgentType, IntentType`






  - [x] 8.3 Xóa khởi tạo: `self._orchestrator = AgentOrchestrator()` và `self._chat_agent = ChatAgent()`




  - [x] 8.4 Xóa fallback logic trong `process_message()` (phần `else: # LEGACY`)
  - [x] 8.5 Đảm bảo UnifiedAgent là bắt buộc (raise error nếu không khả dụng)
  - _Requirements: 2.1, 2.2_

- [x] 9. Archive legacy files


  - [x] 9.1 Tạo archive/ directory trong maritime-ai-service/
  - [x] 9.2 Di chuyển app/engine/agents/chat_agent.py → archive/chat_agent.py
  - [x] 9.3 Di chuyển app/engine/graph.py → archive/graph.py
  - [x] 9.4 Cập nhật README.md Project Structure section

  - _Requirements: 2.3, 2.4_

- [x] 10. Checkpoint P1 - Verify application works

  - Ensure all tests pass, ask the user if questions arise.
  - Run: pytest tests/ -v
  - Verify UnifiedAgent is working correctly
  - _Requirements: 2.5, 5.2_

## P2: Semantic Memory Refactoring (Week 2)

- [x] 11. Create semantic memory module structure
  - [x] 11.1 Create app/engine/semantic_memory/ directory
  - [x] 11.2 Create __init__.py with facade: `from .core import SemanticMemoryEngine`
  - [x] 11.3 Extract SemanticMemoryEngine class to core.py (~580 lines)
  - [x] 11.4 Extract retrieve_context, retrieve_insights_prioritized to context.py (~242 lines)
  - [x] 11.5 Extract fact/insight extraction logic to extraction.py (~397 lines)
  - Note: Original semantic_memory.py (1,298 lines) → 3 modules (1,240 lines total)
  - _Requirements: 3.1, 3.2_

- [ ]* 12. Write property test for import compatibility
  - **Property 1: Import Backward Compatibility**
  - **Validates: Requirements 3.2, 3.3**

- [x] 13. Update imports across codebase
  - Backward compatibility maintained: both import paths work
  - `from app.engine.semantic_memory import SemanticMemoryEngine` ✅
  - `from app.engine.semantic_memory.core import SemanticMemoryEngine` ✅
  - _Requirements: 3.3_

- [x] 14. Checkpoint P2 - Verify semantic memory works

  - Ensure all tests pass, ask the user if questions arise.
  - Run: pytest tests/ -v
  - _Requirements: 3.4, 5.2_

## P3: Documentation Consolidation (Week 2)

- [x] 15. Consolidate semantic memory documentation
  - [x] 15.1 Create docs/SEMANTIC_MEMORY_ARCHITECTURE.md
  - [x] 15.2 Merge content from: SEMANTIC_MEMORY_V03_GUIDE.md, V04, V05
  - [x] 15.3 Add Version History section documenting evolution from v0.3 → v0.5
  - [x] 15.4 Move old version files to docs/archive/
  - _Requirements: 4.1, 4.2, 4.3_

## Final Verification

- [x] 16. Final Checkpoint - Full system verification


  - Ensure all tests pass, ask the user if questions arise.
  - Run: pytest tests/ -v
  - Run: python scripts/utils/verify_all_systems.py
  - Verify: /chat endpoint, Guardian Agent, RAG search
  - _Requirements: 5.2, 5.3, 5.4, 5.5_
