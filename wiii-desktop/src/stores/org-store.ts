/**
 * Organization store — multi-tenant workspace management.
 * Sprint 156: Org-first UI restructuring.
 * Sprint 161: "Không Gian Riêng" — org settings, branding, permissions.
 *
 * Detects multi-tenant support by calling the organizations API.
 * On 404 → single-tenant mode (personal workspace only).
 * On success → multi-tenant mode with org switching + branding.
 */
import { create } from "zustand";
import type { OrganizationSummary, OrgSettings } from "@/api/types";
import { listOrganizations, getOrgSettings, getOrgPermissions } from "@/api/organizations";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import { applyOrgBranding, resetBranding, DEFAULT_BRANDING } from "@/lib/org-branding";

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

  // Sprint 161: Org settings + permissions
  orgSettings: OrgSettings | null;
  permissions: string[];

  // Actions
  fetchOrganizations: () => Promise<void>;
  setActiveOrg: (id: string | null) => void;
  fetchOrgSettings: (orgId: string) => Promise<void>;

  // Computed helpers
  activeOrg: () => OrganizationSummary | null;
  activeOrgDomains: () => string[]; // [] = all domains allowed
  hasPermission: (action: string, resource: string) => boolean;
  chatbotName: () => string;
  welcomeMessage: () => string;
}

export const useOrgStore = create<OrgState>((set, get) => ({
  organizations: [],
  activeOrgId: null,
  isLoading: false,
  multiTenantEnabled: false,
  orgSettings: null,
  permissions: [],

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
    const orgId = id === PERSONAL_ORG_ID ? null : id;
    set({ activeOrgId: orgId });

    // Sprint 161: Fetch settings + apply branding on org switch
    if (orgId) {
      get().fetchOrgSettings(orgId);
    } else {
      // Personal workspace — reset to platform defaults
      set({ orgSettings: null, permissions: [] });
      resetBranding();
    }
  },

  fetchOrgSettings: async (orgId: string) => {
    try {
      const [settings, permsResp] = await Promise.allSettled([
        getOrgSettings(orgId),
        getOrgPermissions(orgId),
      ]);

      const orgSettings =
        settings.status === "fulfilled" ? settings.value : null;
      const permissions =
        permsResp.status === "fulfilled" ? permsResp.value.permissions : [];

      set({ orgSettings, permissions });

      // Apply branding to CSS custom properties
      if (orgSettings?.branding) {
        applyOrgBranding(orgSettings.branding);
      } else {
        resetBranding();
      }
    } catch (err) {
      console.warn("[OrgStore] Failed to fetch org settings:", err);
      set({ orgSettings: null, permissions: [] });
      resetBranding();
    }
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

  hasPermission: (action: string, resource: string) => {
    const { permissions, multiTenantEnabled } = get();
    // When multi-tenant disabled, all permissions granted
    if (!multiTenantEnabled) return true;
    // When no permissions loaded yet, allow basic access
    if (permissions.length === 0) return true;
    return permissions.includes(`${action}:${resource}`);
  },

  chatbotName: () => {
    return get().orgSettings?.branding?.chatbot_name ?? DEFAULT_BRANDING.chatbot_name;
  },

  welcomeMessage: () => {
    return get().orgSettings?.branding?.welcome_message ?? DEFAULT_BRANDING.welcome_message;
  },
}));
