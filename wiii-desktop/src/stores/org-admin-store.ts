/**
 * Org Admin store — Sprint 181: "Hai Tầng Quyền Lực"
 * Sprint 190: Added document management state + actions for Knowledge tab.
 *
 * Lightweight store for org manager panel (5 tabs).
 * Separated from admin-store (system admin) for cleaner UX.
 */
import { create } from "zustand";
import type { AdminOrgMember, AdminOrgDetail, OrgDocument } from "@/api/types";
import {
  getAdminOrgDetail,
  getAdminOrgMembers,
  addOrgMember as apiAddOrgMember,
  removeOrgMember as apiRemoveOrgMember,
  listOrgDocuments,
  uploadOrgDocument as apiUploadOrgDocument,
  deleteOrgDocument as apiDeleteOrgDocument,
} from "@/api/admin";
import { getOrgSettings, updateOrgSettings } from "@/api/organizations";
import type { OrgSettings } from "@/api/types";

export type OrgManagerTab = "dashboard" | "members" | "analytics" | "settings" | "knowledge";

interface OrgAdminToast {
  type: "success" | "error";
  message: string;
}

interface OrgAdminState {
  activeTab: OrgManagerTab;
  orgId: string | null;
  orgDetail: AdminOrgDetail | null;
  members: AdminOrgMember[];
  orgSettings: OrgSettings | null;
  detailLoading: boolean;
  membersLoading: boolean;
  loading: boolean;
  toast: OrgAdminToast | null;
  _toastTimer: ReturnType<typeof setTimeout> | undefined;

  // Sprint 190: Knowledge documents
  documents: OrgDocument[];
  documentsTotal: number;
  documentsLoading: boolean;

  // Actions
  setActiveTab: (tab: OrgManagerTab) => void;
  setOrgId: (orgId: string) => void;
  reset: () => void;
  fetchOrgDetail: (orgId: string) => Promise<void>;
  fetchMembers: (orgId: string) => Promise<void>;
  fetchSettings: (orgId: string) => Promise<void>;
  addMember: (orgId: string, userId: string, role?: string) => Promise<void>;
  removeMember: (orgId: string, userId: string) => Promise<void>;
  updateSettings: (orgId: string, patch: Record<string, unknown>) => Promise<void>;
  showToast: (type: "success" | "error", message: string) => void;

  // Sprint 190: Knowledge actions
  fetchDocuments: (orgId: string) => Promise<void>;
  uploadDocument: (orgId: string, file: File) => Promise<void>;
  deleteDocument: (orgId: string, docId: string) => Promise<void>;
}

export const useOrgAdminStore = create<OrgAdminState>((set, get) => ({
  activeTab: "dashboard",
  orgId: null,
  orgDetail: null,
  members: [],
  orgSettings: null,
  detailLoading: false,
  membersLoading: false,
  loading: false,
  toast: null,
  _toastTimer: undefined,

  // Sprint 190: Knowledge state
  documents: [],
  documentsTotal: 0,
  documentsLoading: false,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setOrgId: (orgId) => set({ orgId }),
  reset: () => {
    const timer = get()._toastTimer;
    if (timer) clearTimeout(timer);
    set({
      activeTab: "dashboard",
      orgId: null,
      orgDetail: null,
      members: [],
      orgSettings: null,
      detailLoading: false,
      membersLoading: false,
      loading: false,
      toast: null,
      _toastTimer: undefined,
      documents: [],
      documentsTotal: 0,
      documentsLoading: false,
    });
  },

  fetchOrgDetail: async (orgId) => {
    set({ detailLoading: true, loading: true });
    try {
      const detail = await getAdminOrgDetail(orgId);
      set({ orgDetail: detail });
    } catch {
      // Graceful fallback
    } finally {
      set((s) => ({ detailLoading: false, loading: s.membersLoading }));
    }
  },

  fetchMembers: async (orgId) => {
    set({ membersLoading: true, loading: true });
    try {
      const members = await getAdminOrgMembers(orgId);
      set({ members });
    } catch {
      // Graceful fallback
    } finally {
      set((s) => ({ membersLoading: false, loading: s.detailLoading }));
    }
  },

  fetchSettings: async (orgId) => {
    try {
      const settings = await getOrgSettings(orgId);
      set({ orgSettings: settings });
    } catch {
      get().showToast("error", "Không thể tải cài đặt");
    }
  },

  addMember: async (orgId, userId, role) => {
    try {
      await apiAddOrgMember(orgId, userId, role);
      get().showToast("success", "Đã thêm thành viên");
      await get().fetchMembers(orgId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi thêm thành viên";
      get().showToast("error", msg);
    }
  },

  removeMember: async (orgId, userId) => {
    try {
      await apiRemoveOrgMember(orgId, userId);
      get().showToast("success", "Đã xoá thành viên");
      await get().fetchMembers(orgId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi xoá thành viên";
      get().showToast("error", msg);
    }
  },

  updateSettings: async (orgId, patch) => {
    try {
      const updated = await updateOrgSettings(orgId, patch);
      set({ orgSettings: updated });
      get().showToast("success", "Đã cập nhật cài đặt");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi cập nhật cài đặt";
      get().showToast("error", msg);
    }
  },

  // Sprint 190: Knowledge document actions
  fetchDocuments: async (orgId) => {
    set({ documentsLoading: true });
    try {
      const resp = await listOrgDocuments(orgId);
      set({ documents: resp.documents, documentsTotal: resp.total });
    } catch {
      // Graceful fallback
    } finally {
      set({ documentsLoading: false });
    }
  },

  uploadDocument: async (orgId, file) => {
    try {
      await apiUploadOrgDocument(orgId, file);
      get().showToast("success", `Đã tải lên: ${file.name}`);
      await get().fetchDocuments(orgId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi tải lên file";
      get().showToast("error", msg);
    }
  },

  deleteDocument: async (orgId, docId) => {
    try {
      await apiDeleteOrgDocument(orgId, docId);
      get().showToast("success", "Đã xoá tài liệu");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi xoá tài liệu";
      get().showToast("error", msg);
    } finally {
      await get().fetchDocuments(orgId);
    }
  },

  showToast: (type, message) => {
    const prev = get()._toastTimer;
    if (prev) clearTimeout(prev);
    const timer = setTimeout(() => set({ toast: null, _toastTimer: undefined }), 3000);
    set({ toast: { type, message }, _toastTimer: timer });
  },
}));
