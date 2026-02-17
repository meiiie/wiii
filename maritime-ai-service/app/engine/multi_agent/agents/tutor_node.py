"""
Tutor Agent Node - Teaching Specialist (SOTA ReAct Pattern)

Handles educational interactions with tool-enabled RAG retrieval.

**SOTA 2026 Pattern:**
- Tool-Enabled Agent with ReAct Loop
- RAG-First approach via system prompt
- Utility tools: calculator, datetime, web search
- Uses CorrectiveRAG internally via tool_knowledge_search

**Integrated with agents/ framework for config and tracing.**
"""

import logging
from typing import Optional, List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from app.core.config import settings
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.services.output_processor import extract_thinking_from_response
from app.engine.multi_agent.state import AgentState
from app.engine.agents import TUTOR_AGENT_CONFIG
from app.engine.tools.rag_tools import (
    tool_knowledge_search,
    get_last_retrieved_sources,
    get_last_native_thinking,  # CHỈ THỊ SỐ 29 v9: Option B+ thinking propagation
    get_last_reasoning_trace,  # CHỈ THỊ SỐ 31 v3: CRAG trace propagation
    get_last_confidence,  # SOTA 2025: Confidence-based early termination
    clear_retrieved_sources
)
from app.engine.tools.utility_tools import tool_calculator, tool_current_datetime
from app.engine.tools.web_search_tools import tool_web_search
# SOTA 2025: PromptLoader for YAML-driven persona (CrewAI pattern)
from app.prompts.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL INSTRUCTION (Appended to YAML-driven prompt)
# =============================================================================

TOOL_INSTRUCTION_DEFAULT = """
## QUY TẮC TOOL (CRITICAL - RAG-First Pattern):

1. **LUÔN LUÔN** sử dụng tool `tool_knowledge_search` để tìm kiếm kiến thức **TRƯỚC KHI** trả lời bất kỳ câu hỏi nào về kiến thức chuyên ngành.

2. **KHÔNG BAO GIỜ** trả lời từ kiến thức riêng mà không tìm kiếm trước.

3. Sau khi tìm kiếm, giảng dạy **DỰA TRÊN** kết quả tìm được.

4. **TRÍCH DẪN nguồn** trong câu trả lời.

## TOOL BỔ SUNG:
- `tool_calculator`: Tính toán số học (cộng, trừ, nhân, chia, sqrt, sin, cos, log, v.v.)
- `tool_current_datetime`: Xem ngày giờ hiện tại (UTC+7)
- `tool_web_search`: Tìm kiếm thông tin trên web khi cần thông tin mới nhất hoặc ngoài cơ sở dữ liệu nội bộ
"""

# Legacy alias
TOOL_INSTRUCTION = TOOL_INSTRUCTION_DEFAULT


