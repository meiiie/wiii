/**
 * Soul Bridge store — manages peer connections, events, and status.
 * Sprint 216: SoulBridgePanel state management.
 */
import { create } from "zustand";
import {
  getSoulBridgeStatus,
  getPeerDetail,
  type SoulBridgeStatus,
  type PeerDetail,
} from "@/api/soul-bridge";

interface SoulBridgeState {
  /** Bridge status from Wiii backend */
  bridgeStatus: SoulBridgeStatus | null;
  /** Detailed peer data keyed by peer_id */
  peerDetails: Record<string, PeerDetail>;
  /** Loading state */
  loading: boolean;
  /** Error message */
  error: string | null;
  /** Last fetch timestamp */
  lastFetched: number | null;
  /** Selected peer ID for detail view */
  selectedPeerId: string | null;

  // Actions
  fetchBridgeStatus: () => Promise<void>;
  fetchPeerDetail: (peerId: string) => Promise<void>;
  selectPeer: (peerId: string | null) => void;
  refreshAll: () => Promise<void>;
}

const INITIAL_STATE = {
  bridgeStatus: null,
  peerDetails: {},
  loading: false,
  error: null,
  lastFetched: null,
  selectedPeerId: null,
};

export const useSoulBridgeStore = create<SoulBridgeState>((set, get) => ({
  ...INITIAL_STATE,

  fetchBridgeStatus: async () => {
    set({ loading: true, error: null });
    try {
      const status = await getSoulBridgeStatus();
      set({ bridgeStatus: status, loading: false, lastFetched: Date.now() });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to fetch bridge status",
      });
    }
  },

  fetchPeerDetail: async (peerId: string) => {
    try {
      const detail = await getPeerDetail(peerId);
      set((s) => ({
        peerDetails: { ...s.peerDetails, [peerId]: detail },
      }));
    } catch (e) {
      console.warn(`[soul-bridge] Failed to fetch peer ${peerId}:`, e);
    }
  },

  selectPeer: (peerId) => set({ selectedPeerId: peerId }),

  refreshAll: async () => {
    const { fetchBridgeStatus, fetchPeerDetail } = get();
    await fetchBridgeStatus();
    const status = get().bridgeStatus;
    if (status?.peers) {
      await Promise.all(
        Object.keys(status.peers).map((id) => fetchPeerDetail(id))
      );
    }
  },
}));
