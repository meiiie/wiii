import { useEffect, useRef, useState } from "react";
import { Folder, FolderPlus, LoaderCircle, X } from "lucide-react";
import type { NekoProject } from "../stores/neko-project-store";
import { workspaceKey } from "../stores/neko-project-store";
import {
  chooseWorkspaceFolder,
  resolveWorkspaceFolder,
  type WorkspaceRef,
} from "../workspace";

export function ProjectDialog({
  project,
  onCancel,
  onSave,
}: {
  project: NekoProject | null;
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

  const addRoot = async () => {
    try {
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
      setError("Hãy đặt tên cho Project.");
      return;
    }
    if (!roots.length) {
      setError("Project cần ít nhất một thư mục nguồn.");
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
      className="fixed inset-0 m-0 h-full max-h-none w-full max-w-none overflow-y-auto border-0 bg-transparent p-0"
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
      className="grid min-h-full place-items-center bg-[rgba(29,27,24,0.18)] p-5"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) onCancel();
      }}
    >
      <section
        className="w-full max-w-[560px] rounded-[22px] border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-6 shadow-[0_24px_80px_rgba(55,47,39,0.18)]"
        data-testid="project-dialog"
      >
        <header className="flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--nk-ghost)]">
              Neko Chill
            </p>
            <h1 id="project-dialog-title" className="mt-1 text-[21px] font-semibold tracking-[-0.025em] text-[var(--nk-text)]">
              {project ? "Chỉnh sửa Project" : "Tạo Project"}
            </h1>
          </div>
          <button
            type="button"
            className="grid h-8 w-8 place-items-center rounded-lg text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
            aria-label="Đóng"
            disabled={saving}
            onClick={onCancel}
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </header>

        <label className="mt-6 block" htmlFor="project-name">
          <span className="text-[11.5px] font-medium text-[var(--nk-text-2)]">Tên Project</span>
          <div className="nk-input-field mt-2 flex h-11 items-center rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)]">
            <Folder aria-hidden="true" className="mx-3 h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
            <input
              ref={nameRef}
              id="project-name"
              value={name}
              maxLength={80}
              disabled={saving}
              className="min-w-0 flex-1 bg-transparent pr-3 text-[13px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)]"
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
              <h2 className="text-[11.5px] font-medium text-[var(--nk-text-2)]">Workspace / thư mục nguồn</h2>
              <p className="mt-0.5 text-[10.5px] text-[var(--nk-text-3)]">
                Thêm thư mục để Neko làm việc. Mỗi phiên sử dụng một thư mục đã chọn.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-[11px] text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
              disabled={saving}
              onClick={() => void addRoot()}
            >
              <FolderPlus aria-hidden="true" className="h-3.5 w-3.5" />
              Thêm thư mục
            </button>
          </div>

          <div className="mt-2 overflow-hidden rounded-xl border border-[var(--nk-border)] bg-[var(--nk-raised)]">
            {roots.length ? roots.map((root) => (
              <div key={root.path} className="flex min-h-12 items-center gap-3 border-b border-[var(--nk-border)] px-3 last:border-b-0">
                <Folder aria-hidden="true" className="h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-[12px] font-medium text-[var(--nk-text)]">{root.name}</strong>
                  <span className="block truncate text-[10px] text-[var(--nk-ghost)]">{root.path}</span>
                </span>
                <button
                  type="button"
                  className="grid h-7 w-7 place-items-center rounded-md text-[var(--nk-ghost)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-danger)]"
                  aria-label={`Gỡ thư mục ${root.name}`}
                  disabled={saving}
                  onClick={() => setRoots((current) => current.filter((item) => item.path !== root.path))}
                >
                  <X aria-hidden="true" className="h-3.5 w-3.5" />
                </button>
              </div>
            )) : (
              <button
                type="button"
                className="flex min-h-[96px] w-full flex-col items-center justify-center gap-2 text-[11.5px] text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
                disabled={saving}
                onClick={() => void addRoot()}
              >
                <FolderPlus aria-hidden="true" className="h-5 w-5" />
                Chọn thư mục Neko được phép đọc và sửa
              </button>
            )}
          </div>
        </div>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-[var(--nk-danger-soft)] px-3 py-2 text-[10.5px] leading-4 text-[var(--nk-danger)]">
            {error}
          </p>
        ) : null}

        <footer className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            className="h-9 rounded-lg px-3 text-[12px] text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
            disabled={saving}
            onClick={onCancel}
          >
            Hủy
          </button>
          <button
            type="button"
            className="inline-flex h-9 min-w-[110px] items-center justify-center gap-2 rounded-lg bg-[var(--nk-inverse)] px-4 text-[12px] font-medium text-[var(--nk-on-inverse)] transition-opacity hover:opacity-90 active:scale-[0.99] disabled:opacity-35"
            disabled={saving || !name.trim() || roots.length === 0}
            onClick={() => void submit()}
          >
            {saving ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : null}
            {project ? "Lưu thay đổi" : "Tạo Project"}
          </button>
        </footer>
      </section>
    </div>
    </dialog>
  );
}