class TutorAgentNode:
    """
    Tutor Agent - Teaching specialist with SOTA ReAct pattern.
    
    Responsibilities:
    - Explain concepts clearly with RAG-backed knowledge
    - Create quizzes and exercises
    - Adapt to learner level
    - Always cite sources
    
    SOTA Pattern: Tool-Enabled Agent with RAG-First approach
    """
    
    def __init__(self):
        """Initialize Tutor Agent with YAML-driven persona (SOTA 2025)."""
        self._prompt_loader = get_prompt_loader()  # SOTA: YAML persona
        self._llm = None
        self._llm_with_tools = None
        self._config = TUTOR_AGENT_CONFIG
        self._tools = [tool_knowledge_search, tool_calculator, tool_current_datetime, tool_web_search]

        # Sprint 95: Conditionally add character tools
        self._character_tools_enabled = False
        try:
            from app.core.config import settings as _settings
            if _settings.enable_character_tools:
                from app.engine.character.character_tools import get_character_tools
                char_tools = get_character_tools()
                self._tools.extend(char_tools)
                self._character_tools_enabled = True
                logger.info("[TUTOR_AGENT] Character tools enabled: %d tools", len(char_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Character tools not available: %s", e)

        self._init_llm()
        logger.info("TutorAgentNode initialized with YAML persona, tools: %d", len(self._tools))
    
    def _init_llm(self):
        """Initialize teaching LLM with tools and native thinking."""
        try:
            # Sprint 69: Use AgentConfigRegistry for per-node LLM config
            self._llm = AgentConfigRegistry.get_llm("tutor_agent")
            # Bind tools to LLM (SOTA pattern)
            self._llm_with_tools = self._llm.bind_tools(self._tools)
            logger.info("[TUTOR_AGENT] LLM bound with %d tools (via AgentConfigRegistry)", len(self._tools))
        except Exception as e:
            logger.error("Failed to initialize Tutor LLM: %s", e)
            self._llm = None
            self._llm_with_tools = None
    
    def _build_system_prompt(self, context: dict, query: str) -> str:
        """
        Build dynamic system prompt from YAML persona (SOTA 2025).
        
        Pattern: CrewAI YAML → Runtime injection with PromptLoader
        
        Default pronouns: AI xưng "tôi", gọi user là "bạn"
        (Changes only if user requests via Insights/Memory)
        
        Args:
            context: Dict with user_name, user_role, etc.
            query: User query
            
        Returns:
            Complete system prompt string
        """
        user_name = context.get("user_name")
        user_role = context.get("user_role", "student")
        is_follow_up = context.get("is_follow_up", False)
        recent_phrases = context.get("recent_phrases", [])
        pronoun_style = context.get("pronoun_style")  # From SessionState
        user_facts = context.get("user_facts", [])
        
        # Build base prompt from YAML
        # Sprint 115: Forward total_responses + mood_hint for identity anchor + mood
        base_prompt = self._prompt_loader.build_system_prompt(
            role=user_role,
            user_name=user_name,
            user_facts=user_facts,
            is_follow_up=is_follow_up,
            recent_phrases=recent_phrases,
            pronoun_style=pronoun_style,
            total_responses=context.get("total_responses", 0),
            name_usage_count=context.get("name_usage_count", 0),
            mood_hint=context.get("mood_hint", ""),
            # Sprint 124: Per-user character blocks
            user_id=context.get("user_id", "__global__"),
        )
        
        # Build context string for query
        # Sprint 77: Exclude history fields — they're now in LangChain messages
        _exclude_keys = {
            "user_facts", "pronoun_style", "recent_phrases",
            "conversation_history", "langchain_messages", "conversation_summary",
        }
        context_str = "\n".join([
            f"- {k}: {v}" for k, v in context.items() if v and k not in _exclude_keys
        ]) or "Không có thông tin bổ sung"
        
        # Load domain-specific tool instruction if available
        tool_instruction = TOOL_INSTRUCTION_DEFAULT
        try:
            from app.domains.registry import get_domain_registry
            registry = get_domain_registry()
            domain_id = context.get("domain_id", settings.default_domain)
            domain = registry.get(domain_id)
            if domain:
                tool_instruction = domain.get_tool_instruction()
        except Exception as e:
            logger.debug("Failed to load domain tool instruction: %s", e)

        # Build skill context section if available (progressive disclosure)
        skill_section = ""
        skill_context = context.get("skill_context")
        if skill_context:
            skill_section = f"""
## Tài liệu tham khảo (Skill Context):
{skill_context}
"""

        # Sprint 122 (Bug F4): Removed core_memory_block injection.
        # User facts now ONLY via build_system_prompt() → "THÔNG TIN NGƯỜI DÙNG".
        core_memory_section = ""

        # Sprint 97: Character tool instruction when enabled
        character_tool_section = ""
        if self._character_tools_enabled:
            character_tool_section = """
## CONG CU GHI NHO (Character Tools):
- tool_character_note(note, block): Ghi chu khi hoc dieu moi, nhan ra pattern cua user, topic hay.
  Block: learned_lessons | favorite_topics | user_patterns | self_notes
- tool_character_log_experience(content, experience_type): Ghi trai nghiem dang nho.
  Type: milestone | learning | funny | feedback
KHI NAO GHI: User chia se thong tin moi, giai thich thanh cong, nhan feedback.
KHI NAO KHONG: Cau hoi binh thuong, thong tin da biet.
"""

        # Append tool instruction, skill context, core memory, and user context
        full_prompt = f"""{base_prompt}

{tool_instruction}
{character_tool_section}{skill_section}{core_memory_section}
## Ngữ cảnh học viên:
{context_str}

## Yêu cầu:
{query}

## QUY TẮC ĐỘ DÀI: Trả lời tối đa 400 từ. Nếu cần dài hơn, chia thành các phần ngắn gọn.
"""
        
        logger.debug("[TUTOR_AGENT] Built dynamic prompt from YAML (%d chars)", len(full_prompt))
        return full_prompt
    
    async def process(self, state: AgentState) -> AgentState:
        """
        Process educational request with ReAct pattern.
        
        SOTA Pattern: Think → Act → Observe → Repeat
        
        CHỈ THỊ SỐ 29 v9: Option B+ - Propagates thinking to state for API transparency.
        Combines thinking from:
        1. RAG tool (via get_last_native_thinking)
        2. Tutor LLM response (extracted in _react_loop)
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tutor output, sources, tools_used, and thinking
        """
        query = state.get("query", "")
        context = state.get("context", {})
        learning_context = state.get("learning_context", {})

        try:
            # Sprint 66: Per-request thinking effort override
            thinking_effort = state.get("thinking_effort")
            if thinking_effort:
                llm = AgentConfigRegistry.get_llm("tutor_agent", effort_override=thinking_effort)
                self._llm = llm
                self._llm_with_tools = llm.bind_tools(self._tools)
                logger.info("[TUTOR_AGENT] Thinking effort override: %s", thinking_effort)

            # Sprint 69: Get event bus queue for intra-node streaming
            event_queue = None
            bus_id = state.get("_event_bus_id")
            if bus_id:
                from app.engine.multi_agent.graph_streaming import _get_event_queue
                event_queue = _get_event_queue(bus_id)

            # Merge context and inject skill_context from supervisor
            merged_context = {**context, **learning_context}
            skill_context = state.get("skill_context")
            if skill_context:
                merged_context["skill_context"] = skill_context

            # Execute ReAct loop - now returns thinking + bus streaming flag
            response, sources, tools_used, thinking, answer_streamed = await self._react_loop(
                query=query,
                context=merged_context,
                event_queue=event_queue,
            )

            # Sprint 74: Signal to graph_streaming whether answer was already streamed via bus
            if answer_streamed:
                state["_answer_streamed_via_bus"] = True

            # Update state with results
            state["tutor_output"] = response
            state["sources"] = sources
            state["tools_used"] = tools_used
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["tutor"] = response
            state["agent_outputs"]["tutor_tools_used"] = tools_used  # SOTA: Track tool usage
            state["current_agent"] = "tutor_agent"
            
            # CHỈ THỊ SỐ 29 v9: Set thinking in state for SOTA reasoning transparency
            # This follows the same pattern as rag_node.py
            if thinking:
                state["thinking"] = thinking
                logger.info("[TUTOR_AGENT] Thinking propagated to state: %d chars", len(thinking))
            
            # CHỈ THỊ SỐ 31 v3 SOTA: Propagate CRAG trace for synthesizer merge
            # This follows LangGraph shared state pattern
            crag_trace = get_last_reasoning_trace()
            if crag_trace:
                state["reasoning_trace"] = crag_trace
                logger.info("[TUTOR_AGENT] CRAG trace propagated: %d steps", crag_trace.total_steps)
            
            logger.info("[TUTOR_AGENT] ReAct complete: %d tool calls, %d sources", len(tools_used), len(sources))
            
        except Exception as e:
            logger.error("[TUTOR_AGENT] Error: %s", e)
            state["tutor_output"] = "Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại."
            state["error"] = "tutor_error"
            state["sources"] = []
            state["tools_used"] = []
        
        return state
    
    async def _react_loop(
        self,
        query: str,
        context: dict,
        event_queue=None,
    ) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Optional[str], bool]:
        """
        Execute ReAct loop: Think → Act → Observe.

        SOTA Pattern from OpenAI Agents SDK / Anthropic Claude.

        CHỉ THỊ SỐ 29 v9: Now returns thinking for SOTA reasoning transparency.
        Combines thinking from:
        1. RAG tool (get_last_native_thinking)
        2. Tutor LLM final response (extract_thinking_from_response)

        Args:
            query: User query
            context: Additional context
            event_queue: Sprint 69 asyncio.Queue for intra-node streaming

        Returns:
            Tuple of (response, sources, tools_used, thinking, answer_streamed_via_bus)
        """
        if not self._llm_with_tools:
            return self._fallback_response(query), [], [], None, False
        
        # Clear previous sources (also clears thinking)
        clear_retrieved_sources()
        
        # SOTA 2025: Build dynamic prompt from YAML
        system_prompt = self._build_system_prompt(context, query)

        # Initialize messages — Sprint 77: inject conversation history
        messages = [SystemMessage(content=system_prompt)]
        lc_messages = context.get("langchain_messages", [])
        if lc_messages:
            messages.extend(lc_messages[-10:])  # Last 10 turns for tutor
        messages.append(HumanMessage(content=query))
        
        tools_used = []
        max_iterations = 2  # Sprint 103b: 3 → 2 (most queries resolve in 1-2 iterations)
        final_response = ""
        llm_thinking = None  # Thinking from final LLM response
        _answer_streamed_via_bus = False  # Sprint 74: Track if answer was streamed via bus

        # Sprint 70: Sub-chunk size for smooth streaming (matches graph_streaming.py)
        _CHUNK_SIZE = 40  # ~8-10 words per sub-chunk (Sprint 103b: was 12)
        _CHUNK_DELAY = 0.008  # 8ms between sub-chunks (Sprint 103b: was 18ms)

        # Sprint 69: Helper for intra-node event push
        async def _push(evt):
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception as exc:
                    logger.warning("[TUTOR_AGENT] Bus push failed: %s", exc)

        def _extract_chunk_text(content) -> str:
            """Extract text from LLM chunk content (handles str and Gemini list format)."""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        async def _push_thinking_deltas(text: str):
            """Push thinking_delta events with sub-chunking for smooth streaming."""
            import asyncio
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({
                    "type": "thinking_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        async def _push_answer_deltas(text: str):
            """Sprint 74: Push answer_delta events with sub-chunking for real-time answer streaming."""
            import asyncio
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({
                    "type": "answer_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        _BULK_SIZE = 200  # Sprint 75: Large chunks for fast re-emission

        async def _push_answer_bulk(text: str):
            """Sprint 75: Push answer content in large chunks with no delay.

            Used when content was already shown via thinking_delta — the answer_delta
            is just for populating the answer section, no need for smooth streaming.
            Drops answer re-emission from ~7s to <0.5s.
            """
            for i in range(0, len(text), _BULK_SIZE):
                sub = text[i:i + _BULK_SIZE]
                await _push({
                    "type": "answer_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })

        # ReAct Loop
        for iteration in range(max_iterations):
            logger.info("[TUTOR_AGENT] ReAct iteration %d/%d", iteration + 1, max_iterations)

            # THINK: LLM reasons and decides action
            # Sprint 70: Stream LLM tokens for true interleaved thinking
            if event_queue is not None:
                # Emit thinking_start for this iteration
                await _push({
                    "type": "thinking_start",
                    "content": f"Suy nghĩ (lần {iteration + 1})",
                    "node": "tutor_agent",
                })
                response = None
                chunk_count = 0
                async for chunk in self._llm_with_tools.astream(messages):
                    chunk_count += 1
                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk
                    # Sprint 70: Extract text and sub-chunk for smooth streaming
                    text = _extract_chunk_text(chunk.content)
                    if text:
                        await _push_thinking_deltas(text)
                logger.debug("[TUTOR_AGENT] .astream() yielded %d chunks", chunk_count)
                if response is None:
                    # Empty response fallback
                    from langchain_core.messages import AIMessage as _AIMsg
                    response = _AIMsg(content="")
                # Emit thinking_end for this iteration
                await _push({
                    "type": "thinking_end",
                    "content": "",
                    "node": "tutor_agent",
                })
            else:
                response = await self._llm_with_tools.ainvoke(messages)

            # Check if LLM wants to call tools
            if not response.tool_calls:
                # No tool calls = LLM is done, extract final response AND thinking
                final_response, llm_thinking = self._extract_content_with_thinking(response.content)
                # Sprint 74 fix: Content was already streamed as thinking_delta.
                # Now push as answer_delta so it appears in the answer section too.
                # Sprint 75: Use bulk push (no delay) since content already displayed
                # via thinking — drops re-emission from ~7s to <0.5s.
                if event_queue is not None:
                    _answer_streamed_via_bus = True
                    if final_response:
                        await _push_answer_bulk(final_response)
                logger.info("[TUTOR_AGENT] No more tool calls, generating final response")
                break

            # ACT: Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"call_{iteration}")

                # Sprint 69: Push tool_call event
                await _push({
                    "type": "tool_call",
                    "content": {"name": tool_name, "args": tool_args, "id": tool_id},
                    "node": "tutor_agent",
                })

                logger.info("[TUTOR_AGENT] Calling tool: %s with args: %s", tool_name, tool_args)
                
                if tool_name in ("tool_knowledge_search", "tool_maritime_search"):
                    try:
                        # Execute the tool
                        search_query = tool_args.get("query", query)
                        result = await tool_knowledge_search.ainvoke({"query": search_query})

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": f"Tra cứu: {search_query[:60]}..." if len(search_query) > 60 else f"Tra cứu: {search_query}",
                            "iteration": iteration + 1
                        })

                        # Sprint 69: Push tool_result event
                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        # OBSERVE: Add result to conversation
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id
                        ))

                        logger.info("[TUTOR_AGENT] Tool result length: %d", len(str(result)))

                        # ============================================================
                        # SOTA 2025 Phase 2: Confidence-Based Early Termination
                        # Pattern: Focused ReAct (arXiv Oct 2024) - exit on first success
                        # Lowered threshold from 0.85 to 0.70 to match CRAG confidence
                        # ============================================================
                        confidence, is_complete = get_last_confidence()
                        if is_complete and confidence >= 0.70:  # PHASE 2: 0.85 → 0.70
                            logger.info("[TUTOR_AGENT] MEDIUM+ confidence (%.2f) - EARLY TERMINATION", confidence)
                            logger.info("[TUTOR_AGENT] Skipping %d remaining iterations (Focused ReAct)", max_iterations - iteration - 1)
                            break
                        elif confidence >= 0.50:
                            logger.info("[TUTOR_AGENT] LOW-MEDIUM confidence (%.2f) - one more try", confidence)
                        else:
                            logger.info("[TUTOR_AGENT] LOW confidence (%.2f) - will retry", confidence)

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] Tool error: %s", e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id
                        ))

                elif tool_name in ("tool_calculator", "tool_current_datetime", "tool_web_search"):
                    try:
                        # Execute utility/web tools
                        if tool_name == "tool_calculator":
                            tool_input = tool_args.get("expression", "")
                            result = await tool_calculator.ainvoke(tool_input)
                            desc = f"Tính toán: {tool_input[:60]}"
                        elif tool_name == "tool_current_datetime":
                            tool_input = tool_args.get("dummy", "")
                            result = await tool_current_datetime.ainvoke(tool_input)
                            desc = "Xem ngày giờ hiện tại"
                        else:  # tool_web_search
                            tool_input = tool_args.get("query", query)
                            result = await tool_web_search.ainvoke(tool_input)
                            desc = f"Tìm web: {tool_input[:60]}"

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": desc,
                            "iteration": iteration + 1
                        })

                        # Sprint 69: Push tool_result event
                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id
                        ))

                        logger.info("[TUTOR_AGENT] %s result length: %d", tool_name, len(str(result)))

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] %s error: %s", tool_name, e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id
                        ))

                elif tool_name in ("tool_character_note", "tool_character_read"):
                    try:
                        # Sprint 95: Find matching character tool
                        char_tool = next(
                            (t for t in self._tools if getattr(t, 'name', '') == tool_name),
                            None,
                        )
                        if char_tool:
                            result = char_tool.invoke(tool_args)
                            desc = f"Character: {tool_name.replace('tool_character_', '')}"
                        else:
                            result = f"Tool {tool_name} not available"
                            desc = tool_name

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": desc,
                            "iteration": iteration + 1,
                        })

                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        ))

                        logger.info("[TUTOR_AGENT] Character tool %s done", tool_name)

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] Character tool %s error: %s", tool_name, e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                        ))

            # SOTA 2025 Phase 2: Check if we should break outer loop
            confidence, is_complete = get_last_confidence()
            if is_complete and confidence >= 0.70:  # PHASE 2: Match inner loop threshold
                logger.info("[TUTOR_AGENT] Breaking outer loop - MEDIUM+ confidence achieved")
                break
        
        # If we exhausted iterations without final response, generate one
        if not final_response:
            try:
                # Sprint 74: Stream final generation as answer_delta (not thinking_delta)
                # This gives real-time answer streaming — TTFT drops from ~36s to ~15s
                if event_queue is not None:
                    final_msg = None
                    async for chunk in self._llm.astream(messages):
                        if final_msg is None:
                            final_msg = chunk
                        else:
                            final_msg = final_msg + chunk
                        # Sprint 74: Stream as answer_delta for real-time answer display
                        text = _extract_chunk_text(chunk.content)
                        if text:
                            await _push_answer_deltas(text)
                    if final_msg is not None:
                        final_response, llm_thinking = self._extract_content_with_thinking(final_msg.content)
                        _answer_streamed_via_bus = True  # Sprint 74: answer already streamed
                    else:
                        final_response = "Đã xảy ra lỗi khi tạo câu trả lời."
                else:
                    final_msg = await self._llm.ainvoke(messages)
                    final_response, llm_thinking = self._extract_content_with_thinking(final_msg.content)
            except Exception as e:
                logger.error("[TUTOR_AGENT] Final generation error: %s", e)
                final_response = "Đã xảy ra lỗi khi tạo câu trả lời."
        
        # Get sources from tool calls
        sources = get_last_retrieved_sources()
        
        # CHỈ THỊ SỐ 29 v9: Get RAG thinking from tool (Option B+)
        rag_thinking = get_last_native_thinking()
        
        # Combine thinking: prioritize RAG thinking (deeper analysis) 
        # but include LLM thinking if RAG thinking unavailable
        combined_thinking = None
        if rag_thinking and llm_thinking:
            combined_thinking = f"[RAG Analysis]\n{rag_thinking}\n\n[Teaching Process]\n{llm_thinking}"
        elif rag_thinking:
            combined_thinking = rag_thinking
        elif llm_thinking:
            combined_thinking = llm_thinking
        
        if combined_thinking:
            logger.info("[TUTOR_AGENT] Combined thinking: %d chars (rag=%s, llm=%s)", len(combined_thinking), bool(rag_thinking), bool(llm_thinking))
        
        return final_response, sources, tools_used, combined_thinking, _answer_streamed_via_bus

    def _fallback_response(self, query: str) -> str:
        """Fallback when LLM unavailable."""
        return f"""Tôi sẽ giúp bạn với: "{query}"

Để học hiệu quả, bạn nên:
1. Đọc tài liệu gốc liên quan
2. Xem các ví dụ thực tế
3. Làm bài tập thực hành

Bạn muốn tôi giải thích khái niệm nào cụ thể?"""
    
    def _extract_content_with_thinking(self, content) -> tuple[str, Optional[str]]:
        """
        Extract text AND thinking from LLM response content.

        CHỈ THỊ SỐ 29 v9: Option B+ - Returns thinking for state propagation.
        This is the SOTA pattern for reasoning transparency (Anthropic/OpenAI).

        Sprint 64 fix: Gemini sometimes wraps entire response in <thinking> tags
        or returns empty text with content only in native thinking blocks.
        When text is empty but thinking is substantial, recover thinking as response.

        Args:
            content: Response content from LLM

        Returns:
            Tuple of (text, thinking) where thinking may be None
        """
        text, thinking = extract_thinking_from_response(content)
        clean_text = text.strip() if text else ""

        # Log thinking if extracted
        if thinking:
            logger.info("[TUTOR] Native thinking extracted: %d chars", len(thinking))

        # Gemini quirk: Sometimes model wraps entire response in <thinking> tags
        # or native thinking format returns empty text. Recover the response.
        if not clean_text and thinking and len(thinking) > 50:
            logger.warning(
                "[TUTOR] Response empty but thinking has content (%d chars), "
                "recovering thinking as response text",
                len(thinking),
            )
            return thinking.strip(), None

        return clean_text, thinking
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None and self._llm_with_tools is not None


# Singleton
_tutor_node: Optional[TutorAgentNode] = None

def get_tutor_agent_node() -> TutorAgentNode:
    """Get or create TutorAgentNode singleton."""
    global _tutor_node
    if _tutor_node is None:
        _tutor_node = TutorAgentNode()
    return _tutor_node
