"""
Semantic Memory Engine Core - Facade Pattern
CHI THI KY THUAT SO 25 - Project Restructure

Main facade class that maintains backward compatibility.
Delegates to specialized modules:
- ContextRetriever: Context and insights retrieval
- FactExtractor: Fact extraction and storage
- InsightProvider: Insight extraction, validation, and lifecycle management

Requirements: 2.2, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3
"""
import json
import logging
from typing import List, Optional

from app.core.config import settings
from app.services.output_processor import extract_thinking_from_response
from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
from app.models.semantic_memory import (
    ConversationSummary,
    Insight,
    InsightCategory,
    MemoryType,
    SemanticContext,
    SemanticMemoryCreate,
    SemanticMemorySearchResult,
    UserFact,
    UserFactExtraction,
)
from app.repositories.semantic_memory_repository import SemanticMemoryRepository

# Import specialized modules
from .context import ContextRetriever
from .extraction import FactExtractor
from .insight_provider import InsightProvider

logger = logging.getLogger(__name__)


class SemanticMemoryEngine:
    """
    Main Semantic Memory Engine - Facade Pattern.

    Orchestrates:
    - ContextRetriever for context/insights retrieval
    - FactExtractor for fact extraction/storage
    - InsightProvider for insight extraction, validation, and lifecycle
    - GeminiOptimizedEmbeddings for vector generation
    - SemanticMemoryRepository for storage/retrieval

    Maintains backward compatibility with existing code.

    Requirements: 2.2, 2.4
    """

    # Configuration
    DEFAULT_SEARCH_LIMIT = 5
    DEFAULT_SIMILARITY_THRESHOLD = 0.7
    DEFAULT_USER_FACTS_LIMIT = 20  # Sprint 88: 15 fact types need >= 15 slots
    MAX_USER_FACTS = 50  # Memory cap (CHI THI 23)

    # Insight Engine v0.5 Configuration (CHI THI 23 CAI TIEN)
    MAX_INSIGHTS = 50  # Hard limit for insights
    CONSOLIDATION_THRESHOLD = 40  # Trigger consolidation at this count
    PRESERVE_DAYS = 7  # Preserve memories accessed within 7 days

    # Priority categories for retrieval
    PRIORITY_CATEGORIES = [InsightCategory.KNOWLEDGE_GAP, InsightCategory.LEARNING_STYLE]

    def __init__(
        self,
        embeddings: Optional[GeminiOptimizedEmbeddings] = None,
        repository: Optional[SemanticMemoryRepository] = None,
        llm=None  # Optional LLM for fact extraction
    ):
        """
        Initialize SemanticMemoryEngine.

        Args:
            embeddings: GeminiOptimizedEmbeddings instance
            repository: SemanticMemoryRepository instance
            llm: Optional LLM for fact extraction (ChatGoogleGenerativeAI)
        """
        self._embeddings = embeddings or GeminiOptimizedEmbeddings()
        self._repository = repository or SemanticMemoryRepository()
        self._llm = llm
        self._initialized = False

        # Initialize specialized modules
        self._context_retriever = ContextRetriever(self._embeddings, self._repository)
        self._fact_extractor = FactExtractor(self._embeddings, self._repository, llm)
        self._insight_provider = InsightProvider(self._embeddings, self._repository)

        logger.info("SemanticMemoryEngine initialized (v0.5 - Refactored)")

    def is_available(self) -> bool:
        """
        Check if Semantic Memory Engine is available.

        Returns:
            True if repository is available and embeddings are configured
        """
        try:
            return (
                self._repository is not None
                and self._repository.is_available()
                and self._embeddings is not None
            )
        except Exception as e:
            logger.warning("SemanticMemoryEngine availability check failed: %s", e)
            return False

    def _ensure_llm(self):
        """Lazy initialization of LLM for summarization."""
        if self._llm is None:
            try:
                from app.engine.llm_pool import get_llm_light
                self._llm = get_llm_light()
                self._fact_extractor._llm = self._llm
                logger.info("LLM initialized for summarization (LIGHT tier - shared pool)")
            except Exception as e:
                logger.warning("Failed to initialize LLM: %s", e)

    # ==================== CONTEXT RETRIEVAL (Delegated) ====================

    async def retrieve_context(
        self,
        user_id: str,
        query: str,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        include_user_facts: bool = True,
        deduplicate_facts: bool = True
    ) -> SemanticContext:
        """
        Retrieve relevant context for a query.

        Delegates to ContextRetriever.retrieve_context()

        Args:
            user_id: User ID
            query: Query text to find similar memories
            search_limit: Maximum similar memories to return
            similarity_threshold: Minimum similarity score
            include_user_facts: Whether to include user facts
            deduplicate_facts: If True, deduplicate facts by fact_type

        Returns:
            SemanticContext with relevant memories and user facts

        Requirements: 1.1, 2.2, 2.4, 4.3
        """
        return await self._context_retriever.retrieve_context(
            user_id=user_id,
            query=query,
            search_limit=search_limit,
            similarity_threshold=similarity_threshold,
            include_user_facts=include_user_facts,
            deduplicate_facts=deduplicate_facts
        )

    async def retrieve_insights_prioritized(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Insight]:
        """
        Retrieve insights with category prioritization.

        Delegates to ContextRetriever.retrieve_insights_prioritized()

        **Validates: Requirements 4.3, 4.4**
        """
        return await self._context_retriever.retrieve_insights_prioritized(
            user_id=user_id,
            query=query,
            limit=limit,
            update_last_accessed_callback=self.update_last_accessed
        )

    async def get_user_facts(self, user_id: str) -> dict:
        """
        Get user facts as a dictionary for easy access.

        This method converts the List[SemanticMemorySearchResult] from
        repository.get_user_facts() into a dict format with keys:
        - name, role, goal, preference, weakness, background, etc.

        Used by:
        - MemoryAgentNode._get_user_facts() for personalization
        - tool_get_user_info() for tool-based retrieval

        Args:
            user_id: User ID to get facts for

        Returns:
            Dict with fact_type as keys and fact content as values.
            Each value is the fact text. An additional key "{fact_type}__updated_at"
            holds the datetime when the fact was last updated (for staleness display).
            Example: {"name": "User", "name__updated_at": datetime(...)}

        **SOTA Pattern:** MemGPT/Mem0 style archival memory access
        **Validates: Requirements 2.2, 4.3**
        """
        try:
            # Get facts from repository (returns List[SemanticMemorySearchResult])
            facts_list = self._repository.get_user_facts(
                user_id=user_id,
                limit=20,
                deduplicate=True  # Keep only latest of each type
            )

            if not facts_list:
                logger.debug("No user facts found for %s", user_id)
                return {}

            # Convert to dict format
            result = {}
            for fact in facts_list:
                # Get fact_type from metadata
                fact_type = fact.metadata.get("fact_type", "unknown")

                # Extract value from content
                # Format can be "fact_type: value" or just "value"
                content = fact.content
                if ": " in content:
                    # Split and get value part
                    value = content.split(": ", 1)[-1]
                else:
                    value = content

                # Only set if not already present (keep first/latest)
                if fact_type not in result:
                    result[fact_type] = value
                    # Sprint 121 RC-4: Include updated_at for staleness display
                    ts = fact.updated_at or fact.created_at
                    result[f"{fact_type}__updated_at"] = ts

            logger.debug("Retrieved %d user facts for %s: %s", len(result), user_id, list(result.keys()))
            return result

        except Exception as e:
            logger.error("Failed to get user facts for %s: %s", user_id, e)
            return {}

    # ==================== FACT EXTRACTION (Delegated) ====================

    async def _extract_and_store_facts(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> List[UserFact]:
        """
        Extract user facts from a message using LLM.

        Sprint 73 fix: Fetches existing facts and passes them to the
        enhanced extractor so it avoids re-extraction and detects changes.
        This ensures ALL messages (including tutor/RAG-routed) get proper
        15-type extraction with existing facts context.
        """
        # Fetch existing facts for context-aware extraction
        existing_facts = None
        try:
            existing_facts = await self.get_user_facts(user_id)
        except Exception as e:
            logger.warning("Failed to fetch existing facts for extraction context: %s", e)

        return await self._fact_extractor.extract_and_store_facts(
            user_id=user_id,
            message=message,
            session_id=session_id,
            existing_facts=existing_facts,
        )

    async def extract_user_facts(
        self,
        user_id: str,
        message: str
    ) -> UserFactExtraction:
        """
        Use LLM to extract user facts from a message.

        Delegates to FactExtractor.extract_user_facts()
        """
        return await self._fact_extractor.extract_user_facts(user_id, message)

    async def store_user_fact_upsert(
        self,
        user_id: str,
        fact_content: str,
        fact_type: str = "name",
        confidence: float = 0.9,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Store or update a user fact using upsert logic.

        Delegates to FactExtractor.store_user_fact_upsert()
        """
        return await self._fact_extractor.store_user_fact_upsert(
            user_id=user_id,
            fact_content=fact_content,
            fact_type=fact_type,
            confidence=confidence,
            session_id=session_id
        )

    # ==================== INTERACTION STORAGE ====================

    async def store_interaction(
        self,
        user_id: str,
        message: str,
        response: str,
        session_id: Optional[str] = None,
        extract_facts: bool = True
    ) -> bool:
        """
        Store an interaction (message + response) as semantic memories.

        Args:
            user_id: User ID
            message: User's message
            response: AI's response
            session_id: Optional session ID
            extract_facts: Whether to extract user facts

        Returns:
            True if storage successful

        Requirements: 2.1
        """
        try:
            # Store user message (Sprint 27: async embedding)
            message_embeddings = await self._embeddings.aembed_documents([message])
            message_embedding = message_embeddings[0]
            message_memory = SemanticMemoryCreate(
                user_id=user_id,
                content=f"User: {message}",
                embedding=message_embedding,
                memory_type=MemoryType.MESSAGE,
                importance=0.5,
                session_id=session_id
            )
            self._repository.save_memory(message_memory)

            # Store AI response (Sprint 27: async embedding)
            response_embeddings = await self._embeddings.aembed_documents([response])
            response_embedding = response_embeddings[0]
            response_memory = SemanticMemoryCreate(
                user_id=user_id,
                content=f"AI: {response}",
                embedding=response_embedding,
                memory_type=MemoryType.MESSAGE,
                importance=0.5,
                session_id=session_id
            )
            self._repository.save_memory(response_memory)

            # Extract and store user facts if enabled
            if extract_facts:
                await self._extract_and_store_facts(user_id, message, session_id)

            logger.debug("Stored interaction for user %s", user_id)
            return True

        except Exception as e:
            logger.error("Failed to store interaction: %s", e)
            return False

    # ==================== TOKEN COUNTING ====================

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count

        Requirements: 3.1
        """
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            return len(text) // 4
        except Exception as e:
            logger.warning("Token counting failed: %s", e)
            return len(text) // 4

    def count_session_tokens(
        self,
        user_id: str,
        session_id: str
    ) -> int:
        """
        Count total tokens for a session's messages.

        Sprint 27 FIX: Uses get_memories_by_type() with session_id filter
        instead of search_similar() with zero-vector (NaN bug in pgvector).

        Requirements: 3.1
        """
        try:
            messages = self._repository.get_memories_by_type(
                user_id=user_id,
                memory_type=MemoryType.MESSAGE,
                session_id=session_id,
            )

            total_tokens = 0
            for msg in messages:
                total_tokens += self.count_tokens(msg.content)

            return total_tokens

        except Exception as e:
            logger.error("Failed to count session tokens: %s", e)
            return 0

    # ==================== SUMMARIZATION ====================

    async def check_and_summarize(
        self,
        user_id: str,
        session_id: str,
        token_threshold: Optional[int] = None
    ) -> Optional[ConversationSummary]:
        """
        Check if session exceeds token threshold and summarize if needed.

        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        threshold = token_threshold or settings.summarization_token_threshold

        try:
            current_tokens = self.count_session_tokens(user_id, session_id)

            if current_tokens < threshold:
                logger.debug(
                    "Session %s has %d tokens, below threshold %d",
                    session_id, current_tokens, threshold
                )
                return None

            logger.info(
                "Session %s has %d tokens, triggering summarization",
                session_id, current_tokens
            )

            summary = await self._summarize_session(
                user_id=user_id,
                session_id=session_id,
                token_count=current_tokens
            )

            return summary

        except Exception as e:
            logger.error("Summarization check failed: %s", e)
            return None

    async def _summarize_session(
        self,
        user_id: str,
        session_id: str,
        token_count: int
    ) -> Optional[ConversationSummary]:
        """Summarize a session's conversation."""
        self._ensure_llm()

        if not self._llm:
            logger.warning("LLM not available for summarization")
            return None

        try:
            messages = self._get_session_messages(user_id, session_id)

            if not messages:
                return None

            conversation_text = "\n".join([m.content for m in messages])
            summary_text, key_topics = await self._generate_summary(conversation_text)

            summary = ConversationSummary(
                user_id=user_id,
                session_id=session_id,
                summary_text=summary_text,
                original_message_count=len(messages),
                original_token_count=token_count,
                key_topics=key_topics
            )

            # Sprint 27: async embedding to avoid blocking event loop
            summary_embeddings = await self._embeddings.aembed_documents([summary_text])
            summary_embedding = summary_embeddings[0]
            summary_memory = summary.to_semantic_memory_create(summary_embedding)
            self._repository.save_memory(summary_memory)

            self._repository.delete_by_session(user_id, session_id)

            logger.info(
                "Summarized session %s: %d messages -> 1 summary",
                session_id, len(messages)
            )

            return summary

        except Exception as e:
            logger.error("Session summarization failed: %s", e)
            return None

    def _get_session_messages(
        self,
        user_id: str,
        session_id: str
    ) -> List[SemanticMemorySearchResult]:
        """
        Get all messages for a session.

        Sprint 27 FIX: Uses get_memories_by_type() with session_id filter
        instead of search_similar() with zero-vector (NaN bug in pgvector).
        Also filters directly in SQL instead of in-memory Python loop.
        """
        try:
            session_messages = self._repository.get_memories_by_type(
                user_id=user_id,
                memory_type=MemoryType.MESSAGE,
                session_id=session_id,
            )

            # get_memories_by_type returns DESC; we need ASC for chronological
            session_messages.sort(key=lambda x: x.created_at)

            return session_messages

        except Exception as e:
            logger.error("Failed to get session messages: %s", e)
            return []

    async def _generate_summary(
        self,
        conversation_text: str
    ) -> tuple[str, List[str]]:
        """Generate summary using LLM."""
        prompt = f"""Summarize the following conversation between a user and an AI tutor.

Conversation:
{conversation_text}

Provide:
1. A concise summary (2-3 paragraphs) capturing the main points discussed
2. A list of key topics covered

Format your response as JSON:
{{
    "summary": "Your summary here...",
    "key_topics": ["topic1", "topic2", "topic3"]
}}

Return ONLY valid JSON:"""

        try:
            response = await self._llm.ainvoke(prompt)

            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            text_content, _ = extract_thinking_from_response(response.content)
            content = text_content.strip()

            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            summary_text = data.get("summary", "")
            key_topics = data.get("key_topics", [])

            return summary_text, key_topics

        except Exception as e:
            logger.error("Summary generation failed: %s", e)
            return conversation_text[:500] + "...", []

    # ==================== MEMORY MANAGEMENT (Sprint 26) ====================

    async def delete_memory_by_keyword(
        self,
        user_id: str,
        keyword: str
    ) -> int:
        """
        Delete memories matching a keyword for a user.

        Searches content field for keyword match and deletes matching entries.
        Used by tool_forget for user-initiated memory deletion.

        Args:
            user_id: User ID
            keyword: Keyword to search and delete

        Returns:
            Number of memories deleted

        Sprint 26: Fix for CRITICAL-2 (tool_forget silent failure)
        """
        try:
            deleted = self._repository.delete_memories_by_keyword(
                user_id=user_id,
                keyword=keyword
            )
            if deleted > 0:
                logger.info("Deleted %d memories matching '%s' for user %s", deleted, keyword, user_id)
            return deleted
        except Exception as e:
            logger.error("Failed to delete memories by keyword: %s", e)
            return 0

    async def delete_all_user_memories(self, user_id: str) -> int:
        """
        Delete ALL memories for a user (factory reset).

        Removes all memory types: USER_FACT, INSIGHT, MESSAGE, SUMMARY.
        Used by tool_clear_all_memories for user-initiated full reset.

        Args:
            user_id: User ID

        Returns:
            Number of memories deleted

        Sprint 26: Fix for CRITICAL-1 (tool_clear_all_memories only cleared cache)
        """
        try:
            deleted = self._repository.delete_all_user_memories(user_id=user_id)
            logger.info("Deleted ALL %d memories for user %s (factory reset)", deleted, user_id)
            return deleted
        except Exception as e:
            logger.error("Failed to delete all memories for user %s: %s", user_id, e)
            return 0

    async def store_explicit_insight(
        self,
        user_id: str,
        insight_text: str,
        category: str = "preference",
        session_id: Optional[str] = None
    ) -> bool:
        """
        Store an explicit user-requested memory as an INSIGHT.

        Used by tool_remember when user says "remember this".

        Args:
            user_id: User ID
            insight_text: The text to remember
            category: Insight category (default: preference)
            session_id: Optional session ID

        Returns:
            True if stored successfully

        Sprint 26: Fix for CRITICAL-3 (tool_remember called non-existent method)
        """
        try:
            # Validate category
            try:
                insight_category = InsightCategory(category)
            except ValueError:
                insight_category = InsightCategory.PREFERENCE

            insight = Insight(
                user_id=user_id,
                content=insight_text,
                category=insight_category,
                confidence=1.0,  # Explicit memory = max confidence
                source_messages=[insight_text],
            )

            stored = await self._insight_provider._store_insight(insight, session_id)
            if stored:
                logger.info("Stored explicit insight for user %s: %s...", user_id, insight_text[:50])
            return stored

        except Exception as e:
            logger.error("Failed to store explicit insight: %s", e)
            return False

    # ==================== INSIGHT ENGINE v0.5 (Delegated) ====================

    async def update_last_accessed(self, insight_id: int) -> bool:
        """
        Update last_accessed timestamp for an insight.

        Delegates to InsightProvider.update_last_accessed()
        """
        return await self._insight_provider.update_last_accessed(insight_id)

    async def extract_and_store_insights(
        self,
        user_id: str,
        message: str,
        conversation_history: List[str] = None,
        session_id: Optional[str] = None
    ) -> List[Insight]:
        """
        Extract behavioral insights from message and store them.

        Delegates to InsightProvider.extract_and_store_insights()

        v0.5 (CHI THI 23 CAI TIEN):
        1. Extract insights using InsightExtractor
        2. Validate each insight
        3. Handle duplicates (merge) and contradictions (update)
        4. Check consolidation threshold
        5. Store valid insights

        Args:
            user_id: User ID
            message: User message to extract insights from
            conversation_history: Previous messages for context
            session_id: Optional session ID

        Returns:
            List of stored insights

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4**
        """
        return await self._insight_provider.extract_and_store_insights(
            user_id=user_id,
            message=message,
            conversation_history=conversation_history,
            session_id=session_id
        )

    async def enforce_hard_limit(self, user_id: str) -> bool:
        """
        Enforce hard limit of 50 insights.

        Delegates to InsightProvider.enforce_hard_limit()

        **Validates: Requirements 3.1**
        """
        return await self._insight_provider.enforce_hard_limit(user_id)


# Factory function
def get_semantic_memory_engine() -> SemanticMemoryEngine:
    """Get a configured SemanticMemoryEngine instance."""
    return SemanticMemoryEngine()
