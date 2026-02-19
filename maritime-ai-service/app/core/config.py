"""
Configuration Management using Pydantic Settings
Loads configuration from environment variables with validation
Requirements: 9.1
"""
import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_config_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = Field(default="Wiii", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    
    # API Settings
    api_v1_prefix: str = Field(default="/api/v1", description="API version 1 prefix")
    api_key: Optional[str] = Field(default=None, description="API Key for authentication")
    jwt_secret_key: str = Field(default="change-me-in-production", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=30, description="JWT token expiration in minutes")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, description="Max requests per window")
    rate_limit_window_seconds: int = Field(default=60, description="Rate limit window in seconds")
    
    # Database - PostgreSQL (Local Docker)
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5433, description="PostgreSQL port (Docker maps to 5433)")
    postgres_user: str = Field(default="wiii", description="PostgreSQL user")
    postgres_password: str = Field(default="wiii_secret", description="PostgreSQL password")
    postgres_db: str = Field(default="wiii_ai", description="PostgreSQL database name")
    
    # Database - Cloud (Production) - CHỈ THỊ 19: Now using Neon
    database_url: Optional[str] = Field(default=None, description="Full database URL (Neon/Cloud)")

    # AsyncPG Connection Pool Settings
    async_pool_min_size: int = Field(default=2, description="Minimum async connection pool size")
    async_pool_max_size: int = Field(default=10, description="Maximum async connection pool size")

    # Supabase Settings (CHỈ THỊ 26: Multimodal RAG - Hybrid Infrastructure)
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anon/service key")
    supabase_storage_bucket: str = Field(default="wiii-docs", description="Supabase Storage bucket for document images")
    
    # LMS API Key (for authentication from LMS)
    lms_api_key: Optional[str] = Field(default=None, description="API Key for LMS integration")
    
    # LMS Callback Configuration (AI-LMS Integration v2.0)
    lms_callback_url: Optional[str] = Field(default=None, description="LMS callback URL for AI events")
    lms_callback_secret: Optional[str] = Field(default=None, description="Shared secret for callback authentication")

    
    @property
    def postgres_url(self) -> str:
        """
        Construct PostgreSQL connection URL.
        Prioritizes DATABASE_URL (cloud) over individual settings (local).
        """
        # Use DATABASE_URL if provided (Neon/Cloud)
        if self.database_url:
            # Convert to asyncpg format if needed
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        
        # Fallback to local Docker settings
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def asyncpg_url(self) -> str:
        """
        Construct asyncpg-compatible URL (plain postgresql://).

        Use this property instead of manually converting postgresql+asyncpg://
        to postgresql:// in every module that uses asyncpg directly.

        Sprint 32: Centralized URL conversion (was duplicated in 5+ files).
        """
        if self.database_url:
            url = self.database_url
            url = url.replace("postgresql+asyncpg://", "postgresql://")
            url = url.replace("postgres://", "postgresql://")
            return url
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def postgres_url_sync(self) -> str:
        """
        Construct synchronous PostgreSQL connection URL (for Alembic migrations).
        
        CHỈ THỊ KỸ THUẬT SỐ 19: Xử lý ssl=require cho psycopg2
        """
        if self.database_url:
            url = self.database_url
            # Ensure it's standard postgresql:// format
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            url = url.replace("postgresql+asyncpg://", "postgresql://")
            # Convert ssl=require to sslmode=require for psycopg2
            if "ssl=require" in url:
                url = url.replace("ssl=require", "sslmode=require")
            return url
        
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # Database - Neo4j (Local Docker)
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI (local or Aura)")
    neo4j_user: str = Field(default="neo4j", description="Neo4j user")
    neo4j_username: Optional[str] = Field(default=None, description="Neo4j username (Aura format)")
    neo4j_password: str = Field(default="neo4j_secret", description="Neo4j password")
    
    @property
    def neo4j_username_resolved(self) -> str:
        """Get Neo4j username (supports both neo4j_user and neo4j_username)"""
        return self.neo4j_username or self.neo4j_user
    
    # LLM Settings - OpenAI/OpenRouter (legacy)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_base_url: Optional[str] = Field(default=None, description="OpenAI-compatible API base URL (e.g., OpenRouter)")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model for general tasks")
    openai_model_advanced: str = Field(default="gpt-4o", description="OpenAI model for complex tasks")
    
    # LLM Settings - Google Gemini (primary)
    google_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    google_model: str = Field(default="gemini-3-flash-preview", description="Google Gemini model (3.0 Flash = 3× faster)")
    llm_provider: str = Field(default="google", description="LLM provider: google, openai, openrouter")

    # LLM Settings - Ollama (local/self-hosted)
    ollama_base_url: Optional[str] = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_model: str = Field(default="qwen3:8b", description="Ollama model name (Sprint 59: Qwen3 default)")
    ollama_thinking_models: list[str] = Field(
        default=["qwen3", "deepseek-r1", "qwq"],
        description="Models supporting thinking mode via Ollama (matched by prefix)"
    )

    # Multi-Provider Failover (Sprint 11: OpenClaw-inspired)
    llm_failover_chain: list[str] = Field(
        default=["google", "openai", "ollama"],
        description="LLM provider failover chain (try in order)"
    )
    enable_llm_failover: bool = Field(default=True, description="Enable automatic LLM provider failover")
    
    # Semantic Memory Settings (v0.3 - Vector Embeddings)
    embedding_model: str = Field(default="models/gemini-embedding-001", description="Gemini embedding model")
    embedding_dimensions: int = Field(default=768, description="Embedding vector dimensions (MRL)")
    semantic_memory_enabled: bool = Field(default=True, description="Enable semantic memory v0.3")
    summarization_token_threshold: int = Field(default=2000, description="Token threshold for summarization")
    
    # Deep Reasoning Settings (CHỈ THỊ KỸ THUẬT SỐ 21)
    deep_reasoning_enabled: bool = Field(default=True, description="Enable Deep Reasoning with <thinking> tags")
    context_window_size: int = Field(default=50, description="Number of messages to include in context window")

    # Multi-Agent System Settings (Phase 8: SOTA 2025)
    # ACTIVE: LangGraph Supervisor + Workers pattern (Self-RAG + Meta CRAG)
    use_multi_agent: bool = Field(default=True, description="Use Multi-Agent System (SOTA 2025) - recommended")
    multi_agent_grading_threshold: float = Field(default=6.0, description="Minimum grader score to accept response")
    enable_corrective_rag: bool = Field(default=True, description="Enable Corrective RAG with self-correction")
    retrieval_grade_threshold: float = Field(default=7.0, description="Minimum score for retrieval grading")
    enable_answer_verification: bool = Field(default=True, description="Enable hallucination checking")
    
    # =============================================================================
    # SELF-REFLECTIVE AGENTIC RAG (SOTA 2025 - Self-RAG + Meta CRAG Pattern)
    # =============================================================================
    # Pattern: Confidence-based smart iteration, not hardcoded loops
    # Reference: Self-RAG (Asai et al.), Meta CRAG (ICLR 2025), Anthropic, Qwen
    # Quality-first approach for maritime domain (high-stakes accuracy)
    
    # Quality Mode: Controls accuracy vs speed trade-off
    rag_quality_mode: str = Field(
        default="balanced",
        description="RAG quality mode: 'speed' (fast, less accurate), 'balanced' (default), 'quality' (slow, high accuracy)"
    )
    
    # Confidence Thresholds (normalized 0-1 scale)
    # HIGH: No iteration needed, generate immediately
    # MEDIUM: Allow single correction if reflection detects issues
    # Below MEDIUM: Fallback to web search or extended retrieval
    rag_confidence_high: float = Field(
        default=0.70,  # SOTA 2025: 0.85 → 0.70. Maritime domain score 7/10 is often sufficient
        description="HIGH confidence threshold: Skip iteration, generate immediately"
    )
    rag_confidence_medium: float = Field(
        default=0.60,
        description="MEDIUM confidence threshold: Allow single correction if needed"
    )
    
    # Iteration Control (soft limits, not hard stops)
    rag_max_iterations: int = Field(
        default=2,
        description="Soft limit on CRAG iterations (can early-exit on high confidence)"
    )
    rag_enable_reflection: bool = Field(
        default=True,
        description="Enable Self-RAG reflection tokens for quality assessment"
    )
    rag_early_exit_on_high_confidence: bool = Field(
        default=True,
        description="Exit iteration loop early if HIGH confidence achieved"
    )
    
    # Gemini 3.0 Thinking Level (Dec 2025)
    # Controls reasoning depth: minimal | low | medium | high
    gemini_thinking_level: str = Field(
        default="medium",
        description="Gemini 3.0 thinking level: 'minimal', 'low', 'medium', 'high'"
    )
    
    # =============================================================================
    # GEMINI THINKING CONFIGURATION (SOTA 2025 - CHỈ THỊ SỐ 28)
    # =============================================================================
    # 4-Tier Thinking Strategy based on Chain of Draft (CoD) pattern
    # All components need thinking, but level varies by task complexity
    # Budget values: -1=dynamic, 0=disabled, 1-24576=fixed tokens
    
    # Global settings
    thinking_enabled: bool = Field(default=True, description="Enable Gemini native thinking globally")
    include_thought_summaries: bool = Field(default=True, description="Include thinking summaries in API response")
    
    # Per-tier budgets (4-tier strategy)
    thinking_budget_deep: int = Field(
        default=8192, 
        description="DEEP tier: Teaching agents (tutor) - requires full explanation"
    )
    thinking_budget_moderate: int = Field(
        default=4096, 
        description="MODERATE tier: RAG synthesis agents (rag_agent, grader) - requires summarization"
    )
    thinking_budget_light: int = Field(
        default=1024, 
        description="LIGHT tier: Quick check agents (analyzer, verifier) - basic self-check"
    )
    thinking_budget_minimal: int = Field(
        default=512, 
        description="MINIMAL tier: Structured tasks (extraction, memory) - minimal buffer"
    )
    
    # Similarity Thresholds (Configurable - Phase 2 Refactoring)
    similarity_threshold: float = Field(default=0.7, description="Default similarity threshold for semantic search")
    fact_similarity_threshold: float = Field(default=0.90, description="Similarity threshold for fact deduplication")
    memory_duplicate_threshold: float = Field(default=0.90, description="Similarity threshold for memory duplicates")
    memory_related_threshold: float = Field(default=0.75, description="Similarity threshold for related memories")
    
    # Rate Limits (Configurable)
    chat_rate_limit: str = Field(default="30/minute", description="Rate limit for chat endpoint")
    default_history_limit: int = Field(default=20, description="Default chat history limit")
    max_history_limit: int = Field(default=100, description="Maximum chat history limit")
    
    # Contextual RAG Settings (Anthropic-style Context Enrichment)
    contextual_rag_enabled: bool = Field(default=True, description="Enable Contextual RAG for chunk enrichment")
    contextual_rag_batch_size: int = Field(default=5, description="Number of chunks to enrich concurrently")
    
    # Document KG Entity Extraction Settings (Feature: document-kg)
    entity_extraction_enabled: bool = Field(default=True, description="Enable entity extraction during ingestion")
    entity_extraction_batch_size: int = Field(default=3, description="Chunks to process concurrently for extraction")
    
    # =============================================================================
    # SEMANTIC CACHE SETTINGS (SOTA 2025 - RAG Latency Optimization)
    # =============================================================================
    # Multi-tier caching: Response (L1), Retrieval (L2), Embedding (L3)
    # Expert-recommended conservative thresholds
    
    semantic_cache_enabled: bool = Field(default=True, description="Enable semantic response caching")
    cache_similarity_threshold: float = Field(default=0.92, description="Similarity threshold for cache hits (industry standard 0.85-0.95)")
    cache_response_ttl: int = Field(default=7200, description="Base response cache TTL in seconds (2 hours)")
    cache_retrieval_ttl: int = Field(default=1800, description="Retrieval cache TTL in seconds (30 min)")
    cache_embedding_ttl: int = Field(default=3600, description="Embedding cache TTL in seconds (1 hour)")
    cache_max_response_entries: int = Field(default=10000, description="Maximum response cache entries")
    cache_log_operations: bool = Field(default=True, description="Log cache hit/miss operations")
    cache_adaptive_ttl: bool = Field(default=True, description="Enable adaptive TTL (hot queries get longer TTL)")
    cache_adaptive_ttl_max_multiplier: float = Field(default=3.0, description="Maximum TTL multiplier for hot queries")
    
    # Semantic Chunking Settings (Feature: semantic-chunking)
    chunk_size: int = Field(default=800, description="Target chunk size in characters")
    chunk_overlap: int = Field(default=100, description="Overlap between consecutive chunks")
    min_chunk_size: int = Field(default=50, description="Minimum chunk size to avoid tiny fragments")
    dpi_optimized: int = Field(default=100, description="Optimized DPI for PDF to image conversion")
    vision_max_dimension: int = Field(default=1024, description="Max dimension for vision API images")
    vision_image_quality: int = Field(default=85, description="JPEG quality for vision API images")
    
    # Hybrid Text/Vision Detection Settings (Feature: hybrid-text-vision)
    # Goal: Reduce Gemini Vision API calls by 50-70%
    hybrid_detection_enabled: bool = Field(default=True, description="Enable hybrid text/vision detection")
    min_text_length_for_direct: int = Field(default=100, description="Minimum text length for direct extraction")
    force_vision_mode: bool = Field(default=False, description="Force Vision extraction for all pages (bypass hybrid detection)")
    
    # Domain Plugin System (Wiii)
    active_domains: list[str] = Field(default=["maritime", "traffic_law"], description="List of active domain plugin IDs")
    default_domain: str = Field(default="maritime", description="Default domain when not specified")

    # Evaluation Framework (SOTA 2026: opt-in per deployment)
    enable_evaluation: bool = Field(default=False, description="Enable lightweight evaluation metrics on responses")

    # Multi-Channel Gateway (Sprint 12: OpenClaw-inspired)
    enable_websocket: bool = Field(default=True, description="Enable WebSocket chat endpoint")
    enable_telegram: bool = Field(default=False, description="Enable Telegram bot integration")
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram Bot API token")
    telegram_webhook_url: Optional[str] = Field(default=None, description="Telegram webhook callback URL")

    # Background Infrastructure (Sprint 18: Valkey + Taskiq)
    valkey_url: str = Field(default="redis://localhost:6379/0", description="Valkey/Redis broker URL")
    enable_background_tasks: bool = Field(default=False, description="Enable background task processing via Taskiq")
    enable_scheduler: bool = Field(default=False, description="Enable scheduled task execution (proactive agent)")

    # Scheduler Execution (Sprint 20: Proactive Agent Activation)
    scheduler_poll_interval: int = Field(default=60, description="Seconds between scheduler polls (10-3600)")
    scheduler_max_concurrent: int = Field(default=5, description="Max concurrent task executions (1-20)")
    scheduler_agent_timeout: int = Field(default=120, description="Timeout for agent invocation in seconds")

    # Extended Tools (Sprint 13: OpenClaw-inspired self-extending agent)
    workspace_root: str = Field(default="~/.wiii/workspace", description="Root directory for workspace operations")
    enable_filesystem_tools: bool = Field(default=False, description="Enable sandboxed filesystem tools (opt-in)")
    enable_code_execution: bool = Field(default=False, description="Enable sandboxed Python execution (opt-in, dangerous)")
    code_execution_timeout: int = Field(default=30, description="Code execution timeout in seconds")
    enable_skill_creation: bool = Field(default=False, description="Enable runtime skill creation (opt-in)")

    # Unified LLM Client (Sprint 55: AsyncOpenAI SDK alongside LangChain)
    enable_unified_client: bool = Field(default=False, description="Enable UnifiedLLMClient (AsyncOpenAI SDK for OpenAI-compatible endpoints)")
    google_openai_compat_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Google Gemini OpenAI-compatible endpoint URL"
    )

    # Agentic Loop (Sprint 57: Generalized tool-calling loop)
    enable_agentic_loop: bool = Field(default=True, description="Enable generalized agentic loop in LangGraph nodes (Sprint 147: default=True)")
    agentic_loop_max_steps: int = Field(default=8, ge=1, le=20, description="Max tool-calling steps per agentic loop (Sprint 147: 5→8 for complex queries)")

    # Per-Agent Provider Config (Sprint 69: Per-node LLM configuration)
    agent_provider_configs: str = Field(
        default="{}",
        description='JSON per-node overrides: {"tutor_agent": {"tier": "moderate", "provider": "google"}}'
    )

    # MCP Support (Sprint 56: Model Context Protocol)
    enable_mcp_server: bool = Field(default=False, description="Enable MCP Server (exposes tools at /mcp)")
    enable_mcp_client: bool = Field(default=False, description="Enable MCP Client (connects to external MCP servers)")
    mcp_server_configs: str = Field(default="[]", description="JSON list of external MCP server configs")

    # Structured Outputs (Sprint 67: LLM JSON schema enforcement)
    enable_structured_outputs: bool = Field(default=True, description="Enable structured outputs (constrained decoding) for Supervisor, Grader, Guardian, RetrievalGrader. Sprint 103: default=True (was False)")

    # Multi-Tenant (Sprint 24: Multi-Organization Architecture)
    enable_multi_tenant: bool = Field(default=False, description="Enable multi-organization support")
    default_organization_id: str = Field(default="default", description="Default org for unauthenticated or migrated users")

    # Living Memory System (Sprint 73: Core Memory Blocks + Mem0 Pipeline + Decay)
    enable_core_memory_block: bool = Field(default=True, description="Compile structured user profile for all agents")
    core_memory_max_tokens: int = Field(default=800, description="Max tokens for core memory profile block")
    core_memory_cache_ttl: int = Field(default=300, description="Core memory cache TTL in seconds")
    enable_memory_decay: bool = Field(default=True, description="Enable Ebbinghaus importance decay on facts")
    memory_decay_floor: float = Field(default=0.1, description="Delete facts with effective importance below this")
    enable_enhanced_extraction: bool = Field(default=True, description="Enable Mem0-style 15-type fact extraction")

    # Sprint 122: Configurable memory constants (Bug F6)
    max_user_facts: int = Field(default=50, description="Maximum user facts per user before eviction")
    character_cache_ttl: int = Field(default=60, description="Character block cache TTL in seconds")
    memory_prune_threshold: float = Field(default=0.1, description="Prune facts with effective importance below this")
    fact_injection_min_confidence: float = Field(default=0.5, description="Minimum confidence for fact injection into prompt")
    max_injected_facts: int = Field(default=5, description="Maximum facts injected into system prompt")
    enable_memory_pruning: bool = Field(default=True, description="Enable active memory pruning during extraction")

    # Character Reflection Engine (Sprint 94: Self-Evolving Character)
    enable_character_reflection: bool = Field(default=True, description="Enable periodic character self-reflection after conversations")
    character_reflection_interval: int = Field(default=5, ge=1, le=50, description="Reflect after every N conversations (1-50)")
    enable_character_tools: bool = Field(default=True, description="Enable character self-editing tools in agents")
    character_reflection_threshold: float = Field(default=5.0, description="Importance sum threshold to trigger reflection early")
    character_experience_retention_days: int = Field(default=90, description="Delete experiences older than N days")
    character_experience_keep_min: int = Field(default=100, description="Always keep at least N most recent experiences")

    # Stanford Generative Agents Memory Retrieval (Sprint 98)
    stanford_recency_weight: float = Field(default=0.3, description="Weight for recency in Stanford memory ranking (alpha)")
    stanford_importance_weight: float = Field(default=0.3, description="Weight for importance in Stanford memory ranking (beta)")
    stanford_relevance_weight: float = Field(default=0.4, description="Weight for relevance in Stanford memory ranking (gamma)")

    # SOTA Personality System (Sprint 115)
    identity_anchor_interval: int = Field(default=6, ge=3, le=50, description="Re-inject identity anchor every N responses (research: drift starts at 8 turns)")
    enable_emotional_state: bool = Field(default=False, description="Enable 2D mood state machine (keyword-based sentiment detection)")
    emotional_decay_rate: float = Field(default=0.15, description="Rate of mood decay toward neutral per turn (0.0-1.0)")
    enable_personality_eval: bool = Field(default=False, description="Enable personality drift evaluator (opt-in for testing)")

    # Soul Emotion (Sprint 135: LLM-Driven Avatar Expression)
    enable_soul_emotion: bool = Field(default=False, description="Enable LLM inline <!--WIII_SOUL:{...}--> emotion tags for avatar control")
    soul_emotion_buffer_bytes: int = Field(default=512, ge=256, le=2048, description="Max bytes to buffer at stream start for soul emotion extraction (min 256 to fit max tag ~170 bytes)")

    # Knowledge Management (Sprint 136: Universal KB)
    cross_domain_search: bool = Field(default=True, description="Search all domains with soft boost (not hard filter)")
    domain_boost_score: float = Field(default=0.15, description="RRF boost for same-domain results in cross-domain search")
    enable_text_ingestion: bool = Field(default=True, description="Allow text/markdown ingestion via API")
    max_ingestion_size_mb: int = Field(default=50, description="Maximum file size for ingestion in MB")

    # Semantic Fact Retrieval (Sprint 137: Vector Facts)
    enable_semantic_fact_retrieval: bool = Field(default=True, description="Use embedding similarity for fact retrieval instead of SQL-only")
    fact_retrieval_alpha: float = Field(default=0.3, description="Importance weight in combined fact scoring")
    fact_retrieval_beta: float = Field(default=0.5, description="Cosine similarity weight in combined fact scoring")
    fact_retrieval_gamma: float = Field(default=0.2, description="Recency weight in combined fact scoring")
    fact_min_similarity: float = Field(default=0.3, description="Minimum cosine similarity for semantic fact retrieval")

    # Intelligent Tool Selection (Sprint 138: Tool Pre-Filtering)
    enable_tool_selection: bool = Field(default=False, description="Enable semantic tool pre-filtering for direct node")
    tool_selection_top_k: int = Field(default=5, description="Maximum tools to bind after semantic selection")
    tool_selection_core_tools: list[str] = Field(
        default=["tool_current_datetime", "tool_knowledge_search", "tool_think"],
        description="Tools always included regardless of similarity score"
    )

    # LangSmith Observability (Sprint 144b)
    enable_langsmith: bool = Field(default=False, description="Enable LangSmith tracing for LangChain/LangGraph observability")
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key (from smith.langchain.com)")
    langsmith_project: str = Field(default="wiii", description="LangSmith project name for trace grouping")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")

    # Multi-Phase Thinking Chain (Sprint 148: "Chuỗi Tư Duy")
    enable_thinking_chain: bool = Field(default=False, description="Enable multi-phase thinking chain (tool_report_progress for Claude-like phase transitions)")

    # Product Search Agent (Sprint 148: "Săn Hàng" + Sprint 149: "Cắm & Chạy")
    enable_product_search: bool = Field(default=False, description="Enable product search agent (multi-platform e-commerce search)")
    serper_api_key: Optional[str] = Field(default=None, description="Serper.dev API key for Google Shopping search")
    apify_api_token: Optional[str] = Field(default=None, description="Apify API token for e-commerce scrapers (Shopee, TikTok Shop, Lazada, FB)")
    product_search_max_results: int = Field(default=30, description="Max results per platform search")
    product_search_timeout: int = Field(default=30, description="Timeout in seconds for each platform search")

    # Sprint 149: Search Platform Plugin Architecture
    product_search_platforms: list = Field(
        default=["google_shopping", "shopee", "tiktok_shop", "lazada", "facebook_marketplace", "all_web", "instagram"],
        description="List of enabled search platform IDs",
    )
    enable_tiktok_native_api: bool = Field(default=False, description="Enable TikTok Research API (native, free)")
    tiktok_client_key: Optional[str] = Field(default=None, description="TikTok Developer Portal client key")
    tiktok_client_secret: Optional[str] = Field(default=None, description="TikTok Developer Portal client secret")

    # OAuth skeleton (future)
    enable_oauth_token_store: bool = Field(default=False, description="Enable OAuth token store for platform auth")
    oauth_encryption_key: Optional[str] = Field(default=None, description="Fernet encryption key for OAuth tokens")

    # Quality & Model Config
    quality_skip_threshold: float = Field(default=0.85, description="Skip grader when CRAG confidence >= this value (saves ~7.8s)")
    rag_model_version: str = Field(default="agentic-rag-v3", description="RAG model version string for metadata")
    insight_duplicate_threshold: float = Field(default=0.85, description="Cosine similarity threshold for duplicate insight detection")
    insight_contradiction_threshold: float = Field(default=0.70, description="Cosine similarity threshold for contradiction detection")

    # Security
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    mask_pii: bool = Field(default=True, description="Mask PII in logs")
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()

    @field_validator("jwt_expire_minutes")
    @classmethod
    def validate_jwt_expire(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("jwt_expire_minutes must be positive")
        if v > 43200:  # 30 days max
            raise ValueError("jwt_expire_minutes must not exceed 43200 (30 days)")
        return v

    @field_validator("postgres_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("postgres_port must be between 1 and 65535")
        return v

    @field_validator("rate_limit_requests")
    @classmethod
    def validate_rate_limit_requests(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("rate_limit_requests must be positive")
        return v

    @field_validator("rate_limit_window_seconds")
    @classmethod
    def validate_rate_limit_window(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("rate_limit_window_seconds must be positive")
        return v

    @field_validator("scheduler_poll_interval")
    @classmethod
    def validate_scheduler_poll_interval(cls, v: int) -> int:
        if not (10 <= v <= 3600):
            raise ValueError("scheduler_poll_interval must be between 10 and 3600")
        return v

    @field_validator("scheduler_max_concurrent")
    @classmethod
    def validate_scheduler_max_concurrent(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("scheduler_max_concurrent must be between 1 and 20")
        return v

    @field_validator("async_pool_min_size")
    @classmethod
    def validate_async_pool_min_size(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("async_pool_min_size must be between 1 and 100")
        return v

    @field_validator("async_pool_max_size")
    @classmethod
    def validate_async_pool_max_size(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("async_pool_max_size must be between 1 and 100")
        return v

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        if not (100 <= v <= 10000):
            raise ValueError("chunk_size must be between 100 and 10000")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, v: int) -> int:
        if not (0 <= v <= 5000):
            raise ValueError("chunk_overlap must be between 0 and 5000")
        return v

    @field_validator("code_execution_timeout")
    @classmethod
    def validate_code_execution_timeout(cls, v: int) -> int:
        if not (1 <= v <= 300):
            raise ValueError("code_execution_timeout must be between 1 and 300")
        return v

    @field_validator("vision_image_quality")
    @classmethod
    def validate_vision_image_quality(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("vision_image_quality must be between 1 and 100")
        return v

    @field_validator(
        "similarity_threshold",
        "fact_similarity_threshold",
        "memory_duplicate_threshold",
        "memory_related_threshold",
        "cache_similarity_threshold",
        "quality_skip_threshold",
        "insight_duplicate_threshold",
        "insight_contradiction_threshold",
        "rag_confidence_high",
        "rag_confidence_medium",
    )
    @classmethod
    def validate_similarity_thresholds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        return v

    @field_validator("multi_agent_grading_threshold", "retrieval_grade_threshold")
    @classmethod
    def validate_grading_thresholds(cls, v: float) -> float:
        if not (0.0 <= v <= 10.0):
            raise ValueError("Grading threshold must be between 0.0 and 10.0")
        return v

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = ["google", "openai", "ollama", "openrouter"]
        if v not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}")
        return v

    @field_validator("rag_quality_mode")
    @classmethod
    def validate_rag_quality_mode(cls, v: str) -> str:
        allowed = ["speed", "balanced", "quality"]
        if v not in allowed:
            raise ValueError(f"rag_quality_mode must be one of {allowed}")
        return v

    @field_validator("gemini_thinking_level")
    @classmethod
    def validate_gemini_thinking_level(cls, v: str) -> str:
        allowed = ["minimal", "low", "medium", "high"]
        if v not in allowed:
            raise ValueError(f"gemini_thinking_level must be one of {allowed}")
        return v

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        allowed = ["json", "text"]
        if v.lower() not in allowed:
            raise ValueError(f"log_format must be one of {allowed}")
        return v.lower()

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int) -> int:
        if not (128 <= v <= 4096):
            raise ValueError("embedding_dimensions must be between 128 and 4096")
        return v

    @field_validator("cache_max_response_entries")
    @classmethod
    def validate_cache_max_response_entries(cls, v: int) -> int:
        if not (100 <= v <= 1_000_000):
            raise ValueError("cache_max_response_entries must be between 100 and 1,000,000")
        return v

    @field_validator("contextual_rag_batch_size", "entity_extraction_batch_size")
    @classmethod
    def validate_batch_sizes(cls, v: int) -> int:
        if not (1 <= v <= 50):
            raise ValueError("batch_size must be between 1 and 50")
        return v

    @field_validator("agentic_loop_max_steps")
    @classmethod
    def validate_agentic_loop_max_steps(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("agentic_loop_max_steps must be between 1 and 20")
        return v

    @field_validator("rag_max_iterations")
    @classmethod
    def validate_rag_max_iterations(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("rag_max_iterations must be between 1 and 10")
        return v

    @field_validator("ollama_base_url", "openai_base_url")
    @classmethod
    def validate_url_fields(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("google_openai_compat_url")
    @classmethod
    def validate_google_compat_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("google_openai_compat_url must start with http:// or https://")
        return v

    # =========================================================================
    # Sprint 83: Cross-field validators + security hardening
    # =========================================================================

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Validate security-critical settings in production."""
        if self.environment == "production":
            # C1: JWT secret must not be default in production
            if self.jwt_secret_key == "change-me-in-production":
                raise ValueError(
                    "SECURITY: jwt_secret_key must be changed from default "
                    "in production. Set JWT_SECRET_KEY environment variable."
                )
            # C2: CORS wildcard is dangerous in production
            if self.cors_origins == ["*"]:
                _config_logger.warning(
                    "SECURITY WARNING: cors_origins=['*'] in production. "
                    "Set CORS_ORIGINS to specific allowed origins."
                )
        return self

    @model_validator(mode="after")
    def validate_cross_field_consistency(self) -> "Settings":
        """Validate related config fields are consistent."""
        # M8: Confidence thresholds must be ordered
        if self.rag_confidence_high <= self.rag_confidence_medium:
            raise ValueError(
                f"rag_confidence_high ({self.rag_confidence_high}) must be > "
                f"rag_confidence_medium ({self.rag_confidence_medium})"
            )
        # M8: Pool size ordering
        if self.async_pool_min_size > self.async_pool_max_size:
            raise ValueError(
                f"async_pool_min_size ({self.async_pool_min_size}) must be <= "
                f"async_pool_max_size ({self.async_pool_max_size})"
            )
        # M8: Chunk overlap must be less than chunk size
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < "
                f"chunk_size ({self.chunk_size})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Export settings instance for convenience
settings = get_settings()
