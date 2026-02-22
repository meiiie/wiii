"""
Configuration Management using Pydantic Settings
Loads configuration from environment variables with validation
Requirements: 9.1

Sprint 154: Added 8 nested BaseModel config groups for structured access.
Flat fields remain the source of truth (backward compat for 92 importing files).
Nested groups are synced FROM flat fields via @model_validator.
Access: settings.google_api_key (flat, original) or settings.llm.google_api_key (nested, new).
"""
import logging
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_config_logger = logging.getLogger(__name__)


# =============================================================================
# Sprint 154: Nested Config Groups (read-only views of flat fields)
# =============================================================================

class DatabaseConfig(BaseModel):
    """PostgreSQL + async pool configuration."""
    host: str = "localhost"
    port: int = 5433
    user: str = "wiii"
    password: str = "wiii_secret"
    db: str = "wiii_ai"
    database_url: Optional[str] = None
    async_pool_min_size: int = 2
    async_pool_max_size: int = 10


class LLMConfig(BaseModel):
    """LLM provider settings — Gemini, OpenAI, Ollama."""
    provider: str = "google"
    failover_chain: list[str] = ["google", "openai", "ollama"]
    enable_failover: bool = True
    google_api_key: Optional[str] = None
    google_model: str = "gemini-3-flash-preview"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: Optional[str] = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_thinking_models: list[str] = ["qwen3", "deepseek-r1", "qwq"]


class RAGConfig(BaseModel):
    """RAG quality, confidence, iteration settings."""
    enable_corrective_rag: bool = True
    quality_mode: str = "balanced"
    confidence_high: float = 0.70
    confidence_medium: float = 0.60
    max_iterations: int = 2
    enable_reflection: bool = True
    early_exit_on_high_confidence: bool = True
    grading_threshold: float = 6.0
    retrieval_grade_threshold: float = 7.0
    enable_answer_verification: bool = True


class MemoryConfig(BaseModel):
    """Memory system — core memory, facts, character, emotion."""
    enable_core_memory_block: bool = True
    core_memory_max_tokens: int = 800
    core_memory_cache_ttl: int = 300
    max_user_facts: int = 50
    max_injected_facts: int = 5
    fact_injection_min_confidence: float = 0.5
    enable_memory_decay: bool = True
    enable_memory_pruning: bool = True
    enable_semantic_fact_retrieval: bool = True
    fact_retrieval_alpha: float = 0.3
    fact_retrieval_beta: float = 0.5
    fact_retrieval_gamma: float = 0.2


class ProductSearchConfig(BaseModel):
    """Product search — platforms, scraping, browser."""
    enable_product_search: bool = False
    serper_api_key: Optional[str] = None
    apify_api_token: Optional[str] = None
    max_results: int = 30
    timeout: int = 30
    platforms: list[str] = ["google_shopping", "shopee", "tiktok_shop", "lazada", "facebook_marketplace", "all_web", "instagram", "websosanh"]
    max_iterations: int = 15
    scrape_timeout: int = 10
    max_scrape_pages: int = 10
    enable_tiktok_native_api: bool = False
    enable_browser_scraping: bool = False
    browser_scraping_timeout: int = 15
    enable_browser_screenshots: bool = False
    browser_screenshot_quality: int = 40
    enable_network_interception: bool = True
    network_interception_max_response_size: int = 5_000_000
    enable_auto_group_discovery: bool = False
    auto_group_max_groups: int = 3


class ThinkingConfig(BaseModel):
    """Deep reasoning and thinking budget."""
    enabled: bool = True
    include_summaries: bool = True
    budget_deep: int = 8192
    budget_moderate: int = 4096
    budget_light: int = 1024
    budget_minimal: int = 512
    gemini_level: str = "medium"
    enable_chain: bool = False


class CharacterConfig(BaseModel):
    """Character reflection, personality, emotion."""
    enable_reflection: bool = True
    reflection_interval: int = 5
    enable_tools: bool = True
    reflection_threshold: float = 5.0
    experience_retention_days: int = 90
    enable_emotional_state: bool = False
    emotional_decay_rate: float = 0.15
    enable_soul_emotion: bool = False


class CacheConfig(BaseModel):
    """Semantic cache settings."""
    enabled: bool = True
    similarity_threshold: float = 0.92
    response_ttl: int = 7200
    retrieval_ttl: int = 1800
    max_entries: int = 10000
    adaptive_ttl: bool = True


class LivingAgentConfig(BaseModel):
    """Living Agent — autonomous life, browsing, learning, emotion (Sprint 170)."""
    enabled: bool = False
    heartbeat_interval: int = 1800
    active_hours_start: int = 8
    active_hours_end: int = 23
    local_model: str = "qwen3:8b"
    max_browse_items: int = 10
    enable_social_browse: bool = False
    enable_skill_building: bool = False
    enable_journal: bool = True
    require_human_approval: bool = True
    max_actions_per_heartbeat: int = 3
    max_skills_per_week: int = 5
    max_searches_per_heartbeat: int = 3
    max_daily_cycles: int = 48
    callmebot_api_key: Optional[str] = None
    notification_channel: str = "websocket"


