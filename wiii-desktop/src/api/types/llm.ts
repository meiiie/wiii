export interface LlmRuntimeConfig {
  provider: "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  use_multi_agent: boolean;
  google_model: string;
  openai_base_url?: string | null;
  openai_model: string;
  openai_model_advanced: string;
  openrouter_base_url?: string | null;
  openrouter_model: string;
  openrouter_model_advanced: string;
  nvidia_base_url?: string | null;
  nvidia_model: string;
  nvidia_model_advanced: string;
  zhipu_base_url?: string | null;
  zhipu_model: string;
  zhipu_model_advanced: string;
  openrouter_model_fallbacks: string[];
  openrouter_provider_order: string[];
  openrouter_allowed_providers: string[];
  openrouter_ignored_providers: string[];
  openrouter_allow_fallbacks?: boolean | null;
  openrouter_require_parameters?: boolean | null;
  openrouter_data_collection?: "allow" | "deny" | null;
  openrouter_zdr?: boolean | null;
  openrouter_provider_sort?: "price" | "latency" | "throughput" | null;
  ollama_base_url?: string | null;
  ollama_model: string;
  ollama_keep_alive?: string | null;
  google_api_key_configured: boolean;
  openai_api_key_configured: boolean;
  openrouter_api_key_configured: boolean;
  nvidia_api_key_configured: boolean;
  zhipu_api_key_configured: boolean;
  ollama_api_key_configured: boolean;
  enable_llm_failover: boolean;
  llm_failover_chain: string[];
  active_provider?: string | null;
  providers_registered: string[];
  request_selectable_providers: string[];
  provider_status: ProviderRuntimeStatus[];
  agent_profiles: Record<string, AgentRuntimeProfileConfig>;
  timeout_profiles: LlmTimeoutProfilesConfig;
  timeout_provider_overrides: Record<string, LlmTimeoutProviderOverride>;
  vision_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_describe_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_describe_model?: string | null;
  vision_ocr_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_ocr_model?: string | null;
  vision_grounded_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_grounded_model?: string | null;
  vision_failover_chain?: string[];
  vision_timeout_seconds: number;
  vision_provider_status?: VisionProviderRuntimeStatus[];
  vision_audit_updated_at?: string | null;
  vision_last_live_probe_at?: string | null;
  vision_audit_persisted?: boolean;
  vision_audit_warnings?: string[];
  embedding_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  embedding_failover_chain?: string[];
  embedding_model: string;
  embedding_dimensions: number;
  embedding_status: string;
  embedding_provider_status?: EmbeddingProviderRuntimeStatus[];
  embedding_space_status?: EmbeddingSpaceStatusSummary | null;
  embedding_migration_previews?: EmbeddingMigrationPreview[];
  runtime_policy_persisted: boolean;
  runtime_policy_updated_at?: string | null;
  warnings: string[];
}

export interface ProviderRuntimeStatus {
  provider: string;
  display_name: string;
  configured: boolean;
  available: boolean;
  registered: boolean;
  request_selectable: boolean;
  in_failover_chain: boolean;
  is_default: boolean;
  is_active: boolean;
  configurable_via_admin: boolean;
  reason_code?: ProviderDisabledReasonCode | string | null;
  reason_label?: string | null;
}

export interface EmbeddingProviderRuntimeStatus {
  provider: string;
  display_name: string;
  configured: boolean;
  available: boolean;
  in_failover_chain: boolean;
  is_default: boolean;
  is_active: boolean;
  selected_model?: string | null;
  selected_dimensions?: number | null;
  supports_dimension_override: boolean;
  reason_code?: string | null;
  reason_label?: string | null;
}

export interface VisionCapabilityRuntimeStatus {
  capability: string;
  display_name: string;
  available: boolean;
  selected_model?: string | null;
  lane_fit?: string | null;
  lane_fit_label?: string | null;
  reason_code?: string | null;
  reason_label?: string | null;
  resolved_base_url?: string | null;
  last_probe_attempt_at?: string | null;
  last_probe_success_at?: string | null;
  last_probe_error?: string | null;
  live_probe_note?: string | null;
  last_runtime_observation_at?: string | null;
  last_runtime_success_at?: string | null;
  last_runtime_error?: string | null;
  last_runtime_note?: string | null;
  last_runtime_source?: string | null;
  recovered?: boolean;
  recovered_label?: string | null;
}

export interface VisionProviderRuntimeStatus {
  provider: string;
  display_name: string;
  configured: boolean;
  available: boolean;
  in_failover_chain: boolean;
  is_default: boolean;
  is_active: boolean;
  selected_model?: string | null;
  reason_code?: string | null;
  reason_label?: string | null;
  last_probe_attempt_at?: string | null;
  last_probe_success_at?: string | null;
  last_probe_error?: string | null;
  last_runtime_observation_at?: string | null;
  last_runtime_success_at?: string | null;
  last_runtime_error?: string | null;
  last_runtime_note?: string | null;
  last_runtime_source?: string | null;
  degraded?: boolean;
  degraded_reasons?: string[];
  recovered?: boolean;
  recovered_reasons?: string[];
  capabilities: VisionCapabilityRuntimeStatus[];
}

