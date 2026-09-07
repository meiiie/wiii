import { beforeEach, describe, expect, it, vi } from "vitest";

const storage = vi.hoisted(() => new Map<string, unknown>());

vi.mock("@/lib/storage", () => ({
  loadStoreStrict: vi.fn(async (store: string, key: string, dflt: unknown) =>
    storage.get(`${store}:${key}`) ?? dflt),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    storage.set(`${store}:${key}`, value);
  }),
  saveStoreStrict: vi.fn(async (store: string, key: string, value: unknown) => {
    storage.set(`${store}:${key}`, value);
  }),
}));

import {
  projectForSession,
  useNekoProjectStore,
  workspaceKey,
  type NekoProject,
} from "@/neko-chill/stores/neko-project-store";

function project(id: string, name: string, path: string): NekoProject {
  return {
    id,
    name,
    roots: [{ path, name }],
    preferredHarnessId: null,
    createdAt: 1,
    updatedAt: 1,
  };
}

describe("Neko Project registry", () => {
  beforeEach(() => {
    storage.clear();
    useNekoProjectStore.setState({
      projects: [],
      hydrated: true,
      hydrating: false,
      error: null,
    });
  });

  it("prepends a newly created Project and persists that explicit order", async () => {
    useNekoProjectStore.setState({
      projects: [project("older", "Older", "E:/work/older")],
    });

    const id = await useNekoProjectStore.getState().createProject(
      "Newest",
      [{ path: "E:/work/newest", name: "newest" }],
    );

    expect(useNekoProjectStore.getState().projects.map((item) => item.id)).toEqual([
      id,
      "older",
    ]);
    expect(storage.get("neko-chill-projects.json:projects")).toMatchObject({
      projects: [{ id }, { id: "older" }],
    });
  });

  it("treats equivalent Windows workspace spellings as the same identity", async () => {
    expect(workspaceKey("E:\\work\\wiii\\.\\src\\..")).toBe(
      workspaceKey("e:/work/wiii/"),
    );

    await useNekoProjectStore.getState().createProject(
      "Wiii",
      [{ path: "E:\\work\\wiii", name: "wiii" }],
    );
    await expect(useNekoProjectStore.getState().createProject(
      "Duplicate",
      [{ path: "e:/work/wiii/.", name: "duplicate" }],
    )).rejects.toThrow("đã thuộc Project");
  });

  it("uses an explicit Project binding before legacy workspace inference", () => {
    const projects = [
      project("alpha", "Alpha", "E:/work/alpha"),
      project("beta", "Beta", "E:/work/beta"),
    ];

    expect(projectForSession(projects, {
      projectId: "beta",
      workspace: { path: "E:/work/alpha" },
    })?.id).toBe("beta");
    expect(projectForSession(projects, {
      projectId: null,
      workspace: { path: "e:\\work\\alpha\\." },
    })?.id).toBe("alpha");
  });
});
