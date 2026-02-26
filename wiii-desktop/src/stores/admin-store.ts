/**
 * Admin store — Sprint 179: "Quản Trị Toàn Diện"
 *
 * Manages all admin panel state: dashboard, users, feature flags,
 * analytics, audit logs, and GDPR operations.
 */
import { create } from "zustand";
import type {
  AdminDashboard,
  AdminUser,
  AdminFeatureFlag,
  AdminOrgSummary,
  AdminOrgDetail,
  AdminOrgMember,
  AnalyticsOverview,
  LlmUsageAnalytics,
  UserAnalytics,
  AdminAuditEntry,
  AdminAuthEvent,
  GdprExportResponse,
  GdprForgetResponse,
} from "@/api/types";
import {
  getAdminDashboard,
  searchAdminUsers,
  getFeatureFlags,
  toggleFeatureFlag,
  deleteFeatureFlagOverride,
  getAnalyticsOverview,
  getLlmUsageAnalytics,
  getUserAnalytics,
  getAuditLogs,
  getAuthEvents,
  gdprExportUser,
  gdprForgetUser,
  getAdminOrgDetail,
  getAdminOrgMembers,
  getFeatureFlagsForOrg,
  getOrgAnalyticsOverview,
  getOrgLlmUsage,
  deactivateUser as apiDeactivateUser,
  reactivateUser as apiReactivateUser,
  changeUserRole as apiChangeUserRole,
  addOrgMember as apiAddOrgMember,
  removeOrgMember as apiRemoveOrgMember,
} from "@/api/admin";

export type AdminTab = "dashboard" | "users" | "organizations" | "flags" | "analytics" | "audit" | "gdpr";
export type OrgSubView = "overview" | "members" | "flags" | "analytics" | "settings";
export type AuditSubTab = "admin" | "auth";
export type DateRange = "7d" | "30d" | "90d" | "all";

interface AdminState {
  // Navigation
  activeTab: AdminTab;

  // Dashboard
  dashboard: AdminDashboard | null;

  // Users
  users: AdminUser[];
  usersTotal: number;
  usersSearch: string;
  usersPage: number;
  usersSort: string;
  usersRoleFilter: string;
  usersStatusFilter: string;

  // Organizations (Sprint 179b)
  organizations: AdminOrgSummary[];
  selectedOrgId: string | null;
  selectedOrgDetail: AdminOrgDetail | null;
  selectedOrgMembers: AdminOrgMember[];
  orgFeatureFlags: AdminFeatureFlag[];
  orgAnalytics: AnalyticsOverview | null;
  orgLlmUsage: LlmUsageAnalytics | null;
  orgSubView: OrgSubView;

  // Feature Flags
  featureFlags: AdminFeatureFlag[];
  flagSearch: string;
  flagsOrgFilter: string | null;

  // Analytics
  analyticsOverview: AnalyticsOverview | null;
  llmUsage: LlmUsageAnalytics | null;
  userAnalytics: UserAnalytics | null;
  analyticsDateRange: DateRange;

  // Audit
  auditLogs: AdminAuditEntry[];
  auditLogsTotal: number;
  auditLogsPage: number;
  authEvents: AdminAuthEvent[];
  authEventsTotal: number;
  authEventsPage: number;
  auditSubTab: AuditSubTab;

  // GDPR
  gdprExportResult: GdprExportResponse | null;
  gdprForgetResult: GdprForgetResponse | null;

  // Toast (Sprint 180)
  toast: { message: string; type: "success" | "error" } | null;

  // Common
  loading: boolean;
  error: string | null;

