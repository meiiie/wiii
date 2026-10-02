import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { writeFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { useNekoSessionCatalog } from "@/neko-chill/hooks/useNekoSessionCatalog";
import { NekoComposer } from "@/neko-chill/components/NekoComposer";
import { useNekoSessionStore, type NekoSession } from "@/neko-chill/stores/neko-session-store";
function percentile(values: number[], p: number) { return [...values].sort((a, b) => a - b)[Math.min(values.length - 1, Math.floor(values.length * p))]; }
function statistics(values: number[]) { return { n: values.length, median_ms: percentile(values, .5), p95_ms: percentile(values, .95), max_ms: Math.max(...values) }; }
describe("workflow responsiveness harness", () => {
  it("keeps the session catalog stable during token updates and accepts typing", () => {
    const original = useNekoSessionStore.getState();
    const base = { agentId: "neko", agentName: "Neko", title: "Synthetic session", status: "streaming", workspace: { name: "fixture", path: "/fixture" },
      controls: [], commands: [], messages: [], events: [], createdAt: 1, updatedAt: 1 } as unknown as NekoSession;
    const sessions = Object.fromEntries(Array.from({ length: 500 }, (_, n) => [`bench-${n}`, { ...base, id: `bench-${n}` }]));
    useNekoSessionStore.setState({ sessions, activeSessionId: "bench-0" });
    let catalogRenders = 0;
    const catalog = renderHook(() => { catalogRenders++; return useNekoSessionCatalog(); });
    const inputView = render(<NekoComposer session={sessions["bench-0"]} streaming disabled={false}
      onSend={vi.fn()} onCancel={vi.fn()} onSetConfigOption={vi.fn()} onClientCommand={vi.fn()} />);
    const input = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    const inputMs: number[] = []; const streamMs: number[] = []; const switchMs: number[] = [];
    const heapBefore = process.memoryUsage().heapUsed;
    const active = renderHook(() => useNekoSessionStore(s => s.activeSessionId));
    for (let n = 0; n < 100; n++) {
      let start = performance.now();
      act(() => { const state = useNekoSessionStore.getState(); const s = state.sessions["bench-0"];
        useNekoSessionStore.setState({ sessions: { ...state.sessions, "bench-0": { ...s, updatedAt: n + 2,
          messages: [{ id: "answer", role: "assistant", text: "x".repeat(n + 1) }] } } }); });
      streamMs.push(performance.now() - start);
      start = performance.now(); fireEvent.change(input, { target: { value: `draft ${n}` } }); inputMs.push(performance.now() - start);
      start = performance.now(); act(() => useNekoSessionStore.setState({ activeSessionId: `bench-${n + 1}` })); switchMs.push(performance.now() - start);
    }
    expect(catalogRenders).toBe(1); expect(input.value).toBe("draft 99"); expect(active.result.current).toBe("bench-100");
    if (process.env.WIII_BENCH_OUT) writeFileSync(process.env.WIII_BENCH_OUT, JSON.stringify({
      environment: `Node ${process.version}, Linux, jsdom; synthetic React/store timings, NOT native paint/INP or a leak test`,
      sessions: 500, token_updates: 100, catalog_renders: catalogRenders, input: statistics(inputMs), stream_store: statistics(streamMs),
      active_session_state: statistics(switchMs), heap_before_bytes: heapBefore, heap_after_bytes: process.memoryUsage().heapUsed,
    }, null, 2));
    inputView.unmount(); catalog.unmount(); active.unmount(); useNekoSessionStore.setState(original, true);
  });
});
