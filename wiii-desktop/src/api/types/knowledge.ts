export type OrgDocumentStatus = "uploading" | "processing" | "ready" | "failed" | "deleted";

export interface OrgDocument {
  document_id: string;
  organization_id: string;
  filename: string;
  file_size_bytes: number | null;
  status: OrgDocumentStatus;
  page_count: number | null;
  chunk_count: number | null;
  error_message: string | null;
  uploaded_by: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface OrgDocumentListResponse {
  documents: OrgDocument[];
  total: number;
}

export interface ScatterPoint {
  x: number;
  y: number;
  z?: number | null;
  document_id: string;
  document_name: string;
  content_preview: string;
  content_type?: string | null;
  page_number?: number | null;
}

export interface ScatterDocument {
  id: string;
  name: string;
  color: string;
}

export interface ScatterResponse {
  points: ScatterPoint[];
  documents: ScatterDocument[];
  method: string;
  dimensions: number;
  computation_ms: number;
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  node_type: "document" | "chunk";
  document_id?: string | null;
  page_number?: number | null;
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  edge_type: "contains" | "similar_to";
  weight?: number | null;
}

export interface KnowledgeGraphResponse {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  mermaid_code: string;
  computation_ms: number;
}

export interface RagFlowStep {
  name: string;
  duration_ms: number;
  detail?: string | null;
}

export interface RagFlowChunk {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content_preview: string;
  page_number?: number | null;
  similarity: number;
  grade: "relevant" | "partial" | "irrelevant";
  content_type?: string | null;
}

export interface RagFlowResponse {
  query: string;
  steps: RagFlowStep[];
  chunks: RagFlowChunk[];
  computation_ms: number;
}
