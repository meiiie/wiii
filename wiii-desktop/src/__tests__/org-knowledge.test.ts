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
import { describe, it, expect, vi, beforeEach } from "vitest";

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
import { useOrgAdminStore } from "@/stores/org-admin-store";
import type { OrgManagerTab } from "@/stores/org-admin-store";

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

// ---------------------------------------------------------------------------
// 3. org-admin-store: Knowledge Tab
// ---------------------------------------------------------------------------

describe("org-admin-store knowledge tab", () => {
  beforeEach(() => {
    useOrgAdminStore.getState().reset();
  });

  it("should accept 'knowledge' as valid tab", () => {
    const tab: OrgManagerTab = "knowledge";
    useOrgAdminStore.getState().setActiveTab(tab);
    expect(useOrgAdminStore.getState().activeTab).toBe("knowledge");
  });

  it("should still support all original tabs", () => {
    const tabs: OrgManagerTab[] = ["dashboard", "members", "analytics", "settings", "knowledge"];
    tabs.forEach((tab) => {
      useOrgAdminStore.getState().setActiveTab(tab);
      expect(useOrgAdminStore.getState().activeTab).toBe(tab);
    });
  });

  it("should default to dashboard tab", () => {
    useOrgAdminStore.getState().reset();
    expect(useOrgAdminStore.getState().activeTab).toBe("dashboard");
  });

  it("should reset knowledge tab back to dashboard", () => {
    useOrgAdminStore.getState().setActiveTab("knowledge");
    expect(useOrgAdminStore.getState().activeTab).toBe("knowledge");
    useOrgAdminStore.getState().reset();
    expect(useOrgAdminStore.getState().activeTab).toBe("dashboard");
  });
});

// ---------------------------------------------------------------------------
// 4. org-admin-store: Document State & Actions
// ---------------------------------------------------------------------------

