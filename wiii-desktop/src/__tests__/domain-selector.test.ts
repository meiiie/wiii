/**
 * Unit tests for DomainSelector store integration.
 * Sprint 82: Domain switching via inline selector.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useDomainStore } from "@/stores/domain-store";

describe("DomainSelector store integration", () => {
  beforeEach(() => {
    // Reset domain store
    useDomainStore.setState({
      domains: [],
      activeDomainId: "maritime",
      isLoading: false,
    });
  });

  it("defaults to maritime domain", () => {
    const state = useDomainStore.getState();
    expect(state.activeDomainId).toBe("maritime");
  });

  it("switches domain via setActiveDomain", () => {
    useDomainStore.getState().setActiveDomain("traffic_law");
    expect(useDomainStore.getState().activeDomainId).toBe("traffic_law");
  });

  it("switches back to maritime", () => {
    useDomainStore.getState().setActiveDomain("traffic_law");
    useDomainStore.getState().setActiveDomain("maritime");
    expect(useDomainStore.getState().activeDomainId).toBe("maritime");
  });

  it("handles unknown domain id gracefully", () => {
    useDomainStore.getState().setActiveDomain("unknown_domain");
    expect(useDomainStore.getState().activeDomainId).toBe("unknown_domain");
  });

  it("uses fetched domains list when available", () => {
    useDomainStore.setState({
      domains: [
        {
          id: "maritime",
          name: "Maritime",
          name_vi: "Hàng hải",
          version: "1.0",
          description: "Maritime domain",
          skill_count: 5,
          keyword_count: 10,
        },
        {
          id: "traffic_law",
          name: "Traffic Law",
          name_vi: "Luật giao thông",
          version: "1.0",
          description: "Traffic law domain",
          skill_count: 3,
          keyword_count: 8,
        },
      ],
    });
    const state = useDomainStore.getState();
    expect(state.domains).toHaveLength(2);
    expect(state.domains[0].name_vi).toBe("Hàng hải");
  });
});
