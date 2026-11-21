export type UserRole = "student" | "teacher" | "admin";

export type PlatformRole = "user" | "platform_admin";

export type OrganizationRole = "member" | "org_admin" | "owner" | "admin";

export interface UserProfile {
  id: string;
  email?: string;
  name?: string;
  avatar_url?: string;
  role: string;
  legacy_role?: string;
  platform_role?: PlatformRole;
  organization_role?: OrganizationRole | string;
  host_role?: string;
  role_source?: string;
  active_organization_id?: string;
  connector_id?: string;
  identity_version?: string;
  connected_workspaces_count?: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserIdentity {
  id: string;
  provider: string;
  provider_sub: string;
  provider_issuer?: string;
  email?: string;
  display_name?: string;
  avatar_url?: string;
  linked_at?: string;
  last_used_at?: string;
}
