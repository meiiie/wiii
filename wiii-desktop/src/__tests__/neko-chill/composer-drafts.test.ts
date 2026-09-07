import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearNekoComposerDraft,
  flushNekoComposerDrafts,
  readNekoComposerDraft,
  resetNekoComposerDraftCache,
  writeNekoComposerDraft,
} from "@/neko-chill/composer-drafts";

describe("Neko composer drafts", () => {
  const values = new Map<string, string>();
  const storage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => values.set(key, value)),
  };

  beforeEach(() => {
    vi.useFakeTimers();
    values.clear();
    storage.getItem.mockClear();
    storage.setItem.mockClear();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: storage,
    });
    resetNekoComposerDraftCache();
  });

  afterEach(() => {
    resetNekoComposerDraftCache();
    vi.useRealTimers();
  });

  it("coalesces rapid input into one durable write", () => {
    writeNekoComposerDraft("session:one", "hello");
    writeNekoComposerDraft("session:one", "hello Neko");

    expect(storage.setItem).not.toHaveBeenCalled();
    vi.advanceTimersByTime(299);
    expect(storage.setItem).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(storage.setItem).toHaveBeenCalledTimes(1);

    resetNekoComposerDraftCache();
    expect(readNekoComposerDraft("session:one")).toBe("hello Neko");
  });

  it("keeps drafts isolated and removes a sent draft immediately", () => {
    writeNekoComposerDraft("project:a", "task A");
    writeNekoComposerDraft("project:b", "task B");
    flushNekoComposerDrafts();

    expect(readNekoComposerDraft("project:a")).toBe("task A");
    expect(readNekoComposerDraft("project:b")).toBe("task B");

    clearNekoComposerDraft("project:a");
    resetNekoComposerDraftCache();
    expect(readNekoComposerDraft("project:a")).toBe("");
    expect(readNekoComposerDraft("project:b")).toBe("task B");
  });
});
