/**
 * Code Studio store — manages streaming code sessions with versioning.
 *
 * Receives code_open → code_delta × N → code_complete SSE events
 * and accumulates code for the CodeStudioPanel to render.
 *
 * Metadata fields (studioLane, artifactKind, qualityProfile, rendererContract)
 * are session-level — set once on code_open, immutable across versions.
 * Backend uses code_studio_context.active_session for quality/session decisions.
 */
import { create } from "zustand";
import type { VisualPayload } from "@/api/types";

/** Metadata from backend code_open/code_complete events — session-level, not per-version. */
export interface CodeStudioMetadata {
  studioLane?: string;
  artifactKind?: string;
  qualityProfile?: string;
  rendererContract?: string;
  requestedView?: "code" | "preview";
}

export interface CodeVersion {
  version: number;
  code: string;
  title: string;
  timestamp: number;
  visualPayload?: VisualPayload;
}

export interface CodeStudioSession {
  sessionId: string;
  title: string;
  language: string;
  status: "streaming" | "complete" | "error";
  code: string;
  versions: CodeVersion[];
  activeVersion: number;
  chunkCount: number;
  totalBytes: number;
  visualPayload?: VisualPayload;
  /** Maps this streaming session to the visual_open session ID for frontend unification */
  visualSessionId?: string;
  createdAt: number;
  /** Session-level metadata from backend — immutable across versions */
  metadata: CodeStudioMetadata;
}

interface CodeStudioState {
  activeSessionId: string | null;
  sessions: Record<string, CodeStudioSession>;

  openSession: (sessionId: string, title: string, language: string, version: number, metadata?: CodeStudioMetadata) => void;
  appendCode: (sessionId: string, chunk: string, chunkIndex: number, totalBytes: number) => void;
  completeSession: (sessionId: string, fullCode: string, language: string, version: number, visualPayload?: VisualPayload, visualSessionId?: string) => void;
  switchVersion: (sessionId: string, version: number) => void;
  setActiveSession: (sessionId: string | null) => void;
  setRequestedView: (sessionId: string, requestedView?: "code" | "preview") => void;
  /** Serialize active session info for backend context injection */
  getActiveSessionContext: () => Record<string, unknown> | undefined;
  clearSessions: () => void;
}

export const useCodeStudioStore = create<CodeStudioState>((set, get) => ({
  activeSessionId: null,
  sessions: {},

  openSession: (sessionId, title, language, version, meta) =>
    set((state) => {
      const existing = state.sessions[sessionId];
      if (existing && existing.status === "complete") {
        return {
          activeSessionId: sessionId,
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...existing,
              status: "streaming" as const,
              code: "",
              chunkCount: 0,
              totalBytes: 0,
              title,
              language,
              activeVersion: version,
              // Merge backend metadata with any local UI preference like requestedView.
              metadata: { ...existing.metadata, ...(meta || {}) },
            },
          },
        };
      }
      return {
        activeSessionId: sessionId,
        sessions: {
          ...state.sessions,
          [sessionId]: {
            sessionId,
            title,
            language,
            status: "streaming" as const,
            code: "",
            versions: [],
            activeVersion: version,
            chunkCount: 0,
            totalBytes: 0,
            createdAt: Date.now(),
            metadata: meta || {},
          },
        },
      };
    }),

  appendCode: (sessionId, chunk, chunkIndex, totalBytes) =>
    set((state) => {
      const session = state.sessions[sessionId];
      if (!session || session.status !== "streaming") return state;
      return {
        sessions: {
          ...state.sessions,
          [sessionId]: {
            ...session,
            code: session.code + chunk,
            chunkCount: chunkIndex + 1,
            totalBytes,
          },
        },
      };
    }),

  completeSession: (sessionId, fullCode, language, version, visualPayload, visualSessionId) =>
    set((state) => {
      const session = state.sessions[sessionId];
      if (!session) return state;
      const newVersion: CodeVersion = {
        version,
        code: fullCode,
        title: session.title,
        timestamp: Date.now(),
        visualPayload,
      };
      const existingVersions = session.versions.filter((v) => v.version !== version);
      return {
        sessions: {
          ...state.sessions,
          [sessionId]: {
            ...session,
            status: "complete" as const,
            code: fullCode,
            language,
            activeVersion: version,
            versions: [...existingVersions, newVersion],
            visualPayload,
            // Store visual_session_id mapping so CodeStudioCard can link to VisualBlock
            ...(visualSessionId ? { visualSessionId } : {}),
          },
        },
      };
    }),

  switchVersion: (sessionId, version) =>
    set((state) => {
      const session = state.sessions[sessionId];
      if (!session) return state;
      const target = session.versions.find((v) => v.version === version);
      if (!target) return state;
      return {
        sessions: {
          ...state.sessions,
          [sessionId]: {
            ...session,
            activeVersion: version,
            code: target.code,
            visualPayload: target.visualPayload,
          },
        },
      };
    }),

  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

  setRequestedView: (sessionId, requestedView) =>
    set((state) => {
      const session = state.sessions[sessionId];
      if (!session) return state;
      return {
        sessions: {
          ...state.sessions,
          [sessionId]: {
            ...session,
            metadata: {
              ...session.metadata,
              requestedView,
            },
          },
        },
      };
    }),

  getActiveSessionContext: () => {
    const { activeSessionId, sessions } = get();
    if (!activeSessionId) return undefined;
    const session = sessions[activeSessionId];
    if (!session) return undefined;
    return {
      active_session: {
        session_id: session.sessionId,
        title: session.title,
        status: session.status,
        active_version: session.activeVersion,
        version_count: session.versions.length,
        language: session.language,
          studio_lane: session.metadata.studioLane,
          artifact_kind: session.metadata.artifactKind,
          quality_profile: session.metadata.qualityProfile,
          renderer_contract: session.metadata.rendererContract,
          requested_view: session.metadata.requestedView,
          has_preview: Boolean(session.visualPayload),
        },
        requested_view: session.metadata.requestedView,
      };
    },

  clearSessions: () => set({ activeSessionId: null, sessions: {} }),
}));
