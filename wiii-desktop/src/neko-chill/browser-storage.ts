type BrowserStorage = Pick<Storage, "getItem" | "setItem">;

const memoryStorage = new Map<string, string>();

export function resolveBrowserStorage(): BrowserStorage | null {
  try {
    if (typeof window === "undefined") return null;
    const candidate = window.localStorage as Partial<BrowserStorage> | undefined;
    if (typeof candidate?.getItem !== "function" || typeof candidate.setItem !== "function") {
      return null;
    }
    return candidate as BrowserStorage;
  } catch {
    return null;
  }
}

export const nekoLayoutStorage: BrowserStorage & Pick<Storage, "removeItem"> = {
  getItem(key) {
    const persistent = resolveBrowserStorage();
    if (persistent) {
      try {
        const value = persistent.getItem(key);
        if (value !== null) memoryStorage.set(key, value);
        return value;
      } catch {
      }
    }
    return memoryStorage.get(key) ?? null;
  },
  setItem(key, value) {
    memoryStorage.set(key, value);
    const persistent = resolveBrowserStorage();
    if (!persistent) return;
    try {
      persistent.setItem(key, value);
    } catch {
    }
  },
  removeItem(key) {
    memoryStorage.delete(key);
    try {
      window.localStorage.removeItem(key);
    } catch {
    }
  },
};
