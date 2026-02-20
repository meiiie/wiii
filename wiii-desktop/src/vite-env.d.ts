/// <reference types="vite/client" />

/** Stub for optional tauri-plugin-oauth (only available in Tauri builds) */
declare module "@fabianlars/tauri-plugin-oauth" {
  export function start(options?: { ports?: number[] }): Promise<number>;
  export function onUrl(callback: (url: string) => void): void;
  export function cancel(port: number): Promise<void>;
}
