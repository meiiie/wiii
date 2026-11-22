import { beforeEach, describe, expect, it, vi } from "vitest";

const load = vi.hoisted(() => vi.fn());
vi.mock("@/neko/legacy-work-storage", async () => ({
  ...await vi.importActual<typeof import("@/neko/legacy-work-storage")>("@/neko/legacy-work-storage"),
  loadAdeWorkSnapshot: load,
}));

describe("legacy native-scope compatibility state", () => {
  beforeEach(() => { vi.resetModules(); load.mockReset(); });

  it("reads only on demand and shares one hydration between concurrent resume attempts", async () => {
    const { emptyAdeGraph } = await import("@/neko/legacy-work-storage");
    const graph = emptyAdeGraph();
    let resolve!: (value: { graph: typeof graph }) => void;
    load.mockReturnValue(new Promise((done) => { resolve = done; }));
    const { legacyWorkState } = await import("@/neko/legacy-work-state");
    expect(load).not.toHaveBeenCalled();
    const first = legacyWorkState.getState().hydrate();
    const second = legacyWorkState.getState().hydrate();
    expect(legacyWorkState.getState().hydrated).toBe(false);
    resolve({ graph });
    await Promise.all([first, second]);
    expect(legacyWorkState.getState()).toMatchObject({ hydrated: true, graph });
    await legacyWorkState.getState().hydrate();
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("does not mark invalid/unreadable legacy data as hydrated and permits an explicit retry", async () => {
    load.mockRejectedValueOnce(new Error("invalid legacy scope")).mockResolvedValueOnce(null);
    const { legacyWorkState } = await import("@/neko/legacy-work-state");
    await expect(legacyWorkState.getState().hydrate()).rejects.toThrow("invalid legacy scope");
    expect(legacyWorkState.getState().hydrated).toBe(false);
    await legacyWorkState.getState().hydrate();
    expect(legacyWorkState.getState().hydrated).toBe(true);
    expect(legacyWorkState.getState().graph.tasks).toEqual([]);
  });
});
