import {
  lazy,
  memo,
  Suspense,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ChevronRight,
  Code2,
  Eye,
  File,
  FileCode2,
  FileImage,
  FileText,
  Folder,
  FolderOpen,
  Globe2,
  GitCompareArrows,
  LoaderCircle,
  MonitorUp,
  Pin,
  Radio,
  RefreshCw,
  Search,
  TerminalSquare,
  X,
} from "lucide-react";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import {
  useNekoSessionStore,
  type NekoSession,
} from "../stores/neko-session-store";
import { projectForWorkspace, useNekoProjectStore } from "../stores/neko-project-store";
import type { WorkspaceRef } from "../workspace";
import {
  useNekoWorkspaceStore,
  type ObservedWorkspaceActivity,
} from "../stores/neko-workspace-store";
import {
  readWorkspaceFile,
  type WorkspaceEntry,
  type WorkspaceFile,
} from "../workspace-files";
import {
  buildWorkspaceTree,
  flattenWorkspaceTree,
  workspaceAncestorPaths,
  type WorkspaceTreeRow,
} from "../workspace-tree";
import { resolvePreviewAssetPath } from "../workspace-preview";
import { WORKSPACE_CODE_EDITOR_OPTIONS } from "../workspace-editor-options";
import { NekoComputerSurface } from "@/neko-computer/NekoComputerSurface";

const MonacoEditor = lazy(async () => {
  const module = await import("@monaco-editor/react");
  return { default: module.Editor };
});
const MonacoDiffEditor = lazy(async () => {
  const module = await import("@monaco-editor/react");
  return { default: module.DiffEditor };
});

export type WorkspaceSurface = "changes" | "terminal" | "browser" | "computer" | "files" | "preview";

export interface NekoWorkspaceTarget {
  id: string;
  sessionId?: string;
  projectId?: string;
  projectName?: string;
  workspace: WorkspaceRef;
}

interface NekoWorkspacePaneProps {
  session?: NekoSession;
  target?: NekoWorkspaceTarget;
  requestedSurface?: Exclude<WorkspaceSurface, "preview">;
  onClose?: () => void;
  exiting?: boolean;
}

function parentPath(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const separator = normalized.lastIndexOf("/");
  return separator > 0 ? normalized.slice(0, separator) : "Gốc dự án";
}

function TreeRow({
  row,
  expanded,
  selected,
  activity,
  onToggle,
  onOpen,
}: {
  row: WorkspaceTreeRow;
  expanded: boolean;
  selected: boolean;
  activity?: ObservedWorkspaceActivity;
  onToggle: () => void;
  onOpen: () => void;
}) {
  const { node, depth } = row;
  const label = activityLabel(activity);
  const paddingLeft = 6 + depth * 14;

  if (node.kind === "folder") {
    return (
      <button
        type="button"
        aria-expanded={expanded}
        aria-label={`${expanded ? "Thu gọn" : "Mở"} thư mục ${node.path}`}
        className="group flex h-8 w-full items-center gap-1.5 rounded-md pr-2 text-left text-[11.5px] font-medium text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
        style={{ paddingLeft }}
        onClick={onToggle}
      >
        <ChevronRight
          aria-hidden="true"
          className={`h-3 w-3 shrink-0 text-[var(--nk-ghost)] transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
        />
        {expanded ? (
          <FolderOpen aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[var(--nk-text-3)]" />
        ) : (
          <Folder aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[var(--nk-text-3)]" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      aria-label={`Mở ${node.path}`}
      className={`group flex h-8 w-full items-center gap-1.5 rounded-md pr-2 text-left transition-colors active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)] ${
        selected
          ? "bg-[var(--nk-item-active)] text-[var(--nk-text)]"
          : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)]"
      }`}
      style={{ paddingLeft: paddingLeft + 18 }}
      onClick={onOpen}
    >
      <span className="shrink-0 text-[var(--nk-text-3)]">{fileIcon(node.path)}</span>
      <span className="min-w-0 flex-1 truncate text-[11px]">{node.name}</span>
      {label ? (
        <span
          className={`flex shrink-0 items-center gap-1 text-[8.5px] ${
            activity?.status === "pending" || activity?.status === "in_progress"
              ? "text-[var(--nk-accent)]"
              : "text-[var(--nk-ghost)]"
          }`}
        >
          <span
            className={`h-1 w-1 rounded-full ${
              activity?.status === "pending" || activity?.status === "in_progress"
                ? "nk-status-pulse bg-[var(--nk-accent)]"
                : "bg-[var(--nk-ghost)]"
            }`}
          />
          {label}
        </span>
      ) : null}
    </button>
  );
}

function fileIcon(path: string, kind?: WorkspaceFile["kind"]) {
  const className = "h-3.5 w-3.5 shrink-0";
  if (kind === "image" || /\.(?:gif|jpe?g|png|webp)$/i.test(path)) {
    return <FileImage aria-hidden="true" className={className} />;
  }
  if (/\.(?:html?|jsx?|tsx?|css|json|py|rs|go|java|rb|sh|sql|ya?ml)$/i.test(path)) {
    return <FileCode2 aria-hidden="true" className={className} />;
  }
  if (/\.(?:md|mdx|txt|pdf)$/i.test(path)) {
    return <FileText aria-hidden="true" className={className} />;
  }
  return <File aria-hidden="true" className={className} />;
}

function activityLabel(activity: ObservedWorkspaceActivity | undefined): string | null {
  if (!activity) return null;
  const action =
    activity.operation === "read"
      ? "Đang đọc"
      : activity.operation === "delete"
        ? "Đang xóa"
        : activity.operation === "move"
          ? "Đang chuyển"
          : "Đang sửa";
  if (activity.status === "pending" || activity.status === "in_progress") return action;
  if (activity.status === "failed" || activity.status === "cancelled") return "Không áp dụng";
  return activity.operation === "read" ? "Đã đọc" : "Đã cập nhật";
}

function secureHtml(content: string): string {
  const csp = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; font-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; media-src data: blob:;">`;
  if (/<head(?:\s[^>]*)?>/i.test(content)) {
    return content.replace(/<head(?:\s[^>]*)?>/i, (head) => `${head}${csp}`);
  }
  return `<!doctype html><html><head>${csp}</head><body>${content}</body></html>`;
}

