/**
 * Domain API module
 */
import type { DomainSummary } from "./types";
import { getClient } from "./client";

/** List all registered domains */
export async function listDomains(): Promise<DomainSummary[]> {
  const client = getClient();
  // Sprint 218: Backend returns list[DomainSummary] directly (not wrapped)
  const response = await client.get<DomainSummary[]>(
    "/api/v1/admin/domains"
  );
  return Array.isArray(response) ? response : [];
}

