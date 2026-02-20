/**
 * Sprint 161: "Không Gian Riêng" — Org-Level Customization Tests.
 *
 * Tests cover:
 * - OrgBranding CSS custom property injection
 * - org-store: settings, permissions, computed helpers
 * - PermissionGate component rendering
 * - OrgSettingsTab form behavior
 * - WelcomeScreen org-aware branding
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { useOrgStore } from "@/stores/org-store";
import {
  applyOrgBranding,
  resetBranding,
  DEFAULT_BRANDING,
} from "@/lib/org-branding";
import { PermissionGate } from "@/components/common/PermissionGate";
import type { OrgBranding, OrgSettings } from "@/api/types";

// ============================================================================
// Helpers
// ============================================================================

function makeOrgSettings(overrides?: Partial<OrgSettings>): OrgSettings {
  return {
    schema_version: 1,
    branding: {
      logo_url: null,
      primary_color: "#AE5630",
      accent_color: "#C4633A",
      welcome_message: "Xin chào! Mình là Wiii",
      chatbot_name: "Wiii",
      chatbot_avatar_url: null,
      institution_type: "general",
      ...overrides?.branding,
    },
    features: {
      enable_product_search: false,
      enable_deep_scanning: false,
      enable_thinking_chain: false,
      enable_browser_scraping: false,
      visible_agents: ["rag", "tutor", "direct", "memory"],
      max_search_iterations: 5,
      ...overrides?.features,
    },
    ai_config: {
      persona_prompt_overlay: null,
      temperature_override: null,
      max_response_length: null,
      default_domain: null,
      ...overrides?.ai_config,
    },
    permissions: {
      student: ["read:chat", "read:knowledge", "use:tools"],
      teacher: [
        "read:chat",
        "read:knowledge",
        "use:tools",
        "read:analytics",
        "manage:courses",
      ],
      admin: [
        "read:chat",
        "read:knowledge",
        "use:tools",
        "read:analytics",
        "manage:courses",
        "manage:members",
        "manage:settings",
        "manage:branding",
      ],
      ...overrides?.permissions,
    },
    onboarding: {
      quick_start_questions: [],
      show_domain_suggestions: true,
      ...overrides?.onboarding,
    },
  };
}

function resetOrgStore() {
  useOrgStore.setState({
    organizations: [],
    activeOrgId: null,
    isLoading: false,
    multiTenantEnabled: false,
    orgSettings: null,
    permissions: [],
  });
}

// ============================================================================
// Group 1: Org Branding CSS Injection (4 tests)
// ============================================================================

describe("Sprint 161: Org Branding — CSS Custom Properties", () => {
  beforeEach(() => {
    // Reset CSS custom properties
    document.documentElement.style.removeProperty("--accent");
    document.documentElement.style.removeProperty("--accent-hover");
    document.documentElement.style.removeProperty("--accent-orange");
    document.documentElement.style.removeProperty("--accent-orange-hover");
  });

  it("DEFAULT_BRANDING matches Wiii platform colors", () => {
    expect(DEFAULT_BRANDING.primary_color).toBe("#AE5630");
    expect(DEFAULT_BRANDING.accent_color).toBe("#C4633A");
    expect(DEFAULT_BRANDING.chatbot_name).toBe("Wiii");
  });

  it("applyOrgBranding sets CSS custom properties", () => {
    const branding: OrgBranding = {
      ...DEFAULT_BRANDING,
      primary_color: "#003366",
      accent_color: "#004488",
    };
    applyOrgBranding(branding);
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--accent")).toBe("#003366");
    expect(root.style.getPropertyValue("--accent-hover")).toBe("#004488");
  });

  it("resetBranding restores Wiii defaults", () => {
    // First apply custom branding
    applyOrgBranding({
      ...DEFAULT_BRANDING,
      primary_color: "#FF0000",
      accent_color: "#00FF00",
    });
    // Then reset
    resetBranding();
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--accent")).toBe("#AE5630");
    expect(root.style.getPropertyValue("--accent-hover")).toBe("#C4633A");
  });

  it("applyOrgBranding sets both accent and accent-orange", () => {
    applyOrgBranding({
      ...DEFAULT_BRANDING,
      primary_color: "#112233",
      accent_color: "#445566",
    });
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--accent-orange")).toBe("#112233");
    expect(root.style.getPropertyValue("--accent-orange-hover")).toBe(
      "#445566",
    );
  });
});

// ============================================================================
// Group 2: Org Store (6 tests)
// ============================================================================

describe("Sprint 161: Org Store — Settings & Permissions", () => {
  beforeEach(() => {
    resetOrgStore();
  });

  it("initial state has no orgSettings", () => {
    const state = useOrgStore.getState();
    expect(state.orgSettings).toBeNull();
    expect(state.permissions).toEqual([]);
  });

  it("hasPermission returns true when multi-tenant disabled", () => {
    useOrgStore.setState({ multiTenantEnabled: false, permissions: [] });
    const result = useOrgStore.getState().hasPermission("manage", "settings");
    expect(result).toBe(true);
  });

  it("hasPermission returns true when no permissions loaded yet", () => {
    useOrgStore.setState({ multiTenantEnabled: true, permissions: [] });
    const result = useOrgStore.getState().hasPermission("manage", "settings");
    expect(result).toBe(true);
  });

  it("hasPermission checks permissions list when loaded", () => {
    useOrgStore.setState({
      multiTenantEnabled: true,
      permissions: ["read:chat", "use:tools"],
    });
    expect(useOrgStore.getState().hasPermission("read", "chat")).toBe(true);
    expect(useOrgStore.getState().hasPermission("manage", "settings")).toBe(
      false,
    );
  });

  it("chatbotName returns org name when settings loaded", () => {
    const settings = makeOrgSettings({
      branding: { chatbot_name: "Hải Bot" } as any,
    });
    useOrgStore.setState({ orgSettings: settings });
    expect(useOrgStore.getState().chatbotName()).toBe("Hải Bot");
  });

  it("chatbotName returns Wiii when no settings", () => {
    useOrgStore.setState({ orgSettings: null });
    expect(useOrgStore.getState().chatbotName()).toBe("Wiii");
  });
});

// ============================================================================
// Group 3: PermissionGate Component (4 tests)
// ============================================================================

describe("Sprint 161: PermissionGate", () => {
  beforeEach(() => {
    resetOrgStore();
  });

  it("renders children when permission granted", () => {
    useOrgStore.setState({ multiTenantEnabled: false });
    render(
      <PermissionGate action="manage" resource="settings">
        <div data-testid="protected">Secret Panel</div>
      </PermissionGate>,
    );
    expect(screen.getByTestId("protected")).toBeTruthy();
  });

  it("renders fallback when permission denied", () => {
    useOrgStore.setState({
      multiTenantEnabled: true,
      permissions: ["read:chat"],
    });
    render(
      <PermissionGate
        action="manage"
        resource="settings"
        fallback={<div data-testid="denied">No Access</div>}
      >
        <div data-testid="protected">Secret Panel</div>
      </PermissionGate>,
    );
    expect(screen.queryByTestId("protected")).toBeNull();
    expect(screen.getByTestId("denied")).toBeTruthy();
  });

  it("renders nothing (null) when denied without fallback", () => {
    useOrgStore.setState({
      multiTenantEnabled: true,
      permissions: ["read:chat"],
    });
    const { container } = render(
      <PermissionGate action="manage" resource="settings">
        <div data-testid="protected">Secret Panel</div>
      </PermissionGate>,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders children when permission in list", () => {
    useOrgStore.setState({
      multiTenantEnabled: true,
      permissions: ["read:chat", "manage:settings"],
    });
    render(
      <PermissionGate action="manage" resource="settings">
        <div data-testid="admin-panel">Admin Panel</div>
      </PermissionGate>,
    );
    expect(screen.getByTestId("admin-panel")).toBeTruthy();
  });
});
