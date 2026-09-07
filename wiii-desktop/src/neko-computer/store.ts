import { create } from "zustand";
import {
  acquireComputerSeat,
  doctorComputer,
  ensureComputer,
  executeComputerTerminal,
  grantCoworkerProject,
  hasNativeComputerAuthority,
  navigateComputerBrowser,
  observeComputerSemantics,
  removeComputer,
  removeComputerPackage,
  releaseComputerSeat,
  resetComputer,
  resolveCoworkerComputer,
  resumeComputer,
  revokeCoworkerProject,
  subscribeComputerSeatChanges,
  suspendComputer,
} from "./client";
import type {
  ComputerDisplaySeat,
  ComputerDoctor,
  ComputerEnvironment,
  ComputerProjectRef,
  ComputerResourcePreset,
  ComputerSemanticSnapshot,
  ComputerTerminalResult,
  CoworkerComputerStatus,
} from "./contracts";
import { LOCAL_WIII_OPERATOR_ID } from "@/neko/coworker-profile";

export interface ProjectComputerState {
  environment: ComputerEnvironment | null;
  semanticSnapshot: ComputerSemanticSnapshot | null;
  semanticError: string | null;
  loading: boolean;
  mutating: boolean;
  error: string | null;
}

interface NekoComputerState {
  doctor: ComputerDoctor | null;
  status: CoworkerComputerStatus | null;
  projects: Record<string, ProjectComputerState>;
  refresh: () => Promise<CoworkerComputerStatus>;
  hydrate: (project: ComputerProjectRef) => Promise<void>;
  grant: (project: ComputerProjectRef) => Promise<void>;
  revoke: (project: ComputerProjectRef) => Promise<void>;
  ensure: (project: ComputerProjectRef, preset?: ComputerResourcePreset) => Promise<void>;
  suspend: (project: ComputerProjectRef) => Promise<void>;
  resume: (project: ComputerProjectRef) => Promise<void>;
  reset: (project: ComputerProjectRef, confirmation: string) => Promise<void>;
  remove: (project: ComputerProjectRef, confirmation: string) => Promise<void>;
  removePackage: (project: ComputerProjectRef) => Promise<void>;
  takeControl: (project: ComputerProjectRef) => Promise<void>;
  handBack: (project: ComputerProjectRef) => Promise<void>;
  execute: (project: ComputerProjectRef, command: string) => Promise<ComputerTerminalResult>;
  navigate: (project: ComputerProjectRef, url: string) => Promise<void>;
  observeSemantics: (project: ComputerProjectRef) => Promise<ComputerSemanticSnapshot>;
}

export function computerProjectKey(projectId: string): string {
  const key = projectId.trim();
  if (!key) throw new Error("Computer requires a stable Wiii Project identity.");
  return key;
}

