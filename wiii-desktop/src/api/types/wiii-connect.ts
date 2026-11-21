export interface WiiiConnectProviderRegistryEntry {
  version?: string;
  slug: string;
  label: string;
  provider_kind: string;
  auth_mode?: string;
  enabled?: boolean;
  agent_ready?: boolean;
  category?: string;
  description?: string;
  allowed_paths?: string[];
  action_count?: number;
  requirements?: string[];
  connect_requirements?: string[];
  agent_ready_requirements?: string[];
  required_fields?: Array<Record<string, unknown>>;
  default_scopes?: Record<string, boolean>;
  source?: string;
  warnings?: string[];
}

export interface WiiiConnectProviderRegistryResponse {
  version: string;
  adapter_version?: string;
  providers: WiiiConnectProviderRegistryEntry[];
}

export interface WiiiConnectProviderConnectionStatus {
  version: string;
  provider_slug: string;
  label: string;
  provider_kind: string;
  auth_mode: string;
  enabled: boolean;
  agent_ready: boolean;
  can_start_authorization: boolean;
  reason: string;
  missing_requirements: string[];
  warnings?: string[];
}

export interface WiiiConnectSessionStartBody {
  surface?: string;
  redirect_uri?: string | null;
  probe_database?: boolean;
  requested_scopes?: Record<string, boolean>;
  request_metadata?: Record<string, unknown>;
}

export interface WiiiConnectSessionAuditEvent {
  version: string;
  stage: string;
  reason: string;
  created_at: string;
  request: {
    provider_slug: string;
    surface: string;
    requested_scopes: Record<string, boolean>;
    redirect_uri_present: boolean;
    request_metadata_keys: string[];
  };
}

export interface WiiiConnectSessionStartDecision {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  label: string;
  provider_kind: string;
  auth_mode: string;
  authorization_url?: string;
  required_next?: string[];
  audit_event?: WiiiConnectSessionAuditEvent | null;
}

export interface WiiiConnectProviderAdapterCapability {
  version: string;
  provider_kind: string;
  adapter_name: string;
  bound: boolean;
  configured: boolean;
  can_create_authorization_url: boolean;
  can_exchange_callback: boolean;
  can_execute_actions: boolean;
  authorization_ready: boolean;
  reason: string;
  warnings?: string[];
}

export interface WiiiConnectAuthorizationUrlDecision {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  label: string;
  provider_kind: string;
  auth_mode: string;
  authorization_url?: string;
  adapter?: WiiiConnectProviderAdapterCapability | null;
  required_next?: string[];
  audit_event?: WiiiConnectSessionAuditEvent | null;
}

export interface WiiiConnectConnectionLifecycleDecision {
  version: string;
  provider_slug: string;
  status:
    | "disconnected"
    | "authorizing"
    | "waiting"
    | "connected"
    | "expired"
    | "error"
    | "disconnecting"
    | string;
  reason: string;
  active?: boolean;
  connection_present?: boolean;
  agent_ready?: boolean;
  ready_to_connect?: boolean;
  ready_to_execute_action?: boolean;
  required_next?: string[];
}

export interface WiiiConnectProviderConnectionRecord {
  version: string;
  connection_ref: string;
  connection_ref_present?: boolean;
  connection_id?: string;
  provider_slug: string;
  state: string;
  active?: boolean;
  scopes?: Record<string, boolean>;
  vault_ref_present?: boolean;
  account_label?: string;
  external_account_ref_present?: boolean;
  last_checked_at?: string | null;
  reason?: string;
  warnings?: string[];
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
}

export interface WiiiConnectProviderConnectionListResponse {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  provider_kind: string;
  connection_count: number;
  connections: WiiiConnectProviderConnectionRecord[];
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
  provider?: Record<string, unknown> | null;
  storage?: Record<string, unknown> | null;
}

export interface WiiiConnectEffectiveActionStage {
  key: string;
  status: "ready" | "pending" | "blocked" | string;
  reason: string;
  required_next?: string[];
}

export interface WiiiConnectEffectiveActionRecord {
  version: string;
  slug: string;
  provider_slug: string;
  label: string;
  mutation: string;
  path: string;
  status: "ready" | "guarded" | "blocked" | string;
  reason: string;
  runtime_enabled: boolean;
  visible_to_agent: boolean;
  executable_now: boolean;
  requires_preview?: boolean;
  requires_approval?: boolean;
  required_scopes?: string[];
  argument_policy_version?: string;
  argument_keys?: string[];
  model_argument_keys?: string[];
  hidden_argument_count?: number;
  stages?: WiiiConnectEffectiveActionStage[];
  gateway?: Record<string, unknown> | null;
  warnings?: string[];
}