  // Actions
  setActiveTab: (tab: AdminTab) => void;
  fetchDashboard: () => Promise<void>;
  fetchUsers: (params?: { search?: string; page?: number; sort?: string; role?: string; status?: string }) => Promise<void>;
  // Organizations (Sprint 179b)
  selectOrg: (orgId: string | null) => void;
  fetchOrgDetail: (orgId: string) => Promise<void>;
  fetchOrgMembers: (orgId: string) => Promise<void>;
  fetchOrgFeatureFlags: (orgId: string) => Promise<void>;
  toggleOrgFlag: (key: string, value: boolean, orgId: string) => Promise<void>;
  deleteOrgFlagOverride: (key: string, orgId: string) => Promise<void>;
  fetchOrgAnalytics: (orgId: string) => Promise<void>;
  fetchOrgLlmUsage: (orgId: string) => Promise<void>;
  setOrgSubView: (view: OrgSubView) => void;
  // Feature Flags
  fetchFeatureFlags: (orgId?: string) => Promise<void>;
  toggleFlag: (key: string, value: boolean) => Promise<void>;
  deleteFlagOverride: (key: string) => Promise<void>;
  setFlagSearch: (search: string) => void;
  setFlagsOrgFilter: (orgId: string | null) => void;
  fetchAnalyticsOverview: (dateRange?: DateRange) => Promise<void>;
  fetchLlmUsage: (dateRange?: DateRange) => Promise<void>;
  fetchUserAnalytics: (dateRange?: DateRange) => Promise<void>;
  setAnalyticsDateRange: (range: DateRange) => void;
  fetchAuditLogs: (page?: number) => Promise<void>;
  fetchAuthEvents: (page?: number) => Promise<void>;
  setAuditSubTab: (tab: AuditSubTab) => void;
  gdprExport: (userId: string) => Promise<void>;
  gdprForget: (userId: string) => Promise<void>;
  // Sprint 180: Toast + user/org member actions
  showToast: (message: string, type: "success" | "error") => void;
  deactivateUser: (userId: string) => Promise<void>;
  reactivateUser: (userId: string) => Promise<void>;
  changeUserRole: (userId: string, role: string) => Promise<void>;
  addOrgMember: (orgId: string, userId: string, role?: string) => Promise<void>;
  removeOrgMember: (orgId: string, userId: string) => Promise<void>;
  reset: () => void;
}

const PAGE_SIZE = 20;

function dateRangeToFrom(range: DateRange): string | undefined {
  if (range === "all") return undefined;
  const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split("T")[0];
}

const INITIAL_STATE = {
  activeTab: "dashboard" as AdminTab,
  dashboard: null,
  users: [],
  usersTotal: 0,
  usersSearch: "",
  usersPage: 0,
  usersSort: "created_at_desc",
  usersRoleFilter: "",
  usersStatusFilter: "",
  organizations: [] as AdminOrgSummary[],
  selectedOrgId: null as string | null,
  selectedOrgDetail: null as AdminOrgDetail | null,
  selectedOrgMembers: [] as AdminOrgMember[],
  orgFeatureFlags: [] as AdminFeatureFlag[],
  orgAnalytics: null as AnalyticsOverview | null,
  orgLlmUsage: null as LlmUsageAnalytics | null,
  orgSubView: "overview" as OrgSubView,
  featureFlags: [],
  flagSearch: "",
  flagsOrgFilter: null as string | null,
  analyticsOverview: null,
  llmUsage: null,
  userAnalytics: null,
  analyticsDateRange: "30d" as DateRange,
  auditLogs: [],
  auditLogsTotal: 0,
  auditLogsPage: 0,
  authEvents: [],
  authEventsTotal: 0,
  authEventsPage: 0,
  auditSubTab: "admin" as AuditSubTab,
  gdprExportResult: null,
  gdprForgetResult: null,
  toast: null,
  loading: false,
  error: null,
};