export interface EmbeddingSpaceContractSummary {
  provider: string;
  model: string;
  dimensions: number;
  fingerprint: string;
  label: string;
}

export interface EmbeddingSpaceTableSummary {
  table_name: string;
  embedded_row_count: number;
  tracked_row_count: number;
  untracked_row_count: number;
  fingerprints: Record<string, number>;
}

export interface EmbeddingMigrationPreview {
  target_model: string;
  target_provider: string;
  target_dimensions: number;
  target_label: string;
  target_status: string;
  same_space: boolean;
  allowed: boolean;
  requires_reembed: boolean;
  target_backend_constructible: boolean;
  maintenance_required: boolean;
  embedded_row_count: number;
  blocking_tables: string[];
  mixed_tables: string[];
  warnings: string[];
  recommended_steps: string[];
  detail?: string | null;
}

export interface EmbeddingSpaceStatusSummary {
  audit_available: boolean;
  policy_contract?: EmbeddingSpaceContractSummary | null;
  active_contract?: EmbeddingSpaceContractSummary | null;
  active_matches_policy?: boolean | null;
  total_embedded_rows: number;
  total_tracked_rows: number;
  total_untracked_rows: number;
  tables: EmbeddingSpaceTableSummary[];
  warnings: string[];
  error?: string | null;
}

export interface EmbeddingSpaceMigrationTablePlanSummary {
  table_name: string;
  candidate_rows: number;
  embedded_rows: number;
  tracked_rows: number;
  untracked_rows: number;
}

export interface EmbeddingSpaceMigrationPlanRequest {
  target_model: string;
  target_dimensions?: number;
  tables?: string[];
}

export interface EmbeddingSpaceMigrationPlanResponse {
  current_contract_fingerprint?: string | null;
  target_contract_fingerprint?: string | null;
  current_contract_label?: string | null;
  target_contract_label?: string | null;
  same_space: boolean;
  transition_allowed: boolean;
  target_backend_constructible: boolean;
  maintenance_required: boolean;
  total_candidate_rows: number;
  total_embedded_rows: number;
  tables: EmbeddingSpaceMigrationTablePlanSummary[];
  warnings: string[];
  recommended_steps: string[];
  detail?: string | null;
}

export interface EmbeddingSpaceMigrationTableResultSummary {
  table_name: string;
  candidate_rows: number;
  updated_rows: number;
  skipped_rows: number;
  failed_rows: number;
}

export interface EmbeddingSpaceMigrationRunRequest {
  target_model: string;
  target_dimensions?: number;
  dry_run?: boolean;
  batch_size?: number;
  limit_per_table?: number;
  tables?: string[];
  acknowledge_maintenance_window?: boolean;
}

export interface EmbeddingSpaceMigrationRunResponse {
  dry_run: boolean;
  maintenance_acknowledged: boolean;
  current_contract_fingerprint?: string | null;
  target_contract_fingerprint?: string | null;
  target_backend_constructible: boolean;
  tables: EmbeddingSpaceMigrationTableResultSummary[];
  warnings: string[];
  detail?: string | null;
  recommended_next_steps: string[];
}

export interface EmbeddingSpaceMigrationPromoteRequest {
  target_model: string;
  target_dimensions?: number;
  tables?: string[];
  acknowledge_maintenance_window?: boolean;
}

export interface AgentRuntimeProfileConfig {
  default_provider: "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  tier: "deep" | "moderate" | "light";
  provider_models: Record<string, string>;
}

export interface LlmTimeoutProfilesConfig {
  light_seconds: number;
  moderate_seconds: number;
  deep_seconds: number;
  structured_seconds: number;
  background_seconds: number;
  stream_keepalive_interval_seconds: number;
  stream_idle_timeout_seconds: number;
}

export interface LlmTimeoutProviderOverride {
  light_seconds?: number | null;
  moderate_seconds?: number | null;
  deep_seconds?: number | null;
  structured_seconds?: number | null;
  background_seconds?: number | null;
}

export interface ModelCatalogEntry {
  provider: string;
  model_name: string;
  display_name: string;
  status: string;
  released_on?: string | null;
  is_default: boolean;
}