function emptyProject(): ProjectComputerState {
  return {
    environment: null,
    semanticSnapshot: null,
    semanticError: null,
    loading: false,
    mutating: false,
    error: null,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function projectStatesForCoworkerStatus(
  current: Record<string, ProjectComputerState>,
  status: CoworkerComputerStatus,
  ensureProjectId?: string,
): Record<string, ProjectComputerState> {
  const projects = { ...current };
  if (ensureProjectId) {
    const key = computerProjectKey(ensureProjectId);
    projects[key] ??= emptyProject();
  }
  const activeKey = status.activeProjectId
    ? computerProjectKey(status.activeProjectId)
    : null;
  for (const [key, project] of Object.entries(projects)) {
    projects[key] = {
      ...project,
      environment: activeKey === key ? status.environment : null,
      loading: false,
    };
  }
  return projects;
}

export function projectStatesWithComputerSeat(
  current: Record<string, ProjectComputerState>,
  environmentId: string,
  seat: ComputerDisplaySeat,
): Record<string, ProjectComputerState> {
  let changed = false;
  const projects = Object.fromEntries(
    Object.entries(current).map(([key, project]) => {
      if (project.environment?.environmentId !== environmentId) {
        return [key, project];
      }
      changed = true;
      return [key, {
        ...project,
        environment: { ...project.environment, seat },
      }];
    }),
  );
  return changed ? projects : current;
}

export const useNekoComputerStore = create<NekoComputerState>((set, get) => {
  const update = (project: ComputerProjectRef, patch: Partial<ProjectComputerState>) =>
    set((state) => {
      const key = computerProjectKey(project.projectId);
      return {
        projects: {
          ...state.projects,
          [key]: { ...(state.projects[key] ?? emptyProject()), ...patch },
        },
      };
    });

  const applyStatus = (status: CoworkerComputerStatus, ensureProjectId?: string) =>
    set((state) => ({
      status,
      projects: projectStatesForCoworkerStatus(state.projects, status, ensureProjectId),
    }));

  const refresh = async (): Promise<CoworkerComputerStatus> => {
    const status = await resolveCoworkerComputer();
    applyStatus(status);
    return status;
  };

  const environmentFor = (project: ComputerProjectRef): ComputerEnvironment => {
    const status = get().status;
    if (status?.activeProjectId !== project.projectId || !status.environment) {
      throw new Error("Project này chưa được mở trong máy làm việc của Neko.");
    }
    return status.environment;
  };

  const mutate = async (
    project: ComputerProjectRef,
    operation: (environment: ComputerEnvironment) => Promise<ComputerEnvironment>,
  ) => {
    update(project, { mutating: true, error: null });
    try {
      const environment = await operation(environmentFor(project));
      set((state) => ({
        status: state.status
          ? {
              ...state.status,
              environment,
              activeProjectId: environment.projectId,
              activeProjectPath: environment.projectPath,
            }
          : state.status,
      }));
      update(project, { environment, mutating: false });
    } catch (error) {
      update(project, { mutating: false, error: errorMessage(error) });
      throw error;
    }
  };

  return {
    doctor: null,
    status: null,
    projects: {},
    refresh,

    hydrate: async (project) => {
      if (!hasNativeComputerAuthority()) {
        update(project, { loading: false, error: "Computer chỉ hoạt động trong Wiii Desktop." });
        return;
      }
      update(project, { loading: true, error: null });
      try {
        const [doctor, status] = await Promise.all([
          doctorComputer(),
          resolveCoworkerComputer(),
        ]);
        set({ doctor });
        applyStatus(status, project.projectId);
      } catch (error) {
        update(project, { loading: false, error: errorMessage(error) });
      }
    },

    grant: async (project) => {
      update(project, { mutating: true, error: null });
      try {
        await grantCoworkerProject(project);
        applyStatus(await resolveCoworkerComputer(), project.projectId);
        update(project, { mutating: false });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    revoke: async (project) => {
      update(project, { mutating: true, error: null });
      try {
        await revokeCoworkerProject(project.projectId);
        applyStatus(await resolveCoworkerComputer(), project.projectId);
        update(project, {
          environment: null,
          semanticSnapshot: null,
          semanticError: null,
          mutating: false,
        });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    ensure: async (project, resourcePreset = "auto") => {
      update(project, { mutating: true, error: null });
      try {
        await ensureComputer(project, resourcePreset);
        const [doctor, status] = await Promise.all([
          doctorComputer(),
          resolveCoworkerComputer(),
        ]);
        set({ doctor });
        applyStatus(status, project.projectId);
        update(project, { mutating: false });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    suspend: (project) =>
      mutate(project, ({ environmentId }) => suspendComputer(environmentId)),
    resume: (project) =>
      mutate(project, ({ environmentId }) => resumeComputer(environmentId)),
    reset: (project, confirmation) =>
      mutate(project, ({ environmentId }) => resetComputer(environmentId, confirmation)),

    remove: async (project, confirmation) => {
      const environment = environmentFor(project);
      update(project, { mutating: true, error: null });
      try {
        await removeComputer(environment.environmentId, confirmation);
        const [doctor, status] = await Promise.all([
          doctorComputer(),
          resolveCoworkerComputer(),
        ]);
        set({ doctor });
        applyStatus(status, project.projectId);
        update(project, {
          environment: null,
          semanticSnapshot: null,
          semanticError: null,
          mutating: false,
        });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    removePackage: async (project) => {
      update(project, { mutating: true, error: null });
      try {
        const doctor = await removeComputerPackage();
        const status = await resolveCoworkerComputer();
        set({ doctor });
        applyStatus(status, project.projectId);
        update(project, { mutating: false });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    takeControl: async (project) => {
      const environment = environmentFor(project);
      update(project, { mutating: true, error: null });
      try {
        const seat = await acquireComputerSeat(
          environment.environmentId,
          LOCAL_WIII_OPERATOR_ID,
          true,
        );
        const next = { ...environment, seat };
        set((state) => ({
          status: state.status ? { ...state.status, environment: next } : state.status,
        }));
        update(project, { environment: next, mutating: false });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    handBack: async (project) => {
      const environment = environmentFor(project);
      if (!environment.seat.leaseId) return;
      update(project, { mutating: true, error: null });
      try {
        const seat = await releaseComputerSeat(
          environment.environmentId,
          environment.seat.leaseId,
        );
        const next = { ...environment, seat };
        set((state) => ({
          status: state.status ? { ...state.status, environment: next } : state.status,
        }));
        update(project, { environment: next, mutating: false });
      } catch (error) {
        update(project, { mutating: false, error: errorMessage(error) });
        throw error;
      }
    },

    execute: async (project, command) =>
      executeComputerTerminal(environmentFor(project).environmentId, command),

    navigate: async (project, url) => {
      await navigateComputerBrowser(environmentFor(project).environmentId, url);
    },

    observeSemantics: async (project) => {
      try {
        const snapshot = await observeComputerSemantics(
          environmentFor(project).environmentId,
        );
        update(project, { semanticSnapshot: snapshot, semanticError: null });
        return snapshot;
      } catch (error) {
        update(project, { semanticError: errorMessage(error) });
        throw error;
      }
    },
  };
});

const unsubscribeComputerSeatChanges = subscribeComputerSeatChanges(
  ({ environmentId, seat }) => {
    useNekoComputerStore.setState((state) => {
      const statusEnvironment = state.status?.environment;
      return {
        status: state.status && statusEnvironment?.environmentId === environmentId
          ? {
              ...state.status,
              environment: { ...statusEnvironment, seat },
            }
          : state.status,
        projects: projectStatesWithComputerSeat(state.projects, environmentId, seat),
      };
    });
  },
);

if (import.meta.hot) {
  import.meta.hot.dispose(unsubscribeComputerSeatChanges);
}
