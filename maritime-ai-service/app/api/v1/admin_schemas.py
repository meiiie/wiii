"""Admin API schemas extracted from admin.py."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    job_id: str = Field(..., description="Ingestion job ID for status tracking")
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="pending | processing | completed | failed")
    message: str = Field(..., description="Status message")


class DocumentStatus(BaseModel):
    """Document ingestion status."""

    job_id: str
    document_id: str
    status: str
    progress_percent: float = 0.0
    total_pages: int = 0
    processed_pages: int = 0
    error: Optional[str] = None


class DocumentInfo(BaseModel):
    """Document information."""

    document_id: str
    title: str
    total_pages: int
    total_chunks: int
    created_at: str
    status: str


class ModelCatalogEntry(BaseModel):
    provider: str
    model_name: str
    display_name: str
    status: str
    released_on: Optional[str] = None
    is_default: bool = False


class ProviderRuntimeStatus(BaseModel):
    provider: str
    display_name: str
    configured: bool
    available: bool
    registered: bool
    request_selectable: bool
    in_failover_chain: bool
    is_default: bool
    is_active: bool
    configurable_via_admin: bool
    reason_code: Optional[str] = None
    reason_label: Optional[str] = None


class EmbeddingProviderRuntimeStatus(BaseModel):
    provider: str
    display_name: str
    configured: bool
    available: bool
    in_failover_chain: bool
    is_default: bool
    is_active: bool
    selected_model: Optional[str] = None
    selected_dimensions: Optional[int] = None
    supports_dimension_override: bool = False
    reason_code: Optional[str] = None
    reason_label: Optional[str] = None


class VisionCapabilityRuntimeStatus(BaseModel):
    capability: str
    display_name: str
    available: bool
    selected_model: Optional[str] = None
    lane_fit: Optional[str] = None
    lane_fit_label: Optional[str] = None
    reason_code: Optional[str] = None
    reason_label: Optional[str] = None
    resolved_base_url: Optional[str] = None
    last_probe_attempt_at: Optional[str] = None
    last_probe_success_at: Optional[str] = None
    last_probe_error: Optional[str] = None
    live_probe_note: Optional[str] = None
    last_runtime_observation_at: Optional[str] = None
    last_runtime_success_at: Optional[str] = None
    last_runtime_error: Optional[str] = None
    last_runtime_note: Optional[str] = None
    last_runtime_source: Optional[str] = None
    recovered: bool = False
    recovered_label: Optional[str] = None


class VisionProviderRuntimeStatus(BaseModel):
    provider: str
    display_name: str
    configured: bool
    available: bool
    in_failover_chain: bool
    is_default: bool
    is_active: bool
    selected_model: Optional[str] = None
    reason_code: Optional[str] = None
    reason_label: Optional[str] = None
    last_probe_attempt_at: Optional[str] = None
    last_probe_success_at: Optional[str] = None
    last_probe_error: Optional[str] = None
    last_runtime_observation_at: Optional[str] = None
    last_runtime_success_at: Optional[str] = None
    last_runtime_error: Optional[str] = None
    last_runtime_note: Optional[str] = None
    last_runtime_source: Optional[str] = None
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    recovered: bool = False
    recovered_reasons: list[str] = Field(default_factory=list)
    capabilities: list[VisionCapabilityRuntimeStatus] = Field(default_factory=list)


class EmbeddingSpaceContractSummary(BaseModel):
    provider: str
    model: str
    dimensions: int
    fingerprint: str
    label: str


class EmbeddingSpaceTableSummary(BaseModel):
    table_name: str
    embedded_row_count: int
    tracked_row_count: int
    untracked_row_count: int
    fingerprints: dict[str, int] = Field(default_factory=dict)


class EmbeddingMigrationPreview(BaseModel):
    target_model: str
    target_provider: str
    target_dimensions: int
    target_label: str
    target_status: str
    same_space: bool
    allowed: bool
    requires_reembed: bool
    target_backend_constructible: bool = False
    maintenance_required: bool = False
    embedded_row_count: int
    blocking_tables: list[str] = Field(default_factory=list)
    mixed_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    detail: Optional[str] = None


class EmbeddingSpaceMigrationTablePlanSummary(BaseModel):
    table_name: str
    candidate_rows: int
    embedded_rows: int
    tracked_rows: int
    untracked_rows: int


class EmbeddingSpaceMigrationPlanRequest(BaseModel):
    target_model: str = Field(min_length=1, max_length=200)
    target_dimensions: Optional[int] = Field(default=None, ge=128, le=4096)
    tables: Optional[list[str]] = None


class EmbeddingSpaceMigrationPlanResponse(BaseModel):
    current_contract_fingerprint: Optional[str] = None
    target_contract_fingerprint: Optional[str] = None
    current_contract_label: Optional[str] = None
    target_contract_label: Optional[str] = None
    same_space: bool
    transition_allowed: bool
    target_backend_constructible: bool
    maintenance_required: bool
    total_candidate_rows: int
    total_embedded_rows: int
    tables: list[EmbeddingSpaceMigrationTablePlanSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    detail: Optional[str] = None


class EmbeddingSpaceMigrationTableResultSummary(BaseModel):
    table_name: str
    candidate_rows: int
    updated_rows: int
    skipped_rows: int
    failed_rows: int


class EmbeddingSpaceMigrationRunRequest(BaseModel):
    target_model: str = Field(min_length=1, max_length=200)
    target_dimensions: Optional[int] = Field(default=None, ge=128, le=4096)
    dry_run: bool = True
    batch_size: int = Field(default=16, ge=1, le=512)
    limit_per_table: Optional[int] = Field(default=None, ge=1, le=100000)
    tables: Optional[list[str]] = None
    acknowledge_maintenance_window: bool = False


class EmbeddingSpaceMigrationRunResponse(BaseModel):
    dry_run: bool
    maintenance_acknowledged: bool
    current_contract_fingerprint: Optional[str] = None
    target_contract_fingerprint: Optional[str] = None
    target_backend_constructible: bool
    tables: list[EmbeddingSpaceMigrationTableResultSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detail: Optional[str] = None
    recommended_next_steps: list[str] = Field(default_factory=list)


class EmbeddingSpaceMigrationPromoteRequest(BaseModel):
    target_model: str = Field(min_length=1, max_length=200)
    target_dimensions: Optional[int] = Field(default=None, ge=128, le=4096)
    tables: Optional[list[str]] = None
    acknowledge_maintenance_window: bool = False


class EmbeddingSpaceStatusSummary(BaseModel):
    audit_available: bool
    policy_contract: Optional[EmbeddingSpaceContractSummary] = None
    active_contract: Optional[EmbeddingSpaceContractSummary] = None
    active_matches_policy: Optional[bool] = None
    total_embedded_rows: int = 0
    total_tracked_rows: int = 0
    total_untracked_rows: int = 0
    tables: list[EmbeddingSpaceTableSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class ProviderCatalogCapability(BaseModel):
    provider: str
    display_name: str
    configured: bool
    available: bool
    request_selectable: bool
    configurable_via_admin: bool
    supports_runtime_discovery: bool = True
    runtime_discovery_enabled: bool = False
    runtime_discovery_succeeded: bool = False
    catalog_source: str = "static"
    model_count: int = 0
    discovered_model_count: int = 0
    selected_model: Optional[str] = None
    selected_model_in_catalog: bool = False
    selected_model_advanced: Optional[str] = None
    selected_model_advanced_in_catalog: bool = False
    last_discovery_attempt_at: Optional[str] = None
    last_discovery_success_at: Optional[str] = None
    last_live_probe_attempt_at: Optional[str] = None
    last_live_probe_success_at: Optional[str] = None
    last_live_probe_error: Optional[str] = None
    live_probe_note: Optional[str] = None
    last_runtime_observation_at: Optional[str] = None
    last_runtime_success_at: Optional[str] = None
    last_runtime_error: Optional[str] = None
    last_runtime_note: Optional[str] = None
    last_runtime_source: Optional[str] = None
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    recovered: bool = False
    recovered_reasons: list[str] = Field(default_factory=list)
    tool_calling_supported: Optional[bool] = None
    tool_calling_source: Optional[str] = None
    structured_output_supported: Optional[bool] = None
    structured_output_source: Optional[str] = None
    streaming_supported: Optional[bool] = None
    streaming_source: Optional[str] = None
    context_window_tokens: Optional[int] = None
    context_window_source: Optional[str] = None
    max_output_tokens: Optional[int] = None
    max_output_source: Optional[str] = None


class ModelCatalogResponse(BaseModel):
    providers: dict[str, list[ModelCatalogEntry]]
    embedding_models: list[ModelCatalogEntry] = Field(default_factory=list)
    provider_capabilities: dict[str, ProviderCatalogCapability] = Field(default_factory=dict)
    ollama_discovered: bool = False
    audit_updated_at: Optional[str] = None
    last_live_probe_at: Optional[str] = None
    degraded_providers: list[str] = Field(default_factory=list)
    audit_persisted: bool = False
    audit_warnings: list[str] = Field(default_factory=list)
    timestamp: str


class AgentRuntimeProfileConfig(BaseModel):
    default_provider: str = ""
    tier: str
    provider_models: dict[str, str] = Field(default_factory=dict)


class LlmTimeoutProfilesConfig(BaseModel):
    light_seconds: float = Field(ge=0, le=600)
    moderate_seconds: float = Field(ge=0, le=900)
    deep_seconds: float = Field(ge=0, le=1800)
    structured_seconds: float = Field(ge=0, le=1800)
    background_seconds: float = Field(ge=0, le=3600)
    stream_keepalive_interval_seconds: float = Field(ge=1, le=300)
    stream_idle_timeout_seconds: float = Field(ge=0, le=3600)


class LlmTimeoutProviderOverride(BaseModel):
    light_seconds: Optional[float] = Field(default=None, ge=0, le=600)
    moderate_seconds: Optional[float] = Field(default=None, ge=0, le=900)
    deep_seconds: Optional[float] = Field(default=None, ge=0, le=1800)
    structured_seconds: Optional[float] = Field(default=None, ge=0, le=1800)
    background_seconds: Optional[float] = Field(default=None, ge=0, le=3600)


class LlmRuntimeConfigResponse(BaseModel):
    provider: str
    use_multi_agent: bool
    google_model: str
    openai_base_url: Optional[str] = None
    openai_model: str
    openai_model_advanced: str
    openrouter_base_url: Optional[str] = None
    openrouter_model: str
    openrouter_model_advanced: str
    nvidia_base_url: Optional[str] = None
    nvidia_model: str
    nvidia_model_advanced: str
    zhipu_base_url: Optional[str] = None
    zhipu_model: str
    zhipu_model_advanced: str
    openrouter_model_fallbacks: list[str] = Field(default_factory=list)
    openrouter_provider_order: list[str] = Field(default_factory=list)
    openrouter_allowed_providers: list[str] = Field(default_factory=list)
    openrouter_ignored_providers: list[str] = Field(default_factory=list)
    openrouter_allow_fallbacks: Optional[bool] = None
    openrouter_require_parameters: Optional[bool] = None
    openrouter_data_collection: Optional[str] = None
    openrouter_zdr: Optional[bool] = None
    openrouter_provider_sort: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: str
    ollama_keep_alive: Optional[str] = None
    google_api_key_configured: bool
    openai_api_key_configured: bool
    openrouter_api_key_configured: bool
    nvidia_api_key_configured: bool
    zhipu_api_key_configured: bool
    ollama_api_key_configured: bool
    enable_llm_failover: bool
    llm_failover_chain: list[str]
    active_provider: Optional[str] = None
    providers_registered: list[str] = Field(default_factory=list)
    request_selectable_providers: list[str] = Field(default_factory=list)
    provider_status: list[ProviderRuntimeStatus] = Field(default_factory=list)
    agent_profiles: dict[str, AgentRuntimeProfileConfig] = Field(default_factory=dict)
    timeout_profiles: LlmTimeoutProfilesConfig
    timeout_provider_overrides: dict[str, LlmTimeoutProviderOverride] = Field(default_factory=dict)
    vision_provider: str = "auto"
    vision_describe_provider: str = "auto"
    vision_describe_model: Optional[str] = None
    vision_ocr_provider: str = "auto"
    vision_ocr_model: Optional[str] = None
    vision_grounded_provider: str = "auto"
    vision_grounded_model: Optional[str] = None
    vision_failover_chain: list[str] = Field(default_factory=list)
    vision_timeout_seconds: float = 30.0
    vision_provider_status: list[VisionProviderRuntimeStatus] = Field(default_factory=list)
    vision_audit_updated_at: Optional[str] = None
    vision_last_live_probe_at: Optional[str] = None
    vision_audit_persisted: bool = False
    vision_audit_warnings: list[str] = Field(default_factory=list)
    embedding_provider: str = "auto"
    embedding_failover_chain: list[str] = Field(default_factory=list)
    embedding_model: str
    embedding_dimensions: int
    embedding_status: str
    embedding_provider_status: list[EmbeddingProviderRuntimeStatus] = Field(default_factory=list)
    embedding_space_status: Optional[EmbeddingSpaceStatusSummary] = None
    embedding_migration_previews: list[EmbeddingMigrationPreview] = Field(default_factory=list)
    runtime_policy_persisted: bool = False
    runtime_policy_updated_at: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class LlmRuntimeConfigUpdate(BaseModel):
    provider: Optional[str] = Field(
        default=None,
        description="google | zhipu | openai | openrouter | nvidia | ollama",
    )
    use_multi_agent: Optional[bool] = None
    google_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    clear_google_api_key: bool = False
    google_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    clear_openai_api_key: bool = False
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    clear_openrouter_api_key: bool = False
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    openai_model_advanced: Optional[str] = Field(default=None, min_length=1, max_length=200)
    openrouter_base_url: Optional[str] = None
    openrouter_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    openrouter_model_advanced: Optional[str] = Field(default=None, min_length=1, max_length=200)
    nvidia_api_key: Optional[str] = Field(default=None, description="NVIDIA NIM API key")
    clear_nvidia_api_key: bool = False
    nvidia_base_url: Optional[str] = None
    nvidia_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    nvidia_model_advanced: Optional[str] = Field(default=None, min_length=1, max_length=200)
    zhipu_api_key: Optional[str] = Field(default=None, description="Zhipu AI / GLM API key")
    clear_zhipu_api_key: bool = False
    zhipu_base_url: Optional[str] = None
    zhipu_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    zhipu_model_advanced: Optional[str] = Field(default=None, min_length=1, max_length=200)
    openrouter_model_fallbacks: Optional[list[str]] = None
    openrouter_provider_order: Optional[list[str]] = None
    openrouter_allowed_providers: Optional[list[str]] = None
    openrouter_ignored_providers: Optional[list[str]] = None
    openrouter_allow_fallbacks: Optional[bool] = None
    openrouter_require_parameters: Optional[bool] = None
    openrouter_data_collection: Optional[str] = None
    openrouter_zdr: Optional[bool] = None
    openrouter_provider_sort: Optional[str] = None
    ollama_api_key: Optional[str] = Field(default=None, description="Ollama Cloud API key")
    clear_ollama_api_key: bool = False
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    ollama_keep_alive: Optional[str] = None
    enable_llm_failover: Optional[bool] = None
    llm_failover_chain: Optional[list[str]] = None
    agent_profiles: Optional[dict[str, AgentRuntimeProfileConfig]] = None
    timeout_profiles: Optional[LlmTimeoutProfilesConfig] = None
    timeout_provider_overrides: Optional[dict[str, LlmTimeoutProviderOverride]] = None
    vision_provider: Optional[str] = Field(
        default=None,
        description="auto | google | zhipu | openai | openrouter | ollama",
    )
    vision_describe_provider: Optional[str] = Field(
        default=None,
        description="auto | google | zhipu | openai | openrouter | ollama",
    )
    vision_describe_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vision_ocr_provider: Optional[str] = Field(
        default=None,
        description="auto | google | zhipu | openai | openrouter | ollama",
    )
    vision_ocr_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vision_grounded_provider: Optional[str] = Field(
        default=None,
        description="auto | google | zhipu | openai | openrouter | ollama",
    )
    vision_grounded_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vision_failover_chain: Optional[list[str]] = None
    vision_timeout_seconds: Optional[float] = Field(default=None, ge=5.0, le=120.0)
    embedding_provider: Optional[str] = Field(
        default=None,
        description="auto | google | zhipu | openai | openrouter | ollama",
    )
    embedding_failover_chain: Optional[list[str]] = None
    embedding_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    embedding_dimensions: Optional[int] = Field(default=None, ge=128, le=4096)


class LlmRuntimeAuditRefreshRequest(BaseModel):
    providers: Optional[list[str]] = None


class DomainSummary(BaseModel):
    """Domain plugin summary for list endpoint."""

    id: str
    name: str
    name_vi: str
    version: str
    description: str
    skill_count: int
    keyword_count: int


class DomainDetail(BaseModel):
    """Full domain plugin detail."""

    id: str
    name: str
    name_vi: str
    version: str
    description: str
    routing_keywords: list[str]
    mandatory_search_triggers: list[str]
    rag_agent_description: str
    tutor_agent_description: str
    skills: list[dict]
    has_prompts: bool
    has_hyde_templates: bool


class SkillDetail(BaseModel):
    """Skill manifest detail."""

    id: str
    name: str
    description: str
    domain_id: str
    version: str
    triggers: list[str]
    content_length: int
