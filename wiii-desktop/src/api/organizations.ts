/**
 * Organization API module — Sprint 156 + Sprint 161 (settings/permissions).
 */
import type {
  OrganizationSummary,
  OrgSettings,
  OrgPermissionsResponse,
  AdminAuthEventsResponse,
} from "./types";
import { getClient } from "./client";

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

export async function getOrgHostActionEvents(
  orgId: string,
  params?: {
    event_type?: string;
    limit?: number;
    offset?: number;
  },
): Promise<AdminAuthEventsResponse> {
  const client = getClient();
  const query = new URLSearchParams();
  if (params?.event_type) query.set("event_type", params.event_type);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return client.get<AdminAuthEventsResponse>(
    `/api/v1/organizations/${encodeURIComponent(orgId)}/host-action-events${qs ? `?${qs}` : ""}`,
  );
}
