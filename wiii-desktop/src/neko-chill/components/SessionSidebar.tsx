import { memo, useDeferredValue, useMemo, useState, type ReactNode } from "react";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  History,
  LayoutDashboard,
  MonitorCog,
  MoreHorizontal,
  PlugZap,
  Plus,
  Search,
  X,
} from "lucide-react";
import type { NekoProject } from "../stores/neko-project-store";
import { projectForSession } from "../stores/neko-project-store";
import {
  useNekoSessionStore,
  type NekoSession,
} from "../stores/neko-session-store";
import { sessionStatusDotClass } from "../session-catalog";
import { useNekoSessionCatalog } from "../hooks/useNekoSessionCatalog";

interface ProjectProjection {
  project: NekoProject;
  sessions: NekoSession[];
}

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi")
    .trim();
}

export const SessionSidebar = memo(function SessionSidebar({
  header,
  overviewActive,
  coworkerActive,
  projects,
  selectedProjectId,
  externalSessionCount,
  onShowOverview,
  onShowCoworker,
  onShowConnections,
  onNewSession,
  onCreateProject,
  onSelectProject,
  onEditProject,
  onOpenSession,
}: {
  header?: ReactNode;
  overviewActive: boolean;
  coworkerActive: boolean;
  projects: NekoProject[];
  selectedProjectId: string | null;
  externalSessionCount: number;
  onShowOverview: () => void;
  onShowCoworker: () => void;
  onShowConnections: () => void;
  onNewSession: () => void;
  onCreateProject: () => void;
  onSelectProject: (projectId: string) => void;
  onEditProject: (projectId: string) => void;
  onOpenSession: (sessionId: string, projectId: string | null) => void;
}) {
  const sessions = useNekoSessionCatalog();
  const activeSessionId = useNekoSessionStore((state) => state.activeSessionId);
  const deleteSession = useNekoSessionStore((state) => state.deleteSession);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  const { projectRows, legacySessions } = useMemo(() => {
    const term = normalize(deferredQuery);
    const sessionsByProject = new Map<string, NekoSession[]>();
    const unassigned: NekoSession[] = [];
    for (const session of sessions) {
      const project = projectForSession(projects, session);
      if (!project) {
        unassigned.push(session);
        continue;
      }
      const bucket = sessionsByProject.get(project.id);
      if (bucket) bucket.push(session);
      else sessionsByProject.set(project.id, [session]);
    }

    const rows: ProjectProjection[] = projects.flatMap((project) => {
      const all = (sessionsByProject.get(project.id) ?? [])
        .sort((left, right) => right.updatedAt - left.updatedAt);
      const projectMatch = !term || normalize([
        project.name,
        ...project.roots.flatMap((root) => [root.name, root.path]),
      ].join(" ")).includes(term);
      const matching = !term || projectMatch
        ? all
        : all.filter((session) => normalize([
            session.title,
            session.agentName,
            session.workspace?.name ?? "",
            session.workspace?.path ?? "",
          ].join(" ")).includes(term));
      if (term && !projectMatch && matching.length === 0) return [];
      return [{ project, sessions: matching }];
    });

    const legacy = unassigned
      .filter((session) => !term || normalize([
        session.title,
        session.agentName,
        session.workspace?.name ?? "",
        session.workspace?.path ?? "",
      ].join(" ")).includes(term))
      .sort((left, right) => right.updatedAt - left.updatedAt);

    return { projectRows: rows, legacySessions: legacy };
  }, [deferredQuery, projects, sessions]);
  const searching = deferredQuery.trim().length > 0;

  const renderSession = (session: NekoSession, projectId: string | null) => (
    <div
      key={session.id}
      className={`nk-session-row group flex h-8 items-center rounded-md pl-7 pr-1 transition-colors ${
        session.id === activeSessionId
          ? "bg-[var(--nk-item-active)]"
          : "hover:bg-[var(--nk-overlay)]"
      }`}
    >
      <button
        type="button"
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
        aria-current={session.id === activeSessionId ? "page" : undefined}
        aria-label={`Mở phiên ${session.title}`}
        onClick={() => onOpenSession(session.id, projectId)}
      >
        <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${sessionStatusDotClass(session)}`} />
        <span className="min-w-0 flex-1 truncate text-[12.5px] text-[var(--nk-text)]">{session.title}</span>
        <span className="max-w-[68px] shrink-0 truncate text-[9.5px] text-[var(--nk-ghost)]">{session.agentName}</span>
      </button>
      <button
        type="button"
        className="nk-row-action rounded p-1 text-[var(--nk-ghost)] transition-colors hover:text-[var(--nk-danger)]"
        title="Xoá phiên"
        aria-label={`Xoá phiên ${session.title}`}
        onClick={() => void deleteSession(session.id)}
      >
        <X aria-hidden="true" className="h-3 w-3" />
      </button>
    </div>
  );

  return (
    <aside className="flex w-[292px] shrink-0 flex-col border-r border-[var(--nk-border)] bg-[var(--nk-sidebar)]" data-testid="session-sidebar">
      <div className="flex h-12 shrink-0 items-center justify-between px-3" data-testid="sidebar-header">
        {header ?? <span className="text-[15px] font-semibold text-[var(--nk-text)]">Wiii</span>}
      </div>

      <div className="px-2 pb-2">
        <button
          type="button"
          className={`flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[12.5px] font-medium transition-colors ${overviewActive ? "bg-[var(--nk-item-active)] text-[var(--nk-text)]" : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"}`}
          aria-current={overviewActive ? "page" : undefined}
          onClick={onShowOverview}
          data-testid="neko-overview-link"
        >
          <LayoutDashboard aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
          Tổng quan
          {externalSessionCount ? <span className="ml-auto text-[9.5px] font-normal tabular-nums text-[var(--nk-ghost)]">{externalSessionCount} ngoài Wiii</span> : null}
        </button>
        <button
          type="button"
          className={`mt-0.5 flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[12.5px] font-medium transition-colors ${coworkerActive ? "bg-[var(--nk-item-active)] text-[var(--nk-text)]" : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"}`}
          aria-current={coworkerActive ? "page" : undefined}
          onClick={onShowCoworker}
          data-testid="neko-coworker-link"
        >
          <MonitorCog aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
          Neko · Đồng nghiệp AI
        </button>
        <button
          type="button"
          className="mt-0.5 flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[12.5px] font-medium text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
          onClick={onShowConnections}
          data-testid="neko-connections-link"
        >
          <PlugZap aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
          Kết nối
          <span className="ml-auto text-[9.5px] font-normal text-[var(--nk-ghost)]">Tài khoản</span>
        </button>
        <button
          type="button"
          className="mt-0.5 flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[12.5px] font-medium text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
          onClick={onNewSession}
          data-testid="new-session"
        >
          <Plus aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
          Phiên mới
        </button>
        <label className="nk-input-field mt-1.5 flex h-8 items-center gap-2 rounded-lg bg-[var(--nk-inset)] px-2.5 text-[var(--nk-text-3)]">
          <Search aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-w-0 flex-1 bg-transparent text-[12px] text-[var(--nk-text)] placeholder:text-[var(--nk-ghost)] focus:outline-none"
            placeholder="Lọc cây dự án…"
            aria-label="Tìm phiên Neko Chill"
            aria-busy={query !== deferredQuery}
          />
          {query ? (
            <button type="button" aria-label="Xoá tìm kiếm" className="rounded p-0.5 hover:bg-[var(--nk-overlay)]" onClick={() => setQuery("")}>
              <X aria-hidden="true" className="h-3 w-3" />
            </button>
          ) : null}
        </label>
      </div>

      <div className="flex h-8 items-center justify-between px-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--nk-ghost)]">
        <span>Projects</span>
        <button
          type="button"
          className="grid h-6 w-6 place-items-center rounded-md transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
          aria-label="Tạo Project"
          title="Tạo Project"
          onClick={onCreateProject}
        >
          <Plus aria-hidden="true" className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="nk-scroll-surface min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {projectRows.length === 0 && legacySessions.length === 0 ? (
          <p className="px-2.5 py-3 text-[12px] leading-5 text-[var(--nk-text-3)]">
            {searching ? "Không tìm thấy phiên hoặc Project phù hợp." : "Chưa có Project. Nhấn + để thêm thư mục đầu tiên."}
          </p>
        ) : (
          <div className="space-y-1" data-testid="project-session-tree">
            {projectRows.map(({ project, sessions: projectSessions }) => {
              const isCollapsed = collapsed.has(project.id) && !searching;
              const selected = selectedProjectId === project.id && !activeSessionId;
              const visibleSessions = projectSessions.slice(0, searching ? 50 : 7);
              return (
                <section className="nk-project-section" key={project.id} data-testid={`project-${project.id}`}>
                  <div className={`group flex h-8 items-center rounded-lg transition-colors ${selected ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"}`}>
                    <button
                      type="button"
                      className="grid h-8 w-6 shrink-0 place-items-center text-[var(--nk-text-3)]"
                      aria-label={`${isCollapsed ? "Mở" : "Thu gọn"} Project ${project.name}`}
                      aria-expanded={!isCollapsed}
                      onClick={() => setCollapsed((current) => {
                        const next = new Set(current);
                        if (next.has(project.id)) next.delete(project.id);
                        else next.add(project.id);
                        return next;
                      })}
                    >
                      {isCollapsed ? <ChevronRight aria-hidden="true" className="h-3 w-3" /> : <ChevronDown aria-hidden="true" className="h-3 w-3" />}
                    </button>
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                      aria-current={selected ? "page" : undefined}
                      aria-label={`${project.name} ${projectSessions.length}`}
                      onClick={() => onSelectProject(project.id)}
                    >
                      <Folder aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[var(--nk-text-3)]" />
                      <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-[var(--nk-text-2)]">{project.name}</span>
                      <span className="text-[9.5px] tabular-nums text-[var(--nk-ghost)]">{projectSessions.length}</span>
                    </button>
                    <button
                      type="button"
                      className="nk-row-action mr-1 grid h-6 w-6 place-items-center rounded-md text-[var(--nk-ghost)] transition-colors hover:bg-[var(--nk-raised)] hover:text-[var(--nk-text)]"
                      aria-label={`Chỉnh sửa Project ${project.name}`}
                      onClick={() => onEditProject(project.id)}
                    >
                      <MoreHorizontal aria-hidden="true" className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  {!isCollapsed ? (
                    <div className="space-y-px pb-1">
                      {visibleSessions.map((session) => renderSession(session, project.id))}
                      {projectSessions.length === 0 ? <p className="py-1 pl-8 text-[10.5px] text-[var(--nk-ghost)]">Chưa có phiên</p> : null}
                      {projectSessions.length > visibleSessions.length ? (
                        <button type="button" className="ml-7 rounded-md px-2 py-1 text-[10.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]" onClick={onShowOverview}>
                          Xem tất cả {projectSessions.length} phiên
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              );
            })}

            {legacySessions.length ? (
              <section>
                <div className="flex h-8 items-center gap-2 px-2 text-[12px] text-[var(--nk-text-3)]">
                  <History aria-hidden="true" className="h-3.5 w-3.5" />
                  <span className="min-w-0 flex-1 truncate">Legacy · Chưa gắn Project</span>
                  <span className="text-[9.5px] tabular-nums text-[var(--nk-ghost)]">{legacySessions.length}</span>
                </div>
                {legacySessions.slice(0, searching ? 50 : 6).map((session) => renderSession(session, null))}
              </section>
            ) : null}
          </div>
        )}
      </div>

      <div className="border-t border-[var(--nk-border)] px-3 py-2 text-[10.5px] text-[var(--nk-ghost)]">
        {projects.length} Project · {sessions.length} phiên Wiii
      </div>
    </aside>
  );
});
