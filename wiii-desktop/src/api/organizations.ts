/**
 * Organization API module — Sprint 156
 */
import type { OrganizationSummary } from "./types";
import { getClient } from "./client";

/** List organizations for the current user */
export async function listMyOrganizations(): Promise<OrganizationSummary[]> {
  const client = getClient();
  return client.get<OrganizationSummary[]>("/api/v1/users/me/organizations");
}

/** List all organizations (admin) */
export async function listOrganizations(): Promise<OrganizationSummary[]> {
  const client = getClient();
  return client.get<OrganizationSummary[]>("/api/v1/organizations");
}

/** Get single organization details */
export async function getOrganization(orgId: string): Promise<OrganizationSummary> {
  const client = getClient();
  return client.get<OrganizationSummary>(`/api/v1/organizations/${encodeURIComponent(orgId)}`);
}
