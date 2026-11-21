import type { WiiiConnectConnectionLifecycleDecision } from "./wiii-connect";

export interface WiiiConnectRuntimeConnection {
  id?: string | null;
  provider_kind?: string;
  slug: string;
  label: string;
  status: string;
  active?: boolean;
  agent_ready?: boolean;
  scopes?: Record<string, boolean>;
  capabilities?: string[];
  required_for_paths?: string[];
  source?: string;
  last_checked_at?: string | null;
  reason?: string;
  warnings?: string[];
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
  [key: string]: unknown;
}

export interface WiiiConnectRuntimePathCapability {
  path: string;
  allowed_connection_slugs?: string[];
  required_connection_slugs?: string[];
  allowed_tool_groups?: string[];
  forbidden_tool_groups?: string[];
  mutation_policy?: string;
  delegation_policy?: string;
  [key: string]: unknown;
}

export interface WiiiConnectRuntimePathReadiness {
  path: string;
  status: "ready" | "guarded" | "blocked" | string;
  reason: string;
  required_connection_slugs?: string[];
  missing_connection_slugs?: string[];
  agent_ready_connection_slugs?: string[];
  allowed_tool_groups?: string[];
  suppressed_tool_groups?: string[];
  mutation_policy?: string;
  delegation_policy?: string;
  [key: string]: unknown;
}

export interface WiiiConnectCapabilitySummary {
  active_connection_slugs?: string[];
  agent_ready_connection_slugs?: string[];
  connected_provider_slugs?: string[];
  agent_ready_provider_slugs?: string[];
  connected_scope_names?: string[];
  suppressed_tool_groups?: string[];
  path_readiness?: WiiiConnectRuntimePathReadiness[];
}

export interface WiiiConnectRuntimeSnapshot {
  version: string;
  generated_at?: string;
  surface?: string;
  connections?: WiiiConnectRuntimeConnection[];
  path_capabilities?: WiiiConnectRuntimePathCapability[];
  capability_summary?: WiiiConnectCapabilitySummary;
  warnings?: string[];
}

export interface WiiiConnectDoctorPathDiagnostic {
  path: string;
  status: "ready" | "guarded" | "blocked" | string;
  reason: string;
  required_connection_slugs?: string[];
  missing_connection_slugs?: string[];
  blocked_connection_reasons?: string[];
  mutation_policy?: string;
  delegation_policy?: string;
  agent_ready_connection_slugs?: string[];
}

export interface WiiiConnectDoctorProviderStage {
  key: string;
  status: "ready" | "pending" | "blocked" | string;
  reason: string;
  required_next?: string[];
}

export interface WiiiConnectDoctorProviderDiagnostic {
  provider_slug: string;
  label: string;
  provider_kind: string;
  status: "ready" | "guarded" | "blocked" | string;
  reason: string;
  connection_status: string;
  active?: boolean;
  agent_ready?: boolean;
  connection_count?: number;
  active_connection_count?: number;
  action_count?: number;
  scope_count?: number;
  required_next?: string[];
  stages?: WiiiConnectDoctorProviderStage[];
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
}

export interface WiiiConnectDoctorReport {
  version: string;
  generated_at?: string;
  surface?: string;
  status: "ready" | "degraded" | "blocked" | string;
  summary?: Record<string, number>;
  path_diagnostics?: WiiiConnectDoctorPathDiagnostic[];
  provider_diagnostics?: WiiiConnectDoctorProviderDiagnostic[];
  top_blockers?: string[];
  warnings?: string[];
}

export interface RuntimeFlowDoctorAlert {
  code: string;
  severity?: "critical" | "error" | "warning" | string;
  count?: number;
  threshold?: string;
}

export interface RuntimeFlowDoctorTrendBucket {
  bucket_start: string;
  turn_count: number;
  alert_counts?: Record<string, number>;
  status_counts?: Record<string, number>;
}

export interface RuntimeFlowDoctorSubagentSummary {
  turn_count?: number;
  report_count?: number;
  state_projected_key_count?: number;
  state_dropped_key_count?: number;
  source_count?: number;
  tool_count?: number;
  thinking_dropped_count?: number;
  raw_content_flag_count?: number;
  warning_count?: number;
  warnings?: Record<string, number>;
  identifier_strategy?: string;
}

export interface RuntimeLifecycleHookRegistration {
  point?: string;
  owner?: string;
  name?: string;
  registered?: boolean;
}

