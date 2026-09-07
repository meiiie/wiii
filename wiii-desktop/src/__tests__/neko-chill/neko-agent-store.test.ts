import { beforeEach, expect, it, vi } from "vitest";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";

const { listProviders } = vi.hoisted(() => ({ listProviders: vi.fn() }));
vi.mock("@/neko/control-client", () => ({ getNekoControlClient: () => ({ listProviders }) }));

beforeEach(() => {
  listProviders.mockReset();
  useNekoAgentStore.setState({ agents: [], isLoading: false, error: null, probeStates: {} });
});

it("joins a duplicate probe and waits for the requested provider during another probe", async () => {
  const resolvers = new Map<string, (value: unknown) => void>();
  listProviders.mockImplementation((id: string) => new Promise((resolve) => resolvers.set(id, resolve)));
  const store = useNekoAgentStore.getState();
  const neko = store.detect("neko");
  const codex = store.detect("codex");
  const codexJoined = store.detect("codex");
  await vi.waitFor(() => expect(listProviders).toHaveBeenCalledTimes(2));
  resolvers.get("codex")!([{ id: "codex", found: true, availability: "available" }]);
  await Promise.all([codex, codexJoined]);
  expect(useNekoAgentStore.getState()).toMatchObject({
    agents: [{ id: "codex" }], isLoading: true, probeStates: { codex: "ready", neko: "checking" },
  });
  resolvers.get("neko")!([{ id: "neko", found: true, availability: "available" }]);
  await neko;
  expect(useNekoAgentStore.getState().agents.map((agent) => agent.id).sort()).toEqual(["codex", "neko"]);
  expect(useNekoAgentStore.getState().isLoading).toBe(false);
});

it("waits for a full scan instead of issuing an overlapping per-provider scan", async () => {
  let finish!: (value: unknown) => void;
  listProviders.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const all = useNekoAgentStore.getState().detect();
  const selected = useNekoAgentStore.getState().detect("neko");
  await vi.waitFor(() => expect(listProviders).toHaveBeenCalledOnce());
  finish([{ id: "neko", found: true, availability: "available" }]);
  await Promise.all([all, selected]);
  expect(useNekoAgentStore.getState().probeStates.neko).toBe("ready");
});

it("keeps cleanup-proven discovery failures on their provider while another provider becomes ready", async () => {
  listProviders.mockImplementation(async (id: string) => id === "codex"
    ? [{ id, found: false, availability: "probe_failed", discoveryError: "Probe exited; cleanup proven" }]
    : [{ id, found: true, availability: "available" }]);
  await Promise.all([useNekoAgentStore.getState().detect("codex"), useNekoAgentStore.getState().detect("neko")]);
  expect(useNekoAgentStore.getState().error).toBeNull();
  expect(useNekoAgentStore.getState().agents).toEqual(expect.arrayContaining([
    expect.objectContaining({ id: "codex", availability: "probe_failed" }),
    expect.objectContaining({ id: "neko", availability: "available" }),
  ]));
});

it("does not clear uncertain native cleanup when a concurrent provider succeeds", async () => {
  let succeed!: (value: unknown) => void;
  listProviders.mockImplementation((id: string) => id === "codex"
    ? Promise.reject(new Error("native cleanup unproven"))
    : new Promise((resolve) => { succeed = resolve; }));
  const unsafe = useNekoAgentStore.getState().detect("codex");
  const safe = useNekoAgentStore.getState().detect("neko");
  await unsafe;
  succeed([{ id: "neko", found: true, availability: "available" }]);
  await safe;
  expect(useNekoAgentStore.getState().error).toContain("native cleanup unproven");
});
