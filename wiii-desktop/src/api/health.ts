/**
 * Health check API module
 */
import type { HealthResponse } from "./types";
import { getClient } from "./client";

/** Quick health check (no DB) */
export async function checkHealth(): Promise<HealthResponse> {
  const client = getClient();
  return client.get<HealthResponse>("/api/v1/health");
}

