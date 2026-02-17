# FastAPI Production Templates Skill

## Description
FastAPI production patterns for building async Python web APIs. Use for WiiiGov AI backend development.

## Project Structure
```
src-python/
├── main.py              # FastAPI app entry, lifespan, middleware
├── config.py            # pydantic-settings configuration
├── api/
│   ├── __init__.py
│   ├── router.py        # Main router aggregation
│   ├── chat.py          # Chat endpoints
│   ├── search.py        # Search endpoints
│   └── dependencies.py  # Shared dependencies
├── core/                # Business logic
├── db/                  # Database operations
├── services/            # Background services
└── tests/               # Pytest tests
```

## Patterns

### App Entry Point
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    init_vectorstore()
    yield
    # Shutdown
    await cleanup()

app = FastAPI(
    title="WiiiGov AI API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Configuration with pydantic-settings
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"
    GOOGLE_API_KEY: str
    CHROMA_DB_PATH: str = "./data/chroma_db"

    class Config:
        env_file = "../.env"

settings = Settings()
```

### Request/Response Models
```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict] = Field(default_factory=list)

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    processing_time_ms: int
```

### Async Endpoints
```python
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    rag_engine: RAGEngine = Depends(get_rag_engine)
) -> ChatResponse:
    try:
        result = await rag_engine.chat(request.message)
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Streaming Response (SSE)
```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        async for chunk in rag_engine.stream(request.message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Dependency Injection
```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

def get_rag_engine(settings: Settings = Depends(get_settings)):
    return RAGEngine(settings)
```

### Background Tasks
```python
from fastapi import BackgroundTasks

@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_crawler_sync)
    return {"status": "sync_started"}
```

## Error Handling
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "validation_error"}
    )
```

## Testing
```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_chat_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"message": "Test question"}
        )
        assert response.status_code == 200
```
