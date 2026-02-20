/**
 * Sprint 156: Organization store tests.
 * Tests multi-tenant detection, org switching, domain filtering.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useOrgStore } from "@/stores/org-store";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import type { OrganizationSummary } from "@/api/types";

// Mock the organizations API
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn(),
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
