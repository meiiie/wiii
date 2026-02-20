/**
 * Sprint 156: Organization UI integration tests.
 * Tests auth headers, conversation creation, domain filtering, conversation grouping.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useSettingsStore } from "@/stores/settings-store";
import { useDomainStore } from "@/stores/domain-store";
import { useChatStore } from "@/stores/chat-store";
import { useOrgStore } from "@/stores/org-store";
import { groupConversations } from "@/lib/conversation-groups";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import type { OrganizationSummary, Conversation, DomainSummary } from "@/api/types";

// Mock API + storage
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn(),
}));
vi.mock("@/api/domains", () => ({
  listDomains: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn().mockResolvedValue([]),
  saveStore: vi.fn().mockResolvedValue(undefined),
}));

const MOCK_DOMAINS: DomainSummary[] = [
  { id: "maritime", name: "Maritime", name_vi: "Hang hai", version: "1.0", description: "", skill_count: 0, keyword_count: 0 },
  { id: "traffic_law", name: "Traffic Law", name_vi: "Luat giao thong", version: "1.0", description: "", skill_count: 0, keyword_count: 0 },
  { id: "general", name: "General", name_vi: "Chung", version: "1.0", description: "", skill_count: 0, keyword_count: 0 },
];

const MOCK_ORGS: OrganizationSummary[] = [
  {
    id: "lms-hang-hai",
    name: "LMS Hang Hai",
    display_name: "Truong DHHH VN",
    allowed_domains: ["maritime"],
    is_active: true,
  },
  {
    id: PERSONAL_ORG_ID,
    name: "Wiii Ca nhan",
    allowed_domains: [],
    is_active: true,
  },
];

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: Math.random().toString(36),
    title: "Test conv",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
    ...overrides,
  };
}

describe("Org UI Integration", () => {
  beforeEach(() => {
    // Reset stores
    useSettingsStore.setState({
      settings: {
        server_url: "http://localhost:8000",
        api_key: "test-key",
        user_id: "user1",
        user_role: "student",
        display_name: "Test",
        default_domain: "maritime",
        organization_id: null,
        theme: "system",
        language: "vi",
        font_size: "medium",
        show_thinking: true,
        show_reasoning_trace: false,
        streaming_version: "v3",
        thinking_level: "balanced",
      },
      isLoaded: true,
    });
    useDomainStore.setState({
      domains: MOCK_DOMAINS,
      activeDomainId: "maritime",
      isLoading: false,
      orgAllowedDomains: [],
    });
    useOrgStore.setState({
      organizations: MOCK_ORGS,
      activeOrgId: null,
      isLoading: false,
      multiTenantEnabled: true,
    });
  });

  // ---- Auth Headers ----

  it("includes X-Organization-ID in auth headers when org is set", () => {
    useSettingsStore.getState().updateSettings({ organization_id: "lms-hang-hai" });
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-Organization-ID"]).toBe("lms-hang-hai");
  });

  it("omits X-Organization-ID when org is null", () => {
    useSettingsStore.getState().updateSettings({ organization_id: null });
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-Organization-ID"]).toBeUndefined();
  });

  it("omits X-Organization-ID when org is 'personal'", () => {
    useSettingsStore.getState().updateSettings({ organization_id: "personal" });
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-Organization-ID"]).toBeUndefined();
  });

  // ---- Conversation Creation ----

  it("creates conversation with organization_id", () => {
    const convId = useChatStore.getState().createConversation("maritime", "lms-hang-hai");
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBe("lms-hang-hai");
  });

  it("creates conversation without org when not provided", () => {
    const convId = useChatStore.getState().createConversation("maritime");
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBeUndefined();
  });

  // ---- Conversation Filtering ----

  it("filters conversations by org in groupConversations", () => {
    const convs = [
      makeConversation({ organization_id: "lms-hang-hai", title: "HH conv" }),
      makeConversation({ organization_id: "other-org", title: "Other conv" }),
      makeConversation({ title: "No org conv" }),
    ];

    const groups = groupConversations(convs, undefined, "lms-hang-hai");
    const allConvs = groups.flatMap((g) => g.conversations);
    expect(allConvs).toHaveLength(1);
    expect(allConvs[0].title).toBe("HH conv");
  });

  it("shows legacy conversations (no org_id) in personal workspace", () => {
    const convs = [
      makeConversation({ organization_id: "lms-hang-hai", title: "HH conv" }),
      makeConversation({ title: "Legacy conv" }),
    ];

    const groups = groupConversations(convs, undefined, PERSONAL_ORG_ID);
    const allConvs = groups.flatMap((g) => g.conversations);
    expect(allConvs).toHaveLength(1);
    expect(allConvs[0].title).toBe("Legacy conv");
  });

  // ---- Domain Filtering ----

  it("filters domains by org allowed_domains", () => {
    useDomainStore.getState().setOrgFilter(["maritime"]);
    const filtered = useDomainStore.getState().getFilteredDomains();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("maritime");
  });

  it("shows all domains when allowed_domains is empty", () => {
    useDomainStore.getState().setOrgFilter([]);
    const filtered = useDomainStore.getState().getFilteredDomains();
    expect(filtered).toHaveLength(3); // all MOCK_DOMAINS
  });

  it("auto-selects first allowed domain when current is not in filter", () => {
    useDomainStore.setState({ activeDomainId: "general" });
    useDomainStore.getState().setOrgFilter(["maritime", "traffic_law"]);
    expect(useDomainStore.getState().activeDomainId).toBe("maritime");
  });

  it("keeps current domain if it is in the filter", () => {
    useDomainStore.setState({ activeDomainId: "maritime" });
    useDomainStore.getState().setOrgFilter(["maritime", "traffic_law"]);
    expect(useDomainStore.getState().activeDomainId).toBe("maritime");
  });

  // ---- Backward Compatibility ----

  it("works with null organization_id in saved settings", () => {
    useSettingsStore.setState({
      settings: {
        ...useSettingsStore.getState().settings,
        organization_id: null,
      },
    });
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-Organization-ID"]).toBeUndefined();
    expect(headers["X-User-ID"]).toBe("user1");
  });

  it("works with undefined organization_id in old settings", () => {
    const settings = { ...useSettingsStore.getState().settings };
    delete (settings as Record<string, unknown>).organization_id;
    useSettingsStore.setState({ settings });
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-Organization-ID"]).toBeUndefined();
  });
});
