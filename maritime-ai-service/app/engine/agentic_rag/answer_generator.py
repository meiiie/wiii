"""
Answer Generator for RAG Agent.

Handles LLM-based answer generation including:
- Synchronous response synthesis with RAG context
- Streaming token-by-token generation
- Role-based prompt building
- Native thinking extraction

Extracted from rag_agent.py as part of modular refactoring.

**Feature: wiii, p3-sota-streaming, document-kg**
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.knowledge_graph import KnowledgeNode

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Handles LLM-based answer generation for the RAG pipeline.

    Methods are designed to be called by RAGAgent as delegation targets.
    Requires an LLM instance and PromptLoader to be passed in.
    """

    @staticmethod
    def generate_response(
        llm,
        prompt_loader,
        question: str,
        nodes: List[KnowledgeNode],
        conversation_history: str = "",
        user_role: str = "student",
        entity_context: str = "",
        user_name: Optional[str] = None,
        is_follow_up: bool = False,
        organization_id: Optional[str] = None,
        host_context_prompt: str = "",
    ) -> Tuple[str, Optional[str]]:
        """
        Generate response using LLM to synthesize retrieved knowledge.

        Uses RAG pattern: Retrieve -> Augment -> Generate
        Includes conversation history for context continuity.
        Now includes entity context from GraphRAG for enriched responses.

        Returns tuple of (answer, native_thinking) for hybrid display.

        Role-Based Prompting:
        - student: AI acts as Tutor - encouraging tone, thorough explanations
        - teacher/admin: AI acts as Assistant - professional, concise

        Args:
            llm: LLM instance for generation
            prompt_loader: PromptLoader instance for building system prompts
            question: User's question
            nodes: Retrieved knowledge nodes
            conversation_history: Formatted conversation history for context
            user_role: User role for role-based prompting
            entity_context: Entity context from GraphRAG

        Returns:
            Tuple of (answer_text, native_thinking) where native_thinking may be None

        **Feature: wiii, Week 2: Memory Lite, document-kg**
        """
        if not nodes:
            return "I couldn't find specific information about that topic.", None

        # Build context from retrieved nodes
        context_parts = []
        sources = []

        for node in nodes[:3]:  # Top 3 most relevant
            context_parts.append(f"### {node.title}\n{node.content}")
            if node.source:
                sources.append(f"- {node.title} ({node.source})")

        context = "\n\n".join(context_parts)

        # If no LLM, return formatted raw content
        if not llm:
            logger.info("No LLM available, returning raw content")
            response = context
            if entity_context:
                response = "**Ng\u1eef c\u1ea3nh th\u1ef1c th\u1ec3:** " + entity_context + "\n\n" + response
            if sources:
                response += "\n\n**Ngu\u1ed3n tham kh\u1ea3o:**\n" + "\n".join(sources)
            return response, None  # No native thinking when no LLM

        # SOTA 2025: Use PromptLoader for persona and thinking rules

        # Get base prompt from YAML (includes persona, style, thinking instruction)
        # Sprint 89: Use actual user_name and is_follow_up from caller
        base_prompt = prompt_loader.build_system_prompt(
            role=user_role,
            user_name=user_name,
            is_follow_up=is_follow_up if is_follow_up else bool(conversation_history),
            organization_id=organization_id,
        )

        # Get thinking instruction from YAML
        thinking_instruction = prompt_loader.get_thinking_instruction()

        # Role-specific additional rules
        role_rules = _get_role_rules(user_role)

        # Combine: base (from YAML) + thinking + role rules
        system_prompt = f"{base_prompt}\n\n{thinking_instruction}\n{role_rules}"

        # Sprint 222: Graph-level host context
        if host_context_prompt:
            system_prompt = system_prompt + "\n\n" + host_context_prompt

        # Build user prompt with history and entity context
        user_prompt = _build_user_prompt(
            context, question, conversation_history, entity_context
        )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            # Sprint audit: Timeout-protected invoke (streaming path already has dual-layer timeout)
            import concurrent.futures
            _SYNC_INVOKE_TIMEOUT = 120  # seconds
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(llm.invoke, messages)
                try:
                    response = future.result(timeout=_SYNC_INVOKE_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    logger.warning("[RAG] LLM invoke timeout after %ds", _SYNC_INVOKE_TIMEOUT)
                    future.cancel()
                    raise TimeoutError(f"LLM generation timed out after {_SYNC_INVOKE_TIMEOUT}s")

            # Extract native thinking from Gemini response
            # Lazy import to avoid circular dependency
            # When thinking_enabled=True, response.content may be a list of content blocks
            from app.services.output_processor import extract_thinking_from_response
            answer, native_thinking = extract_thinking_from_response(response.content)

            if native_thinking:
                logger.info("[RAG] Native thinking extracted: %d chars", len(native_thinking))

            # Add sources
            if sources:
                answer += "\n\n**Ngu\u1ed3n tham kh\u1ea3o:**\n" + "\n".join(sources)

            return answer, native_thinking

        except Exception as e:
            logger.error("LLM synthesis failed: %s", e)
            # Fallback to raw content
            response = context
            if sources:
                response += "\n\n**Ngu\u1ed3n tham kh\u1ea3o:**\n" + "\n".join(sources)
            return response, None  # No native thinking on error

    @staticmethod
    async def generate_response_streaming(
        llm,
        prompt_loader,
        question: str,
        nodes: List[KnowledgeNode],
        conversation_history: str = "",
        user_role: str = "student",
        entity_context: str = "",
        user_name: Optional[str] = None,
        is_follow_up: bool = False,
        organization_id: Optional[str] = None,
        host_context_prompt: str = "",
    ):
        """
        SOTA Streaming Generation - yields tokens as they arrive from LLM.

        Pattern from ChatGPT/Claude Dec 2025:
        - First token appears after ~20s (post-CRAG) instead of ~60s
        - Perceived latency reduced by 3x
        - Uses llm.astream() for true token streaming

        Args:
            llm: LLM instance for generation
            prompt_loader: PromptLoader instance for building system prompts
            question: User's question
            nodes: Retrieved knowledge nodes
            conversation_history: Formatted conversation history for context
            user_role: User role for role-based prompting
            entity_context: Entity context from GraphRAG

        Yields:
            str: Token chunks as they arrive from LLM

        **Feature: p3-sota-streaming**
        """
        if not nodes:
            yield "Kh\u00f4ng t\u00ecm th\u1ea5y th\u00f4ng tin c\u1ee5 th\u1ec3 v\u1ec1 ch\u1ee7 \u0111\u1ec1 n\u00e0y."
            return

        # Build context from retrieved nodes (same as generate_response)
        context_parts = []
        sources = []

        for node in nodes[:3]:
            context_parts.append(f"### {node.title}\n{node.content}")
            if node.source:
                sources.append(f"- {node.title} ({node.source})")

        context = "\n\n".join(context_parts)

        if not llm:
            logger.info("[STREAMING] No LLM available, yielding raw content")
            yield context
            if sources:
                yield "\n\n**Ngu\u1ed3n tham kh\u1ea3o:**\n" + "\n".join(sources)
            return

        # Build prompts (same as generate_response)
        # Sprint 89: Use actual user_name and is_follow_up from caller
        base_prompt = prompt_loader.build_system_prompt(
            role=user_role,
            user_name=user_name,
            is_follow_up=is_follow_up if is_follow_up else bool(conversation_history),
            organization_id=organization_id,
        )

        thinking_instruction = prompt_loader.get_thinking_instruction()

        if user_role == "student":
            role_rules = _get_streaming_student_rules()
        else:
            role_rules = _get_streaming_other_rules()

        system_prompt = f"{base_prompt}\n\n{thinking_instruction}\n{role_rules}"

        # Sprint 222: Graph-level host context
        if host_context_prompt:
            system_prompt = system_prompt + "\n\n" + host_context_prompt

        history_section = ""
        if conversation_history:
            history_section = (
                "\n---\n"
                + "L\u1ecaCH S\u1eec H\u1ed8I THO\u1ea0I:\n"
                + conversation_history
                + "\n---\n"
            )

        entity_section = ""
        if entity_context:
            entity_section = (
                "\n---\n"
                + "NG\u1eee C\u1ea2NH TH\u1ef0C TH\u1ec2:\n"
                + entity_context
                + "\n---\n"
            )

        user_prompt = (
            history_section + entity_section + "\n"
            + "KI\u1ebeN TH\u1ee8C TRA C\u1ee8U \u0110\u01af\u1ee2C (RAG):\n"
            + context + "\n"
            + "---\n\n"
            + "C\u00c2U H\u1eceI HI\u1ec6N T\u1ea0I:\n"
            + question + "\n\n"
            + "H\u00e3y tr\u1ea3 l\u1eddi c\u00e2u h\u1ecfi d\u1ef1a tr\u00ean th\u00f4ng tin tr\u00ean."
        )

        # Timeout constants for streaming safety
        CHUNK_TIMEOUT = 120  # Max seconds to wait for next chunk
        TOTAL_TIMEOUT = 600  # Max total streaming time (10 min)

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info("[STREAMING] Starting token-by-token generation...")

            # P3 SOTA: Use astream() with per-chunk timeout to prevent hangs
            stream_start = time.time()
            aiter = llm.astream(messages).__aiter__()
            while True:
                if time.time() - stream_start > TOTAL_TIMEOUT:
                    logger.warning("[STREAMING] Total timeout exceeded (%ds)", TOTAL_TIMEOUT)
                    break
                try:
                    chunk = await asyncio.wait_for(
                        aiter.__anext__(), timeout=CHUNK_TIMEOUT
                    )
                    content = AnswerGenerator.extract_content_from_chunk(chunk)
                    if content:
                        yield content
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    logger.warning("[STREAMING] Chunk timeout (%ds), aborting", CHUNK_TIMEOUT)
                    break

            # After streaming completes, yield sources
            if sources:
                yield "\n\n**Ngu\u1ed3n tham kh\u1ea3o:**\n" + "\n".join(sources)

            logger.info("[STREAMING] Generation complete")

        except Exception as e:
            logger.error("[STREAMING] LLM synthesis failed: %s", e)
            yield "Internal processing error"

    @staticmethod
    def extract_content_from_chunk(chunk) -> str:
        """
        Extract text content from LLM streaming chunk.

        Handles both:
        - String content (simple case)
        - List of content blocks (Gemini with thinking_enabled=True)

        **Feature: p3-sota-streaming, gemini-3-flash-thinking**
        """
        if isinstance(chunk, str):
            return chunk

        if not hasattr(chunk, 'content'):
            return ""

        content = chunk.content

        # Simple string case
        if isinstance(content, str):
            return content

        # List of content blocks (Gemini thinking mode)
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    # Text block
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    # Skip thinking blocks - only return text
                elif isinstance(block, str):
                    text_parts.append(block)
            return "".join(text_parts)

        return ""


# ==========================================================================
# Private helper functions for prompt building
# ==========================================================================

def _get_role_rules(user_role: str) -> str:
    """Get role-specific rules for the system prompt (full generation)."""
    if user_role == "student":
        return (
            "\nQUY T\u1eaeC G\u1eccI T\u00caN (R\u1ea4T QUAN TR\u1eccNG):\n"
            "- KH\u00d4NG g\u1ecdi t\u00ean \u1edf \u0111\u1ea7u m\u1ed7i c\u00e2u tr\u1ea3 l\u1eddi\n"
            '- KH\u00d4NG b\u1eaft \u0111\u1ea7u b\u1eb1ng "Ch\u00e0o [t\u00ean]" - \u0111\u00e2y l\u00e0 l\u1ed7i ph\u1ed5 bi\u1ebfn c\u1ea7n tr\u00e1nh\n'
            '- \u0110i th\u1eb3ng v\u00e0o n\u1ed9i dung: "Quy t\u1eafc 15 quy \u0111\u1ecbnh r\u1eb1ng...", "Theo COLREGs..."\n'
            "- Ch\u1ec9 g\u1ecdi t\u00ean khi C\u1ea6N THI\u1ebeT trong ng\u1eef c\u1ea3nh\n"
            "\nQUY T\u1eaeC VARIATION:\n"
            '- \u0110a d\u1ea1ng c\u00e1ch m\u1edf \u0111\u1ea7u: "Theo quy \u0111\u1ecbnh...", "C\u1ee5 th\u1ec3 l\u00e0...", "V\u1ec1 v\u1ea5n \u0111\u1ec1 n\u00e0y..."\n'
            "- KH\u00d4NG d\u00f9ng c\u00f9ng pattern cho m\u1ecdi c\u00e2u tr\u1ea3 l\u1eddi\n"
            "- C\u00e2u h\u1ecfi follow-up ng\u1eafn \u2192 Tr\u1ea3 l\u1eddi ng\u1eafn g\u1ecdn, \u0111i th\u1eb3ng v\u00e0o \u0111i\u1ec3m ch\u00ednh\n"
            "\nNHI\u1ec6M V\u1ee4:\n"
            "- Tr\u1ea3 l\u1eddi d\u1ef1a tr\u00ean KI\u1ebeN TH\u1ee8C TRA C\u1ee8U \u0110\u01af\u1ee2C b\u00ean d\u01b0\u1edbi\n"
            "- N\u1ebfu c\u00f3 NG\u1eee C\u1ea2NH TH\u1ef0C TH\u1ec2, s\u1eed d\u1ee5ng \u0111\u1ec3 li\u00ean k\u1ebft c\u00e1c kh\u00e1i ni\u1ec7m v\u00e0 \u0111i\u1ec1u lu\u1eadt li\u00ean quan\n"
            "- Tr\u00edch d\u1eabn ngu\u1ed3n khi \u0111\u1ec1 c\u1eadp quy \u0111\u1ecbnh c\u1ee5 th\u1ec3\n"
            "- D\u1ecbch thu\u1eadt ng\u1eef: starboard = m\u1ea1n ph\u1ea3i, port = m\u1ea1n tr\u00e1i, give-way = nh\u01b0\u1eddng \u0111\u01b0\u1eddng\n"
            "- Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t"
        )
    else:
        return (
            "\nQUY T\u1eaeC:\n"
            "- \u0110i th\u1eb3ng v\u00e0o v\u1ea5n \u0111\u1ec1, KH\u00d4NG greeting\n"
            "- Tr\u00edch d\u1eabn ch\u00ednh x\u00e1c s\u1ed1 hi\u1ec7u quy \u0111\u1ecbnh\n"
            "- S\u00fac t\u00edch, chuy\u00ean nghi\u1ec7p\n"
            "\nNHI\u1ec6M V\u1ee4:\n"
            "- Tr\u1ea3 l\u1eddi d\u1ef1a tr\u00ean KI\u1ebeN TH\u1ee8C TRA C\u1ee8U \u0110\u01af\u1ee2C b\u00ean d\u01b0\u1edbi\n"
            "- N\u1ebfu c\u00f3 NG\u1eee C\u1ea2NH TH\u1ef0C TH\u1ec2, tham chi\u1ebfu c\u00e1c \u0111i\u1ec1u lu\u1eadt li\u00ean quan\n"
            "- Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t"
        )


def _get_streaming_student_rules() -> str:
    """Get role rules for streaming student responses (shorter version)."""
    return (
        "\nQUY T\u1eaeC G\u1eccI T\u00caN (R\u1ea4T QUAN TR\u1eccNG):\n"
        "- KH\u00d4NG g\u1ecdi t\u00ean \u1edf \u0111\u1ea7u m\u1ed7i c\u00e2u tr\u1ea3 l\u1eddi\n"
        "- \u0110i th\u1eb3ng v\u00e0o n\u1ed9i dung\n"
        "\nNHI\u1ec6M V\u1ee4:\n"
        "- Tr\u1ea3 l\u1eddi d\u1ef1a tr\u00ean KI\u1ebeN TH\u1ee8C TRA C\u1ee8U \u0110\u01af\u1ee2C b\u00ean d\u01b0\u1edbi\n"
        "- Tr\u00edch d\u1eabn ngu\u1ed3n khi \u0111\u1ec1 c\u1eadp quy \u0111\u1ecbnh c\u1ee5 th\u1ec3\n"
        "- Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t"
    )


def _get_streaming_other_rules() -> str:
    """Get role rules for streaming non-student responses (shorter version)."""
    return (
        "\nQUY T\u1eaeC:\n"
        "- \u0110i th\u1eb3ng v\u00e0o v\u1ea5n \u0111\u1ec1, KH\u00d4NG greeting\n"
        "- S\u00fac t\u00edch, chuy\u00ean nghi\u1ec7p\n"
        "- Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t"
    )


def _build_user_prompt(
    context: str,
    question: str,
    conversation_history: str = "",
    entity_context: str = ""
) -> str:
    """Build the user prompt with history and entity context."""
    history_section = ""
    if conversation_history:
        history_section = (
            "\n---\n"
            + "L\u1ecaCH S\u1eec H\u1ed8I THO\u1ea0I (G\u1ea7n nh\u1ea5t):\n"
            + conversation_history
            + "\n---\n"
        )

    # Feature: document-kg - Add entity context section
    entity_section = ""
    if entity_context:
        entity_section = (
            "\n---\n"
            + "NG\u1eee C\u1ea2NH TH\u1ef0C TH\u1ec2 (GraphRAG):\n"
            + entity_context
            + "\n---\n"
        )

    return (
        history_section + entity_section + "\n"
        + "KI\u1ebeN TH\u1ee8C TRA C\u1ee8U \u0110\u01af\u1ee2C (RAG):\n"
        + context + "\n"
        + "---\n\n"
        + "C\u00c2U H\u1eceI HI\u1ec6N T\u1ea0I:\n"
        + question + "\n\n"
        + "H\u00e3y tr\u1ea3 l\u1eddi c\u00e2u h\u1ecfi d\u1ef1a tr\u00ean th\u00f4ng tin tr\u00ean."
    )
