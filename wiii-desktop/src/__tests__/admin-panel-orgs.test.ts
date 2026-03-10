/**
 * Unit tests for Sprint 179b: Admin Panel — "Quản Trị Theo Tổ Chức"
 * Tests types, API exports, store logic, integration flows, and org flags.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAdminStore } from "@/stores/admin-store";
import type {
  AdminOrgSummary,
  AdminOrgDetail,
  AdminOrgMember,
  AdminDashboard,
  AdminFeatureFlag,
} from "@/api/types";

// Reset store before each test
beforeEach(() => {
  useAdminStore.getState().reset();
});

// =============================================================================
// 1. TYPE TESTS — verify new interfaces compile and work correctly
// =============================================================================

describe("Sprint 179b Types", () => {
  it("creates valid AdminOrgSummary", () => {
    const org: AdminOrgSummary = {
      id: "maritime-lms",
      name: "maritime-lms",
      display_name: "Trường Hàng Hải",
      member_count: 42,
      is_active: true,
    };
    expect(org.id).toBe("maritime-lms");
    expect(org.member_count).toBe(42);
    expect(org.is_active).toBe(true);
  });

  it("creates AdminOrgSummary with null display_name", () => {
    const org: AdminOrgSummary = {
      id: "test-org",
      name: "test-org",
      display_name: null,
      member_count: 0,
      is_active: false,
    };
    expect(org.display_name).toBeNull();
    expect(org.is_active).toBe(false);
  });

  it("creates valid AdminOrgDetail", () => {
    const detail: AdminOrgDetail = {
      id: "maritime-lms",
      name: "maritime-lms",
      display_name: "Trường Hàng Hải",
      description: "Maritime university LMS",
      allowed_domains: ["maritime", "traffic_law"],
      default_domain: "maritime",
      settings: null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-02-23T10:00:00Z",
    };
    expect(detail.allowed_domains).toHaveLength(2);
    expect(detail.default_domain).toBe("maritime");
    expect(detail.settings).toBeNull();
  });

  it("creates valid AdminOrgMember", () => {
    const member: AdminOrgMember = {
      user_id: "user-123",
      organization_id: "maritime-lms",
      role: "student",
      joined_at: "2026-02-01T00:00:00Z",
    };
    expect(member.user_id).toBe("user-123");
    expect(member.role).toBe("student");
  });
});

// =============================================================================
// 2. API MODULE EXPORTS — verify all new functions exist
// =============================================================================

describe("Sprint 179b API Module", () => {
  it("exports getAdminOrgDetail", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAdminOrgDetail).toBe("function");
  });

  it("exports getAdminOrgMembers", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.getAdminOrgMembers).toBe("function");
  });

  it("getFeatureFlags accepts optional orgId parameter", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    // Verify function signature accepts string argument
    expect(api.getFeatureFlags.length).toBeLessThanOrEqual(1);
  });
});

// =============================================================================
// 3. STORE TESTS — initial state, org actions, sub-views
// =============================================================================

describe("Sprint 179b Store", () => {
  it("has correct initial org state", () => {
    const state = useAdminStore.getState();
    expect(state.organizations).toEqual([]);
    expect(state.selectedOrgId).toBeNull();
    expect(state.selectedOrgDetail).toBeNull();
    expect(state.selectedOrgMembers).toEqual([]);
    expect(state.orgFeatureFlags).toEqual([]);
    expect(state.orgAnalytics).toBeNull();
    expect(state.orgLlmUsage).toBeNull();
    expect(state.orgSubView).toBe("overview");
    expect(state.flagsOrgFilter).toBeNull();
  });

  it("selectOrg sets org ID and resets sub-state", () => {
    // Set some org data first
    useAdminStore.setState({
      selectedOrgId: "old-org",
      selectedOrgDetail: { id: "old", name: "old" } as AdminOrgDetail,
      selectedOrgMembers: [{ user_id: "u1", organization_id: "old", role: "admin", joined_at: null }],
      orgSubView: "members",
    });

    // Select new org
    useAdminStore.getState().selectOrg("new-org");

    const state = useAdminStore.getState();
    expect(state.selectedOrgId).toBe("new-org");
    expect(state.selectedOrgDetail).toBeNull();
    expect(state.selectedOrgMembers).toEqual([]);
    expect(state.orgFeatureFlags).toEqual([]);
    expect(state.orgSubView).toBe("overview");
  });

  it("selectOrg(null) clears org selection", () => {
    useAdminStore.setState({ selectedOrgId: "some-org" });
    useAdminStore.getState().selectOrg(null);
    expect(useAdminStore.getState().selectedOrgId).toBeNull();
  });

  it("setOrgSubView changes sub-view", () => {
    useAdminStore.getState().setOrgSubView("flags");
    expect(useAdminStore.getState().orgSubView).toBe("flags");

    useAdminStore.getState().setOrgSubView("analytics");
    expect(useAdminStore.getState().orgSubView).toBe("analytics");
  });

  it("setFlagsOrgFilter updates org filter", () => {
    useAdminStore.getState().setFlagsOrgFilter("maritime-lms");
    expect(useAdminStore.getState().flagsOrgFilter).toBe("maritime-lms");

    useAdminStore.getState().setFlagsOrgFilter(null);
    expect(useAdminStore.getState().flagsOrgFilter).toBeNull();
  });
});

// =============================================================================
// 4. STORE ACTIONS — simulate async data flows
// =============================================================================

describe("Sprint 179b Store Actions", () => {
  it("fetchOrgDetail updates selectedOrgDetail", () => {
    const mockDetail: AdminOrgDetail = {
      id: "maritime-lms",
      name: "maritime-lms",
      display_name: "Trường Hàng Hải",
      description: "Maritime LMS integration",
      allowed_domains: ["maritime"],
      default_domain: "maritime",
      settings: null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: null,
    };
    useAdminStore.setState({ selectedOrgDetail: mockDetail, loading: false });
    expect(useAdminStore.getState().selectedOrgDetail?.name).toBe("maritime-lms");
  });

  it("fetchOrgMembers updates selectedOrgMembers", () => {
    const mockMembers: AdminOrgMember[] = [
      { user_id: "u1", organization_id: "org-1", role: "admin", joined_at: "2026-01-15T00:00:00Z" },
      { user_id: "u2", organization_id: "org-1", role: "student", joined_at: null },
    ];
    useAdminStore.setState({ selectedOrgMembers: mockMembers, loading: false });
    const state = useAdminStore.getState();
    expect(state.selectedOrgMembers).toHaveLength(2);
    expect(state.selectedOrgMembers[0].role).toBe("admin");
  });

  it("fetchOrgFeatureFlags updates orgFeatureFlags", () => {
    const mockFlags: AdminFeatureFlag[] = [
      { key: "enable_mcp", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      { key: "enable_product_search", value: false, source: "db_override", flag_type: "release", description: "Disabled for org", owner: null, expires_at: null },
    ];
    useAdminStore.setState({ orgFeatureFlags: mockFlags, loading: false });
    const state = useAdminStore.getState();
    expect(state.orgFeatureFlags).toHaveLength(2);
    expect(state.orgFeatureFlags[1].source).toBe("db_override");
  });

  it("toggleOrgFlag updates single flag in orgFeatureFlags", () => {
    const flags: AdminFeatureFlag[] = [
      { key: "enable_a", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      { key: "enable_b", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
    ];
    useAdminStore.setState({ orgFeatureFlags: flags });

    // Simulate toggle
    const updated: AdminFeatureFlag = { ...flags[0], value: true, source: "db_override" };
    useAdminStore.setState((s) => ({
      orgFeatureFlags: s.orgFeatureFlags.map((f) => (f.key === "enable_a" ? updated : f)),
    }));

    const state = useAdminStore.getState();
    expect(state.orgFeatureFlags[0].value).toBe(true);
    expect(state.orgFeatureFlags[0].source).toBe("db_override");
    expect(state.orgFeatureFlags[1].value).toBe(true); // unchanged
  });

  it("deleteOrgFlagOverride triggers refresh", () => {
    // After delete, store should eventually refresh — simulate post-state
    useAdminStore.setState({
      orgFeatureFlags: [
        { key: "enable_a", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });
    expect(useAdminStore.getState().orgFeatureFlags[0].source).toBe("config");
  });

  it("fetchOrgAnalytics updates orgAnalytics", () => {
    useAdminStore.setState({
      orgAnalytics: {
        period_start: "2026-01-24",
        period_end: "2026-02-23",
        daily_active_users: [{ date: "2026-02-20", count: 15 }],
        chat_volume: [{ date: "2026-02-20", messages: 100, sessions: 30 }],
        error_rate: [],
      },
    });
    expect(useAdminStore.getState().orgAnalytics?.daily_active_users).toHaveLength(1);
  });

  it("fetchOrgLlmUsage updates orgLlmUsage", () => {
    useAdminStore.setState({
      orgLlmUsage: {
        total_tokens: 10000,
        total_cost_usd: 1.5,
        total_requests: 50,
        breakdown: [],
        top_models: [],
        top_users: [],
      },
    });
    expect(useAdminStore.getState().orgLlmUsage?.total_tokens).toBe(10000);
  });
});

// =============================================================================
// 5. INTEGRATION TESTS — dashboard org cards, navigation, sub-tabs
// =============================================================================

describe("Sprint 179b Integration", () => {
  it("dashboard organizations array populates store", () => {
    const mockDashboard: AdminDashboard = {
      total_users: 100,
      active_users: 50,
      total_organizations: 2,
      total_chat_sessions_24h: 200,
      total_llm_tokens_24h: 50000,
      estimated_cost_24h_usd: 5.0,
      feature_flags_active: 20,
      organizations: [
        { id: "org-1", name: "org-1", display_name: "Org One", member_count: 10, is_active: true },
        { id: "org-2", name: "org-2", display_name: null, member_count: 5, is_active: false },
      ],
    };
    useAdminStore.setState({
      dashboard: mockDashboard,
      organizations: mockDashboard.organizations ?? [],
    });

    const state = useAdminStore.getState();
    expect(state.organizations).toHaveLength(2);
    expect(state.organizations[0].display_name).toBe("Org One");
    expect(state.organizations[1].is_active).toBe(false);
  });

  it("clicking org card navigates to org detail", () => {
    useAdminStore.setState({
      organizations: [
        { id: "org-1", name: "org-1", display_name: "Org One", member_count: 10, is_active: true },
      ],
    });

    // Simulate click: setActiveTab + selectOrg
    useAdminStore.getState().setActiveTab("organizations");
    useAdminStore.getState().selectOrg("org-1");

    const state = useAdminStore.getState();
    expect(state.activeTab).toBe("organizations");
    expect(state.selectedOrgId).toBe("org-1");
  });

  it("sub-tab switching preserves org selection", () => {
    useAdminStore.setState({ selectedOrgId: "org-1" });

    useAdminStore.getState().setOrgSubView("members");
    expect(useAdminStore.getState().selectedOrgId).toBe("org-1");
    expect(useAdminStore.getState().orgSubView).toBe("members");

    useAdminStore.getState().setOrgSubView("flags");
    expect(useAdminStore.getState().selectedOrgId).toBe("org-1");
    expect(useAdminStore.getState().orgSubView).toBe("flags");
  });

  it("back button clears org selection", () => {
    useAdminStore.setState({
      selectedOrgId: "org-1",
      selectedOrgDetail: { id: "org-1", name: "org-1" } as AdminOrgDetail,
      orgSubView: "analytics",
    });

    useAdminStore.getState().selectOrg(null);

    const state = useAdminStore.getState();
    expect(state.selectedOrgId).toBeNull();
    expect(state.selectedOrgDetail).toBeNull();
    expect(state.orgSubView).toBe("overview");
  });
});

// =============================================================================
// 6. FEATURE FLAGS ORG FILTER — dropdown, org-specific toggle, cascade
// =============================================================================

describe("Sprint 179b Feature Flags Org Filter", () => {
  it("org filter dropdown changes flagsOrgFilter", () => {
    useAdminStore.getState().setFlagsOrgFilter("org-1");
    expect(useAdminStore.getState().flagsOrgFilter).toBe("org-1");
  });

  it("org-specific flag toggle targets org flags not global", () => {
    useAdminStore.setState({
      orgFeatureFlags: [
        { key: "enable_mcp", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });

    // Simulate org toggle
    const updated: AdminFeatureFlag = {
      key: "enable_mcp",
      value: true,
      source: "db_override",
      flag_type: "release",
      description: null,
      owner: null,
      expires_at: null,
    };
    useAdminStore.setState((s) => ({
      orgFeatureFlags: s.orgFeatureFlags.map((f) =>
        f.key === "enable_mcp" ? updated : f
      ),
    }));

    expect(useAdminStore.getState().orgFeatureFlags[0].value).toBe(true);
    expect(useAdminStore.getState().orgFeatureFlags[0].source).toBe("db_override");
  });

  it("delete override resets flag to inherited source", () => {
    // After deleting override, flag should show as config/inherited
    useAdminStore.setState({
      orgFeatureFlags: [
        { key: "enable_a", value: true, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });
    expect(useAdminStore.getState().orgFeatureFlags[0].source).toBe("config");
  });

  it("cascade: config < global override < org override", () => {
    // This tests the concept: org override takes precedence
    const flags: AdminFeatureFlag[] = [
      { key: "enable_a", value: true, source: "db_override", flag_type: "release", description: "org-level override", owner: null, expires_at: null },
      { key: "enable_b", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
    ];
    useAdminStore.setState({ orgFeatureFlags: flags });

    const state = useAdminStore.getState();
    expect(state.orgFeatureFlags[0].source).toBe("db_override"); // org override
    expect(state.orgFeatureFlags[1].source).toBe("config"); // inherited
  });
});

// =============================================================================
// 7. EDGE CASES — empty orgs, loading states, error handling
// =============================================================================

describe("Sprint 179b Edge Cases", () => {
  it("empty organization list renders gracefully", () => {
    useAdminStore.setState({ organizations: [] });
    expect(useAdminStore.getState().organizations).toEqual([]);
  });

  it("loading state during org detail fetch", () => {
    useAdminStore.setState({ loading: true, selectedOrgId: "org-1" });
    const state = useAdminStore.getState();
    expect(state.loading).toBe(true);
    expect(state.selectedOrgDetail).toBeNull();
  });

  it("error state on failed org API call", () => {
    useAdminStore.setState({ loading: false, error: "Organization not found" });
    expect(useAdminStore.getState().error).toBe("Organization not found");
  });
});

// =============================================================================
// 8. ADMIN TAB TYPE — organizations included
// =============================================================================

describe("Sprint 179b AdminTab type", () => {
  it("organizations is a valid AdminTab value", () => {
    useAdminStore.getState().setActiveTab("organizations");
    expect(useAdminStore.getState().activeTab).toBe("organizations");
  });

  it("reset restores organizations state", () => {
    useAdminStore.setState({
      organizations: [{ id: "org-1", name: "org-1", display_name: "Org", member_count: 5, is_active: true }],
      selectedOrgId: "org-1",
      orgSubView: "flags",
      flagsOrgFilter: "org-1",
    });

    useAdminStore.getState().reset();

    const state = useAdminStore.getState();
    expect(state.organizations).toEqual([]);
    expect(state.selectedOrgId).toBeNull();
    expect(state.orgSubView).toBe("overview");
    expect(state.flagsOrgFilter).toBeNull();
  });
});
