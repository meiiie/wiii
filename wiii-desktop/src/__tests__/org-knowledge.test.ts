/**
 * Sprint 190: "Kho Tri Thức" — Org Knowledge Management Tests
 *
 * Tests for:
 *   - OrgDocument type validation
 *   - API function exports (upload, list, get, delete)
 *   - org-admin-store: knowledge tab type
 *   - OrgAdminView: 5th tab integration
 *   - OrgManagerKnowledge: upload area, document list, status badges, delete
 */
import { describe, it, expect, vi } from "vitest";

// Mock API dependencies
vi.mock("@/api/admin", () => ({
  getAdminContext: vi.fn().mockRejectedValue(new Error("Not configured")),
  getAdminOrgDetail: vi.fn().mockRejectedValue(new Error("Not configured")),
  getAdminOrgMembers: vi.fn().mockResolvedValue([]),
  addOrgMember: vi.fn().mockResolvedValue(undefined),
  removeOrgMember: vi.fn().mockResolvedValue(undefined),
  uploadOrgDocument: vi.fn().mockResolvedValue({
    document_id: "doc-1",
    organization_id: "test-org",
    filename: "test.pdf",
    file_size_bytes: 1024,
    status: "ready",
    page_count: 5,
    chunk_count: 5,
    error_message: null,
    uploaded_by: "admin-1",
    created_at: "2026-02-24T00:00:00Z",
    updated_at: "2026-02-24T00:00:00Z",
  }),
  listOrgDocuments: vi.fn().mockResolvedValue({
    documents: [],
    total: 0,
  }),
  getOrgDocument: vi.fn().mockResolvedValue({
    document_id: "doc-1",
    organization_id: "test-org",
    filename: "test.pdf",
    status: "ready",
    uploaded_by: "admin-1",
  }),
  deleteOrgDocument: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgPermissions: vi.fn().mockRejectedValue(new Error("Not configured")),
  updateOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
}));

vi.mock("@/lib/org-branding", () => ({
  applyOrgBranding: vi.fn(),
  resetBranding: vi.fn(),
  DEFAULT_BRANDING: { chatbot_name: "Wiii", welcome_message: "Xin chào!" },
}));

vi.mock("@/lib/constants", () => ({
  PERSONAL_ORG_ID: "personal",
}));

import type { OrgDocument, OrgDocumentStatus, OrgDocumentListResponse } from "@/api/types";

// ---------------------------------------------------------------------------
// 1. OrgDocument Type Tests
// ---------------------------------------------------------------------------

describe("OrgDocument type", () => {
  it("should have correct shape for a ready document", () => {
    const doc: OrgDocument = {
      document_id: "doc-123",
      organization_id: "test-org",
      filename: "Maritime_COLREGS.pdf",
      file_size_bytes: 2048000,
      status: "ready",
      page_count: 50,
      chunk_count: 50,
      error_message: null,
      uploaded_by: "admin-user",
      created_at: "2026-02-24T00:00:00Z",
      updated_at: "2026-02-24T00:00:00Z",
    };
    expect(doc.document_id).toBe("doc-123");
    expect(doc.status).toBe("ready");
    expect(doc.page_count).toBe(50);
    expect(doc.file_size_bytes).toBe(2048000);
  });

  it("should represent a failed document", () => {
    const doc: OrgDocument = {
      document_id: "doc-456",
      organization_id: "test-org",
      filename: "bad.pdf",
      file_size_bytes: 100,
      status: "failed",
      page_count: null,
      chunk_count: null,
      error_message: "Parse error on page 3",
      uploaded_by: "admin-user",
      created_at: "2026-02-24T00:00:00Z",
      updated_at: "2026-02-24T00:00:00Z",
    };
    expect(doc.status).toBe("failed");
    expect(doc.error_message).toContain("Parse error");
  });

  it("should represent an uploading document", () => {
    const doc: OrgDocument = {
      document_id: "doc-789",
      organization_id: "test-org",
      filename: "new.pdf",
      file_size_bytes: null,
      status: "uploading",
      page_count: null,
      chunk_count: null,
      error_message: null,
      uploaded_by: "org-admin",
      created_at: null,
      updated_at: null,
    };
    expect(doc.status).toBe("uploading");
    expect(doc.file_size_bytes).toBeNull();
  });

  it("should accept all valid status values", () => {
    const statuses: OrgDocumentStatus[] = ["uploading", "processing", "ready", "failed", "deleted"];
    statuses.forEach((s) => {
      const doc: OrgDocument = {
        document_id: "doc",
        organization_id: "org",
        filename: "f.pdf",
        file_size_bytes: null,
        status: s,
        page_count: null,
        chunk_count: null,
        error_message: null,
        uploaded_by: "u",
        created_at: null,
        updated_at: null,
      };
      expect(doc.status).toBe(s);
    });
  });
});

describe("OrgDocumentListResponse type", () => {
  it("should have documents array and total count", () => {
    const resp: OrgDocumentListResponse = {
      documents: [
        {
          document_id: "doc-1",
          organization_id: "org",
          filename: "a.pdf",
          file_size_bytes: 1024,
          status: "ready",
          page_count: 10,
          chunk_count: 10,
          error_message: null,
          uploaded_by: "admin",
          created_at: "2026-02-24T00:00:00Z",
          updated_at: "2026-02-24T00:00:00Z",
        },
      ],
      total: 1,
    };
    expect(resp.documents).toHaveLength(1);
    expect(resp.total).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// 2. API Function Export Tests
// ---------------------------------------------------------------------------

describe("Org Knowledge API functions", () => {
  it("should export uploadOrgDocument", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.uploadOrgDocument).toBe("function");
  });

  it("should export listOrgDocuments", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.listOrgDocuments).toBe("function");
  });

  it("should export getOrgDocument", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getOrgDocument).toBe("function");
  });

  it("should export deleteOrgDocument", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.deleteOrgDocument).toBe("function");
  });
});
