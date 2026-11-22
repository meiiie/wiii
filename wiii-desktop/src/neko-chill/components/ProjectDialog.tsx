import { useEffect, useRef, useState } from "react";
import { Folder, FolderPlus, LoaderCircle, X } from "lucide-react";
import { NekoBadge, NekoButton, NekoCard, NekoDialogPanel, NekoIconButton, NekoInput } from "./ui";
import type { NekoProject } from "../stores/neko-project-store";
import { workspaceKey } from "../stores/neko-project-store";
import {
  BROWSER_FOLDER_PICKER_UNAVAILABLE_VI,
  canChooseWorkspaceFolder,
  chooseWorkspaceFolder,
  resolveWorkspaceFolder,
  type WorkspaceRef,
} from "../workspace";

/** Control-local reason when primary create/save is gated (disabled = explained). */
export function projectDialogPrimaryTitle(args: {
  mode: "create" | "edit";
  saving: boolean;
  hasName: boolean;
  hasRoots: boolean;
}): string {
  if (args.saving) return "Đang lưu…";
  const missingName = !args.hasName;
  const missingRoots = !args.hasRoots;
  if (missingName && missingRoots) {
    return "Hãy đặt tên dự án và thêm ít nhất một thư mục nguồn.";
  }
  if (missingName) return "Hãy đặt tên cho dự án.";
  if (missingRoots) return "Dự án cần ít nhất một thư mục nguồn.";
  return args.mode === "edit" ? "Lưu thay đổi" : "Tạo dự án";
}

