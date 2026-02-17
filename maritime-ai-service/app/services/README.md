# Services Layer

Business logic orchestration layer that coordinates between API and Engine layers.

---

## Overview

The Services layer follows **Clean Architecture** principles with specialized processors and orchestrators. After the refactoring (2025-12-14), this layer uses:

- **Facade Pattern**: `chat_service.py` as thin entry point
- **Pipeline Pattern**: `chat_orchestrator.py` for staged processing
- **Processor Pattern**: Specialized input/output handlers
- **Singleton Pattern**: Lazy initialization with dependency injection

---

## Folder Structure

```
app/services/
├── chat_service.py              # 🎯 FACADE - Main entry point (310 lines)
├── chat_orchestrator.py         # 🔄 PIPELINE - 6-stage processing
├── session_manager.py           # 📦 Session & state management
├── input_processor.py           # 🛡️ Validation, Guardian, context
├── output_processor.py          # 📤 Response formatting
├── thinking_post_processor.py   # 🧠 Centralized thinking extraction (CHỈ THỊ SỐ 29 v8)
├── background_tasks.py          # ⏳ Async task runner
├── chat_context_builder.py      # Context assembly
├── chat_response_builder.py     # Response assembly
├── multimodal_ingestion_service.py  # PDF ingestion pipeline
├── hybrid_search_service.py     # Dense + Sparse search
├── graph_rag_service.py         # GraphRAG with Neo4j
├── chunking_service.py          # Document chunking
├── learning_graph_service.py    # Learning path management
├── supabase_storage.py          # Cloud storage
├── event_callback_service.py    # LMS webhooks (pending)
└── README.md                    # This file
```

---

## Architecture

### Pipeline Flow (ChatOrchestrator)

```
┌──────────────────────────────────────────────────────────────────┐
│                    CHAT PROCESSING PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ChatRequest                                                     │
│        │                                                          │
│        ▼                                                          │
│   ┌─────────────────┐                                            │
│   │ STAGE 1: SESSION│  SessionManager.get_or_create()            │
│   │   Management    │  → SessionContext, SessionState            │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ STAGE 2: INPUT  │  InputProcessor.validate()                 │
│   │   Validation    │  → Guardian Agent / Guardrails             │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ STAGE 3: CONTEXT│  InputProcessor.build_context()            │
│   │   Building      │  → Memory, History, Insights, LMS          │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ STAGE 4: AGENT  │  MultiAgentGraph.process() (LangGraph)      │
│   │   Processing    │  → Supervisor routes to specialized agents  │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ STAGE 5: OUTPUT │  OutputProcessor.validate_and_format()     │
│   │   Formatting    │  → Source merging, validation              │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ STAGE 6: ASYNC  │  BackgroundTaskRunner.schedule_all()       │
│   │   Tasks         │  → Memory, Profile, Summarization          │
│   └────────┬────────┘                                            │
│            ▼                                                      │
│   InternalChatResponse                                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Services

### ChatService (Facade)

**File:** `chat_service.py` (~310 lines)  
**Pattern:** Facade  
**Purpose:** Main entry point, wires dependencies, delegates to orchestrator

```python
class ChatService:
    async def process_message(request: ChatRequest) -> InternalChatResponse:
        return await self._orchestrator.process(request)
```

**Key Features:**
- Initializes all dependencies on startup
- Lazy initialization of optional components
- Backward compatible API

---

### ChatOrchestrator (Pipeline)

**File:** `chat_orchestrator.py` (~320 lines)  
**Pattern:** Pipeline / Orchestrator  
**Purpose:** Coordinates the 6-stage processing pipeline

```python
class ChatOrchestrator:
    async def process(request, background_save) -> InternalChatResponse:
        # Stage 1: Session
        # Stage 2: Validate
        # Stage 3: Context
        # Stage 4: Agent
        # Stage 5: Output
        # Stage 6: Background
```

---

### SessionManager

**File:** `session_manager.py` (~230 lines)  
**Pattern:** Singleton Service  
**Purpose:** Session CRUD and anti-repetition state

**Data Classes:**
- `SessionState`: Tracks phrases, name usage, pronoun style
- `SessionContext`: Complete session info for request

---

### InputProcessor

**File:** `input_processor.py` (~380 lines)  
**Pattern:** Processor Service  
**Purpose:** Validation, Guardian, pronoun detection, context building

**Key Methods:**
- `validate()`: Guardian Agent / Guardrails
- `build_context()`: Memory, history, insights retrieval
- `extract_user_name()`: Vietnamese/English patterns
- `validate_pronoun_request()`: Custom pronoun validation

---

### OutputProcessor

**File:** `output_processor.py` (~220 lines)  
**Pattern:** Processor Service  
**Purpose:** Response formatting, validation, source merging

**Key Methods:**
- `validate_and_format()`: Output validation + formatting
- `merge_same_page_sources()`: Combine same-page citations
- `format_sources()`: Raw dict → Source objects
- `create_blocked_response()`: Blocked content response

---

### BackgroundTaskRunner

**File:** `background_tasks.py` (~260 lines)  
**Pattern:** Task Runner  
**Purpose:** Centralized async task management

**Tasks Managed:**
- Save chat messages
- Store semantic memory interactions
- Extract behavioral insights
- Update learning profile
- Memory summarization

---

## Other Services

### HybridSearchService

Dense + Sparse search with RRF reranking.

```python
await hybrid_search.search(query, limit=5)
# Returns: Combined results from pgvector + tsvector
```

### MultimodalIngestionService

PDF ingestion pipeline: Rasterize → Upload → Vision → Chunk → Index

```python
await ingestion_service.ingest_document(pdf_path)
```

### GraphRAGService

Knowledge Graph integration with Neo4j.

---

## Dependencies

```
chat_service.py (Facade)
    ├── chat_orchestrator.py
    │       ├── session_manager.py
    │       ├── input_processor.py
    │       ├── output_processor.py
    │       └── background_tasks.py
    ├── chat_context_builder.py
    └── chat_response_builder.py
```

---

## Usage

```python
from app.services.chat_service import get_chat_service

chat_service = get_chat_service()
response = await chat_service.process_message(request)
```

---

## SOTA Compliance (2025-12-14)

| Pattern | Status | Implementation |
|---------|--------|----------------|
| Clean Architecture | ✅ | Separated concerns into processors |
| Facade Pattern | ✅ | ChatService as thin entry point |
| Pipeline Pattern | ✅ | 6-stage ChatOrchestrator |
| Dependency Injection | ✅ | init_*() functions |
| Singleton Services | ✅ | get_*() functions |

---

## Audit Status

| File | Status | Notes |
|------|--------|-------|
| `chat_service.py` | ✅ Refactored | 1263 → 310 lines |
| `chat_orchestrator.py` | ✅ NEW | Pipeline orchestration |
| `session_manager.py` | ✅ NEW | Session management |
| `input_processor.py` | ✅ NEW | Input processing |
| `output_processor.py` | ✅ NEW | Output processing |
| `background_tasks.py` | ✅ NEW | Async tasks |
| `event_callback_service.py` | ⚠️ PENDING | Awaiting LMS integration |

---

*Last Updated: 2025-12-16 (CHỈ THỊ SỐ 29 v8 - Centralized Thinking)*
