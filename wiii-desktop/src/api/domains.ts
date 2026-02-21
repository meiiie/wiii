/**
 * Domain API module
 */
import type { DomainSummary } from "./types";
import { getClient } from "./client";

/** List all registered domains */
export async function listDomains(): Promise<DomainSummary[]> {
  const client = getClient();
  const response = await client.get<{ domains: DomainSummary[] }>(
    "/api/v1/admin/domains"
  );
  return response.domains || [];
}

