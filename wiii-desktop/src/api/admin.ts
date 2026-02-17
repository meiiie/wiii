/**
 * Admin API module
 */
import { getClient } from "./client";

/** List all documents */
export async function listDocuments(): Promise<unknown[]> {
  const client = getClient();
  return client.get<unknown[]>("/api/v1/admin/documents");
}

/** Delete a document */
export async function deleteDocument(documentId: string): Promise<unknown> {
  const client = getClient();
  return client.delete(`/api/v1/admin/documents/${documentId}`);
}

/** Get knowledge base statistics */
export async function getKnowledgeStats(): Promise<unknown> {
  const client = getClient();
  return client.get("/api/v1/knowledge/stats");
}
