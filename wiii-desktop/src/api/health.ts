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

/** Deep health check (all components) */
export async function checkDeepHealth(): Promise<HealthResponse> {
  const client = getClient();
  return client.get<HealthResponse>("/api/v1/health/db");
}

/** Liveness probe */
export async function checkLive(): Promise<{ status: string }> {
  const client = getClient();
  return client.get("/api/v1/health/live");
}
