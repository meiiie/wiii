import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  ListPlus,
  Bot,
  Command,
  ChevronDown,
  Folder,
  Gauge,
  LoaderCircle,
  LockKeyhole,
  Square,
} from "lucide-react";
import type { DriverConfigOption } from "../drivers/types";
import type { NekoSession } from "../stores/neko-session-store";
import {
  CLIENT_COMMANDS,
  type ClientCommandName,
} from "../command-items";
import {
  clearNekoComposerDraft,
  readNekoComposerDraft,
  writeNekoComposerDraft,
} from "../composer-drafts";
import {
  BROWSER_FOLDER_PICKER_UNAVAILABLE_VI,
  canChooseWorkspaceFolder,
} from "../workspace";
import { ChillCatalogPicker, type ChillCatalogItem } from "./ChillCatalogPicker";

interface SlashSuggestion {
  name: string;
  description: string;
  source: "Neko Chill" | "Agent";
  inputHint?: string;
  clientCommand?: ClientCommandName;
}

export interface ComposerInsertRequest {
  text: string;
  token: number;
}

interface NekoComposerProps {
  session: NekoSession;
  disabled: boolean;
  streaming: boolean;
  onSend: (text: string, onAccepted: () => void) => void | Promise<void>;
  onCancel: () => void;
  onQueue?: (text: string) => Promise<void>;
  queuedCount?: number;
  onSetConfigOption: (optionId: string, value: string | boolean) => void;
  onClientCommand: (command: ClientCommandName) => void;
  insertRequest?: ComposerInsertRequest | null;
}


/** Turn in flight — show Stop instead of a mute disabled Send (ZCode cue #4). */
export function nekoComposerTurnBusy(
  status: NekoSession["status"],
): boolean {
  return status === "streaming" || status === "dispatching";
}

/** Control-local send tooltip — never leave a mute disabled send as "Gửi". */
export function nekoComposerSendTitle(args: {
  streaming: boolean;
  hasWorkspace: boolean;
  composerDisabled: boolean;
  submitting: boolean;
  hasDraft: boolean;
  pendingPermission: boolean;
  pendingControl: boolean;
}): string {
  if (args.streaming) return "Dừng";
  if (!args.hasWorkspace) return "Gắn dự án trước khi gửi.";
  if (args.pendingPermission) return "Đang chờ bạn xác nhận quyền.";
  if (args.pendingControl) return "Đang đổi cấu hình phiên…";
  if (args.submitting) return "Đang gửi…";
  if (args.composerDisabled) return "Phiên chưa sẵn sàng để nhận tin nhắn.";
  if (!args.hasDraft) return "Nhập nội dung trước khi gửi.";
  return "Gửi";
}

/** Stop control title — explain when cancel is staged / blocked. */
export function nekoComposerStopTitle(args: {
  cancelPending: boolean;
  resolvingPermission: boolean;
}): string {
  if (args.cancelPending) return "Đang lưu yêu cầu dừng…";
  if (args.resolvingPermission) return "Đang lưu quyết định…";
  return "Dừng lượt đang chạy";
}


function ControlSelect({
  option,
  disabled,
  pending,
  onChange,
}: {
  option: DriverConfigOption;
  disabled: boolean;
  pending: boolean;
  onChange(value: string): void;
}) {
  const Icon = option.category === "mode" ? Gauge : Bot;
  const items: ChillCatalogItem[] = (option.choices ?? []).map((choice) => ({
    id: choice.value,
    label: choice.label,
    group: option.label,
    description: choice.description,
  }));
  return (
    <ChillCatalogPicker
      items={items}
      value={String(option.currentValue)}
      onChange={onChange}
      ariaLabel={option.label}
      disabled={disabled}
      pending={pending}
      triggerTitle={option.description ?? option.label}
      searchPlaceholder={`Tìm ${option.label.toLocaleLowerCase("vi")}…`}
      emptyLabel="Không tìm thấy mục phù hợp."
      icon={<Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />}
      testId={`neko-control-${option.category}`}
      className="min-w-0 max-w-[190px] text-[11.5px] text-[var(--nk-text-3)]"
    />
  );
}

