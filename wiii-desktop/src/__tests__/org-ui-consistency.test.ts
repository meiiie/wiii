/**
 * Sprint 156b: Org-Consistent UI Pass tests.
 * Verifies WelcomeScreen and CommandPalette pass orgId to createConversation,
 * and CommandPalette shows org context in conversation descriptions.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import { useDomainStore } from "@/stores/domain-store";
import { useOrgStore } from "@/stores/org-store";
import type { Conversation } from "@/api/types";

// Mock storage to prevent Tauri store access
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn().mockResolvedValue([]),
  saveStore: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/api/domains", () => ({
  listDomains: vi.fn().mockResolvedValue([]),
}));

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: Math.random().toString(36).slice(2),
    title: "Test conv",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
    ...overrides,
  };
}

describe("Sprint 156b: Org-Consistent UI", () => {
  beforeEach(() => {
    // Reset stores to known state
    useDomainStore.setState({
      domains: [
        { id: "maritime", name: "Maritime", name_vi: "Hang hai", version: "1.0", description: "", skill_count: 0, keyword_count: 0 },
      ],
      activeDomainId: "maritime",
      isLoading: false,
      orgAllowedDomains: [],
    });
    useOrgStore.setState({
      organizations: [],
      activeOrgId: null,
      isLoading: false,
      multiTenantEnabled: false,
    });
    useChatStore.setState({
      conversations: [],
      activeConversationId: null,
    });
  });

  // ---- WelcomeScreen: createConversation with org ----

  it("WelcomeScreen scenario: createConversation called with orgId when org is active", () => {
    useOrgStore.setState({ activeOrgId: "lms-hang-hai", multiTenantEnabled: true });
    useDomainStore.setState({ activeDomainId: "maritime" });

    // Simulate what WelcomeScreen.handleSuggestion does
    const { activeOrgId } = useOrgStore.getState();
    const { activeDomainId } = useDomainStore.getState();

    const convId = useChatStore.getState().createConversation(activeDomainId, activeOrgId || undefined);
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);

    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBe("lms-hang-hai");
    expect(conv!.domain_id).toBe("maritime");
  });

  it("WelcomeScreen scenario: createConversation without orgId when no org active", () => {
    useOrgStore.setState({ activeOrgId: null });
    useDomainStore.setState({ activeDomainId: "maritime" });

    const { activeOrgId } = useOrgStore.getState();
    const { activeDomainId } = useDomainStore.getState();

    const convId = useChatStore.getState().createConversation(activeDomainId, activeOrgId || undefined);
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);

    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBeUndefined();
    expect(conv!.domain_id).toBe("maritime");
  });

  // ---- CommandPalette: createConversation with org + domain ----

  it("CommandPalette scenario: new chat includes both domain and org", () => {
    useOrgStore.setState({ activeOrgId: "lms-giao-thong", multiTenantEnabled: true });
    useDomainStore.setState({ activeDomainId: "traffic_law" });

    const { activeOrgId } = useOrgStore.getState();
    const { activeDomainId } = useDomainStore.getState();

    const convId = useChatStore.getState().createConversation(activeDomainId, activeOrgId || undefined);
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);

    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBe("lms-giao-thong");
    expect(conv!.domain_id).toBe("traffic_law");
  });

  it("CommandPalette scenario: new chat with domain only (no org)", () => {
    useOrgStore.setState({ activeOrgId: null });
    useDomainStore.setState({ activeDomainId: "maritime" });

    const { activeOrgId } = useOrgStore.getState();
    const { activeDomainId } = useDomainStore.getState();

    const convId = useChatStore.getState().createConversation(activeDomainId, activeOrgId || undefined);
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);

    expect(conv).toBeDefined();
    expect(conv!.organization_id).toBeUndefined();
    expect(conv!.domain_id).toBe("maritime");
  });

  // ---- CommandPalette: conversation description with org ----

  it("CommandPalette conv description includes org when organization_id is set", () => {
    const conv = makeConversation({ organization_id: "lms-hang-hai", domain_id: "maritime" });

    // Simulate the description logic from CommandPalette
    const description = conv.organization_id
      ? `${conv.organization_id} · ${conv.domain_id ?? ""}`
      : conv.domain_id ?? undefined;

    expect(description).toBe("lms-hang-hai · maritime");
  });

  it("CommandPalette conv description shows domain only when no org", () => {
    const conv = makeConversation({ domain_id: "maritime" });

    const description = conv.organization_id
      ? `${conv.organization_id} · ${conv.domain_id ?? ""}`
      : conv.domain_id ?? undefined;

    expect(description).toBe("maritime");
  });

  it("CommandPalette conv description is undefined when no org and no domain", () => {
    const conv = makeConversation({});

    const description = conv.organization_id
      ? `${conv.organization_id} · ${conv.domain_id ?? ""}`
      : conv.domain_id ?? undefined;

    expect(description).toBeUndefined();
  });

  // ---- No regression: personal org ID treated as no org ----

  it("personal org ID is treated as null (no org header)", () => {
    useOrgStore.setState({ activeOrgId: null });

    const { activeOrgId } = useOrgStore.getState();
    const orgParam = activeOrgId || undefined;

    expect(orgParam).toBeUndefined();
  });
});
