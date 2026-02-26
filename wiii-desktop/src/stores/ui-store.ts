/**
 * UI store — sidebar, modals, theme state (not persisted).
 * Sprint 81: Added commandPaletteOpen state.
 * Sprint 192: Added activeView for full-page admin/settings layout.
 */
import { create } from "zustand";
import type { ArtifactData } from "@/api/types";

/** Sprint 192: Main content view — chat or full-page admin/settings */
export type ActiveView = "chat" | "system-admin" | "org-admin" | "settings";

interface UIState {
  /** Sprint 192: Which view is displayed in the main content area */
  activeView: ActiveView;
  sidebarOpen: boolean;
  /** @deprecated Use activeView === "settings" — kept for backward compat */
  settingsOpen: boolean;
  sourcesPanelOpen: boolean;
  selectedSourceIndex: number | null;
  commandPaletteOpen: boolean;
  inputFocused: boolean;
  characterPanelOpen: boolean;
  /** Sprint 166: Preview panel */
  previewPanelOpen: boolean;
  selectedPreviewId: string | null;
  /** Sprint 167: Artifact panel */
  artifactPanelOpen: boolean;
  selectedArtifactId: string | null;
  artifactActiveTab: "code" | "preview" | "output";
  /** Sprint 168: Ad-hoc artifact from CodeBlock "Sandbox" button */
  _ephemeralArtifact: ArtifactData | null;
  /** @deprecated Use activeView === "system-admin" — kept for backward compat */
  adminPanelOpen: boolean;
  /** @deprecated Use activeView === "org-admin" — kept for backward compat */
  orgManagerPanelOpen: boolean;
  orgManagerTargetOrgId: string | null;

  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  openSettings: () => void;
  closeSettings: () => void;
  toggleSourcesPanel: () => void;
  selectSource: (index: number | null) => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleCommandPalette: () => void;
  setInputFocused: (focused: boolean) => void;
  toggleCharacterPanel: () => void;
  /** Sprint 166: Preview panel actions */
  openPreview: (id: string) => void;
  closePreview: () => void;
  togglePreviewPanel: () => void;
  /** Sprint 167: Artifact panel actions */
  openArtifact: (id: string, artifact?: ArtifactData) => void;
  closeArtifact: () => void;
  setArtifactTab: (tab: "code" | "preview" | "output") => void;
  /** Sprint 179: Admin panel */
  openAdminPanel: () => void;
  closeAdminPanel: () => void;
  /** Sprint 181: Org manager panel */
  openOrgManagerPanel: (orgId: string) => void;
  closeOrgManagerPanel: () => void;
  /** Sprint 192: Navigate back to chat from any view */
  navigateToChat: () => void;
  closeAll: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeView: "chat" as ActiveView,
  sidebarOpen: true,
  settingsOpen: false,
  sourcesPanelOpen: false,
  selectedSourceIndex: null,
  commandPaletteOpen: false,
  inputFocused: false,
  characterPanelOpen: false,
  previewPanelOpen: false,
  selectedPreviewId: null,
  artifactPanelOpen: false,
  selectedArtifactId: null,
  artifactActiveTab: "code" as const,
  _ephemeralArtifact: null,
  adminPanelOpen: false,
  orgManagerPanelOpen: false,
  orgManagerTargetOrgId: null,

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  // Sprint 192: openSettings now sets activeView + boolean compat
  openSettings: () => set({ activeView: "settings" as ActiveView, settingsOpen: true, adminPanelOpen: false, orgManagerPanelOpen: false, commandPaletteOpen: false }),
  closeSettings: () => set({ activeView: "chat" as ActiveView, settingsOpen: false }),
  toggleSourcesPanel: () =>
    set((s) => ({ sourcesPanelOpen: !s.sourcesPanelOpen, previewPanelOpen: false })),
  selectSource: (index) => set({ selectedSourceIndex: index }),
  openCommandPalette: () => set({ commandPaletteOpen: true }),
  closeCommandPalette: () => set({ commandPaletteOpen: false }),
  toggleCommandPalette: () =>
    set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),
  setInputFocused: (focused) => set({ inputFocused: focused }),
  toggleCharacterPanel: () =>
    set((s) => ({
      characterPanelOpen: !s.characterPanelOpen,
      sourcesPanelOpen: s.characterPanelOpen ? s.sourcesPanelOpen : false,
    })),
  // Sprint 166: Preview panel — mutual exclusion with sources panel
  openPreview: (id) => set({ previewPanelOpen: true, selectedPreviewId: id, sourcesPanelOpen: false, artifactPanelOpen: false }),
  closePreview: () => set({ previewPanelOpen: false, selectedPreviewId: null }),
  togglePreviewPanel: () =>
    set((s) => ({ previewPanelOpen: !s.previewPanelOpen, sourcesPanelOpen: s.previewPanelOpen ? s.sourcesPanelOpen : false })),
  // Sprint 167: Artifact panel — mutual exclusion with preview + sources
  // Sprint 168: Optional artifact param for ad-hoc artifacts from CodeBlock
  openArtifact: (id, artifact) => set({ artifactPanelOpen: true, selectedArtifactId: id, artifactActiveTab: "code" as const, previewPanelOpen: false, sourcesPanelOpen: false, _ephemeralArtifact: artifact || null }),
  closeArtifact: () => set({ artifactPanelOpen: false, selectedArtifactId: null, _ephemeralArtifact: null }),
  setArtifactTab: (tab) => set({ artifactActiveTab: tab }),
  // Sprint 192: Admin panel → full-page view
  openAdminPanel: () => set({ activeView: "system-admin" as ActiveView, adminPanelOpen: true, orgManagerPanelOpen: false, settingsOpen: false, commandPaletteOpen: false }),
  closeAdminPanel: () => set({ activeView: "chat" as ActiveView, adminPanelOpen: false }),
  // Sprint 192: Org manager panel → full-page view
  openOrgManagerPanel: (orgId) => set({ activeView: "org-admin" as ActiveView, orgManagerPanelOpen: true, orgManagerTargetOrgId: orgId, adminPanelOpen: false, settingsOpen: false, commandPaletteOpen: false }),
  closeOrgManagerPanel: () => set({ activeView: "chat" as ActiveView, orgManagerPanelOpen: false, orgManagerTargetOrgId: null }),
  // Sprint 192: Navigate back to chat from any view
  navigateToChat: () => set({ activeView: "chat" as ActiveView, settingsOpen: false, adminPanelOpen: false, orgManagerPanelOpen: false, orgManagerTargetOrgId: null }),
  closeAll: () =>
    set({ activeView: "chat" as ActiveView, settingsOpen: false, commandPaletteOpen: false, sourcesPanelOpen: false, characterPanelOpen: false, previewPanelOpen: false, selectedPreviewId: null, artifactPanelOpen: false, selectedArtifactId: null, _ephemeralArtifact: null, adminPanelOpen: false, orgManagerPanelOpen: false, orgManagerTargetOrgId: null }),
}));
