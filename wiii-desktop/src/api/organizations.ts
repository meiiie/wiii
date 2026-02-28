/**
 * Organization API module — Sprint 156 + Sprint 161 (settings/permissions).
 */
import type {
  OrganizationSummary,
  OrgSettings,
  OrgPermissionsResponse,
} from "./types";
import { getClient } from "./client";

/** List organizations for the current user */
export async function listMyOrganizations(): Promise<OrganizationSummary[]> {
  const client = getClient();
  return client.get<OrganizationSummary[]>("/api/v1/organizations/users/me/organizations");
}

/** List all organizations (admin) */
export async function listOrganizations(): Promise<OrganizationSummary[]> {
  const client = getClient();
  return client.get<OrganizationSummary[]>("/api/v1/organizations");
}

/** Sprint 161: Get effective org settings (merged with platform defaults) */
export async function getOrgSettings(orgId: string): Promise<OrgSettings> {
  const client = getClient();
  return client.get<OrgSettings>(`/api/v1/organizations/${encodeURIComponent(orgId)}/settings`);
}

/** Sprint 161: Partial-update org settings */
export async function updateOrgSettings(orgId: string, patch: Record<string, unknown>): Promise<OrgSettings> {
  const client = getClient();
  return client.patch<OrgSettings>(`/api/v1/organizations/${encodeURIComponent(orgId)}/settings`, patch);
}

/** Sprint 161: Get current user's permissions within an org */
export async function getOrgPermissions(orgId: string): Promise<OrgPermissionsResponse> {
  const client = getClient();
  return client.get<OrgPermissionsResponse>(`/api/v1/organizations/${encodeURIComponent(orgId)}/permissions`);
}
