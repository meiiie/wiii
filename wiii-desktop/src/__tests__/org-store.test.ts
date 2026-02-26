/**
 * Sprint 156: Organization store tests.
 * Sprint 175: Subdomain auto-detection tests.
 * Tests multi-tenant detection, org switching, domain filtering, subdomain org.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useOrgStore, detectOrgFromSubdomain } from "@/stores/org-store";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import type { OrganizationSummary } from "@/api/types";

// Mock the organizations API
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn(),
  getOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured in test")),
  getOrgPermissions: vi.fn().mockRejectedValue(new Error("Not configured in test")),
}));

const { listOrganizations } = await import("@/api/organizations");
const mockListOrgs = vi.mocked(listOrganizations);

const MOCK_ORGS: OrganizationSummary[] = [
  {
    id: "lms-hang-hai",
    name: "LMS Hang Hai",
    display_name: "Truong DHHH VN",
    allowed_domains: ["maritime"],
    default_domain: "maritime",
    is_active: true,
  },
  {
    id: "lms-giao-thong",
    name: "LMS Giao Thong",
    display_name: "Truong GT",
    allowed_domains: ["traffic_law"],
    is_active: true,
  },
  {
    id: PERSONAL_ORG_ID,
    name: "Wiii Ca nhan",
    display_name: "Wiii Ca nhan",
    allowed_domains: [],
    is_active: true,
  },
];

function resetStore() {
  useOrgStore.setState({
    organizations: [],
    activeOrgId: null,
    isLoading: false,
    multiTenantEnabled: false,
    subdomainOrgId: null,
  });
}

describe("OrgStore", () => {
  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
  });

  it("has correct initial state", () => {
    const state = useOrgStore.getState();
    expect(state.organizations).toEqual([]);
    expect(state.activeOrgId).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.multiTenantEnabled).toBe(false);
  });

  it("fetches orgs successfully and enables multi-tenant", async () => {
    mockListOrgs.mockResolvedValue(MOCK_ORGS);

    await useOrgStore.getState().fetchOrganizations();

    const state = useOrgStore.getState();
    expect(state.organizations).toHaveLength(3);
    expect(state.multiTenantEnabled).toBe(true);
    expect(state.isLoading).toBe(false);
  });

  it("handles 404 — multi-tenant disabled", async () => {
    mockListOrgs.mockRejectedValue(new Error("HTTP 404: Not Found"));

    await useOrgStore.getState().fetchOrganizations();

    const state = useOrgStore.getState();
    expect(state.multiTenantEnabled).toBe(false);
    expect(state.organizations).toHaveLength(1);
    expect(state.organizations[0].id).toBe(PERSONAL_ORG_ID);
    expect(state.isLoading).toBe(false);
  });

  it("handles network error — graceful fallback", async () => {
    mockListOrgs.mockRejectedValue(new Error("Network error"));

    await useOrgStore.getState().fetchOrganizations();

    const state = useOrgStore.getState();
    expect(state.multiTenantEnabled).toBe(false);
    expect(state.organizations).toHaveLength(1);
    expect(state.organizations[0].id).toBe(PERSONAL_ORG_ID);
  });

  it("sets active org", () => {
    useOrgStore.setState({ organizations: MOCK_ORGS, multiTenantEnabled: true });

    useOrgStore.getState().setActiveOrg("lms-hang-hai");
    expect(useOrgStore.getState().activeOrgId).toBe("lms-hang-hai");
  });

  it("sets personal org via null when PERSONAL_ORG_ID passed", () => {
    useOrgStore.setState({ organizations: MOCK_ORGS, activeOrgId: "lms-hang-hai" });

    useOrgStore.getState().setActiveOrg(PERSONAL_ORG_ID);
    expect(useOrgStore.getState().activeOrgId).toBeNull();
  });

  it("activeOrg returns correct org object", () => {
    useOrgStore.setState({
      organizations: MOCK_ORGS,
      activeOrgId: "lms-hang-hai",
    });

    const org = useOrgStore.getState().activeOrg();
    expect(org).not.toBeNull();
    expect(org!.id).toBe("lms-hang-hai");
    expect(org!.display_name).toBe("Truong DHHH VN");
  });

  it("activeOrg returns personal org when activeOrgId is null", () => {
    useOrgStore.setState({
      organizations: MOCK_ORGS,
      activeOrgId: null,
    });

    const org = useOrgStore.getState().activeOrg();
    expect(org).not.toBeNull();
    expect(org!.id).toBe(PERSONAL_ORG_ID);
  });

  it("activeOrgDomains returns allowed_domains for active org", () => {
    useOrgStore.setState({
      organizations: MOCK_ORGS,
      activeOrgId: "lms-hang-hai",
    });

    const domains = useOrgStore.getState().activeOrgDomains();
    expect(domains).toEqual(["maritime"]);
  });

  it("activeOrgDomains returns empty for personal org (all allowed)", () => {
    useOrgStore.setState({
      organizations: MOCK_ORGS,
      activeOrgId: null,
    });

    const domains = useOrgStore.getState().activeOrgDomains();
    expect(domains).toEqual([]);
  });

  it("personal org fallback has correct structure", async () => {
    mockListOrgs.mockRejectedValue(new Error("HTTP 404: Not Found"));
    await useOrgStore.getState().fetchOrganizations();

    const personalOrg = useOrgStore.getState().organizations[0];
    expect(personalOrg.id).toBe(PERSONAL_ORG_ID);
    expect(personalOrg.name).toBe("Wiii Cá nhân");
    expect(personalOrg.allowed_domains).toEqual([]);
    expect(personalOrg.is_active).toBe(true);
  });

  it("switches between multiple orgs", () => {
    useOrgStore.setState({ organizations: MOCK_ORGS, multiTenantEnabled: true });

    useOrgStore.getState().setActiveOrg("lms-hang-hai");
    expect(useOrgStore.getState().activeOrgId).toBe("lms-hang-hai");

    useOrgStore.getState().setActiveOrg("lms-giao-thong");
    expect(useOrgStore.getState().activeOrgId).toBe("lms-giao-thong");

    useOrgStore.getState().setActiveOrg(null);
    expect(useOrgStore.getState().activeOrgId).toBeNull();
  });

  it("filters out inactive orgs on fetch", async () => {
    const orgsWithInactive = [
      ...MOCK_ORGS,
      { id: "inactive-org", name: "Inactive", allowed_domains: [], is_active: false },
    ];
    mockListOrgs.mockResolvedValue(orgsWithInactive);

    await useOrgStore.getState().fetchOrganizations();

    const state = useOrgStore.getState();
    expect(state.organizations).toHaveLength(3); // 4 - 1 inactive
    expect(state.organizations.find((o) => o.id === "inactive-org")).toBeUndefined();
  });
});


// =============================================================================
// Sprint 175: Subdomain Auto-Detection Tests
// =============================================================================

describe("detectOrgFromSubdomain", () => {
  it("returns null in Tauri environment", () => {
    // Simulate Tauri
    (window as any).__TAURI_INTERNALS__ = {};
    const result = detectOrgFromSubdomain();
    expect(result).toBeNull();
    delete (window as any).__TAURI_INTERNALS__;
  });

  it("returns null for localhost", () => {
    // jsdom default hostname is 'localhost' — no subdomain match
    const result = detectOrgFromSubdomain();
    expect(result).toBeNull();
  });

  it("returns org slug from subdomain", () => {
    // Override hostname for this test
    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "phuong-luu-kiem.holilihu.online" },
      writable: true,
    });

    const result = detectOrgFromSubdomain();
    expect(result).toBe("phuong-luu-kiem");

    // Restore
    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "localhost" },
      writable: true,
    });
  });

  it("returns null for reserved subdomains", () => {
    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "www.holilihu.online" },
      writable: true,
    });

    const result = detectOrgFromSubdomain();
    expect(result).toBeNull();

    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "localhost" },
      writable: true,
    });
  });

  it("returns null for bare domain", () => {
    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "holilihu.online" },
      writable: true,
    });

    const result = detectOrgFromSubdomain();
    expect(result).toBeNull();

    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "localhost" },
      writable: true,
    });
  });
});

describe("OrgStore subdomain mode", () => {
  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
  });

  it("has correct initial subdomain state", () => {
    const state = useOrgStore.getState();
    expect(state.subdomainOrgId).toBeNull();
    expect(state.isSubdomainMode()).toBe(false);
  });

  it("detectSubdomainOrg sets subdomainOrgId when subdomain found", () => {
    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "lms-hang-hai.holilihu.online" },
      writable: true,
    });

    useOrgStore.getState().detectSubdomainOrg();

    const state = useOrgStore.getState();
    expect(state.subdomainOrgId).toBe("lms-hang-hai");
    expect(state.activeOrgId).toBe("lms-hang-hai");
    expect(state.isSubdomainMode()).toBe(true);

    Object.defineProperty(window, "location", {
      value: { ...window.location, hostname: "localhost" },
      writable: true,
    });
  });

  it("detectSubdomainOrg does nothing for localhost", () => {
    useOrgStore.getState().detectSubdomainOrg();

    const state = useOrgStore.getState();
    expect(state.subdomainOrgId).toBeNull();
    expect(state.activeOrgId).toBeNull();
    expect(state.isSubdomainMode()).toBe(false);
  });
});
