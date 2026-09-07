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
