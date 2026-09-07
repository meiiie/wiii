import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";
import { useNekoProviderSessionStore } from "@/neko-chill/stores/neko-provider-session-store";

const { listProviderSessions } = vi.hoisted(() => ({
  listProviderSessions: vi.fn(),
}));

vi.mock("@/neko/control-client", () => ({
  getNekoControlClient: () => ({ listProviderSessions }),
}));

const agents: DetectedAgent[] = [
  {
    id: "codex",
    name: "Codex",
    version: "0.149.0",
    found: true,
    availability: "available",
    supportsProfiles: false,
  },
  {
    id: "gemini",
    name: "Gemini CLI",
    version: "0.38.1",
    found: true,
    availability: "available",
    supportsProfiles: false,
  },
];

describe("Neko provider session discovery", () => {
  beforeEach(() => {
    listProviderSessions.mockReset();
    listProviderSessions.mockImplementation(async ({ providerId }: { providerId: string }) => ({
      providerId,
      scope: providerId === "gemini" ? "known_projects" : "all",
      complete: true,
      detail: null,
      sessions: [],
    }));
    useNekoProviderSessionStore.setState({ catalogs: {}, loading: false, error: null });
  });

  it("keeps Gemini's project-scoped scan explicit while discovering global catalogs at startup", async () => {
    await useNekoProviderSessionStore.getState().refresh(agents, ["E:\\Projects\\wiii"]);

    expect(listProviderSessions).toHaveBeenCalledTimes(1);
    expect(listProviderSessions).toHaveBeenCalledWith({
      providerId: "codex",
      workspacePaths: ["E:\\Projects\\wiii"],
    });
    expect(useNekoProviderSessionStore.getState().catalogs.gemini).toMatchObject({
      scope: "known_projects",
      complete: false,
      sessions: [],
    });

    await useNekoProviderSessionStore.getState().refresh(
      agents,
      ["E:\\Projects\\wiii"],
      { includeProjectScoped: true },
    );

    expect(listProviderSessions).toHaveBeenCalledTimes(3);
    expect(listProviderSessions).toHaveBeenLastCalledWith({
      providerId: "gemini",
      workspacePaths: ["E:\\Projects\\wiii"],
    });
  });
});
