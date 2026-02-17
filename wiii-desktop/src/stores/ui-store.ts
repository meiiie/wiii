/**
 * UI store — sidebar, modals, theme state (not persisted).
 * Sprint 81: Added commandPaletteOpen state.
 */
import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  settingsOpen: boolean;
  sourcesPanelOpen: boolean;
  selectedSourceIndex: number | null;
  commandPaletteOpen: boolean;
  inputFocused: boolean;
  characterPanelOpen: boolean;

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

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  openSettings: () => set({ settingsOpen: true, commandPaletteOpen: false }),
  closeSettings: () => set({ settingsOpen: false }),
  toggleSourcesPanel: () =>
    set((s) => ({ sourcesPanelOpen: !s.sourcesPanelOpen })),
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
  closeAll: () =>
    set({ settingsOpen: false, commandPaletteOpen: false, sourcesPanelOpen: false, characterPanelOpen: false }),
}));
