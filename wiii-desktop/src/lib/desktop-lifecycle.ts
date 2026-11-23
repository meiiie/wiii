import { invoke } from "@tauri-apps/api/core";

export function canQuitApp(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function quitApp(): Promise<void> {
  await invoke<void>("quit_app");
}