export interface RuntimeLifecycleRegistrationSummary {
  version?: string;
  registration_count?: number;
  owner_counts?: Record<string, number>;
  point_counts?: Record<string, number>;
  default_runtime_hooks?: {
    owner?: string;
    required_count?: number;
    registered_count?: number;
    installed?: boolean;
    hooks?: RuntimeLifecycleHookRegistration[];
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
}

export interface RuntimePostTurnLifecycleMetricsBlock {
  event_count?: number;
  status_counts?: Record<string, number>;
  reason_counts?: Record<string, number>;
  transport_counts?: Record<string, number>;
  semantic_memory_policy_counts?: Record<string, number>;
  group_counts?: Record<string, number>;
}

export interface RuntimePostTurnLifecycleMetricsReport {
  version?: string;
  post_turn?: RuntimePostTurnLifecycleMetricsBlock;
  background_tasks?: RuntimePostTurnLifecycleMetricsBlock;
  source?: {
    metrics_backend?: string;
    window?: string;
    org_scoped?: boolean;
    counter_names?: Record<string, string>;
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
}

export interface RuntimePostTurnLifecycleLedgerReport {
  version?: string;
  event_count?: number;
  missing_count?: number;
  status_counts?: Record<string, number>;
  reason_counts?: Record<string, number>;
  semantic_memory_policy_counts?: Record<string, number>;
  background_tasks_scheduled_count?: number;
  background_tasks_skipped_count?: number;
  raw_content_flag_count?: number;
  background_schedule?: RuntimePostTurnLifecycleMetricsBlock & {
    task_count?: number;
  };
  source?: {
    ledger_path?: string;
    window?: string;
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
}

export interface RuntimeFlowDoctorReport {
  version: string;
  generated_at?: string;
  status: "ready" | "degraded" | "blocked" | string;
  alerts?: RuntimeFlowDoctorAlert[];
  summary?: Record<string, number>;
  request_correlation?: Record<string, number | string>;
  subagents?: RuntimeFlowDoctorSubagentSummary;
  routes?: Record<string, number>;
  finalization_statuses?: Record<string, number>;
  stream_events?: Record<string, number>;
  suppressed_tools?: Record<string, number>;
  observed_tools?: Record<string, number>;
  context_warnings?: Record<string, number>;
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
  alert_trend?: {
    bucket_strategy?: string;
    identifier_strategy?: string;
    buckets?: RuntimeFlowDoctorTrendBucket[];
  };
  source?: {
    session_event_count?: number;
    runtime_flow_ledger_event_count?: number;
    limit?: number;
    org_scoped?: boolean;
    window?: string;
    since_seq?: number | null;
  };
  runtime_config?: Record<string, string | number | boolean>;
  lifecycle_registrations?: RuntimeLifecycleRegistrationSummary;
  post_turn_lifecycle?: RuntimePostTurnLifecycleMetricsReport;
  post_turn_lifecycle_ledger?: RuntimePostTurnLifecycleLedgerReport;
}

export interface RuntimeFlowDoctorHistoryBucket {
  bucket_start: string;
  status: "ready" | "degraded" | "blocked" | string;
  alerts?: RuntimeFlowDoctorAlert[];
  summary?: Record<string, number>;
  request_correlation?: Record<string, number | string>;
  subagents?: RuntimeFlowDoctorSubagentSummary;
  routes?: Record<string, number>;
  finalization_statuses?: Record<string, number>;
  post_turn_lifecycle_ledger?: RuntimePostTurnLifecycleLedgerReport;
  context_warnings?: Record<string, number>;
  source?: {
    session_event_count?: number;
    runtime_flow_ledger_event_count?: number;
  };
}

export interface RuntimeFlowDoctorHistoryReport {
  version: string;
  generated_at?: string;
  bucket_strategy?: string;
  identifier_strategy?: string;
  buckets?: RuntimeFlowDoctorHistoryBucket[];
  source?: {
    session_event_count?: number;
    runtime_flow_ledger_event_count?: number;
    bucket_count?: number;
    bucket_limit?: number;
    limit?: number;
    org_scoped?: boolean;
    window?: string;
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
  runtime_config?: Record<string, string | number | boolean>;
  lifecycle_registrations?: RuntimeLifecycleRegistrationSummary;
  post_turn_lifecycle?: RuntimePostTurnLifecycleMetricsReport;
  post_turn_lifecycle_ledger?: RuntimePostTurnLifecycleLedgerReport;
}

export interface RuntimeFlowSessionEventPruneReport {
  schema: string;
  status: "dry_run" | "pruned" | string;
  matched_count: number;
  deleted_count: number;
  retention_days: number;
  cutoff: string;
  dry_run: boolean;
  org_scoped: boolean;
  event_type_filter_applied: boolean;
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
  runtime_config?: Record<string, string | number | boolean>;
}

export interface SemanticMemoryWriteDoctorReport {
  version: string;
  generated_at?: string;
  status: "ready" | "degraded" | "blocked" | string;
  summary?: Record<string, number>;
  write_kinds?: Record<string, number>;
  write_statuses?: Record<string, number>;
  organization_contexts?: Record<string, number>;
  warnings?: Record<string, number>;
  source?: {
    session_event_count?: number;
    semantic_memory_write_event_count?: number;
    limit?: number;
    org_scoped?: boolean;
    window?: string;
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
  runtime_config?: Record<string, string | number | boolean>;
}

export interface SemanticMemoryWriteDoctorHistoryBucket {
  bucket_start: string;
  status: "ready" | "degraded" | "blocked" | string;
  summary?: Record<string, number>;
  write_kinds?: Record<string, number>;
  write_statuses?: Record<string, number>;
  organization_contexts?: Record<string, number>;
  warnings?: Record<string, number>;
  source?: {
    session_event_count?: number;
    semantic_memory_write_event_count?: number;
  };
}

export interface SemanticMemoryWriteDoctorHistoryReport {
  version: string;
  generated_at?: string;
  bucket_strategy?: string;
  identifier_strategy?: string;
  buckets?: SemanticMemoryWriteDoctorHistoryBucket[];
  source?: {
    session_event_count?: number;
    semantic_memory_write_event_count?: number;
    bucket_count?: number;
    bucket_limit?: number;
    limit?: number;
    org_scoped?: boolean;
    window?: string;
  };
  privacy?: {
    raw_content_included?: boolean;
    identifier_strategy?: string;
  };
  runtime_config?: Record<string, string | number | boolean>;
}
