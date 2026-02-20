/**
 * Organization store — multi-tenant workspace management.
 * Sprint 156: Org-first UI restructuring.
 *
 * Detects multi-tenant support by calling the organizations API.
 * On 404 → single-tenant mode (personal workspace only).
 * On success → multi-tenant mode with org switching.
 */
import { create } from "zustand";
import type { OrganizationSummary } from "@/api/types";
import { listOrganizations } from "@/api/organizations";
import { PERSONAL_ORG_ID } from "@/lib/constants";

/** Synthesized personal workspace when multi-tenant is disabled. */
const PERSONAL_ORG: OrganizationSummary = {
  id: PERSONAL_ORG_ID,
  name: "Wiii Cá nhân",
  display_name: "Wiii Cá nhân",
  allowed_domains: [],
  is_active: true,
};

interface OrgState {
  organizations: OrganizationSummary[];
  activeOrgId: string | null; // null = personal
  isLoading: boolean;
  multiTenantEnabled: boolean;

  // Actions
  fetchOrganizations: () => Promise<void>;
  setActiveOrg: (id: string | null) => void;

  // Computed helpers
  activeOrg: () => OrganizationSummary | null;
  activeOrgDomains: () => string[]; // [] = all domains allowed
}

export const useOrgStore = create<OrgState>((set, get) => ({
  organizations: [],
  activeOrgId: null,
  isLoading: false,
  multiTenantEnabled: false,

  fetchOrganizations: async () => {
    set({ isLoading: true });
    try {
      const orgs = await listOrganizations();
      const activeOrgs = orgs.filter((o) => o.is_active);
      set({
        organizations: activeOrgs,
        multiTenantEnabled: true,
        isLoading: false,
      });
    } catch (err) {
      // 404 = multi-tenant not enabled on backend → personal mode
      const isNotFound =
        err instanceof Error && err.message.includes("404");
      if (isNotFound) {
        set({
          organizations: [PERSONAL_ORG],
          multiTenantEnabled: false,
          activeOrgId: null,
          isLoading: false,
        });
      } else {
        // Network error or other failure — graceful fallback
        console.warn("[OrgStore] Failed to fetch organizations:", err);
        set({
          organizations: [PERSONAL_ORG],
          multiTenantEnabled: false,
          activeOrgId: null,
          isLoading: false,
        });
      }
    }
  },

  setActiveOrg: (id) => {
    set({ activeOrgId: id === PERSONAL_ORG_ID ? null : id });
  },

  activeOrg: () => {
    const { organizations, activeOrgId } = get();
    if (!activeOrgId) {
      return organizations.find((o) => o.id === PERSONAL_ORG_ID) || null;
    }
    return organizations.find((o) => o.id === activeOrgId) || null;
  },

  activeOrgDomains: () => {
    const org = get().activeOrg();
    return org?.allowed_domains ?? [];
  },
}));