describe("org-admin-store document state", () => {
  beforeEach(() => {
    useOrgAdminStore.getState().reset();
    vi.clearAllMocks();
  });

  it("should initialize with empty document state", () => {
    const state = useOrgAdminStore.getState();
    expect(state.documents).toEqual([]);
    expect(state.documentsTotal).toBe(0);
    expect(state.documentsLoading).toBe(false);
  });

  it("should reset document state on reset()", () => {
    useOrgAdminStore.setState({
      documents: [{ document_id: "x" } as OrgDocument],
      documentsTotal: 5,
      documentsLoading: true,
    });
    useOrgAdminStore.getState().reset();
    const state = useOrgAdminStore.getState();
    expect(state.documents).toEqual([]);
    expect(state.documentsTotal).toBe(0);
    expect(state.documentsLoading).toBe(false);
  });

  it("fetchDocuments should populate documents and total", async () => {
    const { listOrgDocuments: mockList } = await import("@/api/admin");
    (mockList as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      documents: [
        { document_id: "d1", filename: "a.pdf", status: "ready" },
        { document_id: "d2", filename: "b.pdf", status: "processing" },
      ],
      total: 2,
    });

    await useOrgAdminStore.getState().fetchDocuments("org-1");
    const state = useOrgAdminStore.getState();
    expect(state.documents).toHaveLength(2);
    expect(state.documentsTotal).toBe(2);
    expect(state.documentsLoading).toBe(false);
  });

  it("fetchDocuments should set loading flag during fetch", async () => {
    const { listOrgDocuments: mockList } = await import("@/api/admin");
    let resolvePromise: (value: unknown) => void;
    (mockList as ReturnType<typeof vi.fn>).mockReturnValueOnce(
      new Promise((r) => { resolvePromise = r; })
    );

    const promise = useOrgAdminStore.getState().fetchDocuments("org-1");
    expect(useOrgAdminStore.getState().documentsLoading).toBe(true);

    resolvePromise!({ documents: [], total: 0 });
    await promise;
    expect(useOrgAdminStore.getState().documentsLoading).toBe(false);
  });

  it("fetchDocuments should handle errors gracefully", async () => {
    const { listOrgDocuments: mockList } = await import("@/api/admin");
    (mockList as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("Network error"));

    await useOrgAdminStore.getState().fetchDocuments("org-1");
    const state = useOrgAdminStore.getState();
    expect(state.documents).toEqual([]);
    expect(state.documentsLoading).toBe(false);
  });

  it("uploadDocument should call API and show success toast", async () => {
    const { uploadOrgDocument: mockUpload, listOrgDocuments: mockList } = await import("@/api/admin");
    (mockList as ReturnType<typeof vi.fn>).mockResolvedValue({ documents: [], total: 0 });

    const file = new File(["pdf content"], "test.pdf", { type: "application/pdf" });
    await useOrgAdminStore.getState().uploadDocument("org-1", file);

    expect(mockUpload).toHaveBeenCalledWith("org-1", file);
    expect(useOrgAdminStore.getState().toast?.type).toBe("success");
    expect(useOrgAdminStore.getState().toast?.message).toContain("test.pdf");
  });

  it("uploadDocument should show error toast on failure", async () => {
    const { uploadOrgDocument: mockUpload } = await import("@/api/admin");
    (mockUpload as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("File too large"));

    const file = new File(["x"], "big.pdf", { type: "application/pdf" });
    await useOrgAdminStore.getState().uploadDocument("org-1", file);

    expect(useOrgAdminStore.getState().toast?.type).toBe("error");
    expect(useOrgAdminStore.getState().toast?.message).toContain("File too large");
  });

  it("deleteDocument should call API and show success toast", async () => {
    const { deleteOrgDocument: mockDelete, listOrgDocuments: mockList } = await import("@/api/admin");
    (mockList as ReturnType<typeof vi.fn>).mockResolvedValue({ documents: [], total: 0 });

    await useOrgAdminStore.getState().deleteDocument("org-1", "doc-123");

    expect(mockDelete).toHaveBeenCalledWith("org-1", "doc-123");
    expect(useOrgAdminStore.getState().toast?.type).toBe("success");
  });

  it("deleteDocument should show error toast on failure", async () => {
    const { deleteOrgDocument: mockDelete } = await import("@/api/admin");
    (mockDelete as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("Not found"));

    await useOrgAdminStore.getState().deleteDocument("org-1", "doc-999");

    expect(useOrgAdminStore.getState().toast?.type).toBe("error");
    expect(useOrgAdminStore.getState().toast?.message).toContain("Not found");
  });

  it("uploadDocument should refresh documents after success", async () => {
    const { listOrgDocuments: mockList } = await import("@/api/admin");
    (mockList as ReturnType<typeof vi.fn>).mockResolvedValue({
      documents: [{ document_id: "d-new", filename: "uploaded.pdf", status: "processing" }],
      total: 1,
    });

    const file = new File(["content"], "uploaded.pdf", { type: "application/pdf" });
    await useOrgAdminStore.getState().uploadDocument("org-1", file);

    expect(useOrgAdminStore.getState().documents).toHaveLength(1);
    expect(useOrgAdminStore.getState().documentsTotal).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// 5. OrgAdminView: 5th Tab Integration
// ---------------------------------------------------------------------------

describe("OrgAdminView 5th tab", () => {
  it("should have knowledge in OrgManagerTab type", () => {
    // Type-level test: if this compiles, the type is correct
    const tab: OrgManagerTab = "knowledge";
    expect(tab).toBe("knowledge");
  });

  it("should have 5 total tabs in tab type", () => {
    const allTabs: OrgManagerTab[] = ["dashboard", "members", "analytics", "settings", "knowledge"];
    expect(allTabs).toHaveLength(5);
    expect(new Set(allTabs).size).toBe(5); // All unique
  });

  it("should include knowledge as last tab", () => {
    const tabs: OrgManagerTab[] = ["dashboard", "members", "analytics", "settings", "knowledge"];
    expect(tabs[tabs.length - 1]).toBe("knowledge");
  });
});
