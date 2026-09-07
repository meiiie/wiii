import { resolveBrowserStorage } from "./browser-storage";

const STORAGE_KEY = "wiii:neko-composer-drafts:v1";
const SAVE_DELAY_MS = 300;
const MAX_DRAFTS = 32;
const MAX_DRAFT_LENGTH = 64_000;

interface DraftRecord {
  text: string;
  updatedAt: number;
}

interface DraftSnapshot {
  version: 1;
  drafts: Record<string, DraftRecord>;
}

let snapshot: DraftSnapshot | null = null;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

function storage(): Storage | null {
  return resolveBrowserStorage() as Storage | null;
}

function emptySnapshot(): DraftSnapshot {
  return { version: 1, drafts: {} };
}

function readSnapshot(): DraftSnapshot {
  if (snapshot) return snapshot;
  const target = storage();
  if (!target) return (snapshot = emptySnapshot());
  try {
    const parsed = JSON.parse(target.getItem(STORAGE_KEY) ?? "null") as Partial<DraftSnapshot> | null;
    if (!parsed || parsed.version !== 1 || !parsed.drafts || typeof parsed.drafts !== "object") {
      return (snapshot = emptySnapshot());
    }
    const drafts = Object.fromEntries(
      Object.entries(parsed.drafts)
        .filter((entry): entry is [string, DraftRecord] => {
          const value = entry[1];
          return Boolean(
            value
            && typeof value === "object"
            && typeof value.text === "string"
            && typeof value.updatedAt === "number",
          );
        })
        .sort((left, right) => right[1].updatedAt - left[1].updatedAt)
        .slice(0, MAX_DRAFTS),
    );
    return (snapshot = { version: 1, drafts });
  } catch {
    return (snapshot = emptySnapshot());
  }
}

export function flushNekoComposerDrafts(): void {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  const target = storage();
  if (!target || !snapshot) return;
  try {
    target.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
  }
}

function scheduleSave(): void {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(flushNekoComposerDrafts, SAVE_DELAY_MS);
}

export function readNekoComposerDraft(scope: string): string {
  return readSnapshot().drafts[scope]?.text ?? "";
}

export function writeNekoComposerDraft(scope: string, text: string): void {
  const state = readSnapshot();
  if (!text) {
    delete state.drafts[scope];
  } else if (text.length <= MAX_DRAFT_LENGTH) {
    state.drafts[scope] = { text, updatedAt: Date.now() };
  } else {
    delete state.drafts[scope];
  }

  const staleScopes = Object.entries(state.drafts)
    .sort((left, right) => right[1].updatedAt - left[1].updatedAt)
    .slice(MAX_DRAFTS)
    .map(([key]) => key);
  for (const key of staleScopes) delete state.drafts[key];
  scheduleSave();
}

export function clearNekoComposerDraft(scope: string): void {
  const state = readSnapshot();
  if (!(scope in state.drafts)) return;
  delete state.drafts[scope];
  flushNekoComposerDrafts();
}

export function resetNekoComposerDraftCache(): void {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = null;
  snapshot = null;
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", flushNekoComposerDrafts);
}
