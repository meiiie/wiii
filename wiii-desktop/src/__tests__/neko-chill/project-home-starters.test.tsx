import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectHome } from "@/neko-chill/components/ProjectHome";
import { clearNekoComposerDraft, readNekoComposerDraft } from "@/neko-chill/composer-drafts";
import { NEKO_STARTER_PROMPTS } from "@/neko-chill/starter-prompts";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";

vi.mock("@/neko/control-client", () => ({
  getNekoControlClient: () => ({
    listProfiles: vi.fn(async () => []),
    listProviders: vi.fn(async () => []),
  }),
}));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => false }));

const project = {
  id: "starters-test",
  name: "Wiii",
  roots: [{ name: "workspace", path: "C:/test/project" }],
  preferredHarnessId: "neko",
  createdAt: 1,
  updatedAt: 1,
};

beforeEach(() => {
  clearNekoComposerDraft(`project:${project.id}`);
  useNekoAgentStore.setState({ agents: [], isLoading: false, error: null });
  useNekoProjectStore.setState({ projects: [project], setPreferredHarness: vi.fn(async () => {}) });
  useNekoSessionStore.setState({ createSession: vi.fn(async () => "created"), sendPrompt: vi.fn(async () => {}) });
});

describe("Project Home empty-state starters", () => {
  it("shows session-empty starter CTAs and inserts into the draft", () => {
    render(<ProjectHome project={project} resetToken={0} />);
    const rail = screen.getByTestId("project-home-starters");
    expect(rail.getAttribute("aria-label")).toBe("Gợi ý bắt đầu");

    for (const starter of NEKO_STARTER_PROMPTS) {
      expect(screen.getByRole("button", { name: `Chèn gợi ý ${starter.label}` })).toBeTruthy();
    }

    fireEvent.click(screen.getByRole("button", { name: `Chèn gợi ý ${NEKO_STARTER_PROMPTS[0].label}` }));
    const input = screen.getByTestId("project-home-input") as HTMLTextAreaElement;
    expect(input.value).toBe(NEKO_STARTER_PROMPTS[0].prompt);
    expect(readNekoComposerDraft(`project:${project.id}`)).toBe(NEKO_STARTER_PROMPTS[0].prompt);
  });

  it("hides starters during taskLaunch (task title owns the composer)", () => {
    render(
      <ProjectHome
        project={project}
        resetToken={0}
        taskLaunch={{
          execution: { taskId: "t", runId: "r", environmentId: "e" },
          workspace: project.roots[0],
          title: "Task fixture",
        }}
      />,
    );
    expect(screen.queryByTestId("project-home-starters")).toBeNull();
  });
});
