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

  // Actions
  fetchDomains: () => Promise<void>;
  setActiveDomain: (id: string) => void;
}

export const useDomainStore = create<DomainState>((set) => ({
  domains: [],
  activeDomainId: DEFAULT_DOMAIN,
  isLoading: false,

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
}));
