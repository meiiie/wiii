"""
WiiiChatModel — AsyncOpenAI-backed chat model satisfying BaseChatModel interface.

De-LangChaining Phase 1: Single implementation replaces:
- ChatOpenAI (langchain-openai)
- ChatGoogleGenerativeAI (langchain-google-genai)
- ChatOllama (langchain-ollama)

All major LLM providers (Gemini, OpenAI, Ollama, Zhipu, OpenRouter) expose
OpenAI-compatible endpoints. This model uses the `openai` AsyncOpenAI SDK
directly, removing the need for per-provider LangChain wrapper packages.

Consumer code (50+ files) continues using `BaseChatModel` interface unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from openai import AsyncOpenAI
from pydantic import Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message conversion helpers
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    HumanMessage: "user",
    AIMessage: "assistant",
    SystemMessage: "system",
    ToolMessage: "tool",
    FunctionMessage: "function",
    ChatMessage: "user",
}


def _lc_to_openai_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain message list to OpenAI-compatible format."""
    result: list[dict] = []
    for msg in messages:
        role = _ROLE_MAP.get(type(msg), "user")

        # Tool messages need tool_call_id
        if isinstance(msg, ToolMessage):
            entry: dict[str, Any] = {
                "role": "tool",
                "content": _extract_text(msg.content),
                "tool_call_id": str(msg.tool_call_id) if msg.tool_call_id else "",
            }
            result.append(entry)
            continue

        entry = {"role": role}

        # Content
        content = _extract_text(msg.content)
        if content:
            entry["content"] = content

        # Tool calls (AI messages with tool_calls)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["args"]
                        if isinstance(tc["args"], str)
                        else __import__("json").dumps(tc["args"], ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(msg.tool_calls)
            ]

        # Name (for function messages)
        if isinstance(msg, FunctionMessage):
            entry["name"] = msg.name or ""
            entry["content"] = content

        result.append(entry)
    return result


def _extract_text(content: Any) -> str:
    """Extract text content from message content (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif "text" in block:
                    parts.append(block["text"])
        return "\n".join(parts)
    return str(content) if content is not None else ""


def _openai_response_to_chat_result(response: Any) -> ChatResult:
    """Convert OpenAI ChatCompletion to LangChain ChatResult."""
    generations: list[ChatGeneration] = []
    for choice in response.choices:
        message = choice.message
        content = message.content or ""

        # Extract tool calls if present
        tool_calls = []
        if message.tool_calls:
            import json as _json

            for tc in message.tool_calls:
                args = tc.function.arguments
                try:
                    parsed_args = _json.loads(args) if isinstance(args, str) else args
                except (_json.JSONDecodeError, TypeError):
                    parsed_args = args
                tool_calls.append(
                    {
                        "name": tc.function.name,
                        "args": parsed_args,
                        "id": tc.id,
                        "type": "tool_call",
                    }
                )

        ai_msg = AIMessage(
            content=content,
            tool_calls=tool_calls,
            additional_kwargs={},
        )
        gen = ChatGeneration(
            message=ai_msg,
            generation_info={
                "finish_reason": choice.finish_reason,
            },
        )
        generations.append(gen)

    token_usage = getattr(response, "usage", None)
    llm_output = {}
    if token_usage:
        llm_output["token_usage"] = {
            "prompt_tokens": token_usage.prompt_tokens or 0,
            "completion_tokens": token_usage.completion_tokens or 0,
            "total_tokens": token_usage.total_tokens or 0,
        }

    return ChatResult(generations=generations, llm_output=llm_output)


def _openai_chunk_to_generation_chunk(chunk: Any) -> Optional[ChatGenerationChunk]:
    """Convert OpenAI stream chunk to LangChain ChatGenerationChunk."""
    if not chunk.choices:
        return None

    choice = chunk.choices[0]
    delta = choice.delta

    content = delta.content or ""
    tool_calls = []
    if delta.tool_calls:
        for tc in delta.tool_calls:
            tool_calls.append(
                {
                    "name": tc.function.name if tc.function else "",
                    "args": tc.function.arguments if tc.function else "",
                    "id": tc.id or "",
                    "index": tc.index if hasattr(tc, "index") else 0,
                    "type": "tool_call_chunk",
                }
            )

    ai_chunk = AIMessage(
        content=content,
        tool_calls=tool_calls,
        additional_kwargs={},
    )

    return ChatGenerationChunk(
        message=ai_chunk,
        generation_info={
            "finish_reason": choice.finish_reason,
        },
    )


_ZHIPU_HOSTS = ("open.bigmodel.cn",)

_ZHIPU_ALLOWED_PARAMS = frozenset({
    "model", "messages", "temperature", "top_p", "max_tokens",
    "stream", "stop", "tools", "tool_choice",
})


def _strip_unsupported_params(api_kwargs: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Remove parameters not supported by the target provider."""
    if any(host in base_url for host in _ZHIPU_HOSTS):
        return {k: v for k, v in api_kwargs.items() if k in _ZHIPU_ALLOWED_PARAMS}
    return api_kwargs


