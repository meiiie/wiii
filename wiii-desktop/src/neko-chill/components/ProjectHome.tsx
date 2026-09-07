import { useEffect, useMemo, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  ArrowUp,
  Bot,
  ChevronDown,
  Folder,
  LoaderCircle,
  MoreHorizontal,
  ShieldCheck,
} from "lucide-react";
import { WiiiMark } from "@/components/common/WiiiMark";
import { getNekoControlClient } from "@/neko/control-client";
import type { NekoExecutionBinding } from "@/neko/control-client";
import { findProviderDefinition } from "@/neko/provider-registry";
import {
  codexBootstrapIdentity,
  spawnCodexAccountBootstrap,
} from "../codex-bootstrap-identity";
import {
  CodexAccountSession,
  getCodexAccountBootstrapOwner,
  type CodexAccountSummary,
} from "../drivers/codex/account";
import {
  loadAgentProfiles,
  useNekoAgentStore,
  type AgentLaunchProfile,
} from "../stores/neko-agent-store";
import type { NekoProject } from "../stores/neko-project-store";
import { useNekoProjectStore, workspaceKey } from "../stores/neko-project-store";
import { useNekoSessionStore } from "../stores/neko-session-store";
import type { WorkspaceRef } from "../workspace";
import {
  clearNekoComposerDraft,
  readNekoComposerDraft,
  writeNekoComposerDraft,
} from "../composer-drafts";

export interface NekoTaskLaunchRequest {
  execution: NekoExecutionBinding;
  workspace: WorkspaceRef;
  title: string;
  onSessionCreated?: (sessionId: string) => void | Promise<void>;
  onLaunchError?: (error: unknown) => void | Promise<void>;
}