export interface WiiiConnectEffectiveActionInventoryResponse {
  version: string;
  provider_slug: string;
  provider_kind: string;
  status: "ready" | "guarded" | "blocked" | string;
  reason: string;
  connection_ref_present?: boolean;
  connection_present?: boolean;
  connection_active?: boolean;
  selected_connection_required?: boolean;
  catalog_action_count: number;
  runtime_enabled_action_count: number;
  visible_action_count: number;
  executable_action_count: number;
  actions: WiiiConnectEffectiveActionRecord[];
  storage?: Record<string, unknown> | null;
}

export interface WiiiConnectProviderScopeGrantResponse {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  provider_kind: string;
  connection?: WiiiConnectProviderConnectionRecord | null;
  storage?: Record<string, unknown> | null;
}

export interface WiiiConnectFacebookPageOption {
  page_id: string;
  name: string;
  category?: string;
  link?: string;
}

export interface WiiiConnectFacebookPagesResponse {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  action_slug?: string;
  page_count: number;
  pages: WiiiConnectFacebookPageOption[];
  gateway?: Record<string, unknown> | null;
}

export interface WiiiConnectOperationApprovalLedger {
  version?: string;
  status?: "pending" | "consumed" | "blocked" | "unavailable" | "expired" | string;
  reason?: string;
  provider_slug?: string;
  action_slug?: string;
  preview_evidence_id_present?: boolean;
  request_fingerprint_present?: boolean;
  persistent?: boolean;
  consumed?: boolean;
  blocked?: boolean;
  metadata?: Record<string, unknown>;
}

export interface WiiiConnectFacebookPostPreviewResponse {
  version: string;
  status: "blocked" | "ready" | string;
  reason: string;
  provider_slug: string;
  action_slug?: string;
  preview_evidence_id?: string;
  approval_token?: string;
  preview?: {
    page_id: string;
    message: string;
    image_present: boolean;
    image_media_type?: string;
    image_filename?: string;
    image_url_present?: boolean;
  };
  gateway?: Record<string, unknown> | null;
  approval_ledger?: WiiiConnectOperationApprovalLedger | null;
  storage?: Record<string, unknown> | null;
}

export interface WiiiConnectFacebookPostApplyResponse {
  version: string;
  status: "blocked" | "ready" | "succeeded" | "failed" | string;
  reason: string;
  provider_slug: string;
  action_slug?: string;
  token?: Record<string, unknown> | null;
  gateway?: Record<string, unknown> | null;
  schema?: Record<string, unknown> | null;
  upload?: Record<string, unknown> | null;
  execution?: Record<string, unknown> | null;
  approval_ledger?: WiiiConnectOperationApprovalLedger | null;
  storage?: Record<string, unknown> | null;
  missing_argument_keys?: string[];
}

export interface WiiiConnectActivationGate {
  key: string;
  ready: boolean;
  reason: string;
  required_next?: string[];
  metadata?: Record<string, unknown>;
}

export interface WiiiConnectActivationReadinessConnection {
  present?: boolean;
  provider_slug?: string;
  state?: string;
  active?: boolean;
  scopes?: Record<string, boolean>;
  vault_ref_present?: boolean;
  account_label_present?: boolean;
  external_account_ref_present?: boolean;
  last_checked_at_present?: boolean;
  reason?: string;
  warnings?: string[];
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
}

export interface WiiiConnectActivationReadinessResponse {
  version: string;
  status: "blocked" | "ready" | string;
  provider_slug: string;
  provider_kind: string;
  ready_to_connect: boolean;
  ready_to_execute_action?: boolean;
  ready_to_execute_readonly: boolean;
  gates: WiiiConnectActivationGate[];
  provider?: Record<string, unknown> | null;
  execution_provider?: Record<string, unknown> | null;
  adapter?: WiiiConnectProviderAdapterCapability | null;
  vault?: Record<string, unknown> | null;
  storage?: Record<string, unknown> | null;
  action?: Record<string, unknown> | null;
  connection?: WiiiConnectActivationReadinessConnection | null;
  connection_lifecycle?: WiiiConnectConnectionLifecycleDecision | null;
  execution_gateway?: Record<string, unknown> | null;
}

export interface WiiiConnectProviderDisconnectResponse {
  version: string;
  status: "blocked" | "succeeded" | "failed" | string;
  reason: string;
  provider_slug: string;
  provider_kind: string;
  connection_present: boolean;
  local_disabled: boolean;
  provider?: Record<string, unknown> | null;
  storage?: Record<string, unknown> | null;
}
