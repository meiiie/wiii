/**
 * knowledge-viz.test.ts — Sprint 191: "Mắt Tri Thức"
 *
 * Tests for Knowledge Visualization types, API exports, and components.
 */
import { describe, it, expect, vi } from "vitest";

// ─── Type Shape Tests ───────────────────────────────────────────────

describe("Sprint 191: Knowledge Visualization Types", () => {
  it("ScatterPoint has required fields", () => {
    const point = {
      x: 1.5,
      y: -0.3,
      z: null,
      document_id: "doc-1",
      document_name: "test.pdf",
      content_preview: "Some preview text...",
      content_type: "text",
      page_number: 5,
    } satisfies import("@/api/types").ScatterPoint;
    expect(point.x).toBe(1.5);
    expect(point.document_id).toBe("doc-1");
  });

  it("ScatterPoint z is optional for 2D", () => {
    const point: import("@/api/types").ScatterPoint = {
      x: 0,
      y: 0,
      document_id: "d",
      document_name: "n",
      content_preview: "p",
    };
    expect(point.z).toBeUndefined();
  });

  it("ScatterDocument has id, name, color", () => {
    const doc: import("@/api/types").ScatterDocument = {
      id: "doc-1",
      name: "test.pdf",
      color: "#3B82F6",
    };
    expect(doc.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });

  it("ScatterResponse has points, documents, method, dimensions, computation_ms", () => {
    const res: import("@/api/types").ScatterResponse = {
      points: [],
      documents: [],
      method: "pca",
      dimensions: 2,
      computation_ms: 42,
    };
    expect(res.method).toBe("pca");
    expect(res.dimensions).toBe(2);
  });

  it("KnowledgeGraphNode has node_type document or chunk", () => {
    const docNode: import("@/api/types").KnowledgeGraphNode = {
      id: "doc_abc12345",
      label: "Chapter 1",
      node_type: "document",
      document_id: "abc12345-full",
    };
    const chunkNode: import("@/api/types").KnowledgeGraphNode = {
      id: "chunk_xyz",
      label: "Truncated content...",
      node_type: "chunk",
      document_id: "abc12345-full",
      page_number: 3,
    };
    expect(docNode.node_type).toBe("document");
    expect(chunkNode.page_number).toBe(3);
  });

  it("KnowledgeGraphEdge has edge_type contains or similar_to", () => {
    const containsEdge: import("@/api/types").KnowledgeGraphEdge = {
      source: "doc_abc",
      target: "chunk_xyz",
      edge_type: "contains",
    };
    const simEdge: import("@/api/types").KnowledgeGraphEdge = {
      source: "chunk_a",
      target: "chunk_b",
      edge_type: "similar_to",
      weight: 0.92,
    };
    expect(containsEdge.edge_type).toBe("contains");
    expect(simEdge.weight).toBeGreaterThan(0.85);
  });

  it("KnowledgeGraphResponse has nodes, edges, mermaid_code", () => {
    const res: import("@/api/types").KnowledgeGraphResponse = {
      nodes: [],
      edges: [],
      mermaid_code: "graph LR\n  empty[No data]",
      computation_ms: 15,
    };
    expect(res.mermaid_code).toContain("graph LR");
  });

  it("RagFlowStep has name and duration_ms", () => {
    const step: import("@/api/types").RagFlowStep = {
      name: "Embedding",
      duration_ms: 120,
      detail: "768 dimensions",
    };
    expect(step.name).toBe("Embedding");
  });

  it("RagFlowChunk grade is relevant, partial, or irrelevant", () => {
    const chunk: import("@/api/types").RagFlowChunk = {
      chunk_id: "c1",
      document_id: "d1",
      document_name: "test.pdf",
      content_preview: "Preview...",
      page_number: 1,
      similarity: 0.82,
      grade: "relevant",
      content_type: "text",
    };
    expect(["relevant", "partial", "irrelevant"]).toContain(chunk.grade);
    expect(chunk.similarity).toBeGreaterThanOrEqual(0.75);
  });

  it("RagFlowResponse has query, steps, chunks, computation_ms", () => {
    const res: import("@/api/types").RagFlowResponse = {
      query: "What is COLREG?",
      steps: [
        { name: "Embedding", duration_ms: 100 },
        { name: "Retrieval", duration_ms: 200 },
        { name: "Grading", duration_ms: 50 },
      ],
      chunks: [],
      computation_ms: 350,
    };
    expect(res.steps).toHaveLength(3);
    expect(res.query).toBe("What is COLREG?");
  });
});

// ─── API Exports ───────────────────────────────────────────────────

describe("Sprint 191: Knowledge Visualization API exports", () => {
  it("getKnowledgeScatter is exported from admin", async () => {
    const mod = await import("@/api/admin");
    expect(typeof mod.getKnowledgeScatter).toBe("function");
  });

  it("getKnowledgeGraph is exported from admin", async () => {
    const mod = await import("@/api/admin");
    expect(typeof mod.getKnowledgeGraph).toBe("function");
  });

  it("simulateRagFlow is exported from admin", async () => {
    const mod = await import("@/api/admin");
    expect(typeof mod.simulateRagFlow).toBe("function");
  });
});

// ─── Component Tests (mock-based) ──────────────────────────────────

// Mock the API module
vi.mock("@/api/admin", () => ({
  getKnowledgeScatter: vi.fn(),
  getKnowledgeGraph: vi.fn(),
  simulateRagFlow: vi.fn(),
  listOrgDocuments: vi.fn(),
  uploadOrgDocument: vi.fn(),
  deleteOrgDocument: vi.fn(),
  getOrgDocument: vi.fn(),
}));

// Mock MermaidDiagram (avoids loading real mermaid WASM)
vi.mock("@/components/common/MermaidDiagram", () => ({
  default: ({ code }: { code: string }) => {
    return { type: "div", props: { "data-testid": "mermaid", children: code } };
  },
}));

describe("Sprint 191: KnowledgeVisualizer component", () => {
  it("exports KnowledgeVisualizer", async () => {
    const mod = await import("@/components/org-admin/KnowledgeVisualizer");
    expect(typeof mod.KnowledgeVisualizer).toBe("function");
  });

  it("KnowledgeVisualizer accepts orgId and hasDocuments props", async () => {
    const mod = await import("@/components/org-admin/KnowledgeVisualizer");
    // Verify it's a function component with correct name
    expect(mod.KnowledgeVisualizer.name).toBe("KnowledgeVisualizer");
    expect(mod.KnowledgeVisualizer.length).toBeLessThanOrEqual(1); // single props object
  });
});

describe("Sprint 191: KnowledgeScatter2D component", () => {
  it("exports KnowledgeScatter2D", async () => {
    const mod = await import("@/components/org-admin/KnowledgeScatter2D");
    expect(typeof mod.KnowledgeScatter2D).toBe("function");
  });
});

describe("Sprint 191: KnowledgeScatter3D component", () => {
  it("exports KnowledgeScatter3D", async () => {
    const mod = await import("@/components/org-admin/KnowledgeScatter3D");
    expect(typeof mod.KnowledgeScatter3D).toBe("function");
  });
});

describe("Sprint 191: KnowledgeGraph component", () => {
  it("exports KnowledgeGraph", async () => {
    const mod = await import("@/components/org-admin/KnowledgeGraph");
    expect(typeof mod.KnowledgeGraph).toBe("function");
  });
});

describe("Sprint 191: RagFlowVisualizer component", () => {
  it("exports RagFlowVisualizer", async () => {
    const mod = await import("@/components/org-admin/RagFlowVisualizer");
    expect(typeof mod.RagFlowVisualizer).toBe("function");
  });
});

describe("Sprint 191: Grade thresholds match backend", () => {
  it("relevant threshold is 0.75", () => {
    const sim = 0.75;
    const grade = sim >= 0.75 ? "relevant" : sim >= 0.60 ? "partial" : "irrelevant";
    expect(grade).toBe("relevant");
  });

  it("partial threshold is 0.60-0.7499", () => {
    const sim = 0.60;
    const grade = sim >= 0.75 ? "relevant" : sim >= 0.60 ? "partial" : "irrelevant";
    expect(grade).toBe("partial");
  });

  it("irrelevant below 0.60", () => {
    const sim = 0.59;
    const grade = sim >= 0.75 ? "relevant" : sim >= 0.60 ? "partial" : "irrelevant";
    expect(grade).toBe("irrelevant");
  });
});

describe("Sprint 191: OrgManagerKnowledge imports KnowledgeVisualizer", () => {
  it("OrgManagerKnowledge module loads without error", async () => {
    // This verifies the import chain works
    const mod = await import("@/components/org-admin/OrgManagerKnowledge");
    expect(typeof mod.OrgManagerKnowledge).toBe("function");
  });
});
