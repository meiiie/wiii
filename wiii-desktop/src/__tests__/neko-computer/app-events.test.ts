import { describe, expect, it } from "vitest";

import {
  AppEventCoalescer,
  appEventSignalFrom,
  appEventSubscriptionFrom,
  type AppEventSignal,
} from "@/neko-computer/app-events";

function signal(overrides: Partial<AppEventSignal> = {}): AppEventSignal {
  return {
    eventId: "event-1",
    cursor: "cursor-1",
    appId: "wechat",
    resourceRef: "conversation:meimei",
    kind: "content_changed",
    observedAt: "2026-08-30T14:24:30.647Z",
    ...overrides,
  };
}

describe("app event contract", () => {
  it("accepts a bounded 12-hour subscription without account or message data", () => {
    const now = Date.parse("2026-08-30T14:00:00.000Z");
    const subscription = {
      subscriptionId: "job:wechat-15m",
      appIds: ["wechat"],
      resourceRefs: ["conversation:meimei", "conversation:file-transfer"],
      responseMode: "auto_reply",
      expiresAt: "2026-08-31T02:00:00.000Z",
      heartbeatMs: 60_000,
      maxActions: 100,
    };

    expect(appEventSubscriptionFrom(subscription, now)).toEqual(subscription);
    expect(appEventSubscriptionFrom({ ...subscription, prompt: "read every message" }, now)).toBeNull();
    expect(appEventSubscriptionFrom({ ...subscription, expiresAt: "2026-09-01T15:00:00.000Z" }, now)).toBeNull();
  });

  it("accepts only bounded content-free wake fields", () => {
    expect(appEventSignalFrom(signal())).toEqual(signal());
    expect(appEventSignalFrom({ ...signal(), messageText: "private" })).toBeNull();
    expect(appEventSignalFrom({ ...signal(), kind: "raw_callback" })).toBeNull();
    expect(appEventSignalFrom({ ...signal(), resourceRef: "x".repeat(201) })).toBeNull();
  });

  it("coalesces an event storm into one resource wake after the quiet window", () => {
    const coalescer = new AppEventCoalescer(350);
    coalescer.push(signal(), 1_000);
    coalescer.push(signal({ eventId: "event-2", cursor: "cursor-2" }), 1_120);
    coalescer.push(signal({ eventId: "event-3", cursor: "cursor-3" }), 1_240);

    expect(coalescer.drainReady(1_589)).toEqual([]);
    expect(coalescer.drainReady(1_590)).toEqual([
      expect.objectContaining({
        eventId: "event-3",
        cursor: "cursor-3",
        firstObservedAt: "2026-08-30T14:24:30.647Z",
        coalescedCount: 3,
      }),
    ]);
  });

  it("keeps independent conversations separate and ignores replayed events", () => {
    const coalescer = new AppEventCoalescer(100);
    expect(coalescer.push(signal(), 1_000)).toBe(true);
    expect(coalescer.push(signal(), 1_050)).toBe(true);
    expect(coalescer.push(signal({
      eventId: "event-2",
      resourceRef: "conversation:file-transfer",
    }), 1_060)).toBe(true);

    expect(coalescer.drainReady(1_200)).toEqual([
      expect.objectContaining({ resourceRef: "conversation:meimei", coalescedCount: 1 }),
      expect.objectContaining({ resourceRef: "conversation:file-transfer", coalescedCount: 1 }),
    ]);
  });

  it("applies bounded backpressure instead of growing without limit", () => {
    const coalescer = new AppEventCoalescer(100, 1);
    expect(coalescer.push(signal(), 1_000)).toBe(true);
    expect(coalescer.push(signal({
      eventId: "event-2",
      resourceRef: "conversation:file-transfer",
    }), 1_010)).toBe(false);
    expect(coalescer.pendingCount).toBe(1);
    expect(coalescer.droppedSignals).toBe(1);
  });
});
