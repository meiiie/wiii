/**
 * Code Studio store — manages streaming code sessions with versioning.
 *
 * Receives code_open → code_delta × N → code_complete SSE events
 * and accumulates code for the CodeStudioPanel to render.
 */
import { create } from "zustand";
import type { VisualPayload } from "@/api/types";

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
  code: string; // accumulated from deltas
  versions: CodeVersion[];
  activeVersion: number;
  chunkCount: number;
  totalBytes: number;
  visualPayload?: VisualPayload;
  createdAt: number;
}

interface CodeStudioState {
  /** Active session being displayed in the panel */
  activeSessionId: string | null;
  /** All sessions keyed by sessionId */
  sessions: Record<string, CodeStudioSession>;

  // Actions
  openSession: (sessionId: string, title: string, language: string, version: number) => void;
  appendCode: (sessionId: string, chunk: string, chunkIndex: number, totalBytes: number) => void;
  completeSession: (sessionId: string, fullCode: string, language: string, version: number, visualPayload?: VisualPayload) => void;
  switchVersion: (sessionId: string, version: number) => void;
  setActiveSession: (sessionId: string | null) => void;
  clearSessions: () => void;
}

export const useCodeStudioStore = create<CodeStudioState>((set) => ({
  activeSessionId: null,
  sessions: {},

  openSession: (sessionId, title, language, version) =>
    set((state) => {
      const existing = state.sessions[sessionId];
      if (existing && existing.status === "complete") {
        // New version for existing session — reset streaming state
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
            },
          },
        };
      }
      // Brand new session
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

  completeSession: (sessionId, fullCode, language, version, visualPayload) =>
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
      // Append version (avoid duplicates)
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

  clearSessions: () => set({ activeSessionId: null, sessions: {} }),
}));