function NekoComposerComponent({
  session,
  disabled,
  streaming,
  onSend,
  onCancel,
  onQueue,
  queuedCount = 0,
  onSetConfigOption,
  onClientCommand,
  insertRequest,
}: NekoComposerProps) {
  const draftScope = `session:${session.id}`;
  const [draft, setDraftState] = useState(() => readNekoComposerDraft(draftScope));
  const [highlight, setHighlight] = useState(0);
  const [slashDismissed, setSlashDismissed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const submittingRef = useRef(false);
  const submissionRevision = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const workspaceTriggerRef = useRef<HTMLButtonElement>(null);
  const [workspacePathOpen, setWorkspacePathOpen] = useState(false);
  const contextId = useId();
  const hintId = useId();
  const mode = session.controls.find((option) => option.category === "mode" && option.kind === "select");
  const model = session.controls.find((option) => option.category === "model" && option.kind === "select");
  const interactionBlocked =
    disabled || submitting ||
    streaming ||
    Boolean(session.pendingPermission) ||
    Boolean(session.pendingControlId);
  const composerDisabled =
    (session.status !== "idle" && session.status !== "exited") || interactionBlocked;
  // Draft editing is local intent, not permission to dispatch another turn.
  // Keep lifecycle/configuration gates on sending while the current turn runs.
  const draftEditableDuringTurn = streaming
    && nekoComposerTurnBusy(session.status)
    && !session.pendingControlId
    && !session.pendingPermission
    && !session.closePending
    && !session.deletePending;
  const draftReadOnly = composerDisabled && !draftEditableDuringTurn;
  const controlsDisabled = session.status !== "idle" || interactionBlocked || queuedCount > 0;
  const queueAllowed = Boolean(onQueue) && (draftEditableDuringTurn || (!composerDisabled && queuedCount > 0))
    && !CLIENT_COMMANDS.some(command => `/${command.name}` === draft.trim());
  const slashQuery = draft.startsWith("/") && !draft.includes("\n")
    ? draft.slice(1).toLocaleLowerCase("vi")
    : null;
  const suggestions = useMemo<SlashSuggestion[]>(() => {
    if (slashQuery === null) return [];
    const agent: SlashSuggestion[] = session.commands.map((command) => ({
      ...command,
      source: "Agent" as const,
    }));
    return [...CLIENT_COMMANDS, ...agent]
      .filter((command) =>
        !slashQuery
        || command.name.toLocaleLowerCase("vi").includes(slashQuery)
        || command.description.toLocaleLowerCase("vi").includes(slashQuery),
      )
      .slice(0, 8);
  }, [session.commands, slashQuery]);
  const slashOpen = slashQuery !== null && !slashDismissed && !composerDisabled;
  const sendTitle = nekoComposerSendTitle({
    streaming,
    hasWorkspace: Boolean(session.workspace),
    composerDisabled,
    submitting,
    hasDraft: Boolean(draft.trim()),
    pendingPermission: Boolean(session.pendingPermission),
    pendingControl: Boolean(session.pendingControlId),
  });
  const cancelBlocked = Boolean(
    session.cancelPending
    || session.resolvingPermissionId
    || session.closePending
    || session.deletePending
  );
  const stopTitle = nekoComposerStopTitle({
    cancelPending: Boolean(session.cancelPending),
    resolvingPermission: Boolean(session.resolvingPermissionId),
  });

  const composerHint = queuedCount > 0 && !streaming
    ? "Tin mới được thêm cuối hàng đợi. Model được giữ nguyên."
    : draftEditableDuringTurn
    ? (onQueue ? "Enter để xếp hàng. Dừng sẽ giữ lại các tin chờ." : "Bạn có thể soạn tiếp. Bản nháp chưa được gửi; chờ lượt này kết thúc rồi nhấn Gửi.")
    : session.pendingControlId
    ? "Đang đổi cấu hình. Bản nháp được giữ lại."
    : submitting
      ? "Đang gửi. Bản nháp được giữ tới khi phiên nhận."
      : composerDisabled && !streaming && !session.pendingPermission
        ? sendTitle
        : null;

  useEffect(() => {
    setWorkspacePathOpen(false);
  }, [session.workspace?.path]);

  const changeControl = (optionId: string, value: string) => {
    onSetConfigOption(optionId, value);
    textareaRef.current?.focus();
  };

  const setDraft = (value: string) => {
    setDraftState(value);
    writeNekoComposerDraft(draftScope, value);
  };

  useEffect(() => {
    if (!insertRequest) return;
    setDraft(insertRequest.text);
    setSlashDismissed(true);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }, [insertRequest?.token]);

  const runSuggestion = (suggestion: SlashSuggestion) => {
    if (suggestion.clientCommand) {
      setDraft("");
      setSlashDismissed(true);
      onClientCommand(suggestion.clientCommand);
      return;
    }
    setDraft(`/${suggestion.name}${suggestion.inputHint ? " " : ""}`);
    setSlashDismissed(true);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const submit = async () => {
    const text = draft.trim();
    if (!text || submittingRef.current) return;
    const operation = ++submissionRevision.current;
    const releaseSubmission = () => {
      if (submissionRevision.current !== operation) return;
      submittingRef.current = false;
      setSubmitting(false);
    };
    if (queueAllowed && onQueue) {
      submittingRef.current = true;
      setSubmitting(true); setQueueError(null);
      try {
        await onQueue(text);
        if (readNekoComposerDraft(draftScope) === draft) {
          clearNekoComposerDraft(draftScope);
          setDraftState(current => current === draft ? "" : current);
        }
      } catch (error) { setQueueError(error instanceof Error ? error.message : String(error)); }
      finally { releaseSubmission(); }
      return;
    }
    if (composerDisabled) return;
    const local = CLIENT_COMMANDS.find((command) => `/${command.name}` === text);
    const accepted = () => {
      // prompt() lasts for the entire turn; admission ends as soon as the
      // runtime accepts it. A late turn completion must not unlock a newer enqueue.
      releaseSubmission();
      if (readNekoComposerDraft(draftScope) !== draft) return;
      clearNekoComposerDraft(draftScope);
      setDraftState((current) => current === draft ? "" : current);
      setSlashDismissed(false);
    };
    if (local?.clientCommand) {
      onClientCommand(local.clientCommand);
      accepted();
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    try {
      await onSend(text, accepted);
    } catch {
      // The session owns the failure message; the unsent draft remains here.
    } finally {
      releaseSubmission();
    }
  };

  return (
    <div className="shrink-0 px-5 pb-4 pt-1">
      <div className="relative mx-auto w-full max-w-[780px]">
        {slashOpen ? (
          <div
            className="absolute bottom-[calc(100%-2px)] left-3 right-3 z-30 overflow-hidden rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] shadow-[0_14px_35px_rgba(0,0,0,0.12)]"
            role="listbox"
            aria-label="Lệnh slash"
            data-testid="slash-command-menu"
          >
            <div className="flex items-center gap-2 border-b border-[var(--nk-border)] px-3 py-2 text-[10.5px] text-[var(--nk-text-3)]">
              <Command aria-hidden="true" className="h-3.5 w-3.5" />
              Lệnh cho phiên này
              <span className="ml-auto">↑↓ chọn · Enter chèn</span>
            </div>
            <div className="max-h-[280px] overflow-y-auto p-1.5">
              {suggestions.length ? suggestions.map((suggestion, index) => (
                <button
                  key={`${suggestion.source}:${suggestion.name}`}
                  type="button"
                  role="option"
                  aria-selected={index === highlight}
                  className={`flex min-h-10 w-full items-center gap-3 rounded-lg px-2.5 text-left ${
                    index === highlight ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"
                  }`}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => runSuggestion(suggestion)}
                >
                  <code className="w-[120px] shrink-0 truncate text-[12px] text-[var(--nk-text)]">
                    /{suggestion.name}
                  </code>
                  <span className="min-w-0 flex-1 truncate text-[11.5px] text-[var(--nk-text-3)]">
                    {suggestion.description}
                  </span>
                  <span className="rounded bg-[var(--nk-inset)] px-1.5 py-0.5 text-[9.5px] text-[var(--nk-ghost)]">
                    {suggestion.source}
                  </span>
                </button>
              )) : (
                <p className="px-3 py-4 text-center text-[11.5px] text-[var(--nk-text-3)]">
                  Không có lệnh phù hợp.
                </p>
              )}
            </div>
          </div>
        ) : null}

        <div className="nk-input-field relative rounded-[14px] border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-3 shadow-[0_4px_18px_rgba(30,30,28,0.05)]" data-testid="neko-composer">
          <div className="mb-2 flex min-w-0 items-center gap-2 text-[11.5px] text-[var(--nk-text-3)]">
            {session.workspace ? (
              <button
                ref={workspaceTriggerRef}
                type="button"
                className="flex h-7 min-w-0 max-w-full items-center gap-1.5 rounded-md px-1.5 transition-colors hover:bg-[var(--nk-overlay)]"
                title={session.workspace.path}
                aria-label={`Dự án ${session.workspace.name}. Xem đường dẫn`}
                aria-expanded={workspacePathOpen}
                aria-controls={contextId}
                data-testid="neko-composer-project"
                onClick={() => setWorkspacePathOpen((open) => !open)}
                onKeyDown={(event) => {
                  if (event.key === "Escape" && workspacePathOpen) {
                    event.preventDefault();
                    event.stopPropagation();
                    setWorkspacePathOpen(false);
                    workspaceTriggerRef.current?.focus();
                  }
                }}
              >
                <Folder aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{session.workspace.name}</span>
                <ChevronDown aria-hidden="true" className={`h-3 w-3 shrink-0 transition-transform ${workspacePathOpen ? "rotate-180" : ""}`} />
              </button>
            ) : (
              <>
                <Folder aria-hidden="true" className="ml-1.5 h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 truncate">Chưa gắn dự án</span>
                <button
                  type="button"
                  className="shrink-0 rounded-md px-1.5 py-1 text-[var(--nk-accent)] hover:bg-[var(--nk-overlay)] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent"
                  disabled={!canChooseWorkspaceFolder()}
                  title={!canChooseWorkspaceFolder() ? BROWSER_FOLDER_PICKER_UNAVAILABLE_VI : "Chọn thư mục dự án"}
                  aria-disabled={!canChooseWorkspaceFolder() || undefined}
                  data-testid="neko-composer-choose-folder"
                  onClick={() => {
                    if (canChooseWorkspaceFolder()) onClientCommand("project");
                  }}
                >
                  Chọn thư mục
                </button>
              </>
            )}
          </div>
          {session.workspace ? (
            <div id={contextId} hidden={!workspacePathOpen} className="mb-2 rounded-lg bg-[var(--nk-inset)] px-2.5 py-2">
              <span className="block text-[10px] text-[var(--nk-ghost)]">Đường dẫn dự án của phiên</span>
              <span className="mt-0.5 block break-all text-[11px] leading-4 text-[var(--nk-text-2)]">{session.workspace.path}</span>
            </div>
          ) : null}
          <textarea
            ref={textareaRef}
            className="max-h-44 min-h-[48px] w-full resize-none bg-transparent px-1 pt-0.5 text-[13.5px] leading-[20px] text-[var(--nk-text)] placeholder:text-[var(--nk-ghost)] focus:outline-none"
            rows={Math.min(draft.split("\n").length || 1, 6)}
            placeholder={session.workspace ? "Nhắn cho agent… Gõ / để xem lệnh" : "Gắn dự án trước khi nhắn…"}
            value={draft}
            disabled={!session.workspace}
            readOnly={draftReadOnly}
            aria-busy={draftReadOnly}
            aria-label={`Tin nhắn cho ${session.agentName}`}
            aria-describedby={composerHint ? hintId : undefined}
            data-testid="neko-composer-input"
            onChange={(event) => {
              setDraft(event.target.value);
              setHighlight(0);
              setSlashDismissed(false);
            }}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing || event.keyCode === 229) return;
              if (slashOpen && suggestions.length) {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setHighlight((current) => (current + 1) % suggestions.length);
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setHighlight((current) => (current - 1 + suggestions.length) % suggestions.length);
                  return;
                }
                if (event.key === "Tab" || (event.key === "Enter" && !event.shiftKey)) {
                  event.preventDefault();
                  runSuggestion(suggestions[Math.min(highlight, suggestions.length - 1)]);
                  return;
                }
              }
              if (event.key === "Escape" && slashOpen) {
                event.preventDefault();
                setSlashDismissed(true);
                return;
              }
              if (
                event.key === "Enter"
                && !event.shiftKey
                && !event.nativeEvent.isComposing
                && event.keyCode !== 229
              ) {
                event.preventDefault();
                void submit();
              }
            }}
          />
          <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2 text-[11.5px]">
            <div className="flex min-w-0 flex-wrap items-center gap-x-1 gap-y-0.5" role="group" aria-label="Cấu hình phiên">
            <span className="flex h-8 min-w-0 max-w-[150px] items-center gap-1.5 truncate rounded-md px-1.5 text-[var(--nk-text-3)]" title={session.agentName}>
              <Bot aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{session.agentName}</span>
            </span>
            {mode ? (
              <ControlSelect
                option={mode}
                disabled={controlsDisabled}
                pending={session.pendingControlId === mode.id}
                onChange={(value) => changeControl(mode.id, value)}
              />
            ) : null}
            {model ? (
              <ControlSelect
                option={model}
                disabled={controlsDisabled}
                pending={session.pendingControlId === model.id}
                onChange={(value) => changeControl(model.id, value)}
              />
            ) : session.launchProfile ? (
              <button
                type="button"
                className="flex h-7 max-w-[190px] items-center gap-1.5 rounded-md px-1.5 text-[11.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)]"
                title={`Model ${session.launchProfile.model ?? session.launchProfile.id} cố định cho phiên này (chọn lúc khởi động). Bản nháp vẫn giữ — tạo phiên mới để đổi model.`}
                aria-label={`Model ${session.launchProfile.model ?? session.launchProfile.id} — khóa trong phiên`}
                data-testid="neko-model-locked"
                onClick={() => onClientCommand("info")}
              >
                <LockKeyhole aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{session.launchProfile.model ?? session.launchProfile.id}</span>
              </button>
            ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-2">
            {streaming && onQueue && draft.trim() && <button type="button" onClick={() => void submit()} disabled={!queueAllowed || submitting}
              className="grid h-9 w-9 place-items-center rounded-full bg-[var(--nk-inverse)] text-[var(--nk-on-inverse)] disabled:opacity-40"
              aria-label="Xếp hàng tin nhắn" title="Thêm vào hàng đợi (Enter)">
              {submitting ? <LoaderCircle size={15} aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : <ListPlus size={16} aria-hidden="true" />}
            </button>}
            {streaming ? (
              <button
                type="button"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--nk-danger-soft)] text-[var(--nk-danger)] transition-colors hover:bg-[var(--nk-danger)] hover:text-[var(--nk-on-inverse)] aria-disabled:cursor-wait aria-disabled:opacity-50 aria-disabled:hover:bg-[var(--nk-danger-soft)] aria-disabled:hover:text-[var(--nk-danger)]"
                aria-disabled={cancelBlocked}
                onClick={() => {
                  if (!cancelBlocked) onCancel();
                }}
                title={stopTitle}
                aria-label={cancelBlocked ? stopTitle.replace(/…$/, "") : "Dừng lượt đang chạy"}
                aria-busy={Boolean(session.cancelPending || session.resolvingPermissionId)}
                data-testid="neko-cancel"
              >
                <Square aria-hidden="true" className="h-2.5 w-2.5 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--nk-inverse)] text-[var(--nk-on-inverse)] disabled:opacity-30"
                disabled={composerDisabled || !session.workspace || !draft.trim()}
                onClick={() => void submit()}
                title={queueAllowed ? "Thêm vào cuối hàng đợi" : sendTitle}
                aria-label={submitting ? "Đang gửi" : queueAllowed ? "Xếp hàng tin nhắn" : "Gửi tin nhắn"}
                aria-busy={draftReadOnly}
                data-testid="neko-send"
              >
                {submitting
                  ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" />
                  : <ArrowUp aria-hidden="true" className="h-3 w-3" strokeWidth={1.8} />}
              </button>
            )}
          </div>
          </div>
          {queueError && <p role="alert" className="mt-2 text-[11px] text-[var(--nk-danger)]">{queueError} Bản nháp được giữ lại.</p>}
          {composerHint ? (
            <p id={hintId} role="status" aria-live="polite" aria-atomic="true" className="mt-2 px-1 text-[11px] leading-4 text-[var(--nk-text-3)]">
              {composerHint}
            </p>
          ) : null}
        </div>
        <p className="mx-3 mt-1.5 flex items-center gap-2 px-1 text-[10px] text-[var(--nk-ghost)]" aria-hidden="true">
          {!composerDisabled && <span><kbd className="rounded border border-[var(--nk-border)] bg-[var(--nk-raised)] px-1 py-px text-[9.5px]">Enter</kbd> gửi</span>}
          <span><kbd className="rounded border border-[var(--nk-border)] bg-[var(--nk-raised)] px-1 py-px text-[9.5px]">Shift+Enter</kbd> xuống dòng</span>
        </p>
      </div>
    </div>
  );
}

export const NekoComposer = memo(
  NekoComposerComponent,
  (previous, next) => (
    previous.session.id === next.session.id
    && previous.session.status === next.session.status
    && previous.session.agentName === next.session.agentName
    && previous.session.workspace?.name === next.session.workspace?.name
    && previous.session.workspace?.path === next.session.workspace?.path
    && previous.session.controls === next.session.controls
    && previous.session.commands === next.session.commands
    && previous.session.launchProfile === next.session.launchProfile
    && previous.session.pendingPermission === next.session.pendingPermission
    && previous.session.pendingControlId === next.session.pendingControlId
    && previous.session.cancelPending === next.session.cancelPending
    && previous.session.resolvingPermissionId === next.session.resolvingPermissionId
    && previous.session.closePending === next.session.closePending
    && previous.session.deletePending === next.session.deletePending
    && previous.onQueue === next.onQueue
    && previous.queuedCount === next.queuedCount
    && previous.disabled === next.disabled
    && previous.streaming === next.streaming
    && previous.insertRequest?.token === next.insertRequest?.token
  ),
);