function canPreview(file: WorkspaceFile): boolean {
  return (
    file.kind === "image" ||
    file.kind === "pdf" ||
    file.language === "html" ||
    file.language === "markdown" ||
    file.path.toLowerCase().endsWith(".svg")
  );
}

async function hydrateWorkspaceHtml(
  workspacePath: string,
  file: WorkspaceFile,
): Promise<string> {
  if (file.content === null) return "";
  const documentNode = new DOMParser().parseFromString(file.content, "text/html");
  const stylesheets = [...documentNode.querySelectorAll<HTMLLinkElement>('link[rel~="stylesheet"][href]')]
    .slice(0, 16);
  const images = [...documentNode.querySelectorAll<HTMLImageElement>("img[src]")].slice(0, 32);

  await Promise.all(stylesheets.map(async (link) => {
    const assetPath = resolvePreviewAssetPath(file.path, link.getAttribute("href") ?? "");
    if (!assetPath) return;
    try {
      const asset = await readWorkspaceFile(workspacePath, assetPath);
      if (asset.content === null) return;
      const style = documentNode.createElement("style");
      if (link.media) style.media = link.media;
      style.dataset.wiiiPreviewSource = assetPath;
      style.textContent = asset.content;
      link.replaceWith(style);
    } catch {
      // Keep the original link. The preview CSP blocks unresolved external access.
    }
  }));

  await Promise.all(images.map(async (image) => {
    const assetPath = resolvePreviewAssetPath(file.path, image.getAttribute("src") ?? "");
    if (!assetPath) return;
    try {
      const asset = await readWorkspaceFile(workspacePath, assetPath);
      if (asset.dataUrl) image.src = asset.dataUrl;
    } catch {
      // One missing image must not fail the rest of the document preview.
    }
  }));

  return secureHtml(`<!doctype html>${documentNode.documentElement.outerHTML}`);
}

function HtmlPreview({ file, workspacePath }: { file: WorkspaceFile; workspacePath: string }) {
  const [documentHtml, setDocumentHtml] = useState(() => secureHtml(file.content ?? ""));
  const [hydrating, setHydrating] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setHydrating(true);
    setDocumentHtml(secureHtml(file.content ?? ""));
    void hydrateWorkspaceHtml(workspacePath, file)
      .then((html) => {
        if (!cancelled && html) setDocumentHtml(html);
      })
      .finally(() => {
        if (!cancelled) setHydrating(false);
      });
    return () => {
      cancelled = true;
    };
  }, [file.content, file.modifiedAt, file.path, workspacePath]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 text-[9.5px] text-[var(--nk-text-3)]">
        <Globe2 aria-hidden="true" className="h-3 w-3" />
        <span className="min-w-0 flex-1 truncate">{file.path}</span>
        <span>{hydrating ? "Đang nạp asset…" : "Preview cục bộ"}</span>
      </div>
      <iframe
        title={`Xem trước ${file.name}`}
        srcDoc={documentHtml}
        sandbox="allow-scripts"
        className="min-h-0 flex-1 border-0 bg-white"
      />
    </div>
  );
}

