import { describe, it, expect, vi } from "vitest";
import { DurableOutbox, emptyOutbox, parseOutbox, type OutboxBinding, type OutboxSnapshot } from "@/neko-chill/durable-outbox";
const binding: OutboxBinding = { sessionId: "one", workspace: "/qa/one", task: "task-one", model: "fixture" };
function harness(initial: OutboxSnapshot = emptyOutbox()) {
  let saved = structuredClone(initial);
  const write = vi.fn(async (value: OutboxSnapshot) => { saved = structuredClone(value); });
  const box = new DurableOutbox({ read: async () => saved, write }, vi.fn());
  return { box, write, saved: () => saved };
}
describe("durable per-session outbox", () => {
  it("persists enqueue before reporting it accepted, then dispatches FIFO", async () => {
    const { box, saved } = harness(); await box.hydrate();
    await box.enqueue(binding, "first", "a"); await box.enqueue(binding, "second", "b");
    expect(saved().queues[0].items.map(i => i.text)).toEqual(["first", "second"]);
    const send = vi.fn(async (_text: string, accepted: () => void) => { expect(saved().queues[0].items[0].state).toBe("delivering"); accepted(); return true; });
    await box.dispatch("one", () => binding, () => true, send);
    await box.dispatch("one", () => binding, () => true, send);
    expect(send.mock.calls.map(c => c[0])).toEqual(["first", "second"]);
    expect(box.snapshot.queues[0].items).toEqual([]);
  });
  it("retains the caller draft when saving an enqueue fails", async () => {
    const { box, write } = harness(); await box.hydrate(); write.mockRejectedValueOnce(new Error("disk full"));
    await expect(box.enqueue(binding, "draft", "a")).rejects.toThrow("disk full");
    expect(box.snapshot.queues).toEqual([]);
  });
  it("does not dispatch when the delivery durability barrier fails", async () => {
    const { box, write } = harness(); await box.hydrate(); await box.enqueue(binding, "draft", "a");
    write.mockRejectedValueOnce(new Error("disk full")); const send = vi.fn();
    await box.dispatch("one", () => binding, () => true, send);
    expect(send).not.toHaveBeenCalled(); expect(box.error).toContain("disk full");
  });
  it("halts when the model or target root differs", async () => {
    const { box } = harness(); await box.hydrate(); await box.enqueue(binding, "draft", "a");
    const send = vi.fn(); await box.dispatch("one", () => ({ ...binding, workspace: "/other" }), () => true, send);
    expect(send).not.toHaveBeenCalled(); expect(box.snapshot.queues[0].paused).toBe(true);
  });
  it("does not replay an uncertain invocation after restart", async () => {
    const { box, saved } = harness(); await box.hydrate(); await box.enqueue(binding, "draft", "a");
    await box.dispatch("one", () => binding, () => true, async (_, accepted) => { accepted(); return false; });
    const recovered = harness(saved()).box; await recovered.hydrate(); const send = vi.fn();
    await recovered.dispatch("one", () => binding, () => true, send);
    expect(send).not.toHaveBeenCalled(); expect(recovered.snapshot.queues[0].items[0].state).toBe("uncertain");
    await expect(recovered.resume("one")).rejects.toThrow("chưa rõ");
  });
  it("holds ordinary queued intent after restart until explicit resume", async () => {
    const { box, saved } = harness(); await box.hydrate(); await box.enqueue(binding, "draft", "a");
    const recovered = harness(saved()).box; await recovered.hydrate(); const send = vi.fn(async (_, accepted) => { accepted(); return true; });
    await recovered.dispatch("one", () => binding, () => true, send); expect(send).not.toHaveBeenCalled();
    await recovered.resume("one"); await recovered.dispatch("one", () => binding, () => true, send); expect(send).toHaveBeenCalledOnce();
  });
  it("serializes edits and removal without silently sending removed text", async () => {
    const { box } = harness(); await box.hydrate(); await box.enqueue(binding, "old", "a");
    await box.edit("one", "a", "new"); expect(box.snapshot.queues[0].items[0].text).toBe("new");
    await box.remove("one", "a"); const send = vi.fn(); await box.dispatch("one", () => binding, () => true, send); expect(send).not.toHaveBeenCalled();
  });
  it("blocks duplicate concurrent delivery attempts", async () => {
    const { box } = harness(); await box.hydrate(); await box.enqueue(binding, "draft", "a");
    let finish!: () => void; const wait = new Promise<void>(r => { finish = r; });
    const send = vi.fn(async (_text: string, accepted: () => void) => { accepted(); await wait; return true; });
    const first = box.dispatch("one", () => binding, () => true, send);
    await vi.waitFor(() => expect(send).toHaveBeenCalledOnce());
    await box.dispatch("one", () => binding, () => true, send); finish(); await first;
    expect(send).toHaveBeenCalledOnce();
  });
  it("pause keeps later items from running even after current delivery completes", async () => {
    const { box } = harness(); await box.hydrate(); await box.enqueue(binding, "first", "a"); await box.enqueue(binding, "second", "b");
    const send = vi.fn(async (_text: string, accepted: () => void) => { accepted(); await box.pause("one", "User stopped"); return true; });
    await box.dispatch("one", () => binding, () => true, send); await box.dispatch("one", () => binding, () => true, send);
    expect(send).toHaveBeenCalledOnce(); expect(box.snapshot.queues[0].items[0].text).toBe("second");
  });
  it("marks a delivery interrupted by process death uncertain and holds it", async () => {
    const initial: OutboxSnapshot = { version: 1, queues: [{ sessionId: "one", paused: false, reason: null, items: [{ id: "a", text: "draft", binding, state: "delivering" }] }] };
    const { box, saved } = harness(initial); await box.hydrate();
    expect(saved().queues[0].paused).toBe(true); expect(saved().queues[0].items[0].state).toBe("uncertain");
    const send = vi.fn(); await box.dispatch("one", () => binding, () => true, send); expect(send).not.toHaveBeenCalled();
  });
  it("does not enqueue past its bounded capacity or accept blank text", async () => {
    const { box } = harness(); await box.hydrate();
    await expect(box.enqueue(binding, "   ", "bad")).rejects.toThrow();
    for (let n = 0; n < 100; n++) await box.enqueue(binding, `message ${n}`, `${n}`);
    await expect(box.enqueue(binding, "extra", "overflow")).rejects.toThrow("100");
    expect(box.snapshot.queues[0].items).toHaveLength(100);
  });
  it("rejects malformed snapshots rather than replacing user data with empty state", () => {
    expect(() => parseOutbox({ version: 2, queues: [] })).toThrow();
    expect(() => parseOutbox({ version: 1, queues: [{ sessionId: "one", paused: false, reason: null, items: [{ id: "a", text: "hi", state: "queued", binding: { ...binding, sessionId: "other" } }] }] })).toThrow();
  });
});