class LMSIntegrationConfig(BaseModel):
    """LMS integration — Spring Boot LMS webhook + API (Sprint 155)."""
    enabled: bool = False
    base_url: Optional[str] = None
    service_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_timeout: int = 10


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Sprint 154: Added 8 nested config groups (database, llm, rag, memory,
    product_search, thinking, character, cache) as structured views.
    All flat fields remain for backward compatibility — nested groups are
    synced from flat fields via @model_validator.
    """

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

    # Google OAuth (Sprint 157: Đăng Nhập)
    enable_google_oauth: bool = Field(default=False, description="Enable Google OAuth login")
    google_oauth_client_id: Optional[str] = Field(default=None, description="Google OAuth 2.0 client ID")
    google_oauth_client_secret: Optional[str] = Field(default=None, description="Google OAuth 2.0 client secret")
    oauth_redirect_base_url: Optional[str] = Field(default=None, description="Base URL for OAuth callbacks (e.g. https://api.wiii.app)")
    session_secret_key: str = Field(default="change-session-secret-in-production", description="Session middleware secret for OAuth CSRF state")
    jwt_refresh_expire_days: int = Field(default=30, ge=1, le=365, description="Refresh token expiration in days")

    # LMS Token Exchange (Sprint 159: Cầu Nối Trực Tiếp)
    enable_lms_token_exchange: bool = Field(default=False, description="Enable LMS backend → Wiii JWT token exchange")
    lms_token_exchange_max_age: int = Field(default=300, ge=30, le=600, description="Max request age for replay protection (seconds)")

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

    # PostgreSQL Safety (Sprint 171: CIS Benchmark 5.4)
    postgres_statement_timeout_ms: int = Field(default=30000, ge=1000, le=300000, description="Query timeout in ms (default 30s)")
    postgres_idle_in_transaction_timeout_ms: int = Field(default=60000, ge=10000, le=600000, description="Idle transaction timeout in ms (default 60s)")

    # Object Storage (MinIO / S3-compatible)
    minio_endpoint: Optional[str] = Field(default=None, description="MinIO endpoint (host:port, no scheme)")
    minio_access_key: Optional[str] = Field(default=None, description="MinIO access key")
    minio_secret_key: Optional[str] = Field(default=None, description="MinIO secret key")
    minio_bucket: str = Field(default="wiii-docs", description="Storage bucket for document images")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO connection")

    # LMS API Key (for authentication from LMS)
    lms_api_key: Optional[str] = Field(default=None, description="API Key for LMS integration")

    # LMS Callback Configuration (AI-LMS Integration v2.0)
    lms_callback_url: Optional[str] = Field(default=None, description="LMS callback URL for AI events")
    lms_callback_secret: Optional[str] = Field(default=None, description="Shared secret for callback authentication")

    # LMS Integration (Sprint 155: Cầu Nối — inbound from LMS)
    enable_lms_integration: bool = Field(default=False, description="Enable LMS webhook + API integration")
    lms_base_url: Optional[str] = Field(default=None, description="LMS REST API base URL (single-LMS compat)")
    lms_service_token: Optional[str] = Field(default=None, description="Service account token for LMS API (single-LMS compat)")
    lms_webhook_secret: Optional[str] = Field(default=None, description="HMAC-SHA256 secret for incoming webhooks (single-LMS compat)")
    lms_api_timeout: int = Field(default=10, ge=3, le=60, description="LMS API call timeout (seconds)")
    # Sprint 155b: Multi-LMS connector list (JSON array — takes precedence over flat fields above)
    lms_connectors: str = Field(
        default="[]",
        description='JSON list of LMS connectors: [{"id":"maritime-lms","backend_type":"spring_boot","base_url":"...","webhook_secret":"..."}]'
    )

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
        Construct synchronous PostgreSQL connection URL (standard postgresql:// format).

        Used by: checkpointer (psycopg3 libpq), SQLAlchemy (via database.py dialect override).
        Sprint 165: psycopg2-binary removed Sprint 154, psycopg[binary]>=3.1 is the replacement.
        """
        if self.database_url:
            url = self.database_url
            # Normalize to standard postgresql:// (no dialect suffix)
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            url = url.replace("postgresql+asyncpg://", "postgresql://")
            # Convert ssl=require to sslmode=require for psycopg3
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
    use_multi_agent: bool = Field(default=True, description="Use Multi-Agent System (SOTA 2025) - recommended")
    multi_agent_grading_threshold: float = Field(default=6.0, description="Minimum grader score to accept response")
    enable_corrective_rag: bool = Field(default=True, description="Enable Corrective RAG with self-correction")
    retrieval_grade_threshold: float = Field(default=7.0, description="Minimum score for retrieval grading")
    enable_answer_verification: bool = Field(default=True, description="Enable hallucination checking")

    # RAG Quality Settings
    rag_quality_mode: str = Field(
        default="balanced",
        description="RAG quality mode: 'speed' (fast, less accurate), 'balanced' (default), 'quality' (slow, high accuracy)"
    )
    rag_confidence_high: float = Field(default=0.70, description="HIGH confidence threshold")
    rag_confidence_medium: float = Field(default=0.60, description="MEDIUM confidence threshold")
    rag_max_iterations: int = Field(default=2, description="Soft limit on CRAG iterations")
    rag_enable_reflection: bool = Field(default=True, description="Enable Self-RAG reflection tokens")
    rag_early_exit_on_high_confidence: bool = Field(default=True, description="Exit iteration loop early if HIGH confidence")

    # Gemini Thinking Level
    gemini_thinking_level: str = Field(default="medium", description="Gemini 3.0 thinking level")

    # Thinking Configuration (4-Tier Strategy)
    thinking_enabled: bool = Field(default=True, description="Enable Gemini native thinking globally")
    include_thought_summaries: bool = Field(default=True, description="Include thinking summaries in API response")
    thinking_budget_deep: int = Field(default=8192, description="DEEP tier budget")
    thinking_budget_moderate: int = Field(default=4096, description="MODERATE tier budget")
    thinking_budget_light: int = Field(default=1024, description="LIGHT tier budget")
    thinking_budget_minimal: int = Field(default=512, description="MINIMAL tier budget")

    # Similarity Thresholds
    similarity_threshold: float = Field(default=0.7, description="Default similarity threshold for semantic search")
    fact_similarity_threshold: float = Field(default=0.90, description="Similarity threshold for fact deduplication")
    memory_duplicate_threshold: float = Field(default=0.90, description="Similarity threshold for memory duplicates")
    memory_related_threshold: float = Field(default=0.75, description="Similarity threshold for related memories")

    # Rate Limits (Configurable)
    chat_rate_limit: str = Field(default="30/minute", description="Rate limit for chat endpoint")
    default_history_limit: int = Field(default=20, description="Default chat history limit")
    max_history_limit: int = Field(default=100, description="Maximum chat history limit")

    # Contextual RAG Settings
    contextual_rag_enabled: bool = Field(default=True, description="Enable Contextual RAG for chunk enrichment")
    contextual_rag_batch_size: int = Field(default=5, description="Number of chunks to enrich concurrently")

    # Document KG Entity Extraction Settings
    entity_extraction_enabled: bool = Field(default=True, description="Enable entity extraction during ingestion")
    entity_extraction_batch_size: int = Field(default=3, description="Chunks to process concurrently for extraction")

    # Semantic Cache Settings
    semantic_cache_enabled: bool = Field(default=True, description="Enable semantic response caching")
    cache_similarity_threshold: float = Field(default=0.92, description="Similarity threshold for cache hits")
    cache_response_ttl: int = Field(default=7200, description="Base response cache TTL in seconds")
    cache_retrieval_ttl: int = Field(default=1800, description="Retrieval cache TTL in seconds")
    cache_embedding_ttl: int = Field(default=3600, description="Embedding cache TTL in seconds")
    cache_max_response_entries: int = Field(default=10000, description="Maximum response cache entries")
    cache_log_operations: bool = Field(default=True, description="Log cache hit/miss operations")
    cache_adaptive_ttl: bool = Field(default=True, description="Enable adaptive TTL")
    cache_adaptive_ttl_max_multiplier: float = Field(default=3.0, description="Maximum TTL multiplier for hot queries")

    # Semantic Chunking Settings
    chunk_size: int = Field(default=800, description="Target chunk size in characters")
    chunk_overlap: int = Field(default=100, description="Overlap between consecutive chunks")
    min_chunk_size: int = Field(default=50, description="Minimum chunk size to avoid tiny fragments")
    dpi_optimized: int = Field(default=100, description="Optimized DPI for PDF to image conversion")
    vision_max_dimension: int = Field(default=1024, description="Max dimension for vision API images")
    vision_image_quality: int = Field(default=85, description="JPEG quality for vision API images")

    # Hybrid Text/Vision Detection Settings
    hybrid_detection_enabled: bool = Field(default=True, description="Enable hybrid text/vision detection")
    min_text_length_for_direct: int = Field(default=100, description="Minimum text length for direct extraction")
    force_vision_mode: bool = Field(default=False, description="Force Vision extraction for all pages")

    # Domain Plugin System (Wiii)
    active_domains: list[str] = Field(default=["maritime", "traffic_law"], description="List of active domain plugin IDs")
    default_domain: str = Field(default="maritime", description="Default domain when not specified")

    # Multi-Channel Gateway
    enable_websocket: bool = Field(default=True, description="Enable WebSocket chat endpoint")
    enable_telegram: bool = Field(default=False, description="Enable Telegram bot integration")
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram Bot API token")
    telegram_webhook_url: Optional[str] = Field(default=None, description="Telegram webhook callback URL")
    enable_zalo: bool = Field(default=False, description="Enable Zalo OA notification channel")
    zalo_oa_access_token: Optional[str] = Field(default=None, description="Zalo OA access token")
    zalo_oa_refresh_token: Optional[str] = Field(default=None, description="Zalo OA refresh token")
    zalo_oa_app_id: Optional[str] = Field(default=None, description="Zalo OA application ID")
    zalo_oa_secret_key: Optional[str] = Field(default=None, description="Zalo OA secret key")

    # Background Infrastructure
    valkey_url: str = Field(default="redis://localhost:6379/0", description="Valkey/Redis broker URL")
    enable_background_tasks: bool = Field(default=False, description="Enable background task processing via Taskiq")
    enable_scheduler: bool = Field(default=False, description="Enable scheduled task execution (proactive agent)")

    # Scheduler Execution
    scheduler_poll_interval: int = Field(default=60, description="Seconds between scheduler polls (10-3600)")
    scheduler_max_concurrent: int = Field(default=5, description="Max concurrent task executions (1-20)")
    scheduler_agent_timeout: int = Field(default=120, description="Timeout for agent invocation in seconds")

    # Extended Tools
    workspace_root: str = Field(default="~/.wiii/workspace", description="Root directory for workspace operations")
    enable_filesystem_tools: bool = Field(default=False, description="Enable sandboxed filesystem tools")
    enable_code_execution: bool = Field(default=False, description="Enable sandboxed Python execution")
    code_execution_timeout: int = Field(default=30, description="Code execution timeout in seconds")
    enable_skill_creation: bool = Field(default=False, description="Enable runtime skill creation")

    # Unified LLM Client
    enable_unified_client: bool = Field(default=False, description="Enable UnifiedLLMClient (AsyncOpenAI SDK)")
    google_openai_compat_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Google Gemini OpenAI-compatible endpoint URL"
    )

    # Agentic Loop
    enable_agentic_loop: bool = Field(default=True, description="Enable generalized agentic loop")
    agentic_loop_max_steps: int = Field(default=8, ge=1, le=20, description="Max tool-calling steps per agentic loop")

    # Per-Agent Provider Config
    agent_provider_configs: str = Field(
        default="{}",
        description='JSON per-node overrides: {"tutor_agent": {"tier": "moderate", "provider": "google"}}'
    )

    # Neo4j (Legacy — reserved for future Learning Graph)
    enable_neo4j: bool = Field(default=False, description="Enable Neo4j graph database (legacy, reserved for Learning Graph)")

    # Subagent Architecture (Sprint 163)
    enable_subagent_architecture: bool = Field(default=False, description="Enable subagent/subgraph architecture")
    subagent_default_timeout: int = Field(default=60, ge=10, le=300, description="Default subagent timeout (seconds)")
    subagent_max_parallel: int = Field(default=5, ge=1, le=10, description="Max parallel subagent executions")

    # MCP Support
    enable_mcp_server: bool = Field(default=False, description="Enable MCP Server")
    enable_mcp_client: bool = Field(default=False, description="Enable MCP Client")
    mcp_server_configs: str = Field(default="[]", description="JSON list of external MCP server configs")

    # Structured Outputs
    enable_structured_outputs: bool = Field(default=True, description="Enable structured outputs")

    # Multi-Tenant
    enable_multi_tenant: bool = Field(default=False, description="Enable multi-organization support")
    default_organization_id: str = Field(default="default", description="Default org for unauthenticated users")

    # Living Memory System
    enable_core_memory_block: bool = Field(default=True, description="Compile structured user profile for all agents")
    core_memory_max_tokens: int = Field(default=800, ge=100, le=5000, description="Max tokens for core memory profile block")
    core_memory_cache_ttl: int = Field(default=300, ge=10, le=3600, description="Core memory cache TTL in seconds")
    enable_memory_decay: bool = Field(default=True, description="Enable Ebbinghaus importance decay on facts")
    enable_enhanced_extraction: bool = Field(default=True, description="Enable Mem0-style 15-type fact extraction")

    # Sprint 122: Configurable memory constants
    max_user_facts: int = Field(default=50, ge=1, le=500, description="Maximum user facts per user before eviction")
    character_cache_ttl: int = Field(default=60, ge=5, le=3600, description="Character block cache TTL in seconds")
    memory_prune_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="Prune facts with effective importance below this")
    fact_injection_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence for fact injection into prompt")
    max_injected_facts: int = Field(default=5, ge=1, le=50, description="Maximum facts injected into system prompt")
    enable_memory_pruning: bool = Field(default=True, description="Enable active memory pruning during extraction")

    # Character Reflection Engine
    enable_character_reflection: bool = Field(default=True, description="Enable periodic character self-reflection")
    character_reflection_interval: int = Field(default=5, ge=1, le=50, description="Reflect after every N conversations")
    enable_character_tools: bool = Field(default=True, description="Enable character self-editing tools")
    character_reflection_threshold: float = Field(default=5.0, description="Importance sum threshold for early reflection")
    character_experience_retention_days: int = Field(default=90, description="Delete experiences older than N days")
    character_experience_keep_min: int = Field(default=100, description="Always keep at least N most recent experiences")

    # Stanford Generative Agents Memory Retrieval
    stanford_recency_weight: float = Field(default=0.3, description="Weight for recency in Stanford memory ranking")
    stanford_importance_weight: float = Field(default=0.3, description="Weight for importance in Stanford memory ranking")
    stanford_relevance_weight: float = Field(default=0.4, description="Weight for relevance in Stanford memory ranking")

    # SOTA Personality System
    identity_anchor_interval: int = Field(default=6, ge=3, le=50, description="Re-inject identity anchor every N responses")
    enable_emotional_state: bool = Field(default=False, description="Enable 2D mood state machine")
    emotional_decay_rate: float = Field(default=0.15, ge=0.0, le=1.0, description="Rate of mood decay toward neutral")
    enable_personality_eval: bool = Field(default=False, description="Enable personality drift evaluator")

    # Soul Emotion
    enable_soul_emotion: bool = Field(default=False, description="Enable LLM inline emotion tags for avatar")
    soul_emotion_buffer_bytes: int = Field(default=512, ge=256, le=2048, description="Max bytes to buffer for soul emotion extraction")

    # Knowledge Management
    cross_domain_search: bool = Field(default=True, description="Search all domains with soft boost")
    domain_boost_score: float = Field(default=0.15, ge=0.0, le=1.0, description="RRF boost for same-domain results")
    enable_text_ingestion: bool = Field(default=True, description="Allow text/markdown ingestion via API")
    max_ingestion_size_mb: int = Field(default=50, ge=1, le=500, description="Maximum file size for ingestion in MB")

    # Semantic Fact Retrieval
    enable_semantic_fact_retrieval: bool = Field(default=True, description="Use embedding similarity for fact retrieval")
    fact_retrieval_alpha: float = Field(default=0.3, description="Importance weight in combined fact scoring")
    fact_retrieval_beta: float = Field(default=0.5, description="Cosine similarity weight in combined fact scoring")
    fact_retrieval_gamma: float = Field(default=0.2, description="Recency weight in combined fact scoring")
    fact_min_similarity: float = Field(default=0.3, description="Minimum cosine similarity for semantic fact retrieval")

    # Intelligent Tool Selection
    enable_tool_selection: bool = Field(default=False, description="Enable semantic tool pre-filtering")
    tool_selection_top_k: int = Field(default=5, description="Maximum tools after semantic selection")
    tool_selection_core_tools: list[str] = Field(
        default=["tool_current_datetime", "tool_knowledge_search", "tool_think"],
        description="Tools always included regardless of similarity score"
    )

    # LangSmith Observability
    enable_langsmith: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langsmith_project: str = Field(default="wiii", description="LangSmith project name")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")

    # Multi-Phase Thinking Chain
    enable_thinking_chain: bool = Field(default=False, description="Enable multi-phase thinking chain")

    # Living Agent System (Sprint 170)
    enable_living_agent: bool = Field(default=False, description="Enable Wiii's autonomous living agent system")
    living_agent_heartbeat_interval: int = Field(default=1800, ge=300, le=86400, description="Heartbeat interval in seconds (default 30 min)")
    living_agent_active_hours_start: int = Field(default=8, ge=0, le=23, description="Start hour for active period (UTC+7)")
    living_agent_active_hours_end: int = Field(default=23, ge=0, le=23, description="End hour for active period (UTC+7)")
    living_agent_local_model: str = Field(default="qwen3:8b", description="Local Ollama model for autonomous tasks")
    living_agent_max_browse_items: int = Field(default=10, ge=1, le=50, description="Max items to process per browsing session")
    living_agent_enable_social_browse: bool = Field(default=False, description="Allow Wiii to browse social media autonomously")
    living_agent_enable_skill_building: bool = Field(default=False, description="Allow Wiii to learn new skills autonomously")
    living_agent_enable_journal: bool = Field(default=True, description="Enable daily journal writing")
    living_agent_require_human_approval: bool = Field(default=True, description="Require human approval for external actions")
    living_agent_max_actions_per_heartbeat: int = Field(default=3, ge=1, le=10, description="Max actions per heartbeat cycle")
    living_agent_max_skills_per_week: int = Field(default=5, ge=1, le=20, description="Max new skills to discover per week")
    living_agent_max_searches_per_heartbeat: int = Field(default=3, ge=1, le=10, description="Max web searches per heartbeat cycle")
    living_agent_max_daily_cycles: int = Field(default=48, ge=1, le=200, description="Max heartbeat cycles per 24h")
    living_agent_callmebot_api_key: Optional[str] = Field(default=None, description="CallMeBot API key for Facebook Messenger notifications")
    living_agent_notification_channel: str = Field(default="websocket", description="Notification channel for heartbeat discoveries (websocket, telegram, messenger)")

    # Preview System (Sprint 166)
    enable_preview: bool = Field(default=True, description="Rich preview cards in streaming responses")

    # Artifact System (Sprint 167)
    enable_artifacts: bool = Field(default=True, description="Interactive artifacts (code execution, file preview)")

    # Product Search Agent
    enable_product_search: bool = Field(default=False, description="Enable product search agent")
    serper_api_key: Optional[str] = Field(default=None, description="Serper.dev API key")
    apify_api_token: Optional[str] = Field(default=None, description="Apify API token")
    product_search_max_results: int = Field(default=30, ge=1, le=100, description="Max results per platform search")
    product_search_timeout: int = Field(default=30, ge=5, le=120, description="Timeout for each platform search")

    # Sprint 149: Search Platform Plugin Architecture
    product_search_platforms: list = Field(
        default=["google_shopping", "shopee", "tiktok_shop", "lazada", "facebook_marketplace", "all_web", "instagram", "websosanh"],
        description="List of enabled search platform IDs",
    )
    enable_tiktok_native_api: bool = Field(default=False, description="Enable TikTok Research API")
    tiktok_client_key: Optional[str] = Field(default=None, description="TikTok Developer Portal client key")
    tiktok_client_secret: Optional[str] = Field(default=None, description="TikTok Developer Portal client secret")

    # Sprint 150: Deep Product Search
    product_search_max_iterations: int = Field(default=15, ge=5, le=30, description="Max ReAct iterations")
    product_search_scrape_timeout: int = Field(default=10, ge=3, le=30, description="Timeout for scraping product pages")
    product_search_max_scrape_pages: int = Field(default=10, ge=1, le=30, description="Max pages to scrape per session")

    # Browser Scraping
    enable_browser_scraping: bool = Field(default=False, description="Enable Playwright headless browser")
    browser_scraping_timeout: int = Field(default=15, ge=3, le=60, description="Timeout for browser page load")

    # Browser Screenshots
    enable_browser_screenshots: bool = Field(default=False, description="Stream browser screenshots to UI")
    browser_screenshot_quality: int = Field(default=40, description="JPEG quality for screenshots (10-90)")

    # Facebook Cookie Login (Sprint 154)
    enable_facebook_cookie: bool = Field(default=False, description="Allow Facebook cookie injection for logged-in search")

    # Facebook Group Search (Sprint 155)
    facebook_group_max_scrolls: int = Field(default=10, ge=3, le=20, description="Max scroll iterations for FB group search")
    facebook_group_scroll_delay: float = Field(default=2.5, ge=1.0, le=5.0, description="Delay between scrolls in group search (seconds)")
    facebook_scroll_max_scrolls: int = Field(default=8, ge=3, le=20, description="Max scroll iterations for general FB search (upgraded from 3)")

    # Network Interception (Sprint 156)
    enable_network_interception: bool = Field(default=True, description="Intercept GraphQL responses for structured product data")
    network_interception_max_response_size: int = Field(default=5_000_000, ge=100_000, le=50_000_000, description="Skip responses larger than this (bytes)")

    # Auto Group Discovery (Sprint 157)
    enable_auto_group_discovery: bool = Field(default=False, description="Auto-discover and search FB groups by product category")
    facebook_auto_group_max_groups: int = Field(default=3, ge=1, le=5, description="Max groups to auto-search per query")

    # OAuth skeleton
    enable_oauth_token_store: bool = Field(default=False, description="Enable OAuth token store")
    oauth_encryption_key: Optional[str] = Field(default=None, description="Fernet encryption key for OAuth tokens")

    # Quality & Model Config
    quality_skip_threshold: float = Field(default=0.85, description="Skip grader when confidence >= this")
    rag_model_version: str = Field(default="agentic-rag-v3", description="RAG model version string")
    insight_duplicate_threshold: float = Field(default=0.85, description="Duplicate insight detection threshold")
    insight_contradiction_threshold: float = Field(default=0.70, description="Contradiction detection threshold")

    # Security
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    mask_pii: bool = Field(default=True, description="Mask PII in logs")

    # =========================================================================
    # Sprint 154: Nested Config Groups (synced from flat fields)
    # =========================================================================
    # These provide structured access: settings.llm.google_api_key
    # Flat fields remain the source of truth for env var loading.
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, exclude=True)
    llm: LLMConfig = Field(default_factory=LLMConfig, exclude=True)
    rag: RAGConfig = Field(default_factory=RAGConfig, exclude=True)
    memory: MemoryConfig = Field(default_factory=MemoryConfig, exclude=True)
    product_search: ProductSearchConfig = Field(default_factory=ProductSearchConfig, exclude=True)
    thinking: ThinkingConfig = Field(default_factory=ThinkingConfig, exclude=True)
    character: CharacterConfig = Field(default_factory=CharacterConfig, exclude=True)
    cache: CacheConfig = Field(default_factory=CacheConfig, exclude=True)
    living_agent: LivingAgentConfig = Field(default_factory=LivingAgentConfig, exclude=True)
    lms: LMSIntegrationConfig = Field(default_factory=LMSIntegrationConfig, exclude=True)

    # =========================================================================
    # Field Validators
    # =========================================================================

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
    # Cross-field validators + security hardening
    # =========================================================================

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Validate security-critical settings in production."""
        if self.environment == "production":
            if self.jwt_secret_key == "change-me-in-production":
                raise ValueError(
                    "SECURITY: jwt_secret_key must be changed from default "
                    "in production. Set JWT_SECRET_KEY environment variable."
                )
            if self.cors_origins == ["*"]:
                _config_logger.warning(
                    "SECURITY WARNING: cors_origins=['*'] in production. "
                    "Set CORS_ORIGINS to specific allowed origins."
                )
        return self

    @model_validator(mode="after")
    def validate_cross_field_consistency(self) -> "Settings":
        """Validate related config fields are consistent."""
        if self.rag_confidence_high <= self.rag_confidence_medium:
            raise ValueError(
                f"rag_confidence_high ({self.rag_confidence_high}) must be > "
                f"rag_confidence_medium ({self.rag_confidence_medium})"
            )
        if self.async_pool_min_size > self.async_pool_max_size:
            raise ValueError(
                f"async_pool_min_size ({self.async_pool_min_size}) must be <= "
                f"async_pool_max_size ({self.async_pool_max_size})"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < "
                f"chunk_size ({self.chunk_size})"
            )
        # Sprint 153: Dependent feature flag validation
        if self.enable_tiktok_native_api and not self.enable_product_search:
            _config_logger.warning(
                "enable_tiktok_native_api=True requires enable_product_search=True — TikTok API will be unused"
            )
        if self.enable_browser_scraping and not self.enable_product_search:
            _config_logger.warning(
                "enable_browser_scraping=True requires enable_product_search=True — browser scraping will be unused"
            )
        if self.enable_oauth_token_store and not self.oauth_encryption_key:
            _config_logger.warning(
                "enable_oauth_token_store=True but oauth_encryption_key is not set — tokens will not be encrypted"
            )
        # Sprint 155: Facebook group search requires browser + cookie
        if "facebook_group" in self.product_search_platforms:
            if not self.enable_browser_scraping:
                _config_logger.warning(
                    "facebook_group in product_search_platforms requires enable_browser_scraping=True — group search disabled"
                )
            if not self.enable_facebook_cookie:
                _config_logger.warning(
                    "facebook_group in product_search_platforms requires enable_facebook_cookie=True — group search disabled"
                )
        # Sprint 157: Auto group discovery requires browser + cookie + facebook_group
        if self.enable_auto_group_discovery:
            if not self.enable_browser_scraping:
                _config_logger.warning(
                    "enable_auto_group_discovery=True requires enable_browser_scraping=True"
                )
            if not self.enable_facebook_cookie:
                _config_logger.warning(
                    "enable_auto_group_discovery=True requires enable_facebook_cookie=True"
                )
            if "facebook_group" not in self.product_search_platforms:
                _config_logger.warning(
                    "enable_auto_group_discovery=True but 'facebook_group' not in product_search_platforms"
                )
        # Sprint 157: Google OAuth validation
        if self.enable_google_oauth:
            if not self.google_oauth_client_id or not self.google_oauth_client_secret:
                _config_logger.warning(
                    "enable_google_oauth=True but google_oauth_client_id/secret not set — OAuth will not work"
                )
            if self.session_secret_key == "change-session-secret-in-production" and self.environment == "production":
                raise ValueError(
                    "SECURITY: session_secret_key must be changed from default in production. "
                    "Set SESSION_SECRET_KEY environment variable."
                )
        # Sprint 155: LMS integration without webhook secret
        if self.enable_lms_integration and not self.lms_webhook_secret:
            _config_logger.warning(
                "enable_lms_integration=True but lms_webhook_secret not set — webhooks will accept unsigned requests"
            )
        # Sprint 154: Fact retrieval weights must sum to ~1.0
        alpha = self.fact_retrieval_alpha
        beta = self.fact_retrieval_beta
        gamma = self.fact_retrieval_gamma
        if abs(alpha + beta + gamma - 1.0) > 0.01:
            raise ValueError(
                f"fact_retrieval alpha+beta+gamma must sum to 1.0, got {alpha + beta + gamma:.3f}"
            )
        return self

    @model_validator(mode="after")
    def _sync_nested_groups(self) -> "Settings":
        """Sync flat fields into nested config groups for structured access.

        Sprint 154: Nested groups are read-only views — flat fields are source of truth.
        """
        object.__setattr__(self, "database", DatabaseConfig(
            host=self.postgres_host,
            port=self.postgres_port,
            user=self.postgres_user,
            password=self.postgres_password,
            db=self.postgres_db,
            database_url=self.database_url,
            async_pool_min_size=self.async_pool_min_size,
            async_pool_max_size=self.async_pool_max_size,
        ))
        object.__setattr__(self, "llm", LLMConfig(
            provider=self.llm_provider,
            failover_chain=self.llm_failover_chain,
            enable_failover=self.enable_llm_failover,
            google_api_key=self.google_api_key,
            google_model=self.google_model,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            ollama_base_url=self.ollama_base_url,
            ollama_model=self.ollama_model,
            ollama_thinking_models=self.ollama_thinking_models,
        ))
        object.__setattr__(self, "rag", RAGConfig(
            enable_corrective_rag=self.enable_corrective_rag,
            quality_mode=self.rag_quality_mode,
            confidence_high=self.rag_confidence_high,
            confidence_medium=self.rag_confidence_medium,
            max_iterations=self.rag_max_iterations,
            enable_reflection=self.rag_enable_reflection,
            early_exit_on_high_confidence=self.rag_early_exit_on_high_confidence,
            grading_threshold=self.multi_agent_grading_threshold,
            retrieval_grade_threshold=self.retrieval_grade_threshold,
            enable_answer_verification=self.enable_answer_verification,
        ))
        object.__setattr__(self, "memory", MemoryConfig(
            enable_core_memory_block=self.enable_core_memory_block,
            core_memory_max_tokens=self.core_memory_max_tokens,
            core_memory_cache_ttl=self.core_memory_cache_ttl,
            max_user_facts=self.max_user_facts,
            max_injected_facts=self.max_injected_facts,
            fact_injection_min_confidence=self.fact_injection_min_confidence,
            enable_memory_decay=self.enable_memory_decay,
            enable_memory_pruning=self.enable_memory_pruning,
            enable_semantic_fact_retrieval=self.enable_semantic_fact_retrieval,
            fact_retrieval_alpha=self.fact_retrieval_alpha,
            fact_retrieval_beta=self.fact_retrieval_beta,
            fact_retrieval_gamma=self.fact_retrieval_gamma,
        ))
        object.__setattr__(self, "product_search", ProductSearchConfig(
            enable_product_search=self.enable_product_search,
            serper_api_key=self.serper_api_key,
            apify_api_token=self.apify_api_token,
            max_results=self.product_search_max_results,
            timeout=self.product_search_timeout,
            platforms=list(self.product_search_platforms),
            max_iterations=self.product_search_max_iterations,
            scrape_timeout=self.product_search_scrape_timeout,
            max_scrape_pages=self.product_search_max_scrape_pages,
            enable_tiktok_native_api=self.enable_tiktok_native_api,
            enable_browser_scraping=self.enable_browser_scraping,
            browser_scraping_timeout=self.browser_scraping_timeout,
            enable_browser_screenshots=self.enable_browser_screenshots,
            browser_screenshot_quality=self.browser_screenshot_quality,
            enable_network_interception=self.enable_network_interception,
            network_interception_max_response_size=self.network_interception_max_response_size,
            enable_auto_group_discovery=self.enable_auto_group_discovery,
            auto_group_max_groups=self.facebook_auto_group_max_groups,
        ))
        object.__setattr__(self, "thinking", ThinkingConfig(
            enabled=self.thinking_enabled,
            include_summaries=self.include_thought_summaries,
            budget_deep=self.thinking_budget_deep,
            budget_moderate=self.thinking_budget_moderate,
            budget_light=self.thinking_budget_light,
            budget_minimal=self.thinking_budget_minimal,
            gemini_level=self.gemini_thinking_level,
            enable_chain=self.enable_thinking_chain,
        ))
        object.__setattr__(self, "character", CharacterConfig(
            enable_reflection=self.enable_character_reflection,
            reflection_interval=self.character_reflection_interval,
            enable_tools=self.enable_character_tools,
            reflection_threshold=self.character_reflection_threshold,
            experience_retention_days=self.character_experience_retention_days,
            enable_emotional_state=self.enable_emotional_state,
            emotional_decay_rate=self.emotional_decay_rate,
            enable_soul_emotion=self.enable_soul_emotion,
        ))
        object.__setattr__(self, "cache", CacheConfig(
            enabled=self.semantic_cache_enabled,
            similarity_threshold=self.cache_similarity_threshold,
            response_ttl=self.cache_response_ttl,
            retrieval_ttl=self.cache_retrieval_ttl,
            max_entries=self.cache_max_response_entries,
            adaptive_ttl=self.cache_adaptive_ttl,
        ))
        object.__setattr__(self, "living_agent", LivingAgentConfig(
            enabled=self.enable_living_agent,
            heartbeat_interval=self.living_agent_heartbeat_interval,
            active_hours_start=self.living_agent_active_hours_start,
            active_hours_end=self.living_agent_active_hours_end,
            local_model=self.living_agent_local_model,
            max_browse_items=self.living_agent_max_browse_items,
            enable_social_browse=self.living_agent_enable_social_browse,
            enable_skill_building=self.living_agent_enable_skill_building,
            enable_journal=self.living_agent_enable_journal,
            require_human_approval=self.living_agent_require_human_approval,
            max_actions_per_heartbeat=self.living_agent_max_actions_per_heartbeat,
            max_skills_per_week=self.living_agent_max_skills_per_week,
            max_searches_per_heartbeat=self.living_agent_max_searches_per_heartbeat,
            max_daily_cycles=self.living_agent_max_daily_cycles,
            callmebot_api_key=self.living_agent_callmebot_api_key,
            notification_channel=self.living_agent_notification_channel,
        ))
        object.__setattr__(self, "lms", LMSIntegrationConfig(
            enabled=self.enable_lms_integration,
            base_url=self.lms_base_url,
            service_token=self.lms_service_token,
            webhook_secret=self.lms_webhook_secret,
            api_timeout=self.lms_api_timeout,
        ))
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Export settings instance for convenience
settings = get_settings()
