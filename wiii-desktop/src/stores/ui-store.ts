/**
 * UI store — sidebar, modals, theme state (not persisted).
 * Sprint 81: Added commandPaletteOpen state.
 */
import { create } from "zustand";
import type { ArtifactData } from "@/api/types";

interface UIState {
  sidebarOpen: boolean;
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
  closeAll: () => void;
}

export const useUIStore = create<UIState>((set) => ({
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

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  openSettings: () => set({ settingsOpen: true, commandPaletteOpen: false }),
  closeSettings: () => set({ settingsOpen: false }),
  toggleSourcesPanel: () =>
    set((s) => ({ sourcesPanelOpen: !s.sourcesPanelOpen, previewPanelOpen: false })),
  selectSource: (index) => set({ selectedSourceIndex: index }),
  openCommandPalette: () => set({ commandPaletteOpen: true, settingsOpen: false }),
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
  closeAll: () =>
    set({ settingsOpen: false, commandPaletteOpen: false, sourcesPanelOpen: false, characterPanelOpen: false, previewPanelOpen: false, selectedPreviewId: null, artifactPanelOpen: false, selectedArtifactId: null, _ephemeralArtifact: null }),
}));
