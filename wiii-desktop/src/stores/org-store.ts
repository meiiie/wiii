/**
 * Organization store — multi-tenant workspace management.
 * Sprint 156: Org-first UI restructuring.
 * Sprint 161: "Không Gian Riêng" — org settings, branding, permissions.
 * Sprint 175: "Một Nền Tảng — Nhiều Tổ Chức" — subdomain auto-detection.
 *
 * Detects multi-tenant support by calling the organizations API.
 * On 404 → single-tenant mode (personal workspace only).
 * On success → multi-tenant mode with org switching + branding.
 *
 * Web deployment: When accessed via subdomain (e.g. phuong-luu-kiem.holilihu.online),
 * the org is auto-detected from the hostname — no org selector needed.
 */
import { create } from "zustand";
import type { OrganizationSummary, OrgSettings, AdminContext } from "@/api/types";
import { listOrganizations, getOrgSettings, getOrgPermissions } from "@/api/organizations";
import { getAdminContext } from "@/api/admin";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import { applyOrgBranding, resetBranding, DEFAULT_BRANDING } from "@/lib/org-branding";

// Sprint 175: Base domain for subdomain org detection (matches backend config)
const SUBDOMAIN_BASE_DOMAIN = "holilihu.online";
const RESERVED_SUBDOMAINS = new Set(["www", "api", "admin", "app", "mail", "static", "cdn"]);

/**
 * Detect org slug from current hostname subdomain.
 * Example: 'phuong-luu-kiem.holilihu.online' → 'phuong-luu-kiem'
 * Returns null in Tauri (no subdomain), localhost, or bare domain.
 */
export function detectOrgFromSubdomain(): string | null {
  // Skip in Tauri desktop — no subdomain concept
  if ("__TAURI_INTERNALS__" in window) return null;

  const hostname = window.location.hostname.toLowerCase();
  const suffix = `.${SUBDOMAIN_BASE_DOMAIN}`;

  if (!hostname.endsWith(suffix)) return null;

  const subdomain = hostname.slice(0, -suffix.length);
  if (!subdomain || RESERVED_SUBDOMAINS.has(subdomain)) return null;

  return subdomain;
}

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

  // Sprint 175: Subdomain-detected org (null when in Tauri or no subdomain)
  subdomainOrgId: string | null;

  // Sprint 161: Org settings + permissions
  orgSettings: OrgSettings | null;
  permissions: string[];

  // Sprint 181: Admin context — two-tier admin
  adminContext: AdminContext | null;

  // Actions
  fetchOrganizations: () => Promise<void>;
  setActiveOrg: (id: string | null) => void;
  fetchOrgSettings: (orgId: string) => Promise<void>;
  detectSubdomainOrg: () => void;
  fetchAdminContext: () => Promise<void>;

  // Computed helpers
  activeOrg: () => OrganizationSummary | null;
  activeOrgDomains: () => string[]; // [] = all domains allowed
  hasPermission: (action: string, resource: string) => boolean;
  chatbotName: () => string;
  welcomeMessage: () => string;
  isSubdomainMode: () => boolean;
  isSystemAdmin: () => boolean;
  isOrgAdmin: (orgId?: string) => boolean;
}

export const useOrgStore = create<OrgState>((set, get) => ({
  organizations: [],
  activeOrgId: null,
  isLoading: false,
  multiTenantEnabled: false,
  subdomainOrgId: null,
  orgSettings: null,
  permissions: [],
  adminContext: null,

  detectSubdomainOrg: () => {
    const orgSlug = detectOrgFromSubdomain();
    if (orgSlug) {
      set({ subdomainOrgId: orgSlug, activeOrgId: orgSlug });
      // Immediately fetch settings + branding for the subdomain org
      get().fetchOrgSettings(orgSlug);
    }
  },

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

    // Sprint 194b (H2): Only allow switching to orgs user is a member of.
    // fetchOrganizations() only returns orgs the user belongs to, so checking
    // against that list is sufficient to validate membership.
    if (orgId) {
      const { organizations } = get();
      const isMember = organizations.some((o) => o.id === orgId);
      if (!isMember) {
        console.warn("[org-store] Attempted switch to unknown org:", orgId, "— ignored");
        return;
      }
    }

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

  isSubdomainMode: () => {
    return get().subdomainOrgId !== null;
  },

  // Sprint 181: Admin context
  fetchAdminContext: async () => {
    try {
      const ctx = await getAdminContext();
      set({ adminContext: ctx });
    } catch (err) {
      console.warn("[OrgStore] Failed to fetch admin context:", err);
      set({ adminContext: null });
    }
  },

  isSystemAdmin: () => {
    return get().adminContext?.is_system_admin ?? false;
  },

  isOrgAdmin: (orgId?: string) => {
    const ctx = get().adminContext;
    if (!ctx) return false;
    if (ctx.is_system_admin) return true;
    if (!ctx.enable_org_admin) return false;
    if (orgId) return ctx.admin_org_ids.includes(orgId);
    return ctx.admin_org_ids.length > 0;
  },
}));
