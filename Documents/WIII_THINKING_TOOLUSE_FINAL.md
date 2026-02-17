# WIII — THINKING + TOOL USE | KẾ HOẠCH TRIỂN KHAI TOÀN DIỆN

> **Phiên bản:** FINAL v1.0
> **Team:** HoLiLiHu (The Wiii Lab)
> **Ngày:** 11/02/2026
> **Dự án:** Maritime LMS — AI Tutoring System
> **Mục tiêu:** Đạt UX thinking + tool use như Claude, hỗ trợ MỌI provider, đổi model bất kỳ lúc nào

---

## MỤC LỤC

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Nguyên lý thống nhất — Tại sao KHÔNG cần đổi thiết kế](#2-nguyên-lý-thống-nhất)
3. [Unified Provider Interface — Code duy nhất](#3-unified-provider-interface)
4. [Chi tiết từng Provider](#4-chi-tiết-từng-provider)
5. [Agentic Loop — Core Pattern](#5-agentic-loop)
6. [Streaming UX — Đạt trải nghiệm Claude](#6-streaming-ux)
7. [Agent Configuration Map](#7-agent-configuration-map)
8. [Multi-Tier Strategy](#8-multi-tier-strategy)
9. [Deployment Plan theo giai đoạn](#9-deployment-plan)
10. [Pitfalls & Troubleshooting](#10-pitfalls--troubleshooting)
11. [Checklist triển khai](#11-checklist)

---

## 1. TỔNG QUAN KIẾN TRÚC

### 1.1 Vấn đề cần giải quyết

Wiii cần AI agent có khả năng **suy nghĩ trước khi hành động** (thinking) và **gọi công cụ bên ngoài** (tool use) — giống cách Claude hoạt động:

```
User: "COLREGs Rule 5 là gì?"
  ↓
🧠 AI suy nghĩ: "Cần search knowledge base, rồi check memory của user..."
  ↓
🔧 Gọi tool: search_knowledge_base("COLREGs Rule 5")
  ↓
🧠 Suy nghĩ tiếp: "Tìm được 3 kết quả. User từng nhầm Rule 15 vs 16..."
  ↓
🔧 Gọi tool: recall_user_memory("user_123")
  ↓
🧠 Tổng hợp: "Cần nhắc lại sự khác biệt Rule 5 vs Rule 15..."
  ↓
📝 Trả lời: "COLREGs Rule 5 quy định về trực canh..."
```

### 1.2 Ba pattern thinking + tool use

```
┌────────────────────────────────────────────────────────────────────┐
│                    3 PATTERNS — CÙNG 1 KẾT QUẢ UX                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─ Pattern A: SINGLE-TURN (Claude) ─────────────────────────┐    │
│  │  1 API call → N thinking + N tools + text                  │    │
│  │  Server tự execute tools                                   │    │
│  │  Client chỉ nhận 1 stream liên tục                        │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌─ Pattern B: MULTI-TURN SIGNED (Gemini) ───────────────────┐    │
│  │  N API calls, mỗi call = think + FunctionCall             │    │
│  │  thought_signature mã hóa reasoning state                 │    │
│  │  Client execute tools + gửi lại kết quả                   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌─ Pattern C: MULTI-TURN PLAINTEXT (Ollama/vLLM/SGLang) ───┐    │
│  │  N API calls, mỗi call = <think>...</think> + tool_calls  │    │
│  │  Thinking plaintext (nhìn được toàn bộ)                   │    │
│  │  Client execute tools + gửi lại kết quả                   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ★ USER NHÌN THẤY GIỐNG NHAU: 🧠→🔧→🧠→📝                      │
│  ★ CODE LOGIC GIỐNG NHAU: while(tool_calls) → execute → send     │
│  ★ API FORMAT GIỐNG NHAU: OpenAI-compatible                       │
└────────────────────────────────────────────────────────────────────┘
```

### 1.3 So sánh tổng thể

| Tiêu chí | Claude API | Gemini API | Ollama (Local) | vLLM / SGLang |
|---|---|---|---|---|
| Pattern | Single-turn | Multi-turn + signature | Multi-turn + plaintext | Multi-turn + plaintext |
| Think + Tools | ✅ 1 response | ✅ N round-trips | ✅ N round-trips | ✅ N round-trips |
| Thinking visible | Summarized blocks | Encrypted signature | ✅ **Full plaintext** | ✅ Full plaintext |
| Toggle thinking | effort param | thinking_level | `/think` `/no_think` | enable_thinking |
| Thinking budget | — | — | ✅ thinking_budget | ✅ thinking_budget |
| Parallel tools | ✅ | ✅ | ✅ | ✅ |
| Stream | ✅ | ✅ (text only) | ✅ | ✅ |
| API format | OpenAI-compatible | OpenAI-compatible | OpenAI-compatible | OpenAI-compatible |
| Cost / MTok | $5 / $25 | $0.50 / $3 | **$0** | **$0** |
| Context window | 200K | 1M | 32K–131K | 32K–262K |
| Quality | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐–⭐⭐⭐⭐ | ⭐⭐⭐–⭐⭐⭐⭐ |
| Privacy | Cloud | Cloud | ✅ 100% local | ✅ 100% local |
| Offline | ❌ | ❌ | ✅ | ✅ |
| Concurrent | Unlimited | Unlimited | 1–3 users | 10–100+ users |

---

## 2. NGUYÊN LÝ THỐNG NHẤT

### 2.1 Tại sao KHÔNG cần đổi thiết kế khi đổi provider

**Tất cả providers đã hội tụ về chuẩn OpenAI-compatible API.** Đây là chuẩn công nghiệp (de-facto standard) mà mọi model mới phải hỗ trợ.

```
Code của Wiii (VIẾT 1 LẦN)
        │
        │  OpenAI SDK: client.chat.completions.create(
        │      model=..., messages=..., tools=...
        │  )
        │
        ▼ Chỉ đổi: base_url + api_key + model name
        │
   ┌────┼─────────┬───────────────┬──────────────┐
   ▼    ▼         ▼               ▼              ▼
Ollama  Gemini   Claude    DeepSeek    [Model tương lai]
:11434   API      API       API         Cùng format
  $0    $0.50    $5/MTok   $0.50/MTok
```

**Bằng chứng thực tế — 12 tháng qua, 100% model mới đều dùng cùng format:**

| Model (2025–2026) | Hãng | OpenAI-compatible |
|---|---|---|
| Claude Opus 4.6, Sonnet 4.5 | Anthropic | ✅ |
| Gemini 3 Flash, Pro | Google | ✅ |
| Qwen 3 (all sizes) | Alibaba | ✅ |
| Qwen3-Coder-Next | Alibaba | ✅ |
| GLM-4.7 | Zhipu AI | ✅ |
| DeepSeek V3.2 | DeepSeek | ✅ |
| Llama 4 | Meta | ✅ |
| Mistral Large 3 | Mistral | ✅ |
| Nemotron 3 Nano | NVIDIA | ✅ |

### 2.2 Khi model mới ra — đổi gì?

```python
# Hôm nay
answer = await agent_loop(query, tools, model="qwen3:14b")

# 6 tháng sau — Qwen 4 ra
answer = await agent_loop(query, tools, model="qwen4:14b")
#                                               ^^^^^^^^ CHỈ ĐỔI TÊN

# 1 năm sau — model chưa tồn tại
answer = await agent_loop(query, tools, model="future-model:latest")
#                                               ^^^^^^^^^^^^^^^^ VẪN CHẠY
```

**Kết luận: Thiết kế 1 lần → chạy vĩnh viễn. Đổi model = đổi 1 string.**

---

## 3. UNIFIED PROVIDER INTERFACE

### 3.1 Provider Configuration

```python
# wiii/app/llm/providers.py
# ═══════════════════════════════════════════════════════════
# FILE DUY NHẤT quản lý TẤT CẢ providers
# Đổi/thêm provider = chỉ sửa file này
# ═══════════════════════════════════════════════════════════

import os
from dataclasses import dataclass
from openai import AsyncOpenAI


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str
    think_param: dict  # Cách bật thinking (khác nhỏ giữa providers)


# ─── Provider Registry ───
PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        name="Ollama (Local)",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        default_model="qwen3:14b",
        think_param={"think": True},
    ),
    "gemini": ProviderConfig(
        name="Gemini API",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GEMINI_API_KEY", ""),
        default_model="gemini-2.5-flash-preview",
        think_param={},  # Gemini: handled via native SDK or default on
    ),
    "anthropic": ProviderConfig(
        name="Claude API",
        base_url="https://api.anthropic.com/v1/",
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        default_model="claude-sonnet-4-5-20250929",
        think_param={},  # Claude: thinking automatic
    ),
    "deepseek": ProviderConfig(
        name="DeepSeek API",
        base_url="https://api.deepseek.com/v1",
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        default_model="deepseek-chat",
        think_param={},
    ),
    "vllm": ProviderConfig(
        name="vLLM (Local Production)",
        base_url="http://localhost:8000/v1",
        api_key="vllm",
        default_model="Qwen/Qwen3-14B",
        think_param={"chat_template_kwargs": {"enable_thinking": True}},
    ),
}


def get_client(provider: str = "ollama") -> AsyncOpenAI:
    """Get OpenAI-compatible client for any provider."""
    cfg = PROVIDERS[provider]
    return AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)


def get_think_params(provider: str, think: bool = True) -> dict:
    """Get provider-specific thinking parameters."""
    if not think:
        return {}
    return {"extra_body": PROVIDERS[provider].think_param} if PROVIDERS[provider].think_param else {}
```

### 3.2 Tool Definitions — Dùng chung cho mọi provider

```python
# wiii/app/llm/tools.py
# ═══════════════════════════════════════════════════════════
# Tool definitions theo chuẩn OpenAI — chạy trên MỌI provider
# ═══════════════════════════════════════════════════════════

WIII_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Tìm kiếm trong knowledge base hàng hải (COLREGs, SOLAS, STCW). "
                "Dùng khi cần tra cứu quy định, luật, hướng dẫn hàng hải."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu truy vấn tìm kiếm"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Số kết quả trả về (mặc định 5)",
                        "default": 5
                    },
                    "source_filter": {
                        "type": "string",
                        "enum": ["colregs", "solas", "stcw", "all"],
                        "description": "Lọc theo nguồn tài liệu",
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_user_memory",
            "description": (
                "Truy xuất memory của học viên — lịch sử học, điểm yếu, sở thích. "
                "Dùng để cá nhân hóa phản hồi."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID của học viên"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Chủ đề cần recall (tùy chọn)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Số facts tối đa",
                        "default": 5
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grade_answer",
            "description": (
                "Chấm điểm câu trả lời của học viên so với đáp án chuẩn. "
                "Trả về điểm và feedback chi tiết."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_answer": {
                        "type": "string",
                        "description": "Câu trả lời của học viên"
                    },
                    "reference_answer": {
                        "type": "string",
                        "description": "Đáp án tham khảo"
                    },
                    "question": {
                        "type": "string",
                        "description": "Câu hỏi gốc"
                    }
                },
                "required": ["student_answer", "reference_answer", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_memory",
            "description": (
                "Lưu fact mới về học viên vào memory. "
                "Dùng khi phát hiện điểm yếu, sở thích, hoặc tiến bộ mới."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID của học viên"
                    },
                    "fact": {
                        "type": "string",
                        "description": "Fact cần lưu"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["learning_gap", "knowledge", "preference", "behavior"],
                        "description": "Phân loại fact"
                    }
                },
                "required": ["user_id", "fact", "category"]
            }
        }
    }
]
```

---

## 4. CHI TIẾT TỪNG PROVIDER

### 4.1 Ollama — Development & Testing ($0)

**Setup:**
```bash
# Cài Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model (chọn phù hợp hardware)
ollama pull qwen3:8b       # 5GB, cần 8GB+ RAM — testing
ollama pull qwen3:14b      # 9GB, cần 16GB+ RAM — ★ recommended dev
ollama pull qwen3:30b-a3b  # 4GB, cần 8GB+ RAM — MoE, nhanh + tốt
ollama pull qwen3:32b      # 20GB, cần 24GB+ VRAM — high quality

# API sẵn sàng tại http://localhost:11434/v1
```

**Đặc điểm riêng:**

| Feature | Chi tiết |
|---|---|
| Thinking | `think=True` → output trong `response.message.thinking` |
| Toggle | `/think` và `/no_think` trong prompt content |
| Budget | `options.num_predict` giới hạn total output tokens |
| Tool parse | Auto-detect tool calls, streaming supported |
| History | KHÔNG include thinking content trong history (tự động) |

**Ưu điểm cho Wiii:**
- $0 cost → chạy bao nhiêu requests cũng được
- Thinking plaintext → debug dễ, demo thesis
- 100% offline → data không rời máy
- Auto-parse Python functions thành tool schema

### 4.2 Gemini API — Staging & Production (cheap)

**Setup:**
```bash
pip install google-genai
export GEMINI_API_KEY="your-key-here"
```

**Đặc điểm riêng:**

| Feature | Chi tiết |
|---|---|
| Thinking | `thinking_config.thinking_level` = minimal/low/medium/high |
| State | `thought_signature` mã hóa reasoning state giữa calls |
| Critical | PHẢI append full `model_content` (chứa signature) vào history |
| Budget | `thinking_budget` (tokens) — deprecated, dùng `thinking_level` |
| Parallel | Hỗ trợ parallel function calls |
| Context | 1M tokens |
| Chi phí | Input $0.50 / Output $3 per MTok |

**thought_signature — Cơ chế quan trọng nhất:**
```
API Call #1 → Model thinks + returns FunctionCall
                                + thought_signature="abc..."  ← SAVE STATE
     ↓
Client executes tool
     ↓
API Call #2 → Client sends: tool result + thought_signature
              Model "loads" reasoning state → continues EXACTLY where stopped
```

**Nếu mất signature** → model mất toàn bộ reasoning context → trả lời sai.
**Cách đảm bảo:** Append nguyên `model_content` object, KHÔNG tự construct.

### 4.3 Claude API — Best Quality

**Setup:**
```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
```

**Đặc điểm riêng:**

| Feature | Chi tiết |
|---|---|
| Pattern | Single-turn interleaved — server tự execute tools |
| Thinking | Automatic, summarized blocks |
| Quality | Tốt nhất hiện tại, đặc biệt reasoning phức tạp |
| Chi phí | Input $5 / Output $25 per MTok (Opus) |

**Lưu ý:** Qua OpenAI-compatible endpoint, tool calling hoạt động standard. Thinking blocks được handle bởi platform.

### 4.4 vLLM / SGLang — Production Local Serving

Khi Wiii cần serve **nhiều users đồng thời** trên GPU server.

**Setup vLLM:**
```bash
pip install -U vllm

vllm serve Qwen/Qwen3-14B \
    --tool-call-parser hermes \
    --enable-auto-tool-choice \
    --max-model-len 32768 \
    --port 8000

# API sẵn sàng tại http://localhost:8000/v1
```

**Setup SGLang:**
```bash
pip install sglang

python -m sglang.launch_server \
    --model-path Qwen/Qwen3-14B \
    --tool-call-parser hermes \
    --port 8000
```

**Bật thinking per-request:**
```python
extra_body={"chat_template_kwargs": {"enable_thinking": True}}
# Tắt:
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
```

**Khi nào dùng vLLM/SGLang thay Ollama:**

| Tiêu chí | Ollama | vLLM/SGLang |
|---|---|---|
| Users đồng thời | 1–3 | 10–100+ |
| Batching | Basic | Continuous batching |
| Throughput | ~30 tok/s/user | ~100+ tok/s aggregate |
| Setup | 1 command | Docker + config |

---

## 5. AGENTIC LOOP — CORE PATTERN

### 5.1 The Loop — Chạy giống hệt trên mọi provider

```python
# wiii/app/llm/agent_loop.py
# ═══════════════════════════════════════════════════════════
# CORE: Agentic loop dùng chung cho TẤT CẢ providers
# Viết 1 lần, chạy trên Ollama, Gemini, Claude, vLLM...
# ═══════════════════════════════════════════════════════════

import json
from typing import AsyncGenerator

from .providers import get_client, get_think_params, PROVIDERS
from .tools import WIII_TOOLS
from .tool_executor import execute_tool


async def agentic_loop(
    query: str,
    user_id: str,
    provider: str = "ollama",
    model: str | None = None,
    tools: list = WIII_TOOLS,
    think: bool = True,
    max_steps: int = 10,
    system_prompt: str | None = None,
) -> str:
    """
    Multi-step thinking + tool use loop.
    
    CHẠY GIỐNG HỆT trên mọi provider vì tất cả dùng OpenAI-compatible API.
    
    Flow:
    1. Gửi query + tools → model
    2. Model trả về text (done) hoặc tool_calls (continue)
    3. Execute tools → gửi results lại model
    4. Lặp lại từ bước 2
    """
    client = get_client(provider)
    resolved_model = model or PROVIDERS[provider].default_model
    think_params = get_think_params(provider, think)

    # ── Build messages ──
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({
        "role": "system",
        "content": (
            f"Bạn là Wiii — AI gia sư hàng hải thông minh của hệ thống Maritime LMS. "
            f"Student ID: {user_id}. Luôn trả lời bằng tiếng Việt. "
            f"Sử dụng tools khi cần tra cứu thông tin hoặc truy xuất memory."
        )
    })
    messages.append({"role": "user", "content": query})

    # ── Agentic loop ──
    for step in range(max_steps):
        response = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            tools=tools if tools else None,
            **think_params,
        )

        msg = response.choices[0].message

        # ── Check: final answer or tool calls? ──
        if not msg.tool_calls:
            return msg.content or ""

        # ── Append assistant message (preserves tool_calls structure) ──
        messages.append(msg.model_dump())

        # ── Execute each tool call ──
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            result = await execute_tool(fn_name, fn_args, user_id=user_id)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        # → Loop continues: model receives tool results, thinks, responds

    return "⚠️ Đã đạt giới hạn bước xử lý. Vui lòng thử câu hỏi cụ thể hơn."
```

### 5.2 Tool Executor — Dispatch tới Wiii services

```python
# wiii/app/llm/tool_executor.py
# ═══════════════════════════════════════════════════════════
# Dispatcher: tool name → actual Wiii service call
# ═══════════════════════════════════════════════════════════

from wiii.app.services.rag_service import RagService
from wiii.app.services.memory_service import MemoryService
from wiii.app.services.grading_service import GradingService


# ── Tool registry ──
TOOL_HANDLERS = {}


def tool(name: str):
    """Decorator to register tool handlers."""
    def decorator(fn):
        TOOL_HANDLERS[name] = fn
        return fn
    return decorator


@tool("search_knowledge_base")
async def _search_kb(query: str, top_k: int = 5, source_filter: str = "all", **kw):
    rag = RagService()
    results = await rag.search(query=query, top_k=top_k, source=source_filter)
    return {"results": results}


@tool("recall_user_memory")
async def _recall_memory(user_id: str, topic: str = "", limit: int = 5, **kw):
    mem = MemoryService()
    facts = await mem.recall(user_id=user_id, query=topic, limit=limit)
    return {"facts": facts}


@tool("grade_answer")
async def _grade(student_answer: str, reference_answer: str, question: str, **kw):
    grader = GradingService()
    result = await grader.grade(
        student_answer=student_answer,
        reference=reference_answer,
        question=question,
    )
    return result


@tool("save_user_memory")
async def _save_memory(user_id: str, fact: str, category: str, **kw):
    mem = MemoryService()
    await mem.save_fact(user_id=user_id, text=fact, category=category)
    return {"status": "saved", "fact": fact}


async def execute_tool(name: str, args: dict, user_id: str = "") -> dict:
    """Execute a tool by name with given arguments."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await handler(**args, user_id=user_id)
    except Exception as e:
        return {"error": str(e)}
```

---

## 6. STREAMING UX — ĐẠT TRẢI NGHIỆM CLAUDE

### 6.1 Streaming Agentic Loop

```python
# wiii/app/llm/agent_stream.py
# ═══════════════════════════════════════════════════════════
# Streaming version — user thấy thinking + tools real-time
# Output: Server-Sent Events (SSE) cho Angular frontend
# ═══════════════════════════════════════════════════════════

import json
from typing import AsyncGenerator


async def agentic_stream(
    query: str,
    user_id: str,
    provider: str = "ollama",
    model: str | None = None,
    tools: list = WIII_TOOLS,
    think: bool = True,
    max_steps: int = 10,
) -> AsyncGenerator[dict, None]:
    """
    Streaming agentic loop.
    
    Yields events:
      {"type": "thinking",  "content": "Đang phân tích câu hỏi..."}
      {"type": "tool_call", "name": "search_knowledge_base", "args": {...}}
      {"type": "tool_result", "name": "...", "result": {...}}
      {"type": "text",      "content": "COLREGs Rule 5 quy định..."}
      {"type": "done"}
    """
    client = get_client(provider)
    resolved_model = model or PROVIDERS[provider].default_model

    messages = [
        {"role": "system", "content": f"Bạn là Wiii. Student: {user_id}. Tiếng Việt."},
        {"role": "user", "content": query},
    ]

    for step in range(max_steps):
        # ── Stream response ──
        stream = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            tools=tools,
            stream=True,
            **get_think_params(provider, think),
        )

        collected_content = ""
        collected_thinking = ""
        collected_tool_calls = []

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Thinking tokens (Ollama)
            if hasattr(delta, "thinking") and delta.thinking:
                collected_thinking += delta.thinking
                yield {"type": "thinking", "content": delta.thinking}

            # Text tokens
            if delta.content:
                collected_content += delta.content
                yield {"type": "text", "content": delta.content}

            # Tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.index >= len(collected_tool_calls):
                        collected_tool_calls.append({
                            "id": tc.id or "",
                            "name": tc.function.name or "",
                            "arguments": ""
                        })
                    if tc.function and tc.function.arguments:
                        collected_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # ── No tool calls → done ──
        if not collected_tool_calls:
            yield {"type": "done"}
            return

        # ── Execute tools and stream results ──
        messages.append({
            "role": "assistant",
            "content": collected_content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]}
                }
                for tc in collected_tool_calls
            ]
        })

        for tc in collected_tool_calls:
            args = json.loads(tc["arguments"])
            yield {"type": "tool_call", "name": tc["name"], "args": args}

            result = await execute_tool(tc["name"], args, user_id=user_id)
            yield {"type": "tool_result", "name": tc["name"], "result": result}

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    yield {"type": "done"}
```

### 6.2 SSE Endpoint (FastAPI)

```python
# wiii/app/api/chat.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE endpoint — Angular frontend subscribes to this."""

    async def event_generator():
        async for event in agentic_stream(
            query=request.message,
            user_id=request.user_id,
            provider=request.provider or "ollama",  # Configurable!
            model=request.model,                     # Configurable!
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

### 6.3 Angular Frontend — Hiển thị UX

```typescript
// wiii-frontend/src/app/chat/chat.service.ts

// User nhìn thấy:
// ┌──────────────────────────────────────────┐
// │ 🧠 Đang suy nghĩ...                      │
// │    "Cần search COLREGs Rule 5 trong KB"  │
// │                                          │
// │ 🔧 search_knowledge_base("COLREGs R5")  │
// │    ✅ Tìm được 3 kết quả                │
// │                                          │
// │ 🧠 Đang phân tích...                     │
// │    "User từng nhầm Rule 15 vs 16"       │
// │                                          │
// │ 📝 COLREGs Rule 5 quy định về nghĩa vụ │
// │    trực canh (lookout). Mọi tàu phải   │
// │    duy trì trực canh bằng thị giác...   │
// └──────────────────────────────────────────┘
```

---

## 7. AGENT CONFIGURATION MAP

### 7.1 Mỗi agent — provider + model + thinking riêng

```python
# wiii/app/config/agents.py

AGENT_CONFIG = {
    # ──────────────────────────────────────────────────────
    # TIER 1: FAST — Local, no thinking, < 100ms
    # ──────────────────────────────────────────────────────
    "guardian": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "think": False,           # /no_think — pure speed
        "tools": [],              # Không cần tools
        "description": "Safety check, content filtering",
    },
    "supervisor": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "think": False,
        "tools": [],
        "description": "Intent classification, agent routing",
    },
    "synthesizer": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "think": False,
        "tools": [],
        "description": "Final formatting, Vietnamese polishing",
    },

    # ──────────────────────────────────────────────────────
    # TIER 2: BALANCED — Local with thinking, 1-3s
    # ──────────────────────────────────────────────────────
    "memory": {
        "provider": "ollama",     # ★ Privacy: user data stays local
        "model": "qwen3:14b",
        "think": True,
        "tools": ["recall_user_memory", "save_user_memory"],
        "description": "Fact extraction, user profiling",
    },
    "grader": {
        "provider": "ollama",
        "model": "qwen3:14b",
        "think": True,
        "tools": ["grade_answer", "search_knowledge_base"],
        "description": "Answer quality assessment, scoring",
    },

    # ──────────────────────────────────────────────────────
    # TIER 3: DEEP — API or large local, 3-10s
    # ──────────────────────────────────────────────────────
    "rag": {
        "provider": "gemini",     # Hoặc "ollama" nếu có GPU mạnh
        "model": "gemini-2.5-flash-preview",
        "think": True,
        "tools": ["search_knowledge_base", "recall_user_memory"],
        "description": "Knowledge retrieval + synthesis",
    },
    "tutor": {
        "provider": "gemini",     # Hoặc "anthropic" cho complex topics
        "model": "gemini-2.5-flash-preview",
        "think": True,
        "tools": WIII_TOOLS,      # All tools available
        "description": "Main tutoring response generation",
    },
}
```

### 7.2 Tại sao phân tier?

```
User: "COLREGs Rule 5 là gì?"
  │
  ▼ guardian (ollama, no_think, 50ms) → PASS
  ▼ supervisor (ollama, no_think, 80ms) → route to: tutor
  ▼ tutor (gemini, think=high, 3s)
      🧠 Think → 🔧 search_KB → 🧠 Think → 🔧 recall_memory → 📝 Answer
  ▼ memory (ollama, think, 500ms) → save new facts about user
  ▼ synthesizer (ollama, no_think, 100ms) → polish Vietnamese
  │
  ▼ Total: ~4s — Quality: ⭐⭐⭐⭐
```

**Nếu chạy 100% Gemini API:** ~$0.01/query, quality ⭐⭐⭐⭐
**Nếu chạy 100% local:** ~$0/query, quality ⭐⭐⭐
**Hybrid (khuyến nghị):** ~$0.003/query, quality ⭐⭐⭐⭐ — 70% requests xử lý local

---

## 8. MULTI-TIER STRATEGY

### 8.1 Bảng quyết định

```
┌─────────────────────────────────────────────────────────────────┐
│                   WIII REQUEST ROUTER                            │
│                                                                  │
│   ┌───────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│   │ TIER 1    │  │ TIER 2        │  │ TIER 3               │   │
│   │ LOCAL     │  │ LOCAL+THINK   │  │ API (hoặc local lớn) │   │
│   │ FAST      │  │ BALANCED      │  │ DEEP                 │   │
│   │           │  │               │  │                      │   │
│   │ Ollama    │  │ Ollama        │  │ Gemini Flash /       │   │
│   │ qwen3:8b  │  │ qwen3:14b     │  │ Claude Sonnet /      │   │
│   │ no_think  │  │ think=on      │  │ qwen3:32b local      │   │
│   │           │  │               │  │ think=on             │   │
│   │ • Guard   │  │ • Memory      │  │ • Tutoring           │   │
│   │ • Route   │  │ • Grading     │  │ • RAG synthesis      │   │
│   │ • Format  │  │ • Fact extract│  │ • Exam generation    │   │
│   │           │  │               │  │ • Complex reasoning  │   │
│   │ ~50-100ms │  │ ~0.5-2s       │  │ ~2-10s               │   │
│   │ $0        │  │ $0            │  │ $0.001-0.01/query    │   │
│   └───────────┘  └───────────────┘  └──────────────────────┘   │
│                                                                  │
│   ★ Đổi model/provider = đổi config, KHÔNG đổi code            │
│   ★ Tất cả đều qua OpenAI-compatible API                        │
│   ★ Switch ngay lập tức, không cần restart                      │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Fallback Strategy

```python
# wiii/app/llm/fallback.py

FALLBACK_CHAIN = {
    "gemini":    ["ollama", "anthropic"],   # Gemini fail → try local → try Claude
    "ollama":    ["gemini"],                # Local fail → try Gemini
    "anthropic": ["gemini", "ollama"],      # Claude fail → try Gemini → local
    "vllm":      ["ollama", "gemini"],      # vLLM fail → Ollama → Gemini
}


async def agent_with_fallback(query, user_id, agent_name):
    """Try primary provider, fallback if fails."""
    config = AGENT_CONFIG[agent_name]
    providers_to_try = [config["provider"]] + FALLBACK_CHAIN.get(config["provider"], [])

    for provider in providers_to_try:
        try:
            return await agentic_loop(
                query=query,
                user_id=user_id,
                provider=provider,
                model=PROVIDERS[provider].default_model,
                think=config["think"],
            )
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}, trying next...")
            continue

    return "⚠️ Tất cả providers đều không khả dụng. Vui lòng thử lại sau."
```

---

## 9. DEPLOYMENT PLAN

### Phase 1: MVP — Thesis Demo (1 tuần)

**Target:** Chạy được thinking + tool use trên Ollama local.

| Task | Effort | Kết quả |
|---|---|---|
| Cài Ollama + pull qwen3:14b | 30 phút | Model chạy local |
| Implement `providers.py` | 2 giờ | Provider registry |
| Implement `tools.py` | 1 giờ | Tool definitions |
| Implement `agent_loop.py` | 3 giờ | Core agentic loop |
| Implement `tool_executor.py` | 2 giờ | Tool dispatch |
| Test: multi-step query | 2 giờ | ≥2 tool calls working |
| Kết nối Angular frontend SSE | 4 giờ | Streaming UX |

**Kết quả:** Demo được 🧠→🔧→🧠→📝 trên local, $0 cost.

### Phase 2: Multi-Provider (1 tuần)

**Target:** Chạy được trên Gemini API + fallback.

| Task | Effort | Kết quả |
|---|---|---|
| Đăng ký Gemini API key | 30 phút | Free tier |
| Test agentic_loop với Gemini | 2 giờ | Verify cùng code chạy |
| Implement fallback strategy | 2 giờ | Auto-switch khi fail |
| Implement agent config map | 2 giờ | Per-agent provider |
| Streaming UX polish | 3 giờ | Smooth thinking display |

**Kết quả:** Switch giữa local ↔ Gemini seamlessly.

### Phase 3: Production Ready (2 tuần)

**Target:** Triển khai cho users thực.

| Task | Effort | Kết quả |
|---|---|---|
| Setup vLLM/SGLang (nếu có GPU server) | 4 giờ | Multi-user serving |
| Rate limiting + caching | 4 giờ | Cost control |
| Monitoring (tokens, latency, errors) | 4 giờ | Observability |
| Load testing | 4 giờ | Verify concurrent users |
| Security review (prompt injection) | 4 giờ | Safe deployment |

---

## 10. PITFALLS & TROUBLESHOOTING

| Vấn đề | Nguyên nhân | Giải pháp |
|---|---|---|
| Ollama tool call JSON malformed | Model nhỏ (8B) không ổn định | Dùng 14B+ hoặc 30b-a3b MoE |
| Gemini 400 "missing thought_signature" | Tự construct history thay vì append full model_content | Append nguyên `model_content` object |
| Thinking quá dài, chậm response | Model suy nghĩ không giới hạn | Set thinking_budget hoặc dùng `/no_think` |
| History quá lớn, OOM | Include thinking content trong history | Chỉ giữ final content, bỏ thinking |
| Ollama chậm khi nhiều users | Ollama không batch requests | Switch sang vLLM/SGLang |
| Tool không được gọi | Tool description không rõ ràng | Viết description cụ thể hơn |
| Model hallucinate tool names | Tools list quá dài hoặc tên giống nhau | Giới hạn 5-7 tools, tên unique |
| Infinite tool calling loop | Model cứ gọi tool mà không trả answer | Set `max_steps`, thêm instruction trong system prompt |
| Provider API down | Network issue hoặc rate limit | Implement fallback chain |

---

## 11. CHECKLIST

### Trước khi code

- [ ] Cài Ollama + pull model (qwen3:14b recommended)
- [ ] Test: `ollama run qwen3:14b` trả lời được
- [ ] Đăng ký Gemini API key (free tier)
- [ ] Quyết định tech stack: FastAPI (Python) hoặc Spring Boot (Java)

### Implementation

- [ ] `providers.py` — Provider registry + client factory
- [ ] `tools.py` — Tool definitions (chuẩn OpenAI format)
- [ ] `tool_executor.py` — Tool dispatch + actual service calls
- [ ] `agent_loop.py` — Core agentic loop (async)
- [ ] `agent_stream.py` — Streaming version cho SSE
- [ ] `agents.py` — Per-agent configuration
- [ ] `fallback.py` — Provider fallback chain
- [ ] SSE endpoint trong API layer
- [ ] Angular: EventSource consumer + thinking/tool/text UI

### Testing

- [ ] Single tool call (1 round-trip)
- [ ] Multi-step (≥2 tool calls)
- [ ] Parallel tool calls
- [ ] Streaming thinking display
- [ ] Provider switching (đổi config → verify same result)
- [ ] Fallback (kill Ollama → verify switch to Gemini)
- [ ] Error recovery (tool returns error → model handles gracefully)

### Production

- [ ] Rate limiting per user
- [ ] Token usage monitoring
- [ ] Latency tracking per agent
- [ ] Cost tracking per provider
- [ ] Prompt injection protection
- [ ] max_steps safeguard (default 10)
- [ ] Timeout per tool execution (default 30s)

---

*Tài liệu nội bộ — The Wiii Lab | HoLiLiHu Team*
*Phiên bản FINAL v1.0 — 11/02/2026*
*Code pattern: OpenAI-compatible → viết 1 lần, chạy mọi provider, đổi model đổi 1 string*
