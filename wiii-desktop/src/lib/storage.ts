/**
 * Wrapper around tauri-plugin-store for persistent local storage.
 * Falls back to localStorage when running in browser (dev without Tauri).
 */

let Store: any = null;

async function getStoreClass() {
  if (Store) return Store;
  try {
    const mod = await import("@tauri-apps/plugin-store");
    Store = mod.Store;
    return Store;
  } catch {
    return null;
  }
}

// In-memory fallback for browser dev mode
const memoryStore = new Map<string, Map<string, unknown>>();

function getMemoryStore(name: string): Map<string, unknown> {
  if (!memoryStore.has(name)) {
    // Try to hydrate from localStorage
    const map = new Map<string, unknown>();
    try {
      const raw = localStorage.getItem(`wiii:${name}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        for (const [k, v] of Object.entries(parsed)) {
          map.set(k, v);
        }
      }
    } catch {
      // ignore
    }
    memoryStore.set(name, map);
  }
  return memoryStore.get(name)!;
}

function persistMemoryStore(name: string) {
  const map = getMemoryStore(name);
  const obj: Record<string, unknown> = {};
  for (const [k, v] of map.entries()) {
    obj[k] = v;
  }
  try {
    localStorage.setItem(`wiii:${name}`, JSON.stringify(obj));
  } catch {
    // localStorage full or unavailable
  }
}

export async function loadStore<T>(
  storeName: string,
  key: string,
  defaultValue: T
): Promise<T> {
  const StoreClass = await getStoreClass();

  if (StoreClass) {
    try {
      const store = await StoreClass.load(storeName);
      const value = (await store.get(key)) as T | undefined;
      return value ?? defaultValue;
    } catch (err) {
      console.warn(`[storage] Failed to load ${storeName}/${key}:`, err);
      return defaultValue;
    }
  }

  // Fallback: memory + localStorage
  const map = getMemoryStore(storeName);
  return (map.get(key) as T) ?? defaultValue;
}

export async function saveStore<T>(
  storeName: string,
  key: string,
  value: T
): Promise<void> {
  const StoreClass = await getStoreClass();

  if (StoreClass) {
    try {
      const store = await StoreClass.load(storeName);
      await store.set(key, value);
      await store.save();
      return;
    } catch (err) {
      console.warn(`[storage] Failed to save ${storeName}/${key}:`, err);
    }
  }

  // Fallback
  const map = getMemoryStore(storeName);
  map.set(key, value);
  persistMemoryStore(storeName);
}

export async function deleteStore(
  storeName: string,
  key: string
): Promise<void> {
  const StoreClass = await getStoreClass();

  if (StoreClass) {
    try {
      const store = await StoreClass.load(storeName);
      await store.delete(key);
      await store.save();
      return;
    } catch (err) {
      console.warn(`[storage] Failed to delete ${storeName}/${key}:`, err);
    }
  }

  const map = getMemoryStore(storeName);
  map.delete(key);
  persistMemoryStore(storeName);
}

export async function clearStore(storeName: string): Promise<void> {
  const StoreClass = await getStoreClass();

  if (StoreClass) {
    try {
      const store = await StoreClass.load(storeName);
      await store.clear();
      await store.save();
      return;
    } catch (err) {
      console.warn(`[storage] Failed to clear ${storeName}:`, err);
    }
  }

  memoryStore.delete(storeName);
  try {
    localStorage.removeItem(`wiii:${storeName}`);
  } catch {
    // ignore
  }
}
