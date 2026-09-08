import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectHome } from "@/neko-chill/components/ProjectHome";
import { HarnessSetupNotice } from "@/neko-chill/components/HarnessSetupNotice";
import { NekoOverview } from "@/neko-chill/components/NekoOverview";
import { clearNekoComposerDraft, readNekoComposerDraft, writeNekoComposerDraft } from "@/neko-chill/composer-drafts";
import { useNekoAgentStore, type DetectedAgent } from "@/neko-chill/stores/neko-agent-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";

const host = vi.hoisted(() => ({ profiles: vi.fn(), providers: vi.fn(), open: vi.fn(), native: false }));
vi.mock("@/neko/control-client", () => ({ getNekoControlClient: () => ({
  listProfiles: host.profiles, listProviders: host.providers,
}) }));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => host.native }));
vi.mock("@tauri-apps/plugin-shell", () => ({ open: host.open }));

const project = { id: "readiness-test", name: "Wiii", roots: [{ name: "workspace", path: "C:/test/project" }],
  preferredHarnessId: "neko", createdAt: 1, updatedAt: 1 };
const neko: DetectedAgent = { id: "neko", name: "Neko Core", found: true,
  availability: "available", version: "test", supportsProfiles: true };
const missing: DetectedAgent = { ...neko, found: false, availability: "not_installed", version: null };
const gemini: DetectedAgent = { id: "gemini", name: "Gemini CLI", found: true,
  availability: "available", version: "test", supportsProfiles: false };
const detect = useNekoAgentStore.getState().detect;
const manage = vi.fn();

function home(agents: DetectedAgent[], state = {}) {
  useNekoAgentStore.setState({ agents, ...state });
  render(<ProjectHome project={project} resetToken={0} onManageHarness={manage} />);
  const input = screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" });
  fireEvent.change(input, { target: { value: "Bản nháp cần được giữ" } });
  return input as HTMLTextAreaElement;
}

function sendButton() {
  return screen.getByRole("button", { name: "Gửi và mở phiên" }) as HTMLButtonElement;
}

beforeEach(() => {
  host.native = false;
  manage.mockReset();
  host.open.mockReset().mockResolvedValue(undefined);
  host.profiles.mockReset().mockResolvedValue([{ id: "local", provider: "local", model: "test", active: true }]);
  host.providers.mockReset().mockResolvedValue([neko]);
  clearNekoComposerDraft(`project:${project.id}`);
  useNekoAgentStore.setState({ agents: [], isLoading: false, error: null, detect });
  useNekoProjectStore.setState({ projects: [project], setPreferredHarness: vi.fn(async () => {}) });
  useNekoSessionStore.setState({ createSession: vi.fn(async () => "created"), sendPrompt: vi.fn(async () => {}) });
});