function FilePreview({ file, workspacePath }: { file: WorkspaceFile; workspacePath: string }) {
  if (file.kind === "image" && file.dataUrl) {
    return (
      <div className="grid h-full place-items-center overflow-auto bg-[var(--nk-inset)] p-6">
        <img src={file.dataUrl} alt={file.name} className="max-h-full max-w-full rounded-lg shadow-sm" />
      </div>
    );
  }
  if (file.kind === "pdf" && file.dataUrl) {
    return (
      <iframe
        title={`Xem trước ${file.name}`}
        src={file.dataUrl}
        sandbox=""
        className="h-full w-full border-0 bg-white"
      />
    );
  }
  if (file.language === "markdown" && file.content !== null) {
    return (
      <article className="h-full overflow-auto bg-[var(--nk-composer)] px-8 py-6 text-[14px] leading-6">
        <MarkdownRenderer content={file.content} />
      </article>
    );
  }
  if (
    file.content !== null &&
    (file.language === "html" || file.path.toLowerCase().endsWith(".svg"))
  ) {
    return <HtmlPreview file={file} workspacePath={workspacePath} />;
  }
  return null;
}

function browserImageSource(image: string): string {
  return image.startsWith("data:") ? image : `data:image/jpeg;base64,${image}`;
}

function latestBrowserScreenshot(messages: NekoSession["messages"]) {
  for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
    const blocks = messages[messageIndex].blocks ?? [];
    for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex -= 1) {
      const block = blocks[blockIndex];
      if (block.type === "screenshot") return block;
    }
  }
  return null;
}

function BrowserSurface({
  sessionId,
  file,
  workspacePath,
}: {
  sessionId?: string;
  file: WorkspaceFile | null;
  workspacePath: string;
}) {
  const screenshot = useNekoSessionStore((state) =>
    sessionId
      ? latestBrowserScreenshot(state.sessions[sessionId]?.messages ?? [])
      : null,
  );

  if (file && canPreview(file)) return <FilePreview file={file} workspacePath={workspacePath} />;

  if (screenshot) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-[var(--nk-inset)]">
        <div className="flex h-9 shrink-0 items-center gap-2 border-b border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 text-[10px] text-[var(--nk-text-3)]">
          <Globe2 aria-hidden="true" className="h-3.5 w-3.5" />
          <span className="min-w-0 flex-1 truncate">{screenshot.url}</span>
          <span className="truncate">{screenshot.label}</span>
        </div>
        <div className="grid min-h-0 flex-1 place-items-center overflow-auto p-5">
          <img
            src={browserImageSource(screenshot.image)}
            alt={screenshot.label || "Ảnh chụp từ Browser agent"}
            className="max-h-full max-w-full rounded-lg bg-white shadow-sm"
          />
        </div>
      </div>
    );
  }

  return (
    <SurfaceEmptyState
      icon={Globe2}
      title="Chưa có Browser activity"
      description="Ảnh chụp từ browser tool hoặc bản xem trước HTML, Markdown, PDF và hình ảnh sẽ xuất hiện ở đây. Phiên trình duyệt đăng nhập phải do Neko Browser Runtime quản lý."
    />
  );
}

function SurfaceEmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof File;
  title: string;
  description: string;
}) {
  return (
    <div className="grid h-full place-items-center px-8 text-center">
      <div className="max-w-sm">
        <Icon aria-hidden="true" className="mx-auto h-8 w-8 text-[var(--nk-ghost)]" />
        <p className="mt-3 text-[13px] font-semibold text-[var(--nk-text)]">{title}</p>
        <p className="mt-1.5 text-[11px] leading-5 text-[var(--nk-text-3)]">{description}</p>
      </div>
    </div>
  );
}

function WorkspaceLauncher({ onSelect }: { onSelect: (surface: WorkspaceSurface) => void }) {
  const actions: Array<{
    id: WorkspaceSurface;
    label: string;
    detail: string;
    icon: typeof File;
  }> = [
    { id: "changes", label: "Thay đổi", detail: "Xem diff và trạng thái Git", icon: GitCompareArrows },
    { id: "computer", label: "Máy tính", detail: "Màn hình dùng chung của agent và bạn", icon: MonitorUp },
    { id: "browser", label: "Trình duyệt", detail: "Chromium và phiên đăng nhập bền vững", icon: Globe2 },
    { id: "terminal", label: "Terminal", detail: "Chạy lệnh trong cùng computer", icon: TerminalSquare },
    { id: "files", label: "Tệp", detail: "Mở mã nguồn trong Project", icon: FolderOpen },
  ];

  return (
    <nav className="mx-auto grid w-full max-w-sm gap-1" aria-label="Mở công cụ Project">
      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          className="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-[var(--nk-overlay)] active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
          onClick={() => onSelect(action.id)}
        >
          <action.icon aria-hidden="true" className="h-4 w-4 text-[var(--nk-text-3)] transition-colors group-hover:text-[var(--nk-text)]" />
          <span className="min-w-0 flex-1">
            <span className="block text-[12px] font-medium text-[var(--nk-text)]">{action.label}</span>
            <span className="block text-[10px] text-[var(--nk-text-3)]">{action.detail}</span>
          </span>
        </button>
      ))}
    </nav>
  );
}