export function ProjectDialog({
  project,
  reason = null,
  onCancel,
  onSave,
}: {
  project: NekoProject | null;
  /** Why create was opened — e.g. user chose Phiên mới with no Project yet. */
  reason?: "new-session" | null;
  onCancel: () => void;
  onSave: (name: string, roots: WorkspaceRef[]) => Promise<void>;
}) {
  const [name, setName] = useState(project?.name ?? "");
  const [roots, setRoots] = useState<WorkspaceRef[]>(project?.roots ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const opener = document.activeElement;
    dialog.showModal();
    nameRef.current?.focus();
    return () => {
      dialog.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);

  useEffect(() => {
    setName(project?.name ?? "");
    setRoots(project?.roots ?? []);
    setSaving(false);
    setError(null);
  }, [project?.id]);

  const nativeFolderPicker = canChooseWorkspaceFolder();

  const addRoot = async () => {
    try {
      if (!canChooseWorkspaceFolder()) {
        setError(
          "Bản xem trước trình duyệt không chọn được thư mục trên máy. Hãy dùng app desktop Wiii để gắn thư mục nguồn.",
        );
        return;
      }
      const selected = await chooseWorkspaceFolder();
      if (!selected) return;
      setRoots((current) => current.some((root) =>
        workspaceKey(root.path) === workspaceKey(selected.path),
      ) ? current : [...current, selected]);
      setName((current) => current.trim() || selected.name);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  const submit = async () => {
    if (saving) return;
    if (!name.trim()) {
      setError("Hãy đặt tên cho dự án.");
      return;
    }
    if (!roots.length) {
      setError("Dự án cần ít nhất một thư mục nguồn.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const resolvedRoots = await Promise.all(roots.map((root) => resolveWorkspaceFolder(root.path)));
      setRoots(resolvedRoots);
      await onSave(name, resolvedRoots);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setSaving(false);
    }
  };

  return (
    <dialog ref={dialogRef} aria-labelledby="project-dialog-title"
      className="nk-dialog"
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const items = [...event.currentTarget.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled)")];
        const first = items[0];
        const last = items[items.length - 1];
        if (!first || (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
          event.preventDefault();
          (event.shiftKey ? last : first)?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!saving) onCancel();
      }}>
    <div
      className="nk-dialog-layout"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) onCancel();
      }}
    >
      <NekoDialogPanel
        data-testid="project-dialog"
      >
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 id="project-dialog-title" className="text-[18px] font-semibold tracking-[-0.025em] text-[var(--nk-text)]">
              {project ? "Chỉnh sửa dự án" : "Tạo dự án"}
            </h1>
            {!project && reason === "new-session" ? (
              <p className="mt-2 max-w-[420px] text-[12.5px] leading-5 text-[var(--nk-text-2)]" data-testid="project-required-hint">
                Chọn thư mục để bắt đầu.
              </p>
            ) : null}
          </div>
          <NekoIconButton
            label="Đóng"
            disabled={saving}
            onClick={onCancel}
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </NekoIconButton>
        </header>

        <label className="mt-5 block" htmlFor="project-name">
          <span className="text-[13px] font-medium text-[var(--nk-text-2)]">Tên dự án</span>
          <div className="nk-input-field mt-2">
            <Folder aria-hidden="true" className="mx-3 h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
            <NekoInput
              ref={nameRef}
              id="project-name"
              value={name}
              maxLength={80}
              disabled={saving}
              className="pl-0"
              placeholder="Ví dụ: Wiii"
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
          </div>
        </label>

        <div className="mt-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-[13px] font-medium text-[var(--nk-text-2)]">Thư mục nguồn <NekoBadge aria-label={`${roots.length} thư mục`}>{roots.length}</NekoBadge></h2>
              {!nativeFolderPicker ? (
                <p className="mt-1.5 text-[10.5px] leading-4 text-[var(--nk-text-3)]" data-testid="browser-folder-picker-hint">
                  Bản xem trước trình duyệt không mở được hộp chọn thư mục máy — dùng app desktop Wiii.
                </p>
              ) : null}
            </div>
            {roots.length > 0 ? (
            <NekoButton
              variant="ghost"
              size="sm"
              className="shrink-0"
              disabled={saving || !nativeFolderPicker}
              title={!nativeFolderPicker ? BROWSER_FOLDER_PICKER_UNAVAILABLE_VI : undefined}
              aria-disabled={!nativeFolderPicker || undefined}
              data-testid="project-dialog-add-folder"
              onClick={() => void addRoot()}
            >
              <FolderPlus aria-hidden="true" className="h-3.5 w-3.5" />
              Thêm thư mục
            </NekoButton>
            ) : null}
          </div>

          <NekoCard tone="inset" className="mt-2 overflow-hidden">
            {roots.length ? roots.map((root) => (
              <div key={root.path} className="flex min-h-12 items-center gap-3 border-b border-[var(--nk-border)] px-3 last:border-b-0">
                <Folder aria-hidden="true" className="h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-[12px] font-medium text-[var(--nk-text)]">{root.name}</strong>
                  <span className="block truncate text-[10px] text-[var(--nk-ghost)]">{root.path}</span>
                </span>
                <NekoIconButton
                  label={`Gỡ thư mục ${root.name}`}
                  className="hover:text-[var(--nk-danger)]"
                  disabled={saving}
                  onClick={() => setRoots((current) => current.filter((item) => item.path !== root.path))}
                >
                  <X aria-hidden="true" className="h-3.5 w-3.5" />
                </NekoIconButton>
              </div>
            )) : (
              <button
                type="button"
                className="flex min-h-[96px] w-full flex-col items-center justify-center gap-2 text-[11.5px] text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-[var(--nk-text-3)]"
                disabled={saving || !nativeFolderPicker}
                title={!nativeFolderPicker ? BROWSER_FOLDER_PICKER_UNAVAILABLE_VI : undefined}
                aria-disabled={!nativeFolderPicker || undefined}
                data-testid="project-dialog-empty-folder"
                onClick={() => void addRoot()}
              >
                <FolderPlus aria-hidden="true" className="h-5 w-5" />
                Chọn thư mục Neko được phép đọc và sửa
              </button>
            )}
          </NekoCard>
        </div>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-[var(--nk-danger-soft)] px-3 py-2 text-[13px] leading-5 text-[var(--nk-danger)]">
            {error}
          </p>
        ) : null}

        <footer className="nk-dialog-actions">
          <NekoButton
            variant="ghost"
            disabled={saving}
            onClick={onCancel}
          >
            Hủy
          </NekoButton>
          <NekoButton
            variant="primary"
            disabled={saving || !name.trim() || roots.length === 0}
            title={projectDialogPrimaryTitle({
              mode: project ? "edit" : "create",
              saving,
              hasName: Boolean(name.trim()),
              hasRoots: roots.length > 0,
            })}
            data-testid="project-dialog-primary"
            onClick={() => void submit()}
          >
            {saving ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : null}
            {project ? "Lưu thay đổi" : "Tạo dự án"}
          </NekoButton>
        </footer>
      </NekoDialogPanel>
    </div>
    </dialog>
  );
}
