import { StrictMode, Suspense } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({
  start: vi.fn(() => vi.fn()),
  dispose: vi.fn(async () => {}),
  loadService: undefined as (() => void) | undefined,
  loadWork: undefined as (() => void) | undefined,
}));
vi.mock("@/neko-chill/stores/neko-session-store", () => ({
  startIdleReaper: runtime.start,
  disposeAllNekoRuntimes: runtime.dispose,
  useNekoSessionStore: { getState: () => ({ sessions: {} }) },
}));
vi.mock("@/neko-chill/stores/neko-outbox-store", () => ({
  startNekoOutbox: () => () => {},
}));
vi.mock("@/neko-chill/NekoChillApp", async () => {
  const { NekoRuntimeScope } = await import("@/neko-chill/NekoRuntimeScope");
  return { default: ({ active, onOpenConnections, onOpenWork }: { active: boolean; onOpenConnections: () => void; onOpenWork: () => void }) => (
    <NekoRuntimeScope>
      <button onClick={onOpenConnections}>{active ? "Local ready" : "Local hidden"}</button>
      <button onClick={onOpenWork}>Open Work</button>
    </NekoRuntimeScope>
  ) };
});
vi.mock("@/ade/WiiiAdeApp", async () => {
  await new Promise<void>((resolve) => { runtime.loadWork = resolve; });
  const { NekoRuntimeScope } = await import("@/neko-chill/NekoRuntimeScope");
  return { default: ({ onOpenConnections }: { onOpenConnections: () => void }) => (
    <NekoRuntimeScope><button onClick={onOpenConnections}>Work ready</button></NekoRuntimeScope>
  ) };
});
vi.mock("@/workbench/WiiiServiceSurface", async () => {
  await new Promise<void>((resolve) => { runtime.loadService = resolve; });
  return { WiiiServiceSurface: ({ onBack }: { onBack: () => void }) => (
    <button onClick={onBack}>Back from Service</button>
  ) };
});
import { LocalWorkbenchSurface } from "@/App";

it("keeps runtime ownership while a first Connections visit loads and returns", async () => {
  const view = render(<StrictMode><Suspense fallback={<p>Loading screen</p>}>
    <LocalWorkbenchSurface />
  </Suspense></StrictMode>);
  const local = await screen.findByRole("button", { name: "Local ready" });
  // Lazy content can become visible before StrictMode's effect replay finishes.
  // Establish the runtime owner before comparing navigation cleanup counts.
  await waitFor(() => expect(runtime.start).toHaveBeenCalledTimes(2));
  const initialDisposals = runtime.dispose.mock.calls.length;
  fireEvent.click(local);
  await screen.findByText(/Loading screen|Wiii đang mở/);
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals);
  await act(async () => { runtime.loadService?.(); });
  fireEvent.click(await screen.findByRole("button", { name: "Back from Service" }));
  expect(await screen.findByRole("button", { name: "Local ready" })).toBe(local);
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals);
  view.unmount();
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals + 1);
});

it("keeps existing runtimes while Work first loads and through a Work Connections detour", async () => {
  const view = render(<StrictMode><Suspense fallback={<p>Loading screen</p>}>
    <LocalWorkbenchSurface />
  </Suspense></StrictMode>);
  await screen.findByRole("button", { name: "Local ready" });
  const initialDisposals = runtime.dispose.mock.calls.length;
  fireEvent.click(screen.getByRole("button", { name: "Open Work" }));
  await screen.findByText(/Loading screen|Wiii đang mở Công việc/);
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals);
  await act(async () => { runtime.loadWork?.(); });
  const work = await screen.findByRole("button", { name: "Work ready" });
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals);
  fireEvent.click(work);
  fireEvent.click(await screen.findByRole("button", { name: "Back from Service" }));
  expect(await screen.findByRole("button", { name: "Work ready" })).toBe(work);
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals);
  view.unmount();
  expect(runtime.dispose).toHaveBeenCalledTimes(initialDisposals + 1);
});