function EmptyContent({ tab }: { tab: "files" | "changes" }) {
  return (
    <div className="grid h-full place-items-center px-8 text-center">
      <div className="max-w-xs">
        {tab === "files" ? (
          <FileCode2 aria-hidden="true" className="mx-auto h-8 w-8 text-[var(--nk-ghost)]" />
        ) : (
          <GitCompareArrows aria-hidden="true" className="mx-auto h-8 w-8 text-[var(--nk-ghost)]" />
        )}
        <p className="mt-3 text-[13px] font-medium text-[var(--nk-text-2)]">
          {tab === "files" ? "Chọn một file để xem" : "Chọn một thay đổi để so sánh"}
        </p>
        <p className="mt-1 text-[11.5px] leading-5 text-[var(--nk-text-3)]">
          Pane này theo dõi đúng workspace của phiên và cập nhật khi agent thao tác.
        </p>
      </div>
    </div>
  );
}

function FileRow({
  entry,
  selected,
  activity,
  onClick,
}: {
  entry: WorkspaceEntry;
  selected: boolean;
  activity?: ObservedWorkspaceActivity;
  onClick: () => void;
}) {
  const label = activityLabel(activity);
  return (
    <button
      type="button"
      className={`group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)] ${
        selected ? "bg-[var(--nk-item-active)] text-[var(--nk-text)]" : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)]"
      }`}
      onClick={onClick}
      aria-label={`Mở ${entry.path}`}
    >
      <span className="mt-0.5 text-[var(--nk-text-3)]">{fileIcon(entry.path)}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[11.5px] font-medium">{entry.name}</span>
        <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[9.5px]">
          {label ? <span className={`flex shrink-0 items-center gap-1 ${
            activity?.status === "pending" || activity?.status === "in_progress"
              ? "text-[var(--nk-accent)]"
              : "text-[var(--nk-text-3)]"
          }`}>
            <span className={`h-1 w-1 rounded-full ${
              activity?.status === "pending" || activity?.status === "in_progress"
                ? "nk-status-pulse bg-[var(--nk-accent)]"
                : "bg-[var(--nk-ghost)]"
            }`} />
            {label}
          </span> : null}
          <span className="truncate text-[var(--nk-ghost)]">{parentPath(entry.path)}</span>
        </span>
      </span>
    </button>
  );
}

