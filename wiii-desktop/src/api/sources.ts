/**
 * Sources API module
 */
import type { SourceInfo } from "./types";
import { getClient } from "./client";

/** Get source details by node ID */
export async function getSource(nodeId: string): Promise<SourceInfo> {
  const client = getClient();
  return client.get<SourceInfo>(`/api/v1/sources/${nodeId}`);
}

/** List all sources */
export async function listSources(): Promise<SourceInfo[]> {
  const client = getClient();
  return client.get<SourceInfo[]>("/api/v1/sources/");
}