# ---------------------------------------------------------------------------
# WiiiChatModel
# ---------------------------------------------------------------------------


class WiiiChatModel(BaseChatModel):
    """AsyncOpenAI-backed chat model satisfying the BaseChatModel interface.

    Usage in provider files::

        llm = WiiiChatModel(
            model="gemini-3.1-flash-lite-preview",
            api_key=settings.google_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=0.5,
        )

    All consumers continue to use ``BaseChatModel`` methods:
    ``.ainvoke()``, ``.astream()``, ``.bind_tools()``, etc.
    """

    # Pydantic fields
    model: str = Field(description="Model name (e.g., gemini-3.1-flash-lite-preview)")
    api_key: str = Field(description="API key for the provider")
    base_url: str = Field(default="", description="OpenAI-compatible base URL")
    temperature: float = Field(default=0.5, description="Sampling temperature")
    streaming: bool = Field(default=True, description="Enable streaming")
    model_kwargs: dict = Field(
        default_factory=dict,
        description="Extra kwargs passed to the API (e.g., extra_body for thinking)",
    )

    # Cached client
    _client: Optional[AsyncOpenAI] = None

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True

    @property
    def _llm_type(self) -> str:
        return "wiii-chat"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the AsyncOpenAI client."""
        if self._client is None:
            kwargs: dict[str, Any] = {
                "api_key": self.api_key,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            object.__setattr__(self, "_client", AsyncOpenAI(**kwargs))
        return self._client

    # ------------------------------------------------------------------ #
    # Core: sync _generate (required by BaseChatModel)
    # ------------------------------------------------------------------ #
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Sync generate — delegates to async via event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context (e.g., Jupyter) — use nest_asyncio fallback
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._agenerate(messages, stop=stop, run_manager=None, **kwargs),
                )
                return future.result()
        else:
            return asyncio.run(
                self._agenerate(messages, stop=stop, run_manager=None, **kwargs)
            )

    # ------------------------------------------------------------------ #
    # Core: async _agenerate
    # ------------------------------------------------------------------ #
    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate using OpenAI Chat Completions API."""
        client = self._get_client()
        openai_messages = _lc_to_openai_messages(messages)

        # Merge model_kwargs with call-level kwargs
        api_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            **self.model_kwargs,
        }

        # Tools from bind_tools()
        if "tools" in kwargs:
            api_kwargs["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs:
            api_kwargs["tool_choice"] = kwargs["tool_choice"]

        if stop:
            api_kwargs["stop"] = stop

        api_kwargs = _strip_unsupported_params(api_kwargs, self.base_url)
        response = await client.chat.completions.create(**api_kwargs)
        return _openai_response_to_chat_result(response)

    # ------------------------------------------------------------------ #
    # Core: async _astream
    # ------------------------------------------------------------------ #
    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Async stream using OpenAI Chat Completions API."""
        client = self._get_client()
        openai_messages = _lc_to_openai_messages(messages)

        api_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.model_kwargs,
        }

        if "tools" in kwargs:
            api_kwargs["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs:
            api_kwargs["tool_choice"] = kwargs["tool_choice"]

        if stop:
            api_kwargs["stop"] = stop

        api_kwargs = _strip_unsupported_params(api_kwargs, self.base_url)
        stream = await client.chat.completions.create(**api_kwargs)
        async for chunk in stream:
            gen_chunk = _openai_chunk_to_generation_chunk(chunk)
            if gen_chunk is not None:
                yield gen_chunk

    # ------------------------------------------------------------------ #
    # bind_tools override — convert LC tools to OpenAI format
    # ------------------------------------------------------------------ #
    def bind_tools(self, tools: list, **kwargs: Any) -> "WiiiChatModel":
        """Bind tools to the model for tool calling.

        Converts LangChain tool definitions to OpenAI function format
        and stores them for use in _agenerate/_astream.
        """
        openai_tools = []
        for tool in tools:
            if isinstance(tool, dict) and "type" in tool:
                # Already in OpenAI format
                openai_tools.append(tool)
            elif hasattr(tool, "args_schema"):
                # LangChain @tool / StructuredTool
                schema = tool.args_schema.schema()
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": schema,
                        },
                    }
                )
            elif hasattr(tool, "name") and hasattr(tool, "description"):
                # Simple tool object
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": getattr(tool, "parameters", {}),
                        },
                    }
                )

        # Return a new instance with tools bound
        return self.model_copy(
            update={
                "model_kwargs": {
                    **self.model_kwargs,
                    "tools": openai_tools,
                    **kwargs,
                }
            }
        )