function NekoWorkspacePaneComponent({
  session,
  target,
  requestedSurface = "files",
  onClose,
  exiting = false,
}: NekoWorkspacePaneProps) {
  const targetId = session?.id ?? target?.id ?? "project-workspace-unavailable";
  const workspace = session?.workspace ?? target?.workspace ?? null;
  const sessionId = session?.id ?? target?.sessionId;
  const projects = useNekoProjectStore((state) => state.projects);
  const catalogProject = workspace ? projectForWorkspace(projects, workspace.path) : null;
  const computerProjectId = session?.projectId ?? target?.projectId ?? catalogProject?.id ?? null;
  const computerProjectName = target?.projectName ?? catalogProject?.name ?? workspace?.name ?? "Project";
  const pane = useNekoWorkspaceStore((state) => state.sessions[targetId]);
  const close = useNekoWorkspaceStore((state) => state.close);
  const openChange = useNekoWorkspaceStore((state) => state.openChange);
  const openFile = useNekoWorkspaceStore((state) => state.openFile);
  const refresh = useNekoWorkspaceStore((state) => state.refresh);
  const setFollowAgent = useNekoWorkspaceStore((state) => state.setFollowAgent);
  const setPinned = useNekoWorkspaceStore((state) => state.setPinned);
  const setTab = useNekoWorkspaceStore((state) => state.setTab);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [surface, setSurface] = useState<WorkspaceSurface>(requestedSurface);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(() => new Set());
  const listRef = useRef<HTMLDivElement>(null);

  const normalizedQuery = deferredQuery.trim().toLocaleLowerCase();
  const filteredEntries = useMemo(() => {
    if (!pane) return [];
    if (!normalizedQuery) return [];
    return pane.entries.filter((entry) =>
      entry.path.toLocaleLowerCase().includes(normalizedQuery),
    );
  }, [normalizedQuery, pane]);

  const workspaceTree = useMemo(
    () => buildWorkspaceTree(pane?.entries ?? []),
    [pane?.entries],
  );
  const treeRows = useMemo(
    () => flattenWorkspaceTree(workspaceTree, expandedFolders),
    [expandedFolders, workspaceTree],
  );
  const showingSearchResults = normalizedQuery.length > 0;
  const fileRowCount = showingSearchResults ? filteredEntries.length : treeRows.length;
  const visibleRowCount = pane?.activeTab === "changes" ? (pane?.changes.length ?? 0) : fileRowCount;

  const virtualizer = useVirtualizer({
    count: visibleRowCount,
    getScrollElement: () => listRef.current,
    estimateSize: useCallback(
      () => (pane?.activeTab === "files" && showingSearchResults ? 42 : 32),
      [pane?.activeTab, showingSearchResults],
    ),
    overscan: 10,
  });

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [pane?.activeTab, deferredQuery, targetId]);

  useEffect(() => {
    setExpandedFolders(new Set());
    setSurface(requestedSurface);
  }, [requestedSurface, targetId, workspace?.path]);

  useEffect(() => {
    setSurface(requestedSurface);
  }, [requestedSurface]);

  useEffect(() => {
    if (!pane?.selectedPath) return;
    const ancestors = workspaceAncestorPaths(pane.selectedPath);
    setExpandedFolders((current) => {
      const next = new Set(current);
      let changed = false;
      for (const ancestor of ancestors) {
        if (next.has(ancestor)) continue;
        next.add(ancestor);
        changed = true;
      }
      return changed ? next : current;
    });
  }, [pane?.selectedPath]);

  const closePane = () => {
    close(targetId);
    onClose?.();
  };

  const selectSurface = (nextSurface: WorkspaceSurface) => {
    setSurface(nextSurface);
    setTab(targetId, nextSurface === "changes" ? "changes" : "files");
  };

  if (!workspace || !pane || (!pane.open && !exiting)) return null;

  const computerSurface = (mode: "terminal" | "browser" | "computer") =>
    computerProjectId ? (
      <NekoComputerSurface
        mode={mode}
        projectId={computerProjectId}
        projectName={computerProjectName}
        workspace={workspace}
      />
    ) : (
      <div className="grid h-full place-items-center px-8 text-center">
        <div className="max-w-sm">
          <p className="text-[12px] font-medium text-[var(--nk-text)]">Cần gắn phiên này với một Project</p>
          <p className="mt-1 text-[10.5px] leading-5 text-[var(--nk-text-3)]">
            Computer chỉ nhận quyền qua ProjectId ổn định; Wiii không dùng đường dẫn ổ đĩa làm danh tính thay thế.
          </p>
        </div>
      </div>
    );

  const selectedActivity = pane.selectedPath
    ? pane.activities[pane.selectedPath]
    : undefined;
  const selectedActivityLabel = activityLabel(selectedActivity);
  const showResourceNavigator =
    surface === "files" || surface === "preview" || surface === "changes";

  return (
    <aside
      className="nk-workspace-pane flex h-full min-h-0 flex-col bg-[var(--nk-composer)]"
      aria-label={session ? "Workspace của phiên" : "Công cụ Project"}
      data-testid="neko-workspace-pane"
      onKeyDown={(event) => {
        if (event.key !== "Escape" || event.defaultPrevented || event.nativeEvent.isComposing) return;
        if ((event.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return;
        event.preventDefault();
        event.stopPropagation();
        closePane();
      }}
    >
      <header className="nk-surface-toolbar flex h-12 shrink-0 items-center gap-1 border-b border-[var(--nk-border)] px-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[12.5px] font-semibold text-[var(--nk-text)]">
            {workspace.name}
          </h2>
          <p className="truncate text-[10.5px] text-[var(--nk-text-3)]" title={workspace.path}>
            {workspace.path}
          </p>
        </div>
        {showResourceNavigator ? <><button
          type="button"
          aria-label="Theo agent"
          aria-pressed={pane.followAgent}
          title="Tự mở file agent đang thao tác"
          className={`grid h-7 w-7 place-items-center rounded-md transition-colors ${pane.followAgent ? "bg-[var(--nk-overlay-strong)] text-[var(--nk-accent)]" : "text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)]"}`}
          onClick={() => setFollowAgent(targetId, !pane.followAgent)}
        >
          <Radio aria-hidden="true" className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label="Ghim nội dung"
          aria-pressed={pane.pinned}
          title="Không để event mới đổi file đang xem"
          className={`grid h-7 w-7 place-items-center rounded-md transition-colors ${pane.pinned ? "bg-[var(--nk-overlay-strong)] text-[var(--nk-accent)]" : "text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)]"}`}
          onClick={() => setPinned(targetId, !pane.pinned)}
        >
          <Pin aria-hidden="true" className="h-3.5 w-3.5" />
        </button></> : null}
        <button
          type="button"
          aria-label="Làm mới workspace"
          aria-busy={pane.refreshing}
          className="grid h-7 w-7 place-items-center rounded-md text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] disabled:opacity-50"
          disabled={pane.refreshing}
          onClick={() => void refresh(targetId, workspace, { force: true })}
        >
          <RefreshCw aria-hidden="true" className={`h-3.5 w-3.5 ${pane.refreshing ? "animate-spin" : ""}`} />
        </button>
        <button
          type="button"
          aria-label="Đóng workspace"
          className="grid h-7 w-7 place-items-center rounded-md text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
          title="Đóng công cụ (Esc)"
          onClick={closePane}
        >
          <X aria-hidden="true" className="h-3.5 w-3.5" />
        </button>
      </header>

      <nav className="nk-workspace-tabs flex h-11 shrink-0 items-end gap-x-1 overflow-x-auto border-b border-[var(--nk-border)] px-3" aria-label="Công cụ Project">
        {(["changes", "terminal", "browser", "computer", "files"] as const).map((item) => {
          const Icon = item === "changes"
            ? GitCompareArrows
            : item === "terminal"
              ? TerminalSquare
              : item === "browser"
                ? Globe2
                : item === "computer"
                  ? MonitorUp
                : File;
          const label = item === "changes"
            ? "Thay đổi"
            : item === "terminal"
              ? "Terminal"
                : item === "browser"
                  ? "Trình duyệt"
                : item === "computer"
                  ? "Computer"
                : "Tệp";
          return (
            <button
              key={item}
              type="button"
              title={label}
              aria-pressed={surface === item || (item === "files" && surface === "preview")}
              className={`relative flex h-10 shrink-0 items-center gap-1.5 px-2 text-[12px] font-medium transition-colors ${surface === item || (item === "files" && surface === "preview") ? "text-[var(--nk-text)]" : "text-[var(--nk-text-3)] hover:text-[var(--nk-text-2)]"}`}
              onClick={() => selectSurface(item)}
            >
              <Icon aria-hidden="true" className="h-3.5 w-3.5" />
              {label}
              {item === "changes" && pane.changes.length > 0 ? (
                <span className="font-mono text-[9px] text-[var(--nk-ghost)]">
                  {pane.changes.length}
                </span>
              ) : null}
            </button>
          );
        })}
        {pane.unseenChanges > 0 ? (
          <span className="ml-auto mb-2 rounded-md bg-[var(--nk-danger-soft)] px-1.5 py-0.5 text-[9px] font-medium text-[var(--nk-danger)]">
            {pane.unseenChanges} mới
          </span>
        ) : null}
      </nav>

      <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
        {showResourceNavigator ? <section
          className="nk-workspace-navigator absolute inset-y-0 right-0 z-20 flex w-60 min-h-0 flex-col border-l border-[var(--nk-border)] bg-[var(--nk-sidebar)]"
          data-testid={surface === "changes" ? "workspace-changes-navigator" : "workspace-file-navigator"}
        >
          {pane.activeTab === "files" ? (
            <div className="relative m-2 shrink-0">
              <Search aria-hidden="true" className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--nk-ghost)]" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm tệp…"
                aria-label="Tìm tệp trong workspace"
                aria-busy={query !== deferredQuery}
                className="h-7 w-full rounded-md border border-[var(--nk-border)] bg-[var(--nk-composer)] pl-7 pr-2 text-[10.5px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)] focus:border-[var(--nk-border-strong)] focus:ring-2 focus:ring-[var(--nk-focus-soft)]"
              />
            </div>
          ) : null}
          <div ref={listRef} className="min-h-0 flex-1 overflow-auto px-1.5 pb-2">
            {pane.activeTab === "files" ? (
              fileRowCount > 0 ? (
                <div
                  className="relative w-full"
                  style={{ height: virtualizer.getTotalSize() }}
                >
                  {virtualizer.getVirtualItems().map((virtualRow) => {
                    if (!showingSearchResults) {
                      const row = treeRows[virtualRow.index];
                      const entry = row.node.entry;
                      return (
                        <div
                          key={row.node.path}
                          data-index={virtualRow.index}
                          ref={virtualizer.measureElement}
                          className="absolute left-0 top-0 w-full"
                          style={{ transform: `translateY(${virtualRow.start}px)` }}
                        >
                          <TreeRow
                            row={row}
                            expanded={expandedFolders.has(row.node.path)}
                            selected={pane.selectedPath === row.node.path}
                            activity={entry ? pane.activities[entry.path] : undefined}
                            onToggle={() => {
                              setExpandedFolders((current) => {
                                const next = new Set(current);
                                if (next.has(row.node.path)) next.delete(row.node.path);
                                else next.add(row.node.path);
                                return next;
                              });
                            }}
                            onOpen={() => {
                              if (entry) {
                                setSurface("files");
                                void openFile(targetId, workspace, entry.path);
                              }
                            }}
                          />
                        </div>
                      );
                    }

                    const entry = filteredEntries[virtualRow.index];
                    return (
                      <div
                        key={entry.path}
                        data-index={virtualRow.index}
                        ref={virtualizer.measureElement}
                        className="absolute left-0 top-0 w-full"
                        style={{ transform: `translateY(${virtualRow.start}px)` }}
                      >
                        <FileRow
                          entry={entry}
                          selected={pane.selectedPath === entry.path}
                          activity={pane.activities[entry.path]}
                          onClick={() => {
                            setSurface("files");
                            void openFile(targetId, workspace, entry.path);
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="px-2 py-4 text-[10.5px] leading-4 text-[var(--nk-text-3)]">
                  {pane.refreshing ? "Đang đọc cây tệp…" : pane.error ? "Chưa đọc được cây tệp." : "Không tìm thấy tệp phù hợp."}
                </p>
              )
            ) : pane.isGit === false ? (
              <p className="px-2 py-4 text-[10.5px] leading-4 text-[var(--nk-text-3)]">
                Workspace chưa có Git. File agent chạm vẫn xuất hiện trong tab Files.
              </p>
            ) : pane.changes.length ? (
              <div
                className="relative w-full"
                style={{ height: virtualizer.getTotalSize() }}
              >
                {virtualizer.getVirtualItems().map((virtualRow) => {
                  const change = pane.changes[virtualRow.index];
                  return (
                    <div
                      key={change.path}
                      data-index={virtualRow.index}
                      ref={virtualizer.measureElement}
                      className="absolute left-0 top-0 w-full"
                      style={{ transform: `translateY(${virtualRow.start}px)` }}
                    >
                      <button
                        type="button"
                        className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${pane.selectedPath === change.path ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"}`}
                        onClick={() => {
                          setSurface("changes");
                          void openChange(targetId, workspace, change.path);
                        }}
                      >
                        <span className={`mt-0.5 w-3 shrink-0 font-mono text-[9px] font-semibold ${change.status === "deleted" ? "text-[var(--nk-danger)]" : "text-[var(--nk-accent)]"}`}>
                          {change.status === "untracked" ? "U" : change.status === "added" ? "A" : change.status === "deleted" ? "D" : change.status === "renamed" ? "R" : "M"}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-[11px] text-[var(--nk-text-2)]">{change.path}</span>
                        {change.staged ? <span className="text-[8px] text-[var(--nk-ghost)]">staged</span> : null}
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="px-2 py-4 text-[10.5px] leading-4 text-[var(--nk-text-3)]">
                {pane.refreshing ? "Đang kiểm tra thay đổi…" : pane.error ? "Chưa kiểm tra được thay đổi." : "Workspace đang sạch."}
              </p>
            )}
          </div>
          {pane.filesTruncated && pane.activeTab === "files" ? (
            <p className="shrink-0 border-t border-[var(--nk-border)] px-3 py-2 text-[9px] text-[var(--nk-text-3)]">
              Chỉ mục đã đạt giới hạn an toàn. Các đường dẫn bị Git bỏ qua không được quét.
            </p>
          ) : null}
        </section> : null}

        <section
          className={`nk-workspace-content absolute inset-y-0 left-0 flex min-h-0 min-w-0 flex-col overflow-hidden bg-[var(--nk-canvas)] ${showResourceNavigator ? "right-60" : "right-0"}`}
          data-resource-navigator={showResourceNavigator || undefined}
        >
          {pane.selectedPath && (surface === "files" || surface === "changes" || surface === "preview") ? (
            <div className="flex h-9 shrink-0 items-center gap-2 border-b border-[var(--nk-border)] px-3">
              <span className="text-[var(--nk-text-3)]">{fileIcon(pane.selectedPath, pane.selectedFile?.kind)}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[10.5px] text-[var(--nk-text-2)]">{pane.selectedPath}</span>
              {selectedActivityLabel ? <span className="text-[9px] text-[var(--nk-accent)]">{selectedActivityLabel}</span> : null}
              {pane.selectedFile && canPreview(pane.selectedFile) ? (
                <div className="flex rounded-md bg-[var(--nk-inset)] p-0.5">
                  <button type="button" aria-label="Xem mã" className={`grid h-6 w-6 place-items-center rounded ${surface === "files" ? "bg-[var(--nk-composer)] text-[var(--nk-text)] shadow-sm" : "text-[var(--nk-text-3)] hover:text-[var(--nk-text)]"}`} onClick={() => selectSurface("files")}><Code2 aria-hidden="true" className="h-3 w-3" /></button>
                  <button type="button" aria-label="Xem trước" className={`grid h-6 w-6 place-items-center rounded ${surface === "preview" ? "bg-[var(--nk-composer)] text-[var(--nk-text)] shadow-sm" : "text-[var(--nk-text-3)] hover:text-[var(--nk-text)]"}`} onClick={() => selectSurface("preview")}><Eye aria-hidden="true" className="h-3 w-3" /></button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="min-h-0 flex-1">
            {showResourceNavigator && pane.loading ? (
              <div className="grid h-full place-items-center" role="status">
                <span className="flex items-center gap-2 text-[11px] text-[var(--nk-text-3)]"><LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />Đang mở nội dung…</span>
              </div>
            ) : showResourceNavigator && pane.error ? (
              <div className="grid h-full overflow-auto p-5 text-center" role="alert">
                <div className="w-full min-w-0 max-w-sm">
                  <p className="text-[13px] font-medium text-[var(--nk-text)]">Chưa thể đọc nội dung workspace</p>
                  <p className="mt-2 text-[12px] leading-5 text-[var(--nk-text-3)]">Bạn có thể thử lại hoặc chuyển sang công cụ khác.</p>
                  <button
                    type="button"
                    className="mt-4 inline-flex h-8 items-center gap-2 rounded-lg border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] px-3 text-[12px] text-[var(--nk-text)] hover:bg-[var(--nk-raised)] disabled:opacity-50"
                    disabled={pane.refreshing}
                    onClick={() => {
                      if (pane.selectedPath) {
                        void (surface === "changes" ? openChange : openFile)(targetId, workspace, pane.selectedPath);
                      } else void refresh(targetId, workspace, { force: true });
                    }}
                  >
                    <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
                    Thử đọc lại
                  </button>
                  <details className="mt-4 text-left text-[11px] leading-5 text-[var(--nk-text-3)]">
                    <summary className="cursor-pointer text-center">Chi tiết kỹ thuật</summary>
                    <p className="mt-2 break-words [overflow-wrap:anywhere]">{pane.error}</p>
                  </details>
                </div>
              </div>
            ) : surface === "terminal" ? (
              computerSurface("terminal")
            ) : surface === "browser" ? (
              computerSurface("browser")
            ) : surface === "computer" ? (
              computerSurface("computer")
            ) : surface === "preview" ? (
              <BrowserSurface
                sessionId={sessionId}
                file={pane.selectedFile}
                workspacePath={workspace.path}
              />
            ) : surface === "changes" && pane.selectedDiff ? (
              pane.selectedDiff.binary ? (
                <div className="grid h-full place-items-center text-[11px] text-[var(--nk-text-3)]">Diff nhị phân không thể hiển thị an toàn.</div>
              ) : (
                <Suspense fallback={<SurfaceLoading label="Đang mở trình so sánh…" />}>
                  <MonacoDiffEditor
                    original={pane.selectedDiff.original}
                    modified={pane.selectedDiff.modified}
                    language={pane.selectedDiff.language}
                    theme={document.documentElement.classList.contains("dark") ? "vs-dark" : "light"}
                    options={{ readOnly: true, domReadOnly: true, automaticLayout: true, minimap: { enabled: false }, renderSideBySide: true, wordWrap: "on" }}
                  />
                </Suspense>
              )
            ) : surface === "files" && pane.selectedFile ? (
              pane.selectedFile.content !== null ? (
                <Suspense fallback={<SurfaceLoading label="Đang mở trình soạn thảo…" />}>
                  <MonacoEditor
                    value={pane.selectedFile.content}
                    language={pane.selectedFile.language}
                    theme={document.documentElement.classList.contains("dark") ? "vs-dark" : "light"}
                    options={WORKSPACE_CODE_EDITOR_OPTIONS}
                  />
                </Suspense>
              ) : (
                <FilePreview file={pane.selectedFile} workspacePath={workspace.path} />
              )
            ) : surface === "files" ? (
              <div className="grid h-full place-items-center px-8">
                <WorkspaceLauncher onSelect={selectSurface} />
              </div>
            ) : (
              <EmptyContent tab={surface === "changes" ? "changes" : "files"} />
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}

export const NekoWorkspacePane = memo(NekoWorkspacePaneComponent);

function SurfaceLoading({ label }: { label: string }) {
  return (
    <div className="grid h-full place-items-center" role="status">
      <span className="flex items-center gap-2 text-[11px] text-[var(--nk-text-3)]">
        <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
        {label}
      </span>
    </div>
  );
}