export function ProjectHome({
  project,
  resetToken,
  taskLaunch,
  onEditProject,
  onWorkspaceChange,
  onManageHarness,
}: {
  project: NekoProject;
  resetToken: number;
  taskLaunch?: NekoTaskLaunchRequest | null;
  onEditProject?: () => void;
  onWorkspaceChange?: (workspace: WorkspaceRef) => void;
  onManageHarness?: () => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previousResetTokenRef = useRef(resetToken);
  const draftScope = `project:${project.id}`;
  const { agents, isLoading, discoveryError, detect } = useNekoAgentStore(useShallow((state) => ({
    agents: state.agents,
    isLoading: state.isLoading,
    discoveryError: state.error,
    detect: state.detect,
  })));
  const createSession = useNekoSessionStore((state) => state.createSession);
  const setPreferredHarness = useNekoProjectStore((state) => state.setPreferredHarness);
  const [draft, setDraftState] = useState(
    () => taskLaunch?.title ?? readNekoComposerDraft(draftScope),
  );
  const [selectedRootPath, setSelectedRootPath] = useState(
    taskLaunch?.workspace.path ?? project.roots[0]?.path ?? "",
  );
  const [selectedAgentId, setSelectedAgentId] = useState(project.preferredHarnessId ?? "neko");
  const attemptedProviders = useRef(new Set<string>());
  const [profiles, setProfiles] = useState<AgentLaunchProfile[]>([]);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileAttempt, setProfileAttempt] = useState(0);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [codexAccount, setCodexAccount] = useState<CodexAccountSummary | null>(null);
  const [codexAccountState, setCodexAccountState] = useState<
    "idle" | "checking" | "signed-out" | "signed-in" | "logging-in" | "error"
  >("idle");
  const [codexBootstrapAttempt, setCodexBootstrapAttempt] = useState(0);
  const codexAccountOwner = getCodexAccountBootstrapOwner();

  const setDraft = (value: string) => {
    setDraftState(value);
    writeNekoComposerDraft(draftScope, value);
  };

  const selectedRoot = useMemo(
    () => project.roots.find((root) => workspaceKey(root.path) === workspaceKey(selectedRootPath)) ?? project.roots[0],
    [project.roots, selectedRootPath],
  );

  useEffect(() => {
    if (selectedRoot) onWorkspaceChange?.(selectedRoot);
  }, [onWorkspaceChange, selectedRoot]);
  const launchableAgents = useMemo(
    () => agents.filter((agent) =>
      agent.found && agent.availability === "available" && findProviderDefinition(agent.id)?.launchable === true,
    ),
    [agents],
  );
  const selectedAgent = !isLoading && !discoveryError
    ? launchableAgents.find((agent) => agent.id === selectedAgentId) ?? null
    : null;

  useEffect(() => {
    if (isLoading || discoveryError || agents.some((agent) => agent.id === selectedAgentId)
      || attemptedProviders.current.has(selectedAgentId)) return;
    attemptedProviders.current.add(selectedAgentId);
    void detect(selectedAgentId);
  }, [agents, detect, discoveryError, isLoading, selectedAgentId]);

  useEffect(() => {
    if (taskLaunch?.title) {
      setDraftState(taskLaunch.title);
    } else if (previousResetTokenRef.current !== resetToken) {
      setDraftState("");
      clearNekoComposerDraft(draftScope);
    }
    previousResetTokenRef.current = resetToken;
    setError(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }, [draftScope, resetToken, taskLaunch?.execution.runId, taskLaunch?.title]);

  useEffect(() => {
    const requestedPath = taskLaunch?.workspace.path;
    const requestedRoot = requestedPath
      ? project.roots.find((root) => workspaceKey(root.path) === workspaceKey(requestedPath))
      : null;
    const nextRoot = requestedRoot
      ? requestedRoot.path
      : project.roots[0]?.path ?? "";
    setSelectedRootPath(nextRoot);
  }, [project.id, project.roots, taskLaunch?.workspace.path]);

  useEffect(() => {
    setSelectedAgentId(project.preferredHarnessId ?? "neko");
  }, [project.id, project.preferredHarnessId]);

  useEffect(() => {
    let cancelled = false;
    setProfileError(null);
    setProfiles([]);
    if (!selectedRoot || selectedAgent?.id !== "neko") {
      setSelectedProfileId("");
      setProfileLoading(false);
      return;
    }
    setProfileLoading(true);
    void loadAgentProfiles(selectedAgent, selectedRoot.path)
      .then((items) => {
        if (cancelled) return;
        setProfiles(items);
        setSelectedProfileId((current) =>
          items.some((item) => item.id === current)
            ? current
            : (items.find((item) => item.active) ?? items[0])?.id ?? "",
        );
      })
      .catch((cause) => {
        if (cancelled) return;
        setProfiles([]);
        setSelectedProfileId("");
        setProfileError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAgent?.id, selectedRoot?.path, profileAttempt]);

  useEffect(() => {
    let cancelled = false;
    let bootstrapSession: CodexAccountSession | null = null;
    setCodexAccount(null);
    if (!selectedRoot || selectedAgent?.id !== "codex") {
      setCodexAccountState("idle");
      void codexAccountOwner.release().catch(() => {});
      return;
    }

    setCodexAccountState("checking");
    const bootstrapIdentity = codexBootstrapIdentity(selectedRoot.path);
    void codexAccountOwner
      .replace(async () => {
        const { transport } = await spawnCodexAccountBootstrap(
          getNekoControlClient(),
          bootstrapIdentity,
        );
        return new CodexAccountSession(transport);
      })
      .then(async (session) => {
        bootstrapSession = session;
        if (cancelled) {
          await codexAccountOwner.release(session);
          return;
        }
        const account = await session.start();
        if (cancelled) return;
        setCodexAccount(account);
        setCodexAccountState(account.authenticated ? "signed-in" : "signed-out");
      })
      .catch(async (cause) => {
        if (bootstrapSession) {
          try {
            await codexAccountOwner.release(bootstrapSession);
          } catch {
            // The shared bootstrap owner retries cleanup before replacement.
          }
        }
        if (cancelled) return;
        setCodexAccountState("error");
        setError(cause instanceof Error ? cause.message : String(cause));
      });

    return () => {
      cancelled = true;
      if (bootstrapSession) void codexAccountOwner.release(bootstrapSession).catch(() => {});
    };
  }, [codexAccountOwner, codexBootstrapAttempt, selectedAgent?.id, selectedRoot?.path]);

  const selectAgent = (agentId: string) => {
    setSelectedAgentId(agentId);
    setError(null);
    void setPreferredHarness(project.id, agentId);
  };

  const loginCodex = async () => {
    const session = codexAccountOwner.current();
    if (!session) return;
    setCodexAccountState("logging-in");
    setError(null);
    try {
      const challenge = await session.beginChatGptLogin();
      const { open } = await import("@tauri-apps/plugin-shell");
      await open(challenge.authUrl);
      await session.waitForLogin(challenge.loginId);
      const account = await session.read();
      setCodexAccount(account);
      setCodexAccountState(account.authenticated ? "signed-in" : "signed-out");
    } catch (cause) {
      setCodexAccountState("error");
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  const canStart = Boolean(
    selectedRoot
    && selectedAgent
    && !starting
    && !isLoading
    && !discoveryError
    && (taskLaunch || draft.trim())
    && !(selectedAgent.id === "neko" && (profileLoading || profileError))
    && !(selectedAgent.id === "codex" && codexAccountState !== "signed-in"),
  );

  const start = async () => {
    if (!selectedRoot || !selectedAgent || !canStart) return;
    const profile = selectedAgent.id === "neko"
      ? profiles.find((item) => item.id === selectedProfileId) ?? null
      : null;
    const prompt = taskLaunch?.title ?? draft.trim();
    setStarting(true);
    setError(null);
    try {
      const sessionId = await createSession(
        selectedAgent,
        selectedRoot,
        profile,
        taskLaunch
          ? { execution: taskLaunch.execution, title: taskLaunch.title }
          : { projectId: project.id },
      );
      await taskLaunch?.onSessionCreated?.(sessionId);
      if (!taskLaunch && prompt) {
        await useNekoSessionStore.getState().sendPrompt(prompt);
      }
      clearNekoComposerDraft(draftScope);
      setDraftState("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      try {
        await taskLaunch?.onLaunchError?.(cause);
      } catch (classificationError) {
        setError(classificationError instanceof Error
          ? classificationError.message
          : String(classificationError));
      }
      setStarting(false);
    }
  };

  return (
    <main
      className="nk-project-home nk-scroll-surface flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-[var(--nk-canvas)]"
      data-testid="project-home"
      aria-labelledby="project-home-title"
    >
      <div className="nk-project-hero flex min-h-[360px] flex-[1_0_auto] flex-col items-center justify-center px-8 py-10">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[var(--nk-raised)] shadow-[0_10px_35px_rgba(49,43,36,0.08)]">
          <WiiiMark size={29} />
        </div>
        <div className="mt-5 flex max-w-[760px] items-center gap-2">
          <h1
            id="project-home-title"
            className="nk-project-heading min-w-0 break-words text-center text-[28px] font-medium leading-tight tracking-[-0.035em] text-[var(--nk-text)]"
          >
            Bạn muốn làm gì trong <span className="underline decoration-[var(--nk-border-strong)] decoration-dotted underline-offset-4">{project.name}</span>?
          </h1>
          {onEditProject ? <button
            type="button"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
            aria-label={`Chỉnh sửa Project ${project.name}`}
            onClick={onEditProject}
          >
            <MoreHorizontal aria-hidden="true" className="h-4 w-4" />
          </button> : null}
        </div>
      </div>

      <div className="shrink-0 px-5 pb-5">
        <div className="mx-auto w-full max-w-[900px]">
          {!selectedAgent && <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 text-[11.5px] text-[var(--nk-text-3)]">
            <span role="status">{isLoading ? "Đang kiểm tra harness…" : "Harness đã chọn chưa sẵn sàng. Bản nháp vẫn được giữ."}</span>
            {onManageHarness && <button type="button" className="rounded underline underline-offset-4 hover:text-[var(--nk-text)]"
              onClick={onManageHarness}>Quản lý harness</button>}
          </div>}
          {error ? (
            <div role="alert" className="mb-2 rounded-xl bg-[var(--nk-danger-soft)] px-3 py-2 text-[10.5px] leading-4 text-[var(--nk-danger)]">
              <div className="flex items-start gap-2">
                <span className="min-w-0 flex-1">{error}</span>
                <button
                  type="button"
                  className="shrink-0 font-medium hover:underline"
                  onClick={() => {
                    setError(null);
                    void detect(selectedAgentId);
                  }}
                >
                  Thử lại
                </button>
              </div>
            </div>
          ) : null}

          {selectedAgent?.id === "neko" && !isLoading && !discoveryError && (profileLoading || profileError || profiles.length === 0) ? (
            <div className="mb-3 px-3 text-[12px] leading-5 text-[var(--nk-text-2)]" role={profileError ? "alert" : "status"}>
              <p>{profileLoading ? "Đang đọc cấu hình Neko Core…" : profileError
                ? "Chưa đọc được cấu hình Neko Core. Bản nháp vẫn được giữ lại."
                : "Neko Core đã được tìm thấy. Không có profile riêng để chọn; phiên sẽ dùng cấu hình mặc định của Neko."}</p>
              {!profileLoading && <details className="mt-1">
                <summary className="cursor-pointer">{profileError ? "Chi tiết lỗi" : "Cấu hình tài khoản / model"}</summary>
                {profileError && <p className="mt-1 break-words text-[var(--nk-text-3)]">{profileError}</p>}
                <p>Mở Neko Core và dùng <code>/login</code> để đăng nhập, hoặc cấu hình model cục bộ trong Neko. Wiii không yêu cầu tài khoản Wiii Service.</p>
              </details>}
              {!profileLoading && <button type="button" className="mt-1 font-medium underline underline-offset-4"
                onClick={() => setProfileAttempt((value) => value + 1)}>Đọc lại cấu hình Neko Core</button>}
            </div>
          ) : null}

          <div
            className="mx-3 -mb-2 flex min-h-12 items-center gap-2 rounded-t-xl border border-b-0 border-[var(--nk-border)] bg-[var(--nk-sidebar)] px-2 pb-2 pt-1.5 text-[11.5px] text-[var(--nk-text-2)]"
            aria-label="Ngữ cảnh phiên mới"
          >
            <button
              type="button"
              className="flex min-w-0 max-w-[30%] items-center gap-2 rounded-md px-1.5 py-1.5 text-left transition-colors hover:bg-[var(--nk-overlay)]"
              aria-label={`Chỉnh sửa Project ${project.name}`}
              onClick={onEditProject}
              disabled={!onEditProject}
            >
              <Folder aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[var(--nk-text-3)]" />
              <span className="min-w-0">
                <strong className="block truncate text-[11.5px] font-medium text-[var(--nk-text-2)]">{project.name}</strong>
              </span>
            </button>

            <span aria-hidden="true" className="h-4 w-px shrink-0 bg-[var(--nk-border-strong)]" />

            <div className="relative flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1.5" title={selectedRoot?.path}>
              <span className="min-w-0 flex-1">
                <span className="sr-only">Workspace</span>
                {project.roots.length > 1 ? (
                  <span className="relative block min-w-0">
                    <select
                      className="h-6 w-full appearance-none truncate rounded bg-transparent pr-5 text-[11.5px] font-medium text-[var(--nk-text-2)]"
                      value={selectedRoot?.path ?? ""}
                      aria-label="Chọn Workspace thực thi"
                      onChange={(event) => {
                        setSelectedRootPath(event.target.value);
                        setError(null);
                      }}
                    >
                      {project.roots.map((root) => <option key={root.path} value={root.path}>{root.name}</option>)}
                    </select>
                    <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--nk-ghost)]" />
                  </span>
                ) : (
                  <strong className="block truncate text-[11.5px] font-normal text-[var(--nk-text-2)]">{selectedRoot?.name}</strong>
                )}
              </span>
              <span className="sr-only">
                {selectedRoot?.path}
              </span>
            </div>

            <span className="nk-project-local-badge shrink-0 text-[11px] text-[var(--nk-text-3)]">
              Trên máy
            </span>
          </div>

          <div className="nk-project-composer relative rounded-2xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-3 shadow-[0_6px_24px_rgba(38,33,28,0.05)]">
            <textarea
              ref={textareaRef}
              rows={Math.min(draft.split("\n").length || 1, 6)}
              value={draft}
              readOnly={Boolean(taskLaunch)}
              disabled={starting}
              className="max-h-44 min-h-[62px] w-full resize-none bg-transparent px-1 text-[13.5px] leading-5 text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)]"
              placeholder="Bạn muốn thực hiện việc gì trong dự án này?"
              aria-label="Lời nhắn đầu tiên"
              data-testid="project-home-input"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter"
                  && !event.shiftKey
                  && !event.nativeEvent.isComposing
                  && event.keyCode !== 229
                ) {
                  event.preventDefault();
                  void start();
                }
              }}
            />

            <div className="mt-2 flex min-h-8 flex-wrap items-center gap-1.5">
              <label className="relative flex h-8 min-w-0 max-w-[190px] items-center gap-1.5 rounded-md px-1.5 text-[12px] text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)]">
                <Bot aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                <span className="sr-only">Chọn Harness</span>
                <select
                  value={selectedAgentId}
                  disabled={starting || isLoading || Boolean(discoveryError) || launchableAgents.length === 0}
                  className="min-w-0 flex-1 appearance-none truncate bg-transparent pr-4 outline-none"
                  aria-label="Chọn Harness"
                  onChange={(event) => selectAgent(event.target.value)}
                >
                  {!launchableAgents.some((agent) => agent.id === selectedAgentId) ? <option value={selectedAgentId} disabled>
                    {isLoading ? "Đang kiểm tra Neko Core…" : selectedAgentId === "neko" ? "Neko Core · Chưa sẵn sàng" : "Agent đã chọn chưa sẵn sàng"}
                  </option> : null}
                  {launchableAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                </select>
                <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-1 h-3 w-3 text-[var(--nk-ghost)]" />
              </label>

              {selectedAgent?.id === "neko" && profiles.length ? (
                <label className="relative flex h-8 min-w-0 max-w-[210px] items-center rounded-md px-1.5 text-[12px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)]">
                  <span className="sr-only">Profile / model</span>
                  <select
                    value={selectedProfileId}
                    disabled={starting || profileLoading}
                    className="min-w-0 appearance-none truncate bg-transparent pr-4 outline-none"
                    aria-label="Profile / model"
                    onChange={(event) => setSelectedProfileId(event.target.value)}
                  >
                    {profiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>{profile.id} · {profile.model ?? profile.provider}</option>
                    ))}
                  </select>
                  <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-1 h-3 w-3" />
                </label>
              ) : null}

              {selectedAgent?.id === "codex" ? (
                <span className="text-[10px] text-[var(--nk-text-3)]">
                  {codexAccountState === "signed-in"
                    ? `Đã đăng nhập${codexAccount?.planType ? ` · ${codexAccount.planType}` : ""}`
                    : codexAccountState === "checking"
                      ? "Đang kiểm tra Codex…"
                      : codexAccountState === "logging-in"
                        ? "Hoàn tất trong trình duyệt…"
                        : (
                          <button
                            type="button"
                            className="font-medium text-[var(--nk-accent)] hover:underline"
                            onClick={() => {
                              if (codexAccountState === "error") {
                                setError(null);
                                setCodexBootstrapAttempt((value) => value + 1);
                              } else void loginCodex();
                            }}
                          >
                            {codexAccountState === "error" ? "Kiểm tra lại Codex" : "Đăng nhập Codex"}
                          </button>
                        )}
                </span>
              ) : null}

              <div className="flex-1" />
              <button
                type="button"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[var(--nk-inverse)] text-[var(--nk-on-inverse)] disabled:opacity-30"
                disabled={!canStart}
                aria-label={starting ? "Đang mở phiên" : "Gửi và mở phiên"}
                onClick={() => void start()}
              >
                {starting
                  ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
                  : <ArrowUp aria-hidden="true" className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <p className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-[var(--nk-text-3)]">
            <ShieldCheck aria-hidden="true" className="h-3 w-3" />
            Thư mục đã chọn là ngữ cảnh làm việc của phiên.
          </p>
        </div>
      </div>
    </main>
  );
}