export interface ProviderCatalogCapability {
  provider: string;
  display_name: string;
  configured: boolean;
  available: boolean;
  request_selectable: boolean;
  configurable_via_admin: boolean;
  supports_runtime_discovery: boolean;
  runtime_discovery_enabled: boolean;
  runtime_discovery_succeeded: boolean;
  catalog_source: "static" | "runtime" | "mixed";
  model_count: number;
  discovered_model_count: number;
  selected_model?: string | null;
  selected_model_in_catalog: boolean;
  selected_model_advanced?: string | null;
  selected_model_advanced_in_catalog: boolean;
  last_discovery_attempt_at?: string | null;
  last_discovery_success_at?: string | null;
  last_live_probe_attempt_at?: string | null;
  last_live_probe_success_at?: string | null;
  last_live_probe_error?: string | null;
  live_probe_note?: string | null;
  last_runtime_observation_at?: string | null;
  last_runtime_success_at?: string | null;
  last_runtime_error?: string | null;
  last_runtime_note?: string | null;
  last_runtime_source?: string | null;
  degraded: boolean;
  degraded_reasons: string[];
  recovered: boolean;
  recovered_reasons: string[];
  tool_calling_supported?: boolean | null;
  tool_calling_source?: string | null;
  structured_output_supported?: boolean | null;
  structured_output_source?: string | null;
  streaming_supported?: boolean | null;
  streaming_source?: string | null;
  context_window_tokens?: number | null;
  context_window_source?: string | null;
  max_output_tokens?: number | null;
  max_output_source?: string | null;
}

export interface ModelCatalogResponse {
  providers: Record<string, ModelCatalogEntry[]>;
  embedding_models: ModelCatalogEntry[];
  provider_capabilities: Record<string, ProviderCatalogCapability>;
  ollama_discovered: boolean;
  audit_updated_at?: string | null;
  last_live_probe_at?: string | null;
  degraded_providers: string[];
  audit_persisted: boolean;
  audit_warnings: string[];
  timestamp: string;
}

export interface LlmRuntimeUpdateBody {
  provider?: "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  use_multi_agent?: boolean;
  google_api_key?: string;
  clear_google_api_key?: boolean;
  google_model?: string;
  openai_api_key?: string;
  clear_openai_api_key?: boolean;
  openrouter_api_key?: string;
  clear_openrouter_api_key?: boolean;
  nvidia_api_key?: string;
  clear_nvidia_api_key?: boolean;
  zhipu_api_key?: string;
  clear_zhipu_api_key?: boolean;
  ollama_api_key?: string;
  clear_ollama_api_key?: boolean;
  openai_base_url?: string;
  openai_model?: string;
  openai_model_advanced?: string;
  openrouter_base_url?: string;
  openrouter_model?: string;
  openrouter_model_advanced?: string;
  nvidia_base_url?: string;
  nvidia_model?: string;
  nvidia_model_advanced?: string;
  zhipu_base_url?: string;
  zhipu_model?: string;
  zhipu_model_advanced?: string;
  openrouter_model_fallbacks?: string[];
  openrouter_provider_order?: string[];
  openrouter_allowed_providers?: string[];
  openrouter_ignored_providers?: string[];
  openrouter_allow_fallbacks?: boolean | null;
  openrouter_require_parameters?: boolean | null;
  openrouter_data_collection?: "allow" | "deny" | "";
  openrouter_zdr?: boolean | null;
  openrouter_provider_sort?: "price" | "latency" | "throughput" | "";
  ollama_base_url?: string;
  ollama_model?: string;
  ollama_keep_alive?: string;
  enable_llm_failover?: boolean;
  llm_failover_chain?: string[];
  agent_profiles?: Record<string, AgentRuntimeProfileConfig>;
  timeout_profiles?: LlmTimeoutProfilesConfig;
  timeout_provider_overrides?: Record<string, LlmTimeoutProviderOverride>;
  vision_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_describe_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_describe_model?: string;
  vision_ocr_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_ocr_model?: string;
  vision_grounded_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  vision_grounded_model?: string;
  vision_failover_chain?: string[];
  vision_timeout_seconds?: number;
  embedding_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  embedding_failover_chain?: string[];
  embedding_model?: string;
}

export type ProviderSelectabilityState = "selectable" | "disabled" | "hidden";

export type ProviderDisabledReasonCode =
  | "busy"
  | "rate_limit"
  | "auth_error"
  | "host_down"
  | "model_missing"
  | "capability_missing"
  | "provider_unavailable"
  | "server_error"
  | "timeout"
  | "verifying";

export interface LlmStatusProvider {
  id: string;
  display_name: string;
  available: boolean;
  is_primary: boolean;
  is_fallback: boolean;
  state: ProviderSelectabilityState;
  reason_code?: ProviderDisabledReasonCode | null;
  reason_label?: string | null;
  selected_model?: string | null;
  model_options?: ModelCatalogEntry[];
  strict_pin: boolean;
  verified_at?: string | null;
}

export interface LlmStatusResponse {
  providers: LlmStatusProvider[];
}

export interface LlmRuntimeAuditRefreshBody {
  providers?: Array<"google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama">;
}
