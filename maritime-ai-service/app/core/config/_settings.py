"""Settings class, validators, get_settings() factory and module-level singleton.

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

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.engine.llm_provider_registry import get_supported_provider_names
from app.engine.model_catalog import DEFAULT_EMBEDDING_MODEL, GOOGLE_DEFAULT_MODEL, get_embedding_dimensions

from app.core.config.database import DatabaseConfig
from app.core.config.llm import LLMConfig
from app.core.config.rag import RAGConfig
from app.core.config.memory import MemoryConfig
from app.core.config.product_search import ProductSearchConfig
from app.core.config.thinking import ThinkingConfig
from app.core.config.character import CharacterConfig
from app.core.config.cache import CacheConfig
from app.core.config.living_agent import LivingAgentConfig
from app.core.config.lms import LMSIntegrationConfig

_config_logger = logging.getLogger(__name__)


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
    jwt_expire_minutes: int = Field(default=15, description="JWT token expiration in minutes")

    # Google OAuth (Sprint 157: Đăng Nhập)
    enable_google_oauth: bool = Field(default=False, description="Enable Google OAuth login")
    google_oauth_client_id: Optional[str] = Field(default=None, description="Google OAuth 2.0 client ID")
    google_oauth_client_secret: Optional[str] = Field(default=None, description="Google OAuth 2.0 client secret")
    oauth_redirect_base_url: Optional[str] = Field(default=None, description="Base URL for OAuth callbacks (e.g. https://api.wiii.app)")
    session_secret_key: str = Field(default="change-session-secret-in-production", description="Session middleware secret for OAuth CSRF state")
    # Sprint 193: Allowed redirect origins for web OAuth (comma-separated whitelist)
    oauth_allowed_redirect_origins: str = Field(
        default="http://localhost:1420,http://localhost:1421",
        description="Comma-separated whitelist of allowed origins for web OAuth redirect_uri",
    )
    jwt_refresh_expire_days: int = Field(default=30, ge=1, le=365, description="Refresh token expiration in days")

    # LMS Token Exchange (Sprint 159: Cầu Nối Trực Tiếp)
    enable_lms_token_exchange: bool = Field(default=False, description="Enable LMS backend → Wiii JWT token exchange")
    lms_token_exchange_max_age: int = Field(default=300, ge=30, le=600, description="Max request age for replay protection (seconds)")

    # Magic Link Email Auth (Sprint 224)
    enable_magic_link_auth: bool = Field(default=False, description="Enable Magic Link email authentication")
    resend_api_key: str = Field(default="", description="Resend API key for sending magic link emails")
    magic_link_base_url: str = Field(default="http://localhost:8000", description="Base URL for magic link verification endpoint")
    magic_link_expires_seconds: int = Field(default=600, ge=60, le=3600, description="Magic link token expiry (default 10 min)")
    magic_link_from_email: str = Field(default="Wiii <noreply@wiii.app>", description="Sender email for magic links")
    magic_link_ws_timeout_seconds: int = Field(default=900, ge=60, le=3600, description="WebSocket session timeout (default 15 min)")
    magic_link_resend_cooldown_seconds: int = Field(default=45, ge=15, le=120, description="Cooldown between resend attempts")
    magic_link_max_per_hour: int = Field(default=5, ge=1, le=20, description="Max magic links per email per hour")

    # Sentry — Error Tracking (Production Hardening)
    sentry_dsn: str = Field(default="", description="Sentry DSN — empty disables Sentry")
    sentry_environment: str = Field(default="development", description="Sentry environment tag")
    sentry_traces_sample_rate: float = Field(default=0.2, ge=0.0, le=1.0, description="Sentry performance sampling rate")

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
    async_pool_min_size: int = Field(default=10, description="Minimum async connection pool size")
    async_pool_max_size: int = Field(default=50, description="Maximum async connection pool size")

    # PostgreSQL Safety (Sprint 171: CIS Benchmark 5.4)
    postgres_statement_timeout_ms: int = Field(default=30000, ge=1000, le=300000, description="Query timeout in ms (default 30s)")
    postgres_idle_in_transaction_timeout_ms: int = Field(default=60000, ge=10000, le=600000, description="Idle transaction timeout in ms (default 60s)")
    postgres_connect_timeout_seconds: int = Field(default=5, ge=1, le=60, description="Connection timeout in seconds for PostgreSQL clients")

    # Object Storage (MinIO / S3-compatible)
    minio_endpoint: Optional[str] = Field(default=None, description="MinIO endpoint (host:port, no scheme)")
    minio_external_endpoint: Optional[str] = Field(default=None, description="MinIO endpoint for browser-facing presigned URLs (defaults to minio_endpoint)")
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

    # Sprint 222: Universal Host Context Engine
    enable_host_context: bool = False       # Master gate for v2 host context
    enable_host_actions: bool = False       # Bidirectional host actions
    enable_host_skills: bool = False        # Dynamic YAML skill loading

    # Sprint 223: Hybrid Visual Context Engine
    enable_rich_page_context: bool = False  # Path A: structured data in host_context
    enable_visual_page_capture: bool = False  # Path B: on-demand screenshot + Vision
    visual_capture_timeout: float = 10.0  # Screenshot capture timeout (seconds)
    visual_capture_max_size: int = 1048576  # Max screenshot size (1MB)

    # Sprint 222b Phase 7: Standalone Browser Agent (Playwright MCP)
    enable_browser_agent: bool = False
    browser_agent_mcp_command: str = "npx"
    browser_agent_mcp_args: list = ["@playwright/mcp", "--headless"]
    browser_agent_timeout: int = 120  # seconds per browser session
    browser_agent_max_sessions_per_hour: int = 10

    # Code Studio streaming
    enable_code_studio_streaming: bool = Field(
        default=False,
        description="Emit chunked code_delta SSE events for Code Studio streaming display",
    )
    enable_real_code_streaming: bool = Field(
        default=False,
        description="Use astream for real token-by-token code generation (replaces fake chunking)",
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
            return self._append_connect_timeout(url)

        # Fallback to local Docker settings
        return self._append_connect_timeout(
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

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
            return self._remove_connect_timeout(url)
        return self._remove_connect_timeout(
            f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

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
            return self._append_connect_timeout(url)

        return self._append_connect_timeout(
            f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def _append_connect_timeout(self, url: str) -> str:
        """Add connect_timeout when missing so local misconfigurations fail fast."""
        if "connect_timeout=" in url:
            return url

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}connect_timeout={self.postgres_connect_timeout_seconds}"

    def _remove_connect_timeout(self, url: str) -> str:
        """Strip connect_timeout for asyncpg DSNs, which do not accept it as a server setting."""
        if "connect_timeout=" not in url:
            return url

        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "connect_timeout"
        ]
        return urlunsplit(parts._replace(query=urlencode(filtered_query)))

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
    openrouter_model_fallbacks: list[str] = Field(
        default_factory=list,
        description="Ordered fallback models for OpenRouter requests",
    )
    openrouter_provider_order: list[str] = Field(
        default_factory=list,
        description="Preferred OpenRouter providers in priority order",
    )
    openrouter_allowed_providers: list[str] = Field(
        default_factory=list,
        description="Restrict OpenRouter requests to these providers",
    )
    openrouter_ignored_providers: list[str] = Field(
        default_factory=list,
        description="Providers OpenRouter should avoid",
    )
    openrouter_allow_fallbacks: Optional[bool] = Field(
        default=None,
        description="Override OpenRouter provider fallback behavior",
    )
    openrouter_require_parameters: Optional[bool] = Field(
        default=None,
        description="Only choose OpenRouter providers that support all request params",
    )
    openrouter_data_collection: Optional[str] = Field(
        default=None,
        description="OpenRouter data collection policy: allow | deny",
    )
    openrouter_zdr: Optional[bool] = Field(
        default=None,
        description="Require Zero Data Retention providers on OpenRouter",
    )
    openrouter_provider_sort: Optional[str] = Field(
        default=None,
        description="OpenRouter provider sort: price | latency | throughput",
    )

    # LLM Settings - Google Gemini (cloud fallback)
    google_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    google_model: str = Field(
        default=GOOGLE_DEFAULT_MODEL,
        description="Google Gemini model (default: gemini-3.1-flash-lite-preview, current March 2026 default)",
    )
    llm_provider: str = Field(default="ollama", description="LLM provider: google, openai, openrouter, ollama")

    # LLM Settings - Ollama (local/self-hosted)
    ollama_api_key: Optional[str] = Field(
        default=None,
        description="Ollama Cloud API key for direct access to https://ollama.com/api",
    )
    ollama_base_url: Optional[str] = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_model: str = Field(
        default="qwen3:4b-instruct-2507-q4_K_M",
        description="Ollama model name (explicit Qwen3 instruct default)",
    )
    ollama_keep_alive: Optional[str] = Field(
        default="30m",
        description="How long Ollama should keep the active model loaded in memory",
    )
    ollama_thinking_models: list[str] = Field(
        default=["qwen3", "deepseek-r1", "qwq"],
        description="Models supporting thinking mode via Ollama (matched by prefix)"
    )

    # Multi-Provider Failover (Sprint 11: OpenClaw-inspired)
    llm_failover_chain: list[str] = Field(
        default=["ollama", "google", "openrouter"],
        description="LLM provider failover chain (try in order)"
    )
    enable_llm_failover: bool = Field(default=True, description="Enable automatic LLM provider failover")

    # Semantic Memory Settings (v0.3 - Vector Embeddings)
    embedding_model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="Gemini embedding model (production default remains gemini-embedding-001)",
    )
    embedding_dimensions: int = Field(
        default=get_embedding_dimensions(DEFAULT_EMBEDDING_MODEL),
        description="Embedding vector dimensions for the configured embedding model",
    )
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
    enable_messenger_webhook: bool = Field(default=False, description="Enable Facebook Messenger Platform webhook")
    facebook_app_id: Optional[str] = Field(default=None, description="Facebook App ID")
    facebook_app_secret: Optional[str] = Field(default=None, description="Facebook App Secret for X-Hub-Signature verification")
    facebook_page_id: Optional[str] = Field(default=None, description="Facebook Page ID")
    enable_zalo: bool = Field(default=False, description="Enable Zalo OA notification channel")
    zalo_oa_refresh_token: Optional[str] = Field(default=None, description="Zalo OA refresh token")
    zalo_oa_app_id: Optional[str] = Field(default=None, description="Zalo OA application ID")

    # Sprint 174b: OTP Identity Linking
    otp_link_expiry_seconds: int = Field(default=300, ge=60, le=900, description="OTP code expiry in seconds (default 5 min)")

    # Sprint 174: Cross-Platform Identity + Dual Personality
    enable_cross_platform_identity: bool = Field(default=False, description="Enable canonical identity resolution across platforms")
    enable_zalo_webhook: bool = Field(default=False, description="Enable Zalo OA incoming message webhook")
    zalo_webhook_token: Optional[str] = Field(default=None, description="Verify token for Zalo webhook handshake")
    default_personality_mode: str = Field(default="professional", description="Default personality mode: professional or soul")
    channel_personality_map: str = Field(
        default='{"web":"professional","desktop":"professional","messenger":"soul","zalo":"soul","telegram":"professional"}',
        description="JSON map of channel_type → personality mode",
    )

    # Sprint 176: Auth Hardening
    enable_auth_audit: bool = Field(default=True, description="Log auth events to auth_events table")

    # Sprint 192: Auth Hardening — "Khiên Sắt"
    enable_org_membership_check: bool = Field(default=True, description="Validate org membership on X-Organization-ID header")
    enable_jti_denylist: bool = Field(default=False, description="Enable in-memory JTI denylist for token revocation")
    jwt_audience: str = Field(default="wiii", description="JWT audience claim value")
    enforce_api_key_role_restriction: bool = Field(default=True, description="Block admin role via API key auth in production")
    otp_max_generate_per_window: int = Field(default=5, ge=1, le=20, description="Max OTP codes per user per window")
    otp_generate_window_minutes: int = Field(default=15, ge=1, le=60, description="OTP generation rate limit window (minutes)")
    otp_max_verify_attempts: int = Field(default=5, ge=1, le=10, description="Max failed OTP verify attempts before lockout")

    # Sprint 178: Admin Module
    enable_admin_module: bool = Field(default=False, description="Enable admin dashboard, audit, analytics")

    # Sprint 181: Org-Level Admin
    enable_org_admin: bool = Field(default=False, description="Enable org-level admin for org admins/owners")
    admin_ip_allowlist: str = Field(default="", description="Comma-separated IP allowlist for admin routes (empty=allow all)")
    admin_rate_limit: str = Field(default="30/minute", description="Rate limit for admin endpoints")

    # Sprint 190: Org Knowledge Management
    enable_org_knowledge: bool = Field(default=False, description="Enable org-level knowledge base management (upload/list/delete)")
    org_knowledge_max_file_size_mb: int = Field(default=50, ge=1, le=200, description="Max PDF file size in MB for org knowledge upload")
    org_knowledge_rate_limit: str = Field(default="5/minute", description="Per-org upload rate limit")

    # Sprint 191: Knowledge Visualization
    enable_knowledge_visualization: bool = Field(default=False, description="Enable knowledge base visualization (scatter, graph, RAG flow)")

    # Sprint 179: Multimodal Vision Input
    enable_vision: bool = Field(default=False, description="Enable vision/image understanding in chat")
    vision_max_images_per_request: int = Field(default=5, ge=1, le=20, description="Max images per chat request")
    vision_default_detail: str = Field(default="auto", description="Default vision detail level (low/auto/high)")
    vision_max_file_size_mb: int = Field(default=10, ge=1, le=50, description="Max image file size in MB")

    # Sprint 179: Chart/Diagram Generation
    enable_chart_tools: bool = Field(default=True, description="Enable Mermaid diagram and chart generation tools")
    enable_structured_visuals: bool = Field(
        default=True,
        description="Enable streaming-first structured inline visuals (VisualPayload v1 + SSE visual events)",
    )
    enable_code_gen_visuals: bool = Field(
        default=True,
        description="Route explanatory visuals to inline_html (code-gen) instead of template (card layout)",
    )
    enable_llm_code_gen_visuals: bool = Field(
        default=True,
        description="Allow LLM to write custom HTML/CSS/SVG via code_html param (Claude Artifacts style)",
    )

    # Sprint 179+: Visual RAG — understand charts/tables in documents
    enable_visual_rag: bool = Field(default=False, description="Enable visual context enrichment during RAG retrieval")
    visual_rag_max_images: int = Field(default=3, ge=1, le=10, description="Max images to analyze per RAG query")
    visual_rag_timeout: float = Field(default=15.0, ge=5.0, le=60.0, description="Timeout for image fetch + analysis (seconds)")

    # Sprint 182: Graph RAG — entity-aware knowledge graph retrieval
    enable_graph_rag: bool = Field(default=False, description="Enable entity extraction + graph context in RAG pipeline")
    graph_rag_max_entities: int = Field(default=5, ge=1, le=20, description="Max entities to extract per query")

    # Sprint 184: Temporal Knowledge Graph Memory
    enable_temporal_memory: bool = Field(default=False, description="Enable temporal knowledge graph for memory (entity-relation-episode)")

    # Sprint 186: Visual Memory — remember images users send
    enable_visual_memory: bool = Field(default=False, description="Enable image memory storage and retrieval")
    visual_memory_max_per_user: int = Field(default=100, ge=10, le=500, description="Max image memories per user")
    visual_memory_context_max_items: int = Field(default=3, ge=1, le=10, description="Max visual memories injected into context")

    # Sprint 187: Advanced RAG — HyDE + Adaptive RAG
    enable_hyde: bool = Field(default=False, description="Enable Hypothetical Document Embeddings for improved retrieval")
    hyde_blend_alpha: float = Field(default=0.5, ge=0.0, le=1.0, description="HyDE embedding blend weight (0=query only, 1=HyDE only)")
    enable_adaptive_rag: bool = Field(default=False, description="Enable adaptive routing to different retrieval strategies")

    # Sprint 176: Embed iframe support
    embed_allowed_origins: str = Field(
        default="",
        description="Space-separated list of allowed origins for iframe embedding (CSP frame-ancestors). Empty = 'self' only.",
    )

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
    enable_privileged_sandbox: bool = Field(default=False, description="Enable dedicated privileged sandbox executor for remote code/browser workloads")
    sandbox_provider: str = Field(default="disabled", description="Privileged sandbox provider: disabled, local_subprocess, opensandbox")
    sandbox_default_timeout_seconds: int = Field(default=120, ge=5, le=3600, description="Default timeout for remote sandbox workloads in seconds")
    sandbox_allow_browser_workloads: bool = Field(default=False, description="Allow browser-class workloads to use the privileged sandbox executor")
    opensandbox_base_url: Optional[str] = Field(default=None, description="Base URL for OpenSandbox control plane")
    opensandbox_api_key: Optional[str] = Field(default=None, description="API key for OpenSandbox control plane")
    opensandbox_healthcheck_path: str = Field(default="/health", description="Health check path for OpenSandbox control plane")
    opensandbox_code_template: str = Field(default="opensandbox/code-interpreter:v1.0.1", description="Default OpenSandbox runtime image for Python or command execution")
    opensandbox_browser_template: str = Field(default="opensandbox/playwright:latest", description="Default OpenSandbox runtime image for browser automation workloads")
    opensandbox_network_mode: str = Field(default="egress", description="OpenSandbox network mode: disabled, bridge, egress")
    opensandbox_keepalive_seconds: int = Field(default=600, ge=30, le=86400, description="How long an OpenSandbox session may stay alive for reuse before cleanup")
    enable_skill_creation: bool = Field(default=False, description="Enable runtime skill creation")

    # Unified LLM Client
    enable_unified_client: bool = Field(default=True, description="Enable UnifiedLLMClient (AsyncOpenAI SDK)")

    # Unified Providers (Phase 1: use ChatOpenAI for all providers via OpenAI-compatible endpoints)
    enable_unified_providers: bool = Field(
        default=False,
        description="Use ChatOpenAI for all LLM providers via OpenAI-compatible endpoints. "
                    "Eliminates langchain-google-genai and langchain-ollama dependencies.",
    )
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

    # MCP Tool Server (Sprint 193)
    enable_mcp_tool_server: bool = Field(default=False, description="Expose individual tools as MCP tool definitions")
    mcp_auto_register_external: bool = Field(default=False, description="Auto-register MCP external tools into ToolRegistry")

    # Structured Outputs
    enable_structured_outputs: bool = Field(default=True, description="Enable structured outputs")

    # Multi-Tenant
    enable_multi_tenant: bool = Field(default=False, description="Enable multi-organization support")
    default_organization_id: str = Field(default="default", description="Default org for unauthenticated users")
    enable_rls: bool = Field(default=False, description="Enable PostgreSQL Row-Level Security (requires enable_multi_tenant)")

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
    living_agent_local_model: str = Field(
        default="qwen3:4b-instruct-2507-q4_K_M",
        description="Local Ollama model for autonomous tasks",
    )
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

    # Soul AGI: Weather (Phase 1B)
    living_agent_enable_weather: bool = Field(default=False, description="Enable weather awareness via OpenWeatherMap")
    living_agent_weather_api_key: Optional[str] = Field(default=None, description="OpenWeatherMap API key")
    living_agent_weather_city: str = Field(default="Ho Chi Minh City", description="Default city for weather queries")

    # Soul AGI: Briefing (Phase 2A)
    living_agent_enable_briefing: bool = Field(default=False, description="Enable scheduled briefings (morning/midday/evening)")
    living_agent_briefing_channels: str = Field(default='["messenger"]', description="JSON list of channels for briefing delivery")
    living_agent_briefing_users: str = Field(default='[]', description="JSON list of user_ids to receive briefings")

    # Soul AGI: Routine Tracking (Phase 3B)
    living_agent_enable_routine_tracking: bool = Field(default=False, description="Track user behavior patterns for personalization")

    # Soul AGI: Dynamic Goals (Phase 4B)
    living_agent_enable_dynamic_goals: bool = Field(default=False, description="Enable evolving goal management")

    # Soul AGI: Proactive Messaging (Phase 5A)
    living_agent_enable_proactive_messaging: bool = Field(default=False, description="Allow Wiii to send messages proactively")
    living_agent_max_proactive_per_day: int = Field(default=3, ge=0, le=10, description="Max unsolicited messages per day per user")
    living_agent_proactive_quiet_start: int = Field(default=23, ge=0, le=23, description="Quiet hours start (UTC+7, no proactive messages)")
    living_agent_proactive_quiet_end: int = Field(default=5, ge=0, le=23, description="Quiet hours end (UTC+7)")

    # Soul AGI: Autonomy Graduation (Phase 5B)
    living_agent_autonomy_level: int = Field(default=0, ge=0, le=3, description="Current autonomy level (0=supervised, 3=full trust)")
    living_agent_enable_autonomy_graduation: bool = Field(default=False, description="Enable automatic trust level graduation")

    # Sprint 210: Living Continuity — conversations feed into Living Agent emotion/memory/episodes
    enable_living_continuity: bool = Field(default=False, description="Chat conversations feed into Living Agent emotion/memory/episodes (requires enable_living_agent)")

    # Sprint 210c: Relationship Tiers — emotion impact weighted by user closeness
    living_agent_creator_user_ids: str = Field(default="", description="Comma-separated user IDs treated as Tier 0 (creator). Plus anyone with role=admin")
    living_agent_known_user_threshold: int = Field(default=50, ge=5, le=1000, description="Minimum total_messages to qualify as Tier 1 (known user)")

    # Sprint 219: Adaptive Preference Learning — auto-infer learning preferences from conversation
    enable_adaptive_preferences: bool = Field(default=False, description="Enable behavioral inference rules in FactExtractor to auto-learn user preferences from conversation patterns")

    # Sprint 177: Real Skill Learning via Browsing
    living_agent_enable_skill_learning: bool = Field(default=False, description="Enable browsing→skill learning pipeline with SM-2 spaced repetition")
    living_agent_quiz_questions_per_session: int = Field(default=3, ge=1, le=10, description="Number of quiz questions per practice session")
    living_agent_review_confidence_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="EMA alpha weight for quiz→confidence updates")

    # Sprint 177: Cross-Platform Memory Sync
    enable_cross_platform_memory: bool = Field(default=False, description="Enable memory merge on OTP link + cross-platform context injection")
    cross_platform_context_max_items: int = Field(default=3, ge=1, le=10, description="Max items in cross-platform activity summary")

    # Facebook Messenger (for webhooks)
    facebook_verify_token: Optional[str] = Field(default=None, description="Facebook webhook verification token")
    facebook_page_access_token: Optional[str] = Field(default=None, description="Facebook Page access token for Send API")
    facebook_graph_api_version: str = Field(default="v22.0", description="Facebook Graph API version (Sprint 188)")

    # Zalo OA
    zalo_oa_access_token: Optional[str] = Field(default=None, description="Zalo OA access token")
    zalo_oa_secret_key: Optional[str] = Field(default=None, description="Zalo OA secret key for MAC verification")

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

    # Sprint 190: Enhanced Scraping Backends
    enable_crawl4ai: bool = Field(default=False, description="Enable Crawl4AI scraping backend (general web crawling + AI extraction)")
    crawl4ai_headless: bool = Field(default=True, description="Run Crawl4AI browser in headless mode")
    crawl4ai_use_llm_extraction: bool = Field(default=False, description="Use LLM extraction in Crawl4AI (costs tokens)")
    enable_scrapling: bool = Field(default=False, description="Enable Scrapling stealth scraping backend (anti-bot bypass)")
    scrapling_stealth_mode: bool = Field(default=True, description="Enable Scrapling TLS fingerprint spoofing for Cloudflare bypass")
    # Sprint 195: Jina Reader fallback
    enable_jina_reader: bool = Field(default=False, description="Enable Jina AI Reader as lightweight web-to-markdown fallback")

    # Sprint 196: Professional Product Sourcing
    enable_dealer_search: bool = Field(default=False, description="Enable dealer/distributor discovery via DuckDuckGo + Jina Reader")
    enable_contact_extraction: bool = Field(default=False, description="Enable contact info extraction from web pages (phone, Zalo, email)")
    enable_international_search: bool = Field(default=False, description="Enable international product search with USD→VND conversion")
    enable_advanced_excel_report: bool = Field(default=False, description="Enable 3-sheet Excel reports with dealer contacts and recommendations")
    usd_vnd_exchange_rate: float = Field(default=25500.0, description="USD to VND exchange rate for international price conversion")
    exchange_rate_overrides: dict = Field(
        default_factory=dict,
        description="Override exchange rates. Keys=ISO currency, values=to-USD factor. E.g. {'EUR': 1.10}",
    )

    # Sprint 200: Product Preview Cards (carousel in UI)
    enable_product_preview_cards: bool = Field(
        default=True,
        description="Emit SSE preview events for product search results (card carousel in UI)",
    )
    product_preview_max_cards: int = Field(
        default=20, ge=1, le=50,
        description="Max product preview cards emitted per search session",
    )

    # Sprint 200: Visual Product Search (image → product identification)
    enable_visual_product_search: bool = Field(
        default=False,
        description="Enable Vision LLM product identification from uploaded images",
    )
    visual_product_search_provider: str = Field(
        default="google",
        description="Vision provider for product identification: google, openai (extensible via _PROVIDER_REGISTRY)",
    )
    visual_product_search_model: str = Field(
        default="",
        description=(
            "Vision model for product identification. "
            "Empty = provider default. "
            "Google options: gemini-3.1-flash-lite-preview (default, latest 3.1 preview), "
            "gemini-3-flash-preview (3.0 general), gemini-3-pro-preview (3.0 quality). "
            "OpenAI options: gpt-4o (default), gpt-4o-mini."
        ),
    )

    # Sprint 201: Product Image Enrichment (Google-cached thumbnails for Serper site-filtered results)
    enable_product_image_enrichment: bool = Field(
        default=False,
        description="Enrich product search results with Google-cached thumbnail images via Serper /images API",
    )
    image_enrichment_timeout: int = Field(
        default=8, ge=2, le=30,
        description="Timeout in seconds for Serper /images API call",
    )
    image_enrichment_min_similarity: float = Field(
        default=0.4, ge=0.0, le=1.0,
        description="Minimum Jaccard title similarity for image-to-product matching (Sprint 201b: raised from 0.25 to reduce wrong matches)",
    )

    # Sprint 202: LLM-Curated Product Cards ("Kết Quả Sạch")
    enable_curated_product_cards: bool = Field(
        default=False,
        description="Suppress raw preview cards; emit only LLM-curated top picks after aggregation",
    )
    curated_product_max_cards: int = Field(
        default=8, ge=3, le=15,
        description="Max curated product cards to show (3-15)",
    )
    curated_product_llm_tier: str = Field(
        default="light",
        description="LLM tier for product curation: light (fast) / moderate / deep",
    )

    # Sprint 203: Natural Conversation (SOTA 2026)
    enable_natural_conversation: bool = Field(
        default=False,
        description="Phase-aware natural conversation — no canned greetings, positive framing, no word limits",
    )
    llm_presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0,
        description="LLM presence penalty for response diversity (Gemini/OpenAI)",
    )
    llm_frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0,
        description="LLM frequency penalty against repetition (Gemini/OpenAI)",
    )

    # Sprint 199: Chinese Platform Search (1688, Taobao, AliExpress)
    enable_chinese_platform_search: bool = Field(
        default=True,
        description="Include Chinese platforms (1688, Taobao, AliExpress) in international search",
    )

    # Sprint 198: Serper.dev for web/B2B search (replaces DuckDuckGo)
    enable_serper_web_search: bool = Field(default=True, description="Use Serper.dev for web/B2B search (requires SERPER_API_KEY, falls back to DuckDuckGo)")

    # Sprint 197: LLM Query Planner
    enable_query_planner: bool = Field(default=False, description="LLM query planning before product search (optimizes search queries for Vietnamese/B2B)")

    # Unified Skill Architecture (Sprint 191)
    enable_unified_skill_index: bool = Field(default=False, description="Enable unified skill index across all skill/tool systems")
    enable_skill_metrics: bool = Field(default=False, description="Track per-tool/skill execution metrics (latency, success, cost)")
    skill_metrics_flush_interval_seconds: int = Field(default=60, description="Seconds between DB flushes for skill metrics")

    # Skill ↔ Tool Bridge (Sprint 205)
    enable_skill_tool_bridge: bool = Field(default=False, description="Bridge tool execution to Living Agent skill advancement (DISCOVER→MASTER)")

    # Narrative Context (Sprint 206)
    enable_narrative_context: bool = Field(default=False, description="Inject Wiii's life narrative into system prompt (requires enable_living_agent)")

    # Identity Core (Sprint 207)
    enable_identity_core: bool = Field(default=False, description="Self-evolving identity layer — Wiii learns about itself from reflections (requires enable_living_agent)")

    # SoulBridge (Sprint 213)
    enable_soul_bridge: bool = Field(default=False, description="Enable cross-service soul-to-soul communication bridge (WebSocket + HTTP)")
    soul_bridge_peers: str = Field(default="", description="Comma-separated peer entries: 'peer_id=url' or 'url' (e.g., 'bro=http://localhost:8001')")
    soul_bridge_heartbeat_interval: int = Field(default=30, ge=5, description="SoulBridge peer heartbeat ping interval in seconds")
    soul_bridge_reconnect_max: int = Field(default=60, ge=5, description="Max reconnect backoff delay in seconds")
    soul_bridge_ws_path: str = Field(default="/api/v1/soul-bridge/ws", description="WebSocket path on peer service")
    soul_bridge_bridge_events: str = Field(default="ESCALATION,STATUS_UPDATE,MOOD_CHANGE,DISCOVERY,DAILY_REPORT,CONSULTATION,CONSULTATION_REPLY", description="Comma-separated event types to forward across bridge")

    # Cross-Soul Query Routing (Sprint 215)
    enable_cross_soul_query: bool = Field(default=False, description="Enable cross-soul consultation routing — admin asks Wiii, Wiii asks Bro")
    cross_soul_query_timeout: float = Field(default=15.0, ge=1.0, le=60.0, description="Timeout in seconds for cross-soul query response")
    cross_soul_query_peer_id: str = Field(default="bro", description="Default peer soul ID for cross-soul consultation")

    # Intelligent Tool Selection (Sprint 192)
    enable_intelligent_tool_selection: bool = Field(default=False, description="Enable intelligent tool selection (4-step pipeline)")
    tool_selection_strategy: str = Field(default="hybrid", description="Tool selection strategy: all, category, semantic, metrics, hybrid")
    tool_selection_max_candidates: int = Field(default=15, description="Maximum tools to select per query")

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
    cors_origin_regex: str = Field(default="", description="Regex pattern for CORS origin matching (e.g. r'https://.*\\.holilihu\\.online')")

    # Sprint 175: Subdomain → Org routing
    subdomain_base_domain: str = Field(default="", description="Base domain for subdomain org extraction (e.g. 'holilihu.online')")

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
        allowed = list(get_supported_provider_names())
        if v not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}")
        return v

    @field_validator("sandbox_provider")
    @classmethod
    def validate_sandbox_provider(cls, v: str) -> str:
        allowed = ["disabled", "local_subprocess", "opensandbox"]
        if v not in allowed:
            raise ValueError(f"sandbox_provider must be one of {allowed}")
        return v

    @field_validator("opensandbox_network_mode")
    @classmethod
    def validate_opensandbox_network_mode(cls, v: str) -> str:
        allowed = ["disabled", "bridge", "egress"]
        if v not in allowed:
            raise ValueError(
                f"opensandbox_network_mode must be one of {allowed}"
            )
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

    @field_validator(
        "openrouter_model_fallbacks",
        "openrouter_provider_order",
        "openrouter_allowed_providers",
        "openrouter_ignored_providers",
    )
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            value = item.strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

    @field_validator("openrouter_data_collection")
    @classmethod
    def validate_openrouter_data_collection(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {"allow", "deny"}
        if normalized not in allowed:
            raise ValueError(
                f"openrouter_data_collection must be one of {sorted(allowed)}"
            )
        return normalized

    @field_validator("openrouter_provider_sort")
    @classmethod
    def validate_openrouter_provider_sort(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {"price", "latency", "throughput"}
        if normalized not in allowed:
            raise ValueError(
                f"openrouter_provider_sort must be one of {sorted(allowed)}"
            )
        return normalized

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
            # Production: Block short API key
            if self.api_key and len(self.api_key) < 16:
                raise ValueError(
                    "SECURITY: api_key must be at least 16 characters in production. "
                    "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            # Production: Warn if magic link enabled without Resend key
            if (
                self.enable_magic_link_auth
                and not self.resend_api_key
            ):
                _config_logger.warning(
                    "SECURITY: enable_magic_link_auth=True but RESEND_API_KEY is empty — "
                    "magic link emails will fail silently"
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
        if self.enable_privileged_sandbox:
            if self.sandbox_provider == "disabled":
                _config_logger.warning(
                    "enable_privileged_sandbox=True but sandbox_provider='disabled' — dedicated sandbox executor will be unused"
                )
            if self.sandbox_provider == "opensandbox" and not self.opensandbox_base_url:
                _config_logger.warning(
                    "sandbox_provider='opensandbox' but opensandbox_base_url is not set — OpenSandbox executor will not connect"
                )
        if self.sandbox_provider == "opensandbox" and self.enable_browser_agent and not self.sandbox_allow_browser_workloads:
            _config_logger.warning(
                "enable_browser_agent=True with sandbox_provider='opensandbox' but sandbox_allow_browser_workloads=False — browser workloads stay outside the privileged sandbox"
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
        # Production Hardening: Session secret validation (unconditional in production)
        _BLOCKED_SECRETS = {
            "change-session-secret-in-production",
            "secret", "changeme", "your-secret-here",
            "supersecret",
        }
        if self.session_secret_key.lower() in _BLOCKED_SECRETS and self.environment == "production":
            raise ValueError(
                "SECURITY: session_secret_key must not be a default value in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(self.session_secret_key) < 32 and self.environment == "production":
            raise ValueError(
                f"SECURITY: session_secret_key must be at least 32 characters in production "
                f"(got {len(self.session_secret_key)}). "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(set(self.session_secret_key)) < 10 and self.environment == "production":
            raise ValueError(
                "SECURITY: session_secret_key has low entropy (too few unique characters). "
                "Use a cryptographically random value."
            )
        # Non-production: warn only
        if len(self.session_secret_key) < 32 and self.environment != "production":
            _config_logger.warning(
                "SECURITY: session_secret_key is %d chars — should be at least 32 for secure OAuth CSRF state",
                len(self.session_secret_key),
            )
        # Sprint 157: Google OAuth validation
        if self.enable_google_oauth:
            if not self.google_oauth_client_id or not self.google_oauth_client_secret:
                _config_logger.warning(
                    "enable_google_oauth=True but google_oauth_client_id/secret not set — OAuth will not work"
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
            openai_base_url=self.openai_base_url,
            openai_model=self.openai_model,
            openai_model_advanced=self.openai_model_advanced,
            openrouter_model_fallbacks=self.openrouter_model_fallbacks,
            openrouter_provider_order=self.openrouter_provider_order,
            openrouter_allowed_providers=self.openrouter_allowed_providers,
            openrouter_ignored_providers=self.openrouter_ignored_providers,
            openrouter_allow_fallbacks=self.openrouter_allow_fallbacks,
            openrouter_require_parameters=self.openrouter_require_parameters,
            openrouter_data_collection=self.openrouter_data_collection,
            openrouter_zdr=self.openrouter_zdr,
            openrouter_provider_sort=self.openrouter_provider_sort,
            ollama_api_key=self.ollama_api_key,
            ollama_base_url=self.ollama_base_url,
            ollama_model=self.ollama_model,
            ollama_keep_alive=self.ollama_keep_alive,
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
            enable_skill_learning=self.living_agent_enable_skill_learning,
            quiz_questions_per_session=self.living_agent_quiz_questions_per_session,
            review_confidence_weight=self.living_agent_review_confidence_weight,
        ))
        object.__setattr__(self, "lms", LMSIntegrationConfig(
            enabled=self.enable_lms_integration,
            base_url=self.lms_base_url,
            service_token=self.lms_service_token,
            webhook_secret=self.lms_webhook_secret,
            api_timeout=self.lms_api_timeout,
        ))
        return self

    def refresh_nested_views(self) -> None:
        """Refresh nested config snapshots after runtime field mutation."""
        self._sync_nested_groups()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Export settings instance for convenience
settings = get_settings()
