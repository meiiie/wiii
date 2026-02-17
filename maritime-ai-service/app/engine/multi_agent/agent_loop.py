"""
Generalized Agentic Loop — Multi-step tool-calling pattern.

Sprint 57: Extracts the ReAct pattern from tutor_node._react_loop()
into a reusable function that any LangGraph node can use.

Sprint 69: Added event_queue to LoopConfig for real-time streaming.
When event_queue is set, pushes thinking_delta/tool_call/tool_result
events during execution (not just after completion).

Two code paths:
  Path A: UnifiedLLMClient (AsyncOpenAI SDK) — when enable_unified_client=True
  Path B: LangChain bind_tools fallback — existing behavior

Feature-gated: enable_agentic_loop=False by default.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoopConfig:
    """Configuration for an agentic loop execution."""

    max_steps: int = 5
    temperature: float = 0.5
    provider: Optional[str] = None
    model: Optional[str] = None
    tier: str = "moderate"
    early_exit_confidence: float = 0.70
    system_prompt: Optional[str] = None
    # Sprint 69: asyncio.Queue for real-time streaming events
    event_queue: Optional[Any] = None
    # Sprint 69: node name for event attribution
    node_id: Optional[str] = None


@dataclass
class LoopResult:
    """Result of an agentic loop execution."""

    response: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    thinking: Optional[str] = None
    steps: int = 0
    confidence: float = 0.0


async def agentic_loop(
    query: str,
    tools: List[Callable],
    system_prompt: str,
    config: Optional[LoopConfig] = None,
    context: Optional[Dict[str, Any]] = None,
) -> LoopResult:
    """
    Generalized multi-step tool-calling loop.

    Pattern: messages → LLM → check tool_calls → execute → append results → repeat

    Uses UnifiedLLMClient (AsyncOpenAI) when available,
    falls back to LangChain bind_tools otherwise.

    Args:
        query: User query
        tools: List of callable tool functions
        system_prompt: System prompt for the LLM
        config: Loop configuration (max_steps, temperature, etc.)
        context: Additional context dict

    Returns:
        LoopResult with response, tool calls, sources, thinking, etc.
    """
    config = config or LoopConfig()

    # Try Path A (AsyncOpenAI) first, fall back to Path B (LangChain)
    if _unified_client_available():
        return await _loop_with_unified_client(
            query, tools, system_prompt, config, context,
        )
    else:
        return await _loop_with_langchain(
            query, tools, system_prompt, config, context,
        )


async def agentic_loop_streaming(
    query: str,
    tools: List[Callable],
    system_prompt: str,
    config: Optional[LoopConfig] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator:
    """
    Streaming variant of the agentic loop.

    Sprint 69: Real-time streaming — creates an event_queue, runs the loop
    concurrently, and yields events as they arrive (not post-completion).

    Yields StreamEvent-compatible dicts with types:
    thinking_delta, TOOL_CALL, TOOL_RESULT, THINKING, ANSWER.
    """
    config = config or LoopConfig()
    eq: asyncio.Queue = asyncio.Queue()
    config.event_queue = eq

    loop_task = asyncio.create_task(
        agentic_loop(query, tools, system_prompt, config, context),
    )

    # Yield events as they arrive in real-time
    while not loop_task.done() or not eq.empty():
        try:
            event = await asyncio.wait_for(eq.get(), timeout=0.1)
            yield event
        except asyncio.TimeoutError:
            if loop_task.done():
                # Drain remaining events
                while not eq.empty():
                    yield eq.get_nowait()
                break
        except Exception:
            break

    # Get the final result
    try:
        result = loop_task.result()
        yield {"type": "answer", "content": result.response}
    except Exception as e:
        logger.error("[AGENTIC_LOOP] Streaming loop error: %s", e)
        yield {"type": "error", "content": str(e)}


def _unified_client_available() -> bool:
    """Check if UnifiedLLMClient is initialized and available."""
    try:
        from app.core.config import settings

        if not getattr(settings, "enable_agentic_loop", False):
            return False
        if not getattr(settings, "enable_unified_client", False):
            return False

        from app.engine.llm_providers.unified_client import UnifiedLLMClient

        initialized = UnifiedLLMClient.is_initialized()
        has_providers = len(
            UnifiedLLMClient.get_available_providers(),
        ) > 0
        return initialized and has_providers
    except Exception:
        return False


async def _push_event(queue: Optional[Any], event: Dict[str, Any]) -> None:
    """Push event to queue if available (non-blocking)."""
    if queue is not None:
        try:
            queue.put_nowait(event)
        except Exception:
            pass


async def _loop_with_unified_client(
    query: str,
    tools: List[Callable],
    system_prompt: str,
    config: LoopConfig,
    context: Optional[Dict[str, Any]] = None,
) -> LoopResult:
    """Path A: Use AsyncOpenAI SDK for tool calling."""
    from app.engine.llm_providers.unified_client import UnifiedLLMClient

    client = UnifiedLLMClient.get_client(config.provider)
    model = config.model or UnifiedLLMClient.get_model(config.provider, config.tier)

    # Build OpenAI-format tool definitions
    openai_tools = _tools_to_openai_format(tools)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    all_tool_calls = []
    thinking = None
    node_id = config.node_id

    for step in range(config.max_steps):
        logger.info(
            "[AGENTIC_LOOP] Step %d/%d", step + 1, config.max_steps,
        )

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        # Sprint 69: Stream if event_queue is set for real-time thinking
        if config.event_queue is not None:
            kwargs["stream"] = True
            stream = await client.chat.completions.create(**kwargs)

            # Accumulate streamed response
            content_parts = []
            streamed_tool_calls: Dict[int, Dict[str, Any]] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Stream thinking/content tokens
                if delta.content:
                    content_parts.append(delta.content)
                    await _push_event(config.event_queue, {
                        "type": "thinking_delta",
                        "content": delta.content,
                        "node": node_id,
                    })

                # Accumulate tool calls from stream
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in streamed_tool_calls:
                            streamed_tool_calls[idx] = {
                                "id": "", "name": "", "arguments": "",
                            }
                        tc_acc = streamed_tool_calls[idx]
                        if tc_delta.id:
                            tc_acc["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tc_acc["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tc_acc["arguments"] += tc_delta.function.arguments

            full_content = "".join(content_parts)

            # Check if we got tool calls
            if not streamed_tool_calls:
                return LoopResult(
                    response=full_content,
                    tool_calls=all_tool_calls,
                    thinking=thinking,
                    steps=step + 1,
                )

            # Build assistant message for history
            tc_list_for_msg = []
            for idx in sorted(streamed_tool_calls.keys()):
                tc_info = streamed_tool_calls[idx]
                tc_list_for_msg.append({
                    "id": tc_info["id"],
                    "type": "function",
                    "function": {
                        "name": tc_info["name"],
                        "arguments": tc_info["arguments"],
                    },
                })
            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": tc_list_for_msg,
            })

            # Execute tool calls
            for idx in sorted(streamed_tool_calls.keys()):
                tc_info = streamed_tool_calls[idx]
                func_name = tc_info["name"]
                try:
                    func_args = json.loads(tc_info["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                tc_record = {
                    "name": func_name,
                    "args": func_args,
                    "id": tc_info["id"],
                }
                all_tool_calls.append(tc_record)

                await _push_event(config.event_queue, {
                    "type": "tool_call",
                    "content": tc_record,
                    "node": node_id,
                })

                result = await _execute_tool(tools, func_name, func_args)

                await _push_event(config.event_queue, {
                    "type": "tool_result",
                    "content": {
                        "name": func_name,
                        "result": str(result)[:500],
                        "id": tc_info["id"],
                    },
                    "node": node_id,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_info["id"],
                    "content": str(result),
                })

        else:
            # Non-streaming path (identical to Sprint 68)
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            if not message.tool_calls:
                return LoopResult(
                    response=message.content or "",
                    tool_calls=all_tool_calls,
                    thinking=thinking,
                    steps=step + 1,
                )

            messages.append(_message_to_dict(message))

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                all_tool_calls.append({
                    "name": func_name,
                    "args": func_args,
                    "id": tool_call.id,
                })

                result = await _execute_tool(tools, func_name, func_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

    # Exhausted max steps — get final response
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=config.temperature,
    )
    return LoopResult(
        response=response.choices[0].message.content or "",
        tool_calls=all_tool_calls,
        thinking=thinking,
        steps=config.max_steps,
    )


async def _loop_with_langchain(
    query: str,
    tools: List[Callable],
    system_prompt: str,
    config: LoopConfig,
    context: Optional[Dict[str, Any]] = None,
) -> LoopResult:
    """Path B: Use LangChain bind_tools (existing pattern from tutor_node)."""
    from app.engine.llm_pool import get_llm_moderate, get_llm_deep, get_llm_light

    tier_map = {
        "deep": get_llm_deep,
        "moderate": get_llm_moderate,
        "light": get_llm_light,
    }
    get_llm = tier_map.get(config.tier, get_llm_moderate)
    llm = get_llm()

    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    from langchain_core.messages import (
        SystemMessage, HumanMessage, AIMessage, ToolMessage,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]

    all_tool_calls = []
    thinking = None
    node_id = config.node_id

    for step in range(config.max_steps):
        logger.info(
            "[AGENTIC_LOOP] LangChain step %d/%d",
            step + 1, config.max_steps,
        )

        response = await llm_with_tools.ainvoke(messages)

        # Sprint 69: Push thinking content if event_queue is set
        if response.content and config.event_queue is not None:
            await _push_event(config.event_queue, {
                "type": "thinking_delta",
                "content": response.content,
                "node": node_id,
            })

        if not response.tool_calls:
            content = response.content or ""
            return LoopResult(
                response=content,
                tool_calls=all_tool_calls,
                thinking=thinking,
                steps=step + 1,
            )

        # Execute tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", f"call_{step}")

            tc_record = {
                "name": tool_name,
                "args": tool_args,
                "id": tool_id,
            }
            all_tool_calls.append(tc_record)

            # Sprint 69: Push tool_call event
            await _push_event(config.event_queue, {
                "type": "tool_call",
                "content": tc_record,
                "node": node_id,
            })

            result = await _execute_tool(tools, tool_name, tool_args)

            # Sprint 69: Push tool_result event
            await _push_event(config.event_queue, {
                "type": "tool_result",
                "content": {
                    "name": tool_name,
                    "result": str(result)[:500],
                    "id": tool_id,
                },
                "node": node_id,
            })

            messages.append(AIMessage(content="", tool_calls=[tool_call]))
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

    # Exhausted max steps
    final_msg = await llm.ainvoke(messages)
    return LoopResult(
        response=final_msg.content or "",
        tool_calls=all_tool_calls,
        thinking=thinking,
        steps=config.max_steps,
    )


def _tools_to_openai_format(tools: List[Callable]) -> List[Dict[str, Any]]:
    """Convert LangChain tool functions to OpenAI tool format."""
    result = []
    for tool in tools:
        name = getattr(tool, "name", getattr(tool, "__name__", "unknown"))
        description = getattr(tool, "description", "")

        # Try to get input schema from LangChain tool
        schema = {"type": "object", "properties": {}}
        if hasattr(tool, "args_schema") and tool.args_schema:
            try:
                schema = tool.args_schema.model_json_schema()
                schema.pop("title", None)
                schema.pop("description", None)
            except Exception:
                pass

        if "properties" not in schema:
            schema["properties"] = {}

        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": schema,
            },
        })
    return result


async def _execute_tool(
    tools: List[Callable], name: str, args: Dict[str, Any]
) -> str:
    """Find and execute a tool by name."""
    for tool in tools:
        tool_name = getattr(tool, "name", getattr(tool, "__name__", ""))
        if tool_name == name:
            try:
                if hasattr(tool, "ainvoke"):
                    result = await tool.ainvoke(args)
                elif hasattr(tool, "coroutine"):
                    result = await tool.coroutine(**args)
                else:
                    result = tool(**args)
                return str(result)
            except Exception as e:
                logger.error("[AGENTIC_LOOP] Tool %s error: %s", name, e)
                return f"Error executing {name}: {e}"

    return f"Tool '{name}' not found"


def _message_to_dict(message) -> Dict[str, Any]:
    """Convert OpenAI message object to dict for messages list.

    Preserves Gemini thought_signature when present (required by
    Gemini 3 API for multi-step function calling).
    """
    msg = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        tool_calls_list = []
        for tc in message.tool_calls:
            tc_dict: Dict[str, Any] = {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            # Gemini 3: preserve thought_signature for multi-turn
            # tool calling (returned in extra_content.google)
            extra = getattr(tc, "extra_content", None)
            if extra is not None:
                tc_dict["extra_content"] = (
                    extra if isinstance(extra, dict)
                    else getattr(extra, "__dict__", {})
                )
            tool_calls_list.append(tc_dict)
        msg["tool_calls"] = tool_calls_list
    return msg
