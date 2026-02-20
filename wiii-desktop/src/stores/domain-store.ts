/**
 * Domain store — available domains, active domain.
 */
import { create } from "zustand";
import type { DomainSummary } from "@/api/types";
import { listDomains } from "@/api/domains";
import { DEFAULT_DOMAIN } from "@/lib/constants";

interface DomainState {
  domains: DomainSummary[];
  activeDomainId: string;
  isLoading: boolean;
  /** Sprint 156: Org-restricted domains. Empty = all allowed. */
  orgAllowedDomains: string[];

  // Actions
  fetchDomains: () => Promise<void>;
  setActiveDomain: (id: string) => void;
  /** Sprint 156: Set org filter for domain visibility. */
  setOrgFilter: (allowedDomains: string[]) => void;
  /** Sprint 156: Get domains filtered by org restrictions. */
  getFilteredDomains: () => DomainSummary[];
}

export const useDomainStore = create<DomainState>((set, get) => ({
  domains: [],
  activeDomainId: DEFAULT_DOMAIN,
  isLoading: false,
  orgAllowedDomains: [],

  fetchDomains: async () => {
    set({ isLoading: true });
    try {
      const domains = await listDomains();
      set({ domains, isLoading: false });
    } catch (err) {
      console.warn("[Domains] Failed to fetch:", err);
      set({ isLoading: false });
    }
  },

  setActiveDomain: (id) => {
    set({ activeDomainId: id });
  },

  setOrgFilter: (allowedDomains) => {
    set({ orgAllowedDomains: allowedDomains });
    // Auto-select first allowed domain if current is not in the filter
    const { activeDomainId, domains } = get();
    if (allowedDomains.length > 0 && !allowedDomains.includes(activeDomainId)) {
      const firstAllowed = domains.find((d) => allowedDomains.includes(d.id));
      if (firstAllowed) {
        set({ activeDomainId: firstAllowed.id });
      } else if (allowedDomains[0]) {
        set({ activeDomainId: allowedDomains[0] });
      }
    }
  },

  getFilteredDomains: () => {
    const { domains, orgAllowedDomains } = get();
    if (orgAllowedDomains.length === 0) return domains;
    return domains.filter((d) => orgAllowedDomains.includes(d.id));
  },
}));
