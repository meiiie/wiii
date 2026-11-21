import type { OrgSettings } from "./organizations";
import type { PlatformRole, OrganizationRole } from "./organizations";

/** Sprint 179b: Organization summary in dashboard */
export interface AdminOrgSummary {
  id: string;
  name: string;
  display_name: string | null;
  member_count: number;
  document_count?: number;  // Sprint 190: Org knowledge docs
  is_active: boolean;
}

/** Sprint 179b: Organization detail (from /organizations/{id}) */
export interface AdminOrgDetail {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  allowed_domains: string[];
  default_domain: string | null;
  settings: OrgSettings | null;
  document_count?: number;  // Sprint 190: Org knowledge docs
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Sprint 179b: Organization member */
export interface AdminOrgMember {
  user_id: string;
  organization_id: string;
  role: string;
  joined_at: string | null;
}

/** GET /users/me/admin-context */
export interface AdminContext {
  is_system_admin: boolean;
  is_org_admin: boolean;
  admin_org_ids: string[];
  enable_org_admin: boolean;
  platform_role?: PlatformRole;
  organization_role?: OrganizationRole | string;
  host_role?: string;
  role_source?: string;
  active_organization_id?: string;
  connector_id?: string;
  identity_version?: string;
  legacy_role?: string;
}

/** GET /admin/dashboard */
export interface AdminDashboard {
  total_users: number;
  active_users: number;
  total_organizations: number;
  total_chat_sessions_24h: number;
  total_llm_tokens_24h: number;
  estimated_cost_24h_usd: number;
  feature_flags_active: number;
  /** Sprint 179b: Organization list in dashboard */
  organizations?: AdminOrgSummary[];
}

/** User row in admin search */
export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  legacy_role?: string;
  platform_role?: PlatformRole;
  is_active: boolean;
  created_at: string | null;
  organization_count: number;
}

/** GET /admin/users params */
export interface AdminUserSearchParams {
  q?: string;
  email?: string;
  role?: string;
  platform_role?: PlatformRole | string;
  org_id?: string;
  status?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

/** GET /admin/users response */
export interface AdminUserSearchResponse {
  users: AdminUser[];
  total: number;
  limit: number;
  offset: number;
}

/** Feature flag entry */
export interface AdminFeatureFlag {
  key: string;
  value: boolean;
  source: "config" | "db_override";
  flag_type: string;
  description: string | null;
  owner: string | null;
  expires_at: string | null;
}

/** PATCH /admin/feature-flags/{key} body */
export interface AdminFlagUpdateBody {
  value: boolean;
  flag_type?: string | null;
  description?: string | null;
  organization_id?: string | null;
  expires_at?: string | null;
}

/** Analytics overview response */
export interface AnalyticsOverview {
  period_start: string;
  period_end: string;
  daily_active_users: AnalyticsDataPoint[];
  chat_volume: ChatVolumePoint[];
  error_rate: ErrorRatePoint[];
}

export interface AnalyticsDataPoint {
  date: string;
  count: number;
}

export interface ChatVolumePoint {
  date: string;
  messages: number;
  sessions: number;
}

export interface ErrorRatePoint {
  date: string;
  total: number;
  errors: number;
  rate: number;
}

/** LLM usage analytics */
export interface LlmUsageAnalytics {
  total_tokens: number;
  total_cost_usd: number;
  total_requests: number;
  breakdown: LlmUsageBreakdown[];
  top_models: { model: string; tokens: number; requests: number }[];
  top_users: { user_id: string; tokens: number; requests: number }[];
}

export interface LlmUsageBreakdown {
  group: string;
  tokens: number;
  cost: number;
  requests: number;
}

/** User analytics */
export interface UserAnalytics {
  total_users: number;
  new_users_period: number;
  active_users_period: number;
  user_growth: UserGrowthPoint[];
  role_distribution: Record<string, number>;
  legacy_role_distribution?: Record<string, number>;
  platform_role_distribution?: Record<string, number>;
  organization_role_distribution?: Record<string, number>;
  top_active_users: { user_id: string; sessions: number }[];
}

export interface UserGrowthPoint {
  date: string;
  new_users: number;
}

/** Admin audit log entry */
export interface AdminAuditEntry {
  id: string;
  actor_id: string;
  actor_role: string;
  actor_name: string;
  action: string;
  http_method: string;
  http_path: string;
  http_status: number;
  target_type: string;
  target_id: string;
  target_name: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip_address: string;
  request_id: string;
  organization_id: string | null;
  occurred_at: string | null;
}

/** GET /admin/audit-logs response */
export interface AdminAuditLogsResponse {
  entries: AdminAuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

/** Auth event entry */
export interface AdminAuthEvent {
  id: string;
  event_type: string;
  user_id: string;
  provider: string;
  result: string;
  reason: string | null;
  ip_address: string;
  organization_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

/** GET /admin/auth-events response */
export interface AdminAuthEventsResponse {
  entries: AdminAuthEvent[];
  total: number;
  limit: number;
  offset: number;
}

/** GDPR export response */
export interface GdprExportResponse {
  user_id: string;
  exported_at: string;
  data: {
    profile: Record<string, unknown>;
    identities: Record<string, unknown>[];
    memories: Record<string, unknown>[];
    auth_events: Record<string, unknown>[];
    audit_entries: Record<string, unknown>[];
  };
}

/** GDPR forget response */
export interface GdprForgetResponse {
  user_id: string;
  status: string;
  profile_anonymized: boolean;
  identities_deleted: number;
  tokens_revoked: number;
  memories_deleted: number;
  audit_logs_preserved: boolean;
}
