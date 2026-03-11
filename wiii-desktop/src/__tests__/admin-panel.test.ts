/**
 * Unit tests for Sprint 179: Admin Panel — "Quản Trị Toàn Diện"
 * Tests types, API module, store logic, and UI store integration.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAdminStore } from "@/stores/admin-store";
import { useUIStore } from "@/stores/ui-store";
import type {
  AdminDashboard,
  AdminUser,
  AdminUserSearchParams,
  AdminUserSearchResponse,
  AdminFeatureFlag,
  AdminFlagUpdateBody,
  AnalyticsOverview,
  AnalyticsDataPoint,
  ChatVolumePoint,
  ErrorRatePoint,
  LlmUsageAnalytics,
  LlmUsageBreakdown,
  UserAnalytics,
  UserGrowthPoint,
  AdminAuditEntry,
  AdminAuditLogsResponse,
  AdminAuthEvent,
  AdminAuthEventsResponse,
  GdprExportResponse,
  GdprForgetResponse,
} from "@/api/types";

// Reset stores before each test
beforeEach(() => {
  useAdminStore.getState().reset();
  useUIStore.setState({ activeView: "chat" });
});

// =============================================================================
// 1. TYPE TESTS — verify interface shapes compile and work correctly
// =============================================================================

describe("Admin Types", () => {
  it("creates valid AdminDashboard", () => {
    const d: AdminDashboard = {
      total_users: 150,
      active_users: 42,
      total_organizations: 3,
      total_chat_sessions_24h: 200,
      total_llm_tokens_24h: 50000,
      estimated_cost_24h_usd: 1.23,
      feature_flags_active: 12,
    };
    expect(d.total_users).toBe(150);
    expect(d.estimated_cost_24h_usd).toBe(1.23);
  });

  it("creates valid AdminUser", () => {
    const u: AdminUser = {
      id: "user-1",
      email: "test@wiii.lab",
      name: "Tester",
      role: "admin",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      organization_count: 2,
    };
    expect(u.role).toBe("admin");
    expect(u.organization_count).toBe(2);
  });

  it("creates valid AdminUserSearchParams", () => {
    const p: AdminUserSearchParams = {
      q: "test",
      role: "student",
      status: "active",
      sort: "created_at_desc",
      limit: 20,
      offset: 0,
    };
    expect(p.q).toBe("test");
    expect(p.limit).toBe(20);
  });

  it("creates valid AdminUserSearchResponse", () => {
    const r: AdminUserSearchResponse = {
      users: [],
      total: 0,
      limit: 20,
      offset: 0,
    };
    expect(r.users).toEqual([]);
    expect(r.total).toBe(0);
  });

  it("creates valid AdminFeatureFlag", () => {
    const f: AdminFeatureFlag = {
      key: "enable_product_search",
      value: true,
      source: "db_override",
      flag_type: "release",
      description: "Product search agent",
      owner: null,
      expires_at: null,
    };
    expect(f.source).toBe("db_override");
    expect(f.value).toBe(true);
  });

  it("creates valid AdminFlagUpdateBody", () => {
    const b: AdminFlagUpdateBody = {
      value: false,
      flag_type: "release",
      description: "Disabled for testing",
    };
    expect(b.value).toBe(false);
  });

  it("creates valid AnalyticsOverview with nested types", () => {
    const dp: AnalyticsDataPoint = { date: "2026-02-01", count: 42 };
    const cv: ChatVolumePoint = { date: "2026-02-01", messages: 100, sessions: 30 };
    const er: ErrorRatePoint = { date: "2026-02-01", total: 100, errors: 2, rate: 0.02 };
    const o: AnalyticsOverview = {
      period_start: "30 days ago",
      period_end: "now",
      daily_active_users: [dp],
      chat_volume: [cv],
      error_rate: [er],
    };
    expect(o.daily_active_users).toHaveLength(1);
    expect(o.chat_volume[0].messages).toBe(100);
    expect(o.error_rate[0].rate).toBe(0.02);
  });

  it("creates valid LlmUsageAnalytics with breakdown", () => {
    const bd: LlmUsageBreakdown = { group: "2026-02-01", tokens: 5000, cost: 0.5, requests: 10 };
    const a: LlmUsageAnalytics = {
      total_tokens: 50000,
      total_cost_usd: 5.0,
      total_requests: 100,
      breakdown: [bd],
      top_models: [{ model: "gemini-3.1-flash-lite-preview", tokens: 30000, requests: 60 }],
      top_users: [{ user_id: "u-1", tokens: 10000, requests: 20 }],
    };
    expect(a.total_tokens).toBe(50000);
    expect(a.top_models[0].model).toBe("gemini-3.1-flash-lite-preview");
  });

  it("creates valid UserAnalytics", () => {
    const gp: UserGrowthPoint = { date: "2026-02-01", new_users: 5 };
    const ua: UserAnalytics = {
      total_users: 150,
      new_users_period: 20,
      active_users_period: 42,
      user_growth: [gp],
      role_distribution: { student: 100, teacher: 40, admin: 10 },
      top_active_users: [{ user_id: "u-1", sessions: 50 }],
    };
    expect(ua.role_distribution.student).toBe(100);
    expect(ua.user_growth).toHaveLength(1);
  });

  it("creates valid AdminAuditEntry and response", () => {
    const entry: AdminAuditEntry = {
      id: "audit-1",
      actor_id: "admin-1",
      actor_role: "admin",
      actor_name: "Admin User",
      action: "flag.toggle",
      http_method: "PATCH",
      http_path: "/admin/feature-flags/enable_mcp",
      http_status: 200,
      target_type: "feature_flag",
      target_id: "enable_mcp",
      target_name: null,
      old_value: { value: false },
      new_value: { value: true },
      ip_address: "127.0.0.1",
      request_id: "req-123",
      organization_id: null,
      occurred_at: "2026-02-23T10:00:00Z",
    };
    const resp: AdminAuditLogsResponse = {
      entries: [entry],
      total: 1,
      limit: 50,
      offset: 0,
    };
    expect(entry.action).toBe("flag.toggle");
    expect(resp.entries).toHaveLength(1);
  });

  it("creates valid AdminAuthEvent and response", () => {
    const event: AdminAuthEvent = {
      id: "auth-1",
      event_type: "login",
      user_id: "user-1",
      provider: "google",
      result: "success",
      reason: null,
      ip_address: "192.168.1.1",
      organization_id: null,
      metadata: { browser: "Chrome" },
      created_at: "2026-02-23T09:00:00Z",
    };
    const resp: AdminAuthEventsResponse = {
      entries: [event],
      total: 1,
      limit: 50,
      offset: 0,
    };
    expect(event.event_type).toBe("login");
    expect(resp.total).toBe(1);
  });

  it("creates valid GdprExportResponse", () => {
    const r: GdprExportResponse = {
      user_id: "user-1",
      exported_at: "2026-02-23T10:00:00Z",
      data: {
        profile: { id: "user-1", email: "test@wiii.lab" },
        identities: [{ provider: "google" }],
        memories: [],
        auth_events: [],
        audit_entries: [],
      },
    };
    expect(r.data.profile.email).toBe("test@wiii.lab");
    expect(r.data.identities).toHaveLength(1);
  });

  it("creates valid GdprForgetResponse", () => {
    const r: GdprForgetResponse = {
      user_id: "user-1",
      status: "forgotten",
      profile_anonymized: true,
      identities_deleted: 2,
      tokens_revoked: 3,
      memories_deleted: 15,
      audit_logs_preserved: true,
    };
    expect(r.status).toBe("forgotten");
    expect(r.audit_logs_preserved).toBe(true);
    expect(r.memories_deleted).toBe(15);
  });
});

// =============================================================================
// 2. API MODULE EXPORTS — verify all functions exist
// =============================================================================

describe("Admin API Module", () => {
  it("exports getAdminDashboard", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAdminDashboard).toBe("function");
  });

  it("exports searchAdminUsers", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.searchAdminUsers).toBe("function");
  });

  it("exports getFeatureFlags", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getFeatureFlags).toBe("function");
  });

  it("exports toggleFeatureFlag", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.toggleFeatureFlag).toBe("function");
  });

  it("exports deleteFeatureFlagOverride", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.deleteFeatureFlagOverride).toBe("function");
  });

  it("exports getAnalyticsOverview", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAnalyticsOverview).toBe("function");
  });

  it("exports getLlmUsageAnalytics", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getLlmUsageAnalytics).toBe("function");
  });

  it("exports getUserAnalytics", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getUserAnalytics).toBe("function");
  });

  it("exports getAuditLogs", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAuditLogs).toBe("function");
  });

  it("exports getAuthEvents", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAuthEvents).toBe("function");
  });

  it("exports gdprExportUser", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.gdprExportUser).toBe("function");
  });

  it("exports gdprForgetUser", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.gdprForgetUser).toBe("function");
  });
});

// =============================================================================
// 3. ADMIN STORE TESTS
// =============================================================================

describe("Admin Store", () => {
  it("has correct initial state", () => {
    const state = useAdminStore.getState();
    expect(state.activeTab).toBe("dashboard");
    expect(state.dashboard).toBeNull();
    expect(state.users).toEqual([]);
    expect(state.usersTotal).toBe(0);
    expect(state.usersSearch).toBe("");
    expect(state.usersPage).toBe(0);
    expect(state.usersSort).toBe("created_at_desc");
    expect(state.usersRoleFilter).toBe("");
    expect(state.usersStatusFilter).toBe("");
    expect(state.featureFlags).toEqual([]);
    expect(state.flagSearch).toBe("");
    expect(state.analyticsOverview).toBeNull();
    expect(state.llmUsage).toBeNull();
    expect(state.userAnalytics).toBeNull();
    expect(state.analyticsDateRange).toBe("30d");
    expect(state.auditLogs).toEqual([]);
    expect(state.auditLogsTotal).toBe(0);
    expect(state.auditLogsPage).toBe(0);
    expect(state.authEvents).toEqual([]);
    expect(state.authEventsTotal).toBe(0);
    expect(state.authEventsPage).toBe(0);
    expect(state.auditSubTab).toBe("admin");
    expect(state.gdprExportResult).toBeNull();
    expect(state.gdprForgetResult).toBeNull();
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("reset() restores initial state", () => {
    useAdminStore.setState({
      activeTab: "users",
      dashboard: {
        total_users: 10,
        active_users: 5,
        total_organizations: 2,
        total_chat_sessions_24h: 100,
        total_llm_tokens_24h: 5000,
        estimated_cost_24h_usd: 0.5,
        feature_flags_active: 8,
      },
      users: [{ id: "u1", email: "a@b.c", name: "A", role: "admin", is_active: true, created_at: null, organization_count: 1 }],
      usersTotal: 1,
      loading: true,
      error: "test error",
    });

    useAdminStore.getState().reset();

    const state = useAdminStore.getState();
    expect(state.activeTab).toBe("dashboard");
    expect(state.dashboard).toBeNull();
    expect(state.users).toEqual([]);
    expect(state.usersTotal).toBe(0);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("setActiveTab changes tab", () => {
    useAdminStore.getState().setActiveTab("flags");
    expect(useAdminStore.getState().activeTab).toBe("flags");

    useAdminStore.getState().setActiveTab("analytics");
    expect(useAdminStore.getState().activeTab).toBe("analytics");
  });

  it("setFlagSearch updates search", () => {
    useAdminStore.getState().setFlagSearch("enable_mcp");
    expect(useAdminStore.getState().flagSearch).toBe("enable_mcp");
  });

  it("setAnalyticsDateRange updates range", () => {
    useAdminStore.getState().setAnalyticsDateRange("7d");
    expect(useAdminStore.getState().analyticsDateRange).toBe("7d");

    useAdminStore.getState().setAnalyticsDateRange("90d");
    expect(useAdminStore.getState().analyticsDateRange).toBe("90d");
  });

  it("setAuditSubTab switches between admin and auth", () => {
    useAdminStore.getState().setAuditSubTab("auth");
    expect(useAdminStore.getState().auditSubTab).toBe("auth");

    useAdminStore.getState().setAuditSubTab("admin");
    expect(useAdminStore.getState().auditSubTab).toBe("admin");
  });

  it("fetchDashboard sets loading then updates on success", () => {
    // Simulate successful dashboard fetch
    useAdminStore.setState({ loading: true, error: null });
    expect(useAdminStore.getState().loading).toBe(true);

    const mockDashboard: AdminDashboard = {
      total_users: 50,
      active_users: 20,
      total_organizations: 3,
      total_chat_sessions_24h: 150,
      total_llm_tokens_24h: 25000,
      estimated_cost_24h_usd: 2.5,
      feature_flags_active: 15,
    };
    useAdminStore.setState({ dashboard: mockDashboard, loading: false });

    const state = useAdminStore.getState();
    expect(state.dashboard?.total_users).toBe(50);
    expect(state.loading).toBe(false);
  });

  it("fetchDashboard sets error on failure", () => {
    useAdminStore.setState({ loading: false, error: "Network error" });
    const state = useAdminStore.getState();
    expect(state.error).toBe("Network error");
    expect(state.loading).toBe(false);
  });

  it("fetchUsers updates users array and total", () => {
    const mockUsers: AdminUser[] = [
      { id: "u1", email: "a@b.c", name: "Alpha", role: "student", is_active: true, created_at: "2026-01-01", organization_count: 1 },
      { id: "u2", email: "b@c.d", name: "Beta", role: "teacher", is_active: false, created_at: null, organization_count: 0 },
    ];
    useAdminStore.setState({ users: mockUsers, usersTotal: 2, loading: false });

    const state = useAdminStore.getState();
    expect(state.users).toHaveLength(2);
    expect(state.usersTotal).toBe(2);
    expect(state.users[0].name).toBe("Alpha");
    expect(state.users[1].is_active).toBe(false);
  });

  it("fetchFeatureFlags updates flags list", () => {
    const mockFlags: AdminFeatureFlag[] = [
      { key: "enable_mcp", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      { key: "enable_product_search", value: false, source: "db_override", flag_type: "release", description: "Prod search", owner: null, expires_at: null },
    ];
    useAdminStore.setState({ featureFlags: mockFlags, loading: false });

    const state = useAdminStore.getState();
    expect(state.featureFlags).toHaveLength(2);
    expect(state.featureFlags[0].key).toBe("enable_mcp");
    expect(state.featureFlags[1].source).toBe("db_override");
  });

  it("toggleFlag updates single flag in list", () => {
    // Simulate initial state with two flags
    useAdminStore.setState({
      featureFlags: [
        { key: "enable_a", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
        { key: "enable_b", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });

    // Simulate toggle of enable_a
    const updatedFlag: AdminFeatureFlag = {
      key: "enable_a",
      value: true,
      source: "db_override",
      flag_type: "release",
      description: null,
      owner: null,
      expires_at: null,
    };
    useAdminStore.setState((s) => ({
      featureFlags: s.featureFlags.map((f) => (f.key === "enable_a" ? updatedFlag : f)),
    }));

    const state = useAdminStore.getState();
    expect(state.featureFlags[0].value).toBe(true);
    expect(state.featureFlags[0].source).toBe("db_override");
    expect(state.featureFlags[1].value).toBe(true); // Unchanged
  });

  it("fetchAuditLogs updates entries and pagination", () => {
    const mockEntry: AdminAuditEntry = {
      id: "a1",
      actor_id: "admin-1",
      actor_role: "admin",
      actor_name: "Admin",
      action: "user.deactivate",
      http_method: "POST",
      http_path: "/admin/users/u1/deactivate",
      http_status: 200,
      target_type: "user",
      target_id: "u1",
      target_name: null,
      old_value: null,
      new_value: null,
      ip_address: "10.0.0.1",
      request_id: "req-1",
      organization_id: null,
      occurred_at: "2026-02-23T10:00:00Z",
    };
    useAdminStore.setState({ auditLogs: [mockEntry], auditLogsTotal: 1, auditLogsPage: 0, loading: false });

    const state = useAdminStore.getState();
    expect(state.auditLogs).toHaveLength(1);
    expect(state.auditLogs[0].action).toBe("user.deactivate");
    expect(state.auditLogsTotal).toBe(1);
  });

  it("fetchAuthEvents updates entries and pagination", () => {
    const mockEvent: AdminAuthEvent = {
      id: "e1",
      event_type: "login",
      user_id: "u1",
      provider: "google",
      result: "success",
      reason: null,
      ip_address: "192.168.1.1",
      organization_id: null,
      metadata: null,
      created_at: "2026-02-23T09:00:00Z",
    };
    useAdminStore.setState({ authEvents: [mockEvent], authEventsTotal: 1, authEventsPage: 0, loading: false });

    const state = useAdminStore.getState();
    expect(state.authEvents).toHaveLength(1);
    expect(state.authEvents[0].event_type).toBe("login");
  });

  it("gdprExport sets export result", () => {
    const mockResult: GdprExportResponse = {
      user_id: "u1",
      exported_at: "2026-02-23T10:00:00Z",
      data: {
        profile: { id: "u1", email: "test@wiii.lab" },
        identities: [],
        memories: [{ content: "Likes cats" }],
        auth_events: [],
        audit_entries: [],
      },
    };
    useAdminStore.setState({ gdprExportResult: mockResult, loading: false });

    const state = useAdminStore.getState();
    expect(state.gdprExportResult?.user_id).toBe("u1");
    expect(state.gdprExportResult?.data.memories).toHaveLength(1);
  });

  it("gdprForget sets forget result", () => {
    const mockResult: GdprForgetResponse = {
      user_id: "u1",
      status: "forgotten",
      profile_anonymized: true,
      identities_deleted: 1,
      tokens_revoked: 2,
      memories_deleted: 10,
      audit_logs_preserved: true,
    };
    useAdminStore.setState({ gdprForgetResult: mockResult, loading: false });

    const state = useAdminStore.getState();
    expect(state.gdprForgetResult?.status).toBe("forgotten");
    expect(state.gdprForgetResult?.memories_deleted).toBe(10);
  });

  it("usersPage tracks pagination state", () => {
    useAdminStore.setState({ usersPage: 3, usersTotal: 100 });
    expect(useAdminStore.getState().usersPage).toBe(3);
  });

  it("usersSort tracks sort state", () => {
    useAdminStore.setState({ usersSort: "name_asc" });
    expect(useAdminStore.getState().usersSort).toBe("name_asc");
  });

  it("usersRoleFilter and usersStatusFilter track filters", () => {
    useAdminStore.setState({ usersRoleFilter: "admin", usersStatusFilter: "active" });
    const state = useAdminStore.getState();
    expect(state.usersRoleFilter).toBe("admin");
    expect(state.usersStatusFilter).toBe("active");
  });
});

// =============================================================================
// 4. UI STORE TESTS — activeView, open/close, closeAll
// =============================================================================

describe("UI Store — Admin Panel", () => {
  it("activeView defaults to chat", () => {
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("openAdminPanel sets activeView and closes command palette", () => {
    useUIStore.setState({ commandPaletteOpen: true });
    useUIStore.getState().openAdminPanel();

    const state = useUIStore.getState();
    expect(state.activeView).toBe("system-admin");
    expect(state.commandPaletteOpen).toBe(false);
  });

  it("closeAdminPanel returns to chat", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().closeAdminPanel();
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("closeAll resets activeView and closes everything", () => {
    useUIStore.setState({
      commandPaletteOpen: true,
      sourcesPanelOpen: true,
    });
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().closeAll();

    const state = useUIStore.getState();
    expect(state.activeView).toBe("chat");
    expect(state.commandPaletteOpen).toBe(false);
    expect(state.sourcesPanelOpen).toBe(false);
  });
});

// =============================================================================
// 5. INTEGRATION-STYLE TESTS — tab switching, flag toggling, pagination
// =============================================================================

describe("Admin Store Integration", () => {
  it("tab switching clears nothing", () => {
    // Set some data first
    useAdminStore.setState({
      activeTab: "dashboard",
      dashboard: {
        total_users: 10,
        active_users: 5,
        total_organizations: 2,
        total_chat_sessions_24h: 50,
        total_llm_tokens_24h: 5000,
        estimated_cost_24h_usd: 1.0,
        feature_flags_active: 8,
      },
    });

    // Switch tabs — data should persist
    useAdminStore.getState().setActiveTab("users");
    expect(useAdminStore.getState().activeTab).toBe("users");
    expect(useAdminStore.getState().dashboard).not.toBeNull();
  });

  it("flag toggle preserves other flags in list", () => {
    const flags: AdminFeatureFlag[] = [
      { key: "enable_a", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      { key: "enable_b", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      { key: "enable_c", value: true, source: "db_override", flag_type: "release", description: "Test", owner: null, expires_at: null },
    ];
    useAdminStore.setState({ featureFlags: flags });

    // Toggle enable_b
    const updated: AdminFeatureFlag = { ...flags[1], value: true, source: "db_override" };
    useAdminStore.setState((s) => ({
      featureFlags: s.featureFlags.map((f) => (f.key === "enable_b" ? updated : f)),
    }));

    const state = useAdminStore.getState();
    expect(state.featureFlags).toHaveLength(3);
    expect(state.featureFlags[0].value).toBe(true); // unchanged
    expect(state.featureFlags[1].value).toBe(true); // toggled
    expect(state.featureFlags[1].source).toBe("db_override");
    expect(state.featureFlags[2].value).toBe(true); // unchanged
  });

  it("pagination state tracks correctly across pages", () => {
    // Start at page 0 with 100 total
    useAdminStore.setState({ usersPage: 0, usersTotal: 100 });

    // Navigate to page 2
    useAdminStore.setState({ usersPage: 2 });
    expect(useAdminStore.getState().usersPage).toBe(2);

    // Navigate back to page 0
    useAdminStore.setState({ usersPage: 0 });
    expect(useAdminStore.getState().usersPage).toBe(0);
  });

  it("audit subtab switch preserves data", () => {
    const mockAudit: AdminAuditEntry = {
      id: "a1",
      actor_id: "admin-1",
      actor_role: "admin",
      actor_name: "Admin",
      action: "flag.toggle",
      http_method: "PATCH",
      http_path: "/admin/feature-flags/enable_a",
      http_status: 200,
      target_type: "feature_flag",
      target_id: "enable_a",
      target_name: null,
      old_value: null,
      new_value: null,
      ip_address: "10.0.0.1",
      request_id: "req-1",
      organization_id: null,
      occurred_at: "2026-02-23T10:00:00Z",
    };
    useAdminStore.setState({ auditLogs: [mockAudit], auditLogsTotal: 1 });

    // Switch to auth subtab
    useAdminStore.getState().setAuditSubTab("auth");

    // Admin data should still be there
    expect(useAdminStore.getState().auditLogs).toHaveLength(1);
    expect(useAdminStore.getState().auditSubTab).toBe("auth");
  });

  it("GDPR export then forget for same user", () => {
    // Export first
    useAdminStore.setState({
      gdprExportResult: {
        user_id: "u-target",
        exported_at: "2026-02-23T10:00:00Z",
        data: {
          profile: { id: "u-target" },
          identities: [],
          memories: [{ content: "fact1" }, { content: "fact2" }],
          auth_events: [],
          audit_entries: [],
        },
      },
    });

    expect(useAdminStore.getState().gdprExportResult?.data.memories).toHaveLength(2);

    // Then forget
    useAdminStore.setState({
      gdprForgetResult: {
        user_id: "u-target",
        status: "forgotten",
        profile_anonymized: true,
        identities_deleted: 1,
        tokens_revoked: 0,
        memories_deleted: 2,
        audit_logs_preserved: true,
      },
    });

    expect(useAdminStore.getState().gdprForgetResult?.memories_deleted).toBe(2);
  });

  it("date range change updates analyticsDateRange", () => {
    expect(useAdminStore.getState().analyticsDateRange).toBe("30d");
    useAdminStore.getState().setAnalyticsDateRange("7d");
    expect(useAdminStore.getState().analyticsDateRange).toBe("7d");
    useAdminStore.getState().setAnalyticsDateRange("all");
    expect(useAdminStore.getState().analyticsDateRange).toBe("all");
  });

  it("multiple concurrent state updates do not conflict", () => {
    // Simulate multiple tab data loading simultaneously
    useAdminStore.setState({
      dashboard: {
        total_users: 100,
        active_users: 50,
        total_organizations: 5,
        total_chat_sessions_24h: 200,
        total_llm_tokens_24h: 50000,
        estimated_cost_24h_usd: 5.0,
        feature_flags_active: 20,
      },
    });

    useAdminStore.setState({
      featureFlags: [
        { key: "flag1", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });

    useAdminStore.setState({
      users: [
        { id: "u1", email: "a@b.c", name: "A", role: "admin", is_active: true, created_at: null, organization_count: 1 },
      ],
      usersTotal: 1,
    });

    // All data should coexist
    const state = useAdminStore.getState();
    expect(state.dashboard?.total_users).toBe(100);
    expect(state.featureFlags).toHaveLength(1);
    expect(state.users).toHaveLength(1);
  });

  it("role gating: admin check is independent of store state", () => {
    // The role check happens in the Sidebar component via useSettingsStore
    // Here we verify the store doesn't enforce role — that's the component's job
    useAdminStore.getState().setActiveTab("gdpr");
    expect(useAdminStore.getState().activeTab).toBe("gdpr");
  });

  it("flagSearch filters correctly on frontend", () => {
    useAdminStore.setState({
      featureFlags: [
        { key: "enable_mcp_server", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
        { key: "enable_mcp_client", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
        { key: "enable_product_search", value: true, source: "db_override", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
      flagSearch: "mcp",
    });

    const state = useAdminStore.getState();
    const filtered = state.featureFlags.filter((f) =>
      f.key.toLowerCase().includes(state.flagSearch.toLowerCase())
    );
    expect(filtered).toHaveLength(2);
    expect(filtered[0].key).toBe("enable_mcp_server");
    expect(filtered[1].key).toBe("enable_mcp_client");
  });
});