describe("Project Home readiness and missing Neko recovery", () => {
  it("retains the Project draft when sendPrompt returns without acceptance", async () => {
    home([gemini]);
    fireEvent.change(screen.getByRole("combobox", { name: "Chọn Harness" }), { target: { value: "gemini" } });
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
    await act(async () => { fireEvent.click(sendButton()); });
    await vi.waitFor(() => expect(useNekoSessionStore.getState().sendPrompt).toHaveBeenCalledOnce());
    expect(readNekoComposerDraft(`project:${project.id}`)).toBe("Bản nháp cần được giữ");
    expect((screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" }) as HTMLTextAreaElement).value).toBe("Bản nháp cần được giữ");
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
  });

  it("clears only an accepted Project draft", async () => {
    useNekoSessionStore.setState({ sendPrompt: vi.fn(async (_text, accepted) => { accepted?.(); }) });
    home([gemini]);
    fireEvent.change(screen.getByRole("combobox", { name: "Chọn Harness" }), { target: { value: "gemini" } });
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
    await act(async () => { fireEvent.click(sendButton()); });
    await vi.waitFor(() => expect(readNekoComposerDraft(`project:${project.id}`)).toBe(""));
    expect((screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" }) as HTMLTextAreaElement).value).toBe("");
  });

  it("binds a task session to its Project without deleting the manual draft", async () => {
    const execution = { taskId: "task-test", runId: "run-test", environmentId: "environment-test" };
    writeNekoComposerDraft(`project:${project.id}`, "Manual draft");
    useNekoAgentStore.setState({ agents: [gemini] });
    render(<ProjectHome project={{ ...project, preferredHarnessId: "gemini" }} resetToken={0}
      taskLaunch={{ execution, workspace: project.roots[0], title: "Task fixture" }} />);
    fireEvent.click(sendButton());
    await vi.waitFor(() => expect(useNekoSessionStore.getState().createSession).toHaveBeenCalledWith(
      gemini, project.roots[0], null, { projectId: project.id, execution, title: "Task fixture" },
    ));
    expect(readNekoComposerDraft(`project:${project.id}`)).toBe("Manual draft");
    expect(useNekoSessionStore.getState().sendPrompt).not.toHaveBeenCalled();
  });

  it("removes all four starter actions, keeping the heading and composer", () => {
    home([gemini]);
    expect(screen.getByRole("heading", { name: /Bạn muốn làm gì trong Wiii/ })).toBeTruthy();
    for (const name of ["Khám phá dự án", "Xây một thay đổi", "Rà soát code", "Sửa lỗi"]) {
      expect(screen.queryByRole("button", { name: new RegExp(name) })).toBeNull();
    }
  });

  it("routes missing Neko management away from the draft without launching or installing", () => {
    const input = home([missing]);
    expect(screen.queryByText("Cách cài Neko Core")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Quản lý harness" }));
    expect(manage).toHaveBeenCalledOnce();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(sendButton().disabled).toBe(true);
    expect(input.value).toBe("Bản nháp cần được giữ");
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
    expect(host.open).not.toHaveBeenCalled();
  });

  it("never silently substitutes another agent for missing Neko", async () => {
    home([missing, gemini]);
    const select = screen.getByRole("combobox", { name: "Chọn Harness" });
    expect((select as HTMLSelectElement).value).toBe("neko");
    expect(sendButton().disabled).toBe(true);
    fireEvent.change(select, { target: { value: "gemini" } });
    expect(screen.queryByRole("button", { name: "Quản lý harness" })).toBeNull();
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
    fireEvent.click(sendButton());
    await vi.waitFor(() => expect(useNekoSessionStore.getState().createSession).toHaveBeenCalledWith(
      gemini, project.roots[0], null, { projectId: project.id },
    ));
  });

  it("shows checking instead of missing and blocks launching cached agents", () => {
    const input = home([gemini], { isLoading: true });
    expect(screen.getByText("Đang kiểm tra harness…")).toBeTruthy();
    expect(screen.queryByText("Cách cài Neko Core")).toBeNull();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(sendButton().disabled).toBe(true);
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
  });

  it("does not treat a global discovery error as a missing install or safe cached result", () => {
    const input = home([gemini], { error: "cleanup could not be proven" });
    expect(screen.getByText(/Harness đã chọn chưa sẵn sàng/)).toBeTruthy();
    expect(screen.queryByText("cleanup could not be proven")).toBeNull();
    expect(screen.queryByText("Cách cài Neko Core")).toBeNull();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(sendButton().disabled).toBe(true);
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
  });

  it("keeps a provider-scoped probe failure separate from an alternative", () => {
    home([{ ...missing, availability: "probe_failed", detail: "probe timed out" }, gemini]);
    expect(screen.getByText(/Harness đã chọn chưa sẵn sàng/)).toBeTruthy();
    expect(screen.queryByText("Cách cài Neko Core")).toBeNull();
    expect(sendButton().disabled).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Chọn Harness" }), { target: { value: "gemini" } });
    expect(sendButton().disabled).toBe(false);
  });

  it("defaults an unconfigured Project to Neko regardless of provider order", async () => {
    useNekoAgentStore.setState({ agents: [gemini, neko] });
    render(<ProjectHome project={{ ...project, preferredHarnessId: null }} resetToken={0} />);
    expect((screen.getByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement).value).toBe("neko");
    await vi.waitFor(() => expect(host.profiles).toHaveBeenCalledOnce());
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
  });

  it("preserves a Project's explicit existing agent preference", () => {
    useNekoAgentStore.setState({ agents: [neko, gemini] });
    render(<ProjectHome project={{ ...project, preferredHarnessId: "gemini" }} resetToken={0} />);
    expect((screen.getByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement).value).toBe("gemini");
    expect(host.profiles).not.toHaveBeenCalled();
  });

  it.each([{ isLoading: true }, { error: "cleanup not confirmed" }])(
    "does not start profile setup from cached Neko when discovery is unresolved: %o", (state) => {
      home([neko], state);
      expect(host.profiles).not.toHaveBeenCalled();
      expect(sendButton().disabled).toBe(true);
      expect((screen.getByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement).disabled).toBe(true);
    },
  );

  it("does not recommend installation when this Wiii host is unsupported", () => {
    home([{ ...missing, availability: "host_unsupported" }]);
    expect(screen.getByRole("button", { name: "Quản lý harness" })).toBeTruthy();
    expect(screen.queryByText("Cách cài Neko Core")).toBeNull();
    expect(sendButton().disabled).toBe(true);
  });

  it("does not equate an empty browser discovery result with not installed or poll forever", async () => {
    host.providers.mockResolvedValue([]);
    home([]);
    await vi.waitFor(() => expect(screen.getByText(/Harness đã chọn chưa sẵn sàng/)).toBeTruthy());
    expect(host.providers).toHaveBeenCalledExactlyOnceWith("neko");
    expect(screen.queryByText("Chưa cài Neko Core")).toBeNull();
  });

  it("allows retrying a global failure even if the cached host result is unsupported", async () => {
    home([{ ...missing, availability: "host_unsupported" }], { error: "discovery failed" });
    await act(async () => { await detect("neko"); });
    await vi.waitFor(() => expect(host.providers).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
  });

  it("rechecks installation, reads profiles and never auto-sends the preserved draft", async () => {
    const input = home([missing]);
    await act(async () => { await detect("neko"); });
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
    expect(host.providers).toHaveBeenCalledOnce();
    expect(host.profiles).toHaveBeenCalledOnce();
    expect(input.value).toBe("Bản nháp cần được giữ");
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
    fireEvent.click(sendButton());
    await vi.waitFor(() => expect(useNekoSessionStore.getState().sendPrompt).toHaveBeenCalledOnce());
  });

  it("retries failed profile reads, not the unrelated installation probe", async () => {
    host.profiles.mockRejectedValueOnce(new Error("profile fixture unavailable"));
    home([neko]);
    await screen.findByText(/Chưa đọc được cấu hình Neko Core/);
    expect(sendButton().disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Đọc lại cấu hình Neko Core" }));
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false));
    expect(host.profiles).toHaveBeenCalledTimes(2);
    expect(host.providers).not.toHaveBeenCalled();
  });

  it("allows the existing default-profile path without claiming authentication", async () => {
    host.profiles.mockResolvedValue([]);
    home([neko]);
    await screen.findByText(/phiên sẽ dùng cấu hình mặc định/);
    expect(screen.queryByText("Đã đăng nhập")).toBeNull();
    expect(sendButton().disabled).toBe(false);
  });

  it("does not overlap detection requests from different callers", async () => {
    let resolve!: (value: DetectedAgent[]) => void;
    host.providers.mockReturnValueOnce(new Promise<DetectedAgent[]>((done) => { resolve = done; }));
    const first = detect();
    const joined = detect();
    await vi.waitFor(() => expect(host.providers).toHaveBeenCalledOnce());
    expect(host.providers).toHaveBeenCalledOnce();
    expect(useNekoAgentStore.getState().isLoading).toBe(true);
    resolve([missing]);
    await Promise.all([first, joined]);
    expect(useNekoAgentStore.getState().isLoading).toBe(false);
    expect(useNekoAgentStore.getState().agents).toEqual([missing]);
  });

  it("merges a scoped check without discarding another installed harness", async () => {
    useNekoAgentStore.setState({ agents: [missing, gemini] });
    await detect("neko");
    expect(host.providers).toHaveBeenCalledWith("neko");
    expect(useNekoAgentStore.getState().agents).toEqual([gemini, neko]);
  });

  it("checks an explicit unprobed Project harness on demand", async () => {
    useNekoAgentStore.setState({ agents: [neko] });
    host.providers.mockResolvedValue([gemini]);
    render(<ProjectHome project={{ ...project, preferredHarnessId: "gemini" }} resetToken={0} />);
    await vi.waitFor(() => expect(host.providers).toHaveBeenCalledExactlyOnceWith("gemini"));
    await vi.waitFor(() => expect((screen.getByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement).disabled).toBe(false));
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
  });

  it("opens only the official download page on explicit native link activation", async () => {
    host.native = true;
    host.open.mockRejectedValueOnce(new Error("browser launch denied"));
    render(<HarnessSetupNotice agents={[missing]} loading={false} error={null} selectedAgent={null} onRetry={vi.fn()} />);
    expect(host.open).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Cách cài Neko Core"));
    const link = screen.getByRole("link", { name: /Mở trang tải/ });
    await act(async () => { fireEvent.click(link); });
    expect(host.open).toHaveBeenCalledWith("https://neko.holilihu.online/");
    expect(within(screen.getByRole("alert")).getByText(/Chưa mở được trình duyệt/)).toBeTruthy();
  });

  it("finishes a failed discovery and permits an explicit successful retry", async () => {
    useNekoAgentStore.setState({ agents: [gemini] });
    host.providers.mockRejectedValueOnce(new Error("probe failed safely"));
    await detect();
    expect(useNekoAgentStore.getState().isLoading).toBe(false);
    expect(useNekoAgentStore.getState().error).toContain("probe failed safely");
    await detect();
    expect(useNekoAgentStore.getState().agents).toEqual([neko]);
    expect(useNekoAgentStore.getState().error).toBeNull();
    expect(host.providers).toHaveBeenCalledTimes(2);
  });

  it("offers missing-agent guidance before a first Project exists", async () => {
    const createProject = vi.fn();
    render(<NekoOverview agents={[missing]} sessions={[]} providerCatalogs={[]} discoveryLoading={false}
      onNewSession={createProject} onOpenSession={vi.fn()} onRefreshDiscovery={vi.fn()}
      onImportProviderSession={vi.fn(async () => {})} />);
    expect(screen.getByText("Chưa cài Neko Core")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Phiên mới", exact: true }));
    expect(createProject).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại", exact: true }));
    await vi.waitFor(() => expect(host.providers).toHaveBeenCalledOnce());
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
  });
});