export const useAdminStore = create<AdminState>((set, get) => ({
  ...INITIAL_STATE,

  setActiveTab: (tab) => set({ activeTab: tab }),

  fetchDashboard: async () => {
    set({ loading: true, error: null });
    try {
      const dashboard = await getAdminDashboard();
      set({
        dashboard,
        organizations: dashboard.organizations ?? [],
        loading: false,
      });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchUsers: async (params) => {
    const state = get();
    const search = params?.search ?? state.usersSearch;
    const page = params?.page ?? state.usersPage;
    const sort = params?.sort ?? state.usersSort;
    const role = params?.role ?? state.usersRoleFilter;
    const status = params?.status ?? state.usersStatusFilter;
    set({ loading: true, error: null, usersSearch: search, usersPage: page, usersSort: sort, usersRoleFilter: role, usersStatusFilter: status });
    try {
      const resp = await searchAdminUsers({
        q: search || undefined,
        role: role || undefined,
        status: status || undefined,
        sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      set({ users: resp.users, usersTotal: resp.total, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchFeatureFlags: async (orgId?: string) => {
    set({ loading: true, error: null });
    try {
      const flags = await getFeatureFlags(orgId ?? get().flagsOrgFilter ?? undefined);
      set({ featureFlags: flags, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  toggleFlag: async (key, value) => {
    set({ error: null });
    try {
      const updated = await toggleFeatureFlag(key, { value });
      set((s) => ({
        featureFlags: s.featureFlags.map((f) =>
          f.key === key ? updated : f
        ),
      }));
      get().showToast(`Đã cập nhật flag ${key}`, "success");
    } catch (e) {
      set({ error: String(e) });
      get().showToast(String(e), "error");
    }
  },

  deleteFlagOverride: async (key) => {
    set({ error: null });
    try {
      await deleteFeatureFlagOverride(key);
      // Refresh flags list
      await get().fetchFeatureFlags();
    } catch (e) {
      set({ error: String(e) });
    }
  },

  setFlagSearch: (search) => set({ flagSearch: search }),

  setFlagsOrgFilter: (orgId) => set({ flagsOrgFilter: orgId }),

  // --- Organization actions (Sprint 179b) ---

  selectOrg: (orgId) =>
    set({
      selectedOrgId: orgId,
      selectedOrgDetail: null,
      selectedOrgMembers: [],
      orgFeatureFlags: [],
      orgAnalytics: null,
      orgLlmUsage: null,
      orgSubView: "overview",
    }),

  fetchOrgDetail: async (orgId) => {
    set({ loading: true, error: null });
    try {
      const detail = await getAdminOrgDetail(orgId);
      set({ selectedOrgDetail: detail, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchOrgMembers: async (orgId) => {
    set({ loading: true, error: null });
    try {
      const members = await getAdminOrgMembers(orgId);
      set({ selectedOrgMembers: members, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchOrgFeatureFlags: async (orgId) => {
    set({ loading: true, error: null });
    try {
      const flags = await getFeatureFlagsForOrg(orgId);
      set({ orgFeatureFlags: flags, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  toggleOrgFlag: async (key, value, orgId) => {
    set({ error: null });
    try {
      const updated = await toggleFeatureFlag(key, { value, organization_id: orgId });
      set((s) => ({
        orgFeatureFlags: s.orgFeatureFlags.map((f) =>
          f.key === key ? updated : f
        ),
      }));
    } catch (e) {
      set({ error: String(e) });
    }
  },

  deleteOrgFlagOverride: async (key, orgId) => {
    set({ error: null });
    try {
      await deleteFeatureFlagOverride(key, orgId);
      await get().fetchOrgFeatureFlags(orgId);
    } catch (e) {
      set({ error: String(e) });
    }
  },

  fetchOrgAnalytics: async (orgId) => {
    set({ error: null });
    try {
      const data = await getOrgAnalyticsOverview(orgId, {
        from: dateRangeToFrom(get().analyticsDateRange),
      });
      set({ orgAnalytics: data });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  fetchOrgLlmUsage: async (orgId) => {
    set({ error: null });
    try {
      const data = await getOrgLlmUsage(orgId, {
        from: dateRangeToFrom(get().analyticsDateRange),
      });
      set({ orgLlmUsage: data });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  setOrgSubView: (view) => set({ orgSubView: view }),

  fetchAnalyticsOverview: async (dateRange) => {
    const range = dateRange ?? get().analyticsDateRange;
    set({ loading: true, error: null, analyticsDateRange: range });
    try {
      const data = await getAnalyticsOverview({ from: dateRangeToFrom(range) });
      set({ analyticsOverview: data, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchLlmUsage: async (dateRange) => {
    const range = dateRange ?? get().analyticsDateRange;
    set({ error: null });
    try {
      const data = await getLlmUsageAnalytics({ from: dateRangeToFrom(range) });
      set({ llmUsage: data });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  fetchUserAnalytics: async (dateRange) => {
    const range = dateRange ?? get().analyticsDateRange;
    set({ error: null });
    try {
      const data = await getUserAnalytics({ from: dateRangeToFrom(range) });
      set({ userAnalytics: data });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  setAnalyticsDateRange: (range) => set({ analyticsDateRange: range }),

  fetchAuditLogs: async (page) => {
    const p = page ?? get().auditLogsPage;
    set({ loading: true, error: null, auditLogsPage: p });
    try {
      const resp = await getAuditLogs({ limit: PAGE_SIZE, offset: p * PAGE_SIZE });
      set({ auditLogs: resp.entries, auditLogsTotal: resp.total, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchAuthEvents: async (page) => {
    const p = page ?? get().authEventsPage;
    set({ loading: true, error: null, authEventsPage: p });
    try {
      const resp = await getAuthEvents({ limit: PAGE_SIZE, offset: p * PAGE_SIZE });
      set({ authEvents: resp.entries, authEventsTotal: resp.total, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  setAuditSubTab: (tab) => set({ auditSubTab: tab }),

  gdprExport: async (userId) => {
    set({ loading: true, error: null, gdprExportResult: null });
    try {
      const result = await gdprExportUser(userId);
      set({ gdprExportResult: result, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  gdprForget: async (userId) => {
    set({ loading: true, error: null, gdprForgetResult: null });
    try {
      const result = await gdprForgetUser(userId);
      set({ gdprForgetResult: result, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  // --- Sprint 180: Toast + user/org member actions ---

  showToast: (message, type) => {
    set({ toast: { message, type } });
    setTimeout(() => {
      set({ toast: null });
    }, 3000);
  },

  deactivateUser: async (userId) => {
    try {
      await apiDeactivateUser(userId);
      get().showToast("Đã vô hiệu hoá người dùng", "success");
      await get().fetchUsers();
    } catch (e) {
      get().showToast(String(e), "error");
    }
  },

  reactivateUser: async (userId) => {
    try {
      await apiReactivateUser(userId);
      get().showToast("Đã kích hoạt lại người dùng", "success");
      await get().fetchUsers();
    } catch (e) {
      get().showToast(String(e), "error");
    }
  },

  changeUserRole: async (userId, role) => {
    try {
      await apiChangeUserRole(userId, role);
      get().showToast(`Đã đổi vai trò thành ${role}`, "success");
      await get().fetchUsers();
    } catch (e) {
      get().showToast(String(e), "error");
    }
  },

  addOrgMember: async (orgId, userId, role) => {
    try {
      await apiAddOrgMember(orgId, userId, role);
      get().showToast("Đã thêm thành viên", "success");
      await get().fetchOrgMembers(orgId);
    } catch (e) {
      get().showToast(String(e), "error");
    }
  },

  removeOrgMember: async (orgId, userId) => {
    try {
      await apiRemoveOrgMember(orgId, userId);
      get().showToast("Đã xoá thành viên", "success");
      await get().fetchOrgMembers(orgId);
    } catch (e) {
      get().showToast(String(e), "error");
    }
  },

  reset: () => set(INITIAL_STATE),
}));
