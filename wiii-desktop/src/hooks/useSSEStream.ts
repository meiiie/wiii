/**
 * SSE streaming hook — connects chat store to SSE parser.
 * Sprint 150: StreamBuffer integration for smooth token rendering.
 */
import { useCallback, useRef } from "react";
import { sendMessageStream } from "@/api/chat";
import { initClient } from "@/api/client";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useDomainStore } from "@/stores/domain-store";
import { useOrgStore } from "@/stores/org-store";
import { useContextStore } from "@/stores/context-store";
import { useCharacterStore } from "@/stores/character-store";
import { usePageContextStore } from "@/stores/page-context-store";
import { useHostContextStore } from "@/stores/host-context-store";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import { useUIStore } from "@/stores/ui-store";
import { StreamBuffer } from "@/lib/stream-buffer";
import { trackVisualTelemetry } from "@/lib/visual-telemetry";
import type { SSEEventHandler } from "@/api/sse";
import type {
  AggregationSummary,
  ArtifactType,
  ChatResponseMetadata,
  DisplayPresentationMeta,
  ImageInput,
  MoodType,
  PreviewType,
} from "@/api/types";

const MAX_SSE_RETRIES = 3;
const SSE_BACKOFF_MS = 1000; // 1s, 2s, 4s
const SSE_IDLE_TIMEOUT_MS = 30_000;
const IDLE_TIMEOUT_ABORT_REASON = "stream_idle_timeout";
const STREAM_RESTART_ABORT_REASON = "stream_restart";
const USER_CANCEL_ABORT_REASON = "user_cancel";
const TRACE_SSE = import.meta.env.DEV;

// Sprint 147: Track think tool IDs to skip their results
const _thinkToolIds = new Set<string>();

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Sprint 165: Map error types to Vietnamese-specific messages. */
function _getVietnameseErrorMessage(err: unknown): string {
  if (err instanceof TypeError && err.message.includes("fetch")) {
    return "Mất kết nối với máy chủ. Vui lòng kiểm tra kết nối mạng.";
  }
  if (err instanceof DOMException && err.name === "TimeoutError") {
    return "Phản hồi quá lâu. Vui lòng thử lại.";
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    return "Đã hủy yêu cầu.";
  }
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes("500") || msg.includes("Internal")) {
    return "Lỗi xử lý nội bộ. Wiii đang khắc phục...";
  }
  if (msg.includes("429") || msg.includes("rate")) {
    return "Quá nhiều yêu cầu. Vui lòng đợi một chút.";
  }
  return "Mất kết nối. Vui lòng thử lại.";
}

/**
 * Sprint 164: Extract agent names from parallel dispatch status content.
 * Examples: "Triển khai song song: rag, tutor" → ["rag", "tutor"]
 *           "Dispatching: rag_agent, tutor_agent" → ["rag_agent", "tutor_agent"]
 */
export function _parseParallelTargets(content: string): string[] {
  if (!content) return [];
  // Try colon-separated format: "Label: agent1, agent2"
  const colonIdx = content.indexOf(":");
  const segment = colonIdx >= 0 ? content.slice(colonIdx + 1) : content;
  const names = segment
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && /^[a-z_]+$/i.test(s));
  return names;
}

function toDisplayMeta(
  data: Partial<{
    display_role: DisplayPresentationMeta["displayRole"];
    sequence_id: number;
    step_id: string;
    step_state: DisplayPresentationMeta["stepState"];
    presentation: DisplayPresentationMeta["presentation"];
  }>,
): DisplayPresentationMeta {
  return {
    displayRole: data.display_role,
    sequenceId: data.sequence_id,
    stepId: data.step_id,
    stepState: data.step_state,
    presentation: data.presentation,
  };
}

export function useSSEStream() {
  const abortRef = useRef<AbortController | null>(null);
  // Sprint 150: Token smoothing buffers
  const answerBufferRef = useRef<StreamBuffer | null>(null);
  const thinkingBufferRef = useRef<StreamBuffer | null>(null);
  // Track current thinking node for buffer flush callback
  const thinkingNodeRef = useRef<string | undefined>(undefined);
  const thinkingMetaRef = useRef<DisplayPresentationMeta | undefined>(undefined);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventOrderRef = useRef<string[]>([]);

  const clearIdleGuard = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }, []);

  const hasStreamingOutput = useCallback(() => {
    const state = useChatStore.getState();
    return Boolean(
      state.streamingContent.trim()
      || state.streamingThinking.trim()
      || state.streamingBlocks.length > 0
      || state.streamingSources.length > 0
      || state.streamingToolCalls.length > 0
      || state.streamingPreviews.length > 0
      || state.streamingArtifacts.length > 0
      || state.streamingDomainNotice.trim()
    );
  }, []);

  const finalizeFromTransport = useCallback((
    reason: "done" | "eof" | "idle_timeout",
    metadata?: ChatResponseMetadata,
  ) => {
    clearIdleGuard();
    answerBufferRef.current?.drain();
    thinkingBufferRef.current?.drain();

    const store = useChatStore.getState();
    if (!store.isStreaming) return;

    if (metadata) {
      store.setPendingStreamMetadata(metadata);
    }

    if (hasStreamingOutput()) {
      if (TRACE_SSE) {
        console.debug("[SSE] finalize", { reason, eventOrder: [...eventOrderRef.current] });
      }
      store.finalizeStream();
      return;
    }

    const fallbackMessage =
      reason === "idle_timeout"
        ? "Luồng phản hồi đã im lặng quá lâu trước khi chốt câu trả lời cuối."
        : "Luồng phản hồi kết thúc sớm trước khi Wiii kịp chốt câu trả lời cuối.";
    store.setStreamError(fallbackMessage);
  }, [clearIdleGuard, hasStreamingOutput]);

  const scheduleIdleGuard = useCallback(() => {
    clearIdleGuard();
    if (!abortRef.current) return;

    idleTimerRef.current = setTimeout(() => {
      if (!abortRef.current || abortRef.current.signal.aborted) return;
      if (!useChatStore.getState().isStreaming) return;

      if (TRACE_SSE) {
        console.debug("[SSE] idle-timeout", { eventOrder: [...eventOrderRef.current] });
      }

      abortRef.current.abort(IDLE_TIMEOUT_ABORT_REASON);
      finalizeFromTransport("idle_timeout");
    }, SSE_IDLE_TIMEOUT_MS);
  }, [clearIdleGuard, finalizeFromTransport]);

  const traceEvent = useCallback((eventType: string, payload?: unknown) => {
    eventOrderRef.current.push(eventType);
    if (TRACE_SSE) {
      console.debug("[SSE]", eventType, payload);
    }
    scheduleIdleGuard();
  }, [scheduleIdleGuard]);

  const sendMessage = useCallback(async (content: string, images?: ImageInput[]) => {
    const settings = useSettingsStore.getState().settings;
    const authHeaders = useSettingsStore.getState().getAuthHeaders();
    const domainId = useDomainStore.getState().activeDomainId;
    const chatStore = useChatStore.getState();

    // Sprint 153b: Concurrent stream guard — abort previous stream before starting new one
    if (abortRef.current) {
      abortRef.current.abort(STREAM_RESTART_ABORT_REASON);
      answerBufferRef.current?.discard();
      thinkingBufferRef.current?.discard();
      clearIdleGuard();
    }

    // Ensure we have an active conversation
    let conversationId = chatStore.activeConversationId;
    if (!conversationId) {
      // Sprint 220c: Pass embed session_id for session resumption
      const embedSessionId = (window as any).__WIII_EMBED_CONFIG__?.session_id;
      conversationId = chatStore.createConversation(domainId, undefined, embedSessionId);
    }

    // Add user message (Sprint 179: with optional images)
    chatStore.addUserMessage(content, images);

    // Initialize the HTTP client with current settings
    initClient(settings.server_url, authHeaders);

      // Start streaming
      chatStore.startStreaming();
      useCharacterStore.getState().clearSoulEmotion();

      // Sprint 153b: Clear stale think/progress tool IDs from previous streams
      _thinkToolIds.clear();
    eventOrderRef.current = [];
    thinkingMetaRef.current = undefined;

    // Keep a per-send controller so an aborted previous request cannot
    // accidentally clear/finalize the newly-started stream.
    const streamController = new AbortController();
    abortRef.current = streamController;
    const clearIdleGuardIfCurrent = () => {
      if (abortRef.current === streamController) {
        clearIdleGuard();
      }
    };
    scheduleIdleGuard();

    // Sprint 150: Create fresh StreamBuffer instances for this stream
    answerBufferRef.current = new StreamBuffer({
      onFlush: (chars) => useChatStore.getState().appendStreamingContent(chars),
      initialHoldMs: 80,
      minCharsPerFrame: 3,
      maxCharsPerFrame: 28,
      targetBufferDepth: 40,
      easeInFrames: 15,
    });
    thinkingBufferRef.current = new StreamBuffer({
      onFlush: (chars) => {
        useChatStore.getState().appendThinkingDelta(chars, thinkingNodeRef.current, thinkingMetaRef.current);
        useChatStore.getState().appendPhaseThinkingDelta(
          chars,
          thinkingNodeRef.current,
          thinkingMetaRef.current?.stepId,
        );
      },
      initialHoldMs: 70,
      minCharsPerFrame: 2,
      maxCharsPerFrame: 20,
      targetBufferDepth: 28,
      easeInFrames: 10,
    });

    const handlers: SSEEventHandler = {
      onThinking: (data) => {
        traceEvent("thinking", { node: data.node });
        // Sprint 140b: Thinking events contain AI reasoning ONLY.
        // Pipeline progress is handled by onStatus (event: status).
        // Full thinking events are complete paragraphs — no buffering needed.
        if (data.content) {
          const store = useChatStore.getState();
          store.setStreamingThinking(data.content);
          store.appendPhaseThinking(data.content, data.node, data.step_id);
        }
      },
      onAnswer: (data) => {
        traceEvent("answer", { length: data.content.length });
        // Sprint 150: Push to buffer instead of direct store update
        answerBufferRef.current?.push(data.content);
      },
      onSources: (data) => {
        traceEvent("sources", { count: data.sources?.length || 0 });
        useChatStore.getState().setStreamingSources(data.sources || []);
      },
      onMetadata: (data) => {
        traceEvent("metadata", { session_id: data.session_id, model: data.model });
        useChatStore.getState().setPendingStreamMetadata(data as Partial<ChatResponseMetadata> as ChatResponseMetadata);
        // Sprint 120: Update mood from metadata if present
        const moodData = (data as Record<string, unknown>).mood as
          | { positivity: number; energy: number; mood: MoodType }
          | null
          | undefined;
        if (moodData && moodData.mood) {
          const charStore = useCharacterStore.getState();
          charStore.setMood(moodData.mood, moodData.positivity, moodData.energy);
          charStore.setMoodEnabled(true);
        }
      },
      onDone: () => {
        traceEvent("done");
        queueMicrotask(() => {
          finalizeFromTransport("done");
          const activeConv = useChatStore.getState().activeConversation();
          const sid = activeConv?.session_id || activeConv?.id || "";
          if (sid) {
            setTimeout(() => {
              useContextStore.getState().fetchContextInfo(sid);
            }, 500);
          }
        });
      },
      onError: (data) => {
        traceEvent("error", data);
        clearIdleGuard();
        // Sprint 150: Discard buffered tokens on error
        answerBufferRef.current?.discard();
        thinkingBufferRef.current?.discard();
        useChatStore.getState().setStreamError(data.message);
      },
      onToolCall: (data) => {
        traceEvent("tool_call", { name: data.content.name, node: data.node });
        const store = useChatStore.getState();
        // Sprint 147: Think tool — redirect thought content into thinking block
        if (data.content.name === "tool_think") {
          const thought = String(data.content.args?.thought || "");
          if (thought) {
            // Sprint 150: Push to thinking buffer instead of direct update
            thinkingNodeRef.current = data.node;
            thinkingBufferRef.current?.push(thought);
          }
          // Track the ID so onToolResult can skip it
          _thinkToolIds.add(data.content.id);
          return;
        }
        // Sprint 148: Progress tool — phase transition handled server-side
        // via thinking_end/action_text/thinking_start. Skip tool card display.
        if (data.content.name === "tool_report_progress") {
          _thinkToolIds.add(data.content.id);
          return;
        }
        // Sprint 150: Drain thinking buffer before tool card
        thinkingBufferRef.current?.drain();
        const tc = {
          id: data.content.id,
          name: data.content.name,
          args: data.content.args,
          node: data.node,
        };
        store.appendToolCall(tc, toDisplayMeta(data));
        store.setStreamingStep(`🔧 ${data.content.name}`);
        store.appendPhaseToolCall(tc, data.step_id);
      },
      onToolResult: (data) => {
        traceEvent("tool_result", { id: data.content.id, node: data.node });
        // Sprint 147: Skip think tool results (just acknowledgments)
        if (_thinkToolIds.has(data.content.id)) {
          _thinkToolIds.delete(data.content.id);
          return;
        }
        const store = useChatStore.getState();
        store.updateToolCallResult(data.content.id, data.content.result, toDisplayMeta(data));
        store.updatePhaseToolCallResult(data.content.id, data.content.result);
      },
      onStatus: (data) => {
        traceEvent("status", { node: data.node, step: data.step });
        const label = data.content || data.step;
        const store = useChatStore.getState();

        // Sprint 164: Detect parallel dispatch → open subagent group
        if (data.node === "parallel_dispatch") {
          const agentNames = _parseParallelTargets(data.content);
          if (agentNames.length > 0) {
            store.openSubagentGroup(
              label || "Triển khai song song",
              agentNames,
            );
          }
        }

        // Sprint 164: Detect aggregator → close group + extract decision
        if (data.node === "aggregator") {
          store.closeSubagentGroup();
          const details = (data as unknown as Record<string, unknown>).details as Record<string, unknown> | undefined;
          if (details?.aggregation) {
            store.setAggregationSummary(details.aggregation as AggregationSummary);
          }
        }

        // Sprint 164: Forward status to worker lane when inside group
        if (label && data.node && store._activeSubagentGroupId
            && data.node !== "parallel_dispatch" && data.node !== "aggregator") {
          store.appendWorkerStatus(data.node, label);
        }

        if (label) {
          store.addStreamingStep(label, data.node);
          store.setStreamingStep(label);
          store.appendPhaseStatus(label, data.node, data.step_id);
        }
      },
      onThinkingDelta: (data) => {
        traceEvent("thinking_delta", { node: data.node, length: data.content.length });
        // Sprint 150: Push to thinking buffer instead of direct update
        thinkingNodeRef.current = data.node;
        thinkingMetaRef.current = toDisplayMeta(data);
        thinkingBufferRef.current?.push(data.content);
      },
      onThinkingStart: (data) => {
        traceEvent("thinking_start", { node: data.node, phase: data.phase });
        // Sprint 150: Drain thinking buffer before opening new block
        thinkingBufferRef.current?.drain();
        thinkingMetaRef.current = undefined;
        const store = useChatStore.getState();
        // Sprint 164: Pass node for workerNode tagging inside subagent groups
        store.openThinkingBlock(
          data.content || data.node || "",
          data.summary,
          data.node,
          data.phase,
          toDisplayMeta({
            ...data,
            step_id: data.step_id || data.block_id,
          }),
        );
        store.addOrUpdatePhase(
          data.content || data.node || "",
          data.node,
          data.step_id || data.block_id,
          data.phase,
          data.summary,
        );
      },
      onThinkingEnd: (data) => {
        traceEvent("thinking_end", { node: data.node });
        // Sprint 150: Drain thinking buffer before closing block
        thinkingBufferRef.current?.drain();
        const store = useChatStore.getState();
        store.closeThinkingBlock(data.duration_ms);
        store.closeActivePhase(data.duration_ms);
        // Sprint 164: Mark the specific worker as completed in active group
        if (data.node && store._activeSubagentGroupId) {
          store.markWorkerCompleted(data.node);
        }
      },
      onDomainNotice: (data) => {
        traceEvent("domain_notice");
        useChatStore.getState().setStreamingDomainNotice(data.content);
      },
      onEmotion: (data) => {
        traceEvent("emotion", { mood: data.mood });
        // Sprint 135: Soul emotion — LLM-driven avatar expression
        try {
          const charStore = useCharacterStore.getState();
          charStore.setSoulEmotion({
            mood: data.mood,
            face: data.face ?? {},
            intensity: data.intensity,
          });
        } catch (err) {
          console.error("[Soul Emotion] SSE handler error:", err);
        }
      },
      onActionText: (data) => {
        traceEvent("action_text", { node: data.node });
        // Sprint 150: Drain both buffers before action text block
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        // Sprint 147: Bold action text between thinking blocks
        // Sprint 149: Pass node for agent attribution
        useChatStore.getState().appendActionText(data.content, data.node, toDisplayMeta(data));
      },
      onBrowserScreenshot: (data) => {
        traceEvent("browser_screenshot", { url: data.content.url, node: data.node });
        // Sprint 153: Browser screenshot — visual transparency during search
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        useChatStore.getState().appendScreenshot({
          url: data.content.url,
          image: data.content.image,
          label: data.content.label,
          node: data.node,
        }, toDisplayMeta(data));
      },
      onPreview: (data) => {
        traceEvent("preview", { id: data.content.preview_id, node: data.node });
        // Sprint 166: Rich preview cards
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        const previewSettings = useSettingsStore.getState().settings;
        if (previewSettings.show_previews === false) return;
        useChatStore.getState().addPreviewItem({
          ...data.content,
          preview_type: data.content.preview_type as PreviewType,
        }, data.node, toDisplayMeta(data));
      },
      onArtifact: (data) => {
        traceEvent("artifact", { id: data.content.artifact_id, node: data.node });
        // Sprint 167: Interactive artifacts (code, HTML, data)
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        const artifactSettings = useSettingsStore.getState().settings;
        if (artifactSettings.show_artifacts === false) return;
        useChatStore.getState().addArtifact({
          ...data.content,
          artifact_type: data.content.artifact_type as ArtifactType,
        }, data.node, toDisplayMeta(data));
      },
      onVisual: (data) => {
        traceEvent("visual", { id: data.content.id, type: data.content.type, node: data.node });
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        try {
          useChatStore.getState().openVisualSession(data.content, data.node, toDisplayMeta(data));
          trackVisualTelemetry("visual_opened", {
            visual_id: data.content.id,
            visual_session_id: data.content.visual_session_id,
            visual_type: data.content.type,
            runtime: data.content.runtime,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "unknown visual store error";
          trackVisualTelemetry("visual_render_error", {
            visual_id: data.content.id,
            visual_type: data.content.type,
            runtime: data.content.runtime,
            error: `store_insert_failed:${message}`,
          });
          throw error;
        }
      },
      onVisualOpen: (data) => {
        traceEvent("visual_open", { id: data.content.id, session: data.content.visual_session_id, node: data.node });
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        useChatStore.getState().openVisualSession(data.content, data.node, toDisplayMeta(data));
        trackVisualTelemetry("visual_opened", {
          visual_id: data.content.id,
          visual_session_id: data.content.visual_session_id,
          visual_type: data.content.type,
          runtime: data.content.runtime,
        });
      },
      onVisualPatch: (data) => {
        traceEvent("visual_patch", { id: data.content.id, session: data.content.visual_session_id, node: data.node });
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        useChatStore.getState().patchVisualSession(data.content, data.node, toDisplayMeta(data));
        trackVisualTelemetry("visual_patched", {
          visual_id: data.content.id,
          visual_session_id: data.content.visual_session_id,
          visual_type: data.content.type,
          runtime: data.content.runtime,
        });
      },
      onVisualCommit: (data) => {
        traceEvent("visual_commit", { session: data.content.visual_session_id, node: data.node });
        useChatStore.getState().commitVisualSession(data.content.visual_session_id);
        trackVisualTelemetry("visual_committed", {
          visual_session_id: data.content.visual_session_id,
          status: data.content.status || "committed",
        });
      },
      onVisualDispose: (data) => {
        traceEvent("visual_dispose", { session: data.content.visual_session_id, node: data.node });
        useChatStore.getState().disposeVisualSession(data.content.visual_session_id, data.content.reason);
        trackVisualTelemetry("visual_disposed", {
          visual_session_id: data.content.visual_session_id,
          status: data.content.status || "disposed",
          reason: data.content.reason || "",
        });
      },
      onHostAction: (data) => {
        traceEvent("host_action", { id: data.content?.id, action: data.content?.action });
        // Sprint 222b: AI agent requested a host action
        const { id, action, params } = data.content || {};
        if (id && action) {
          useHostContextStore.getState().requestAction(action, params || {})
            .then((result) => {
              console.log(`[SSE] Host action ${id} resolved:`, result);
            })
            .catch((err) => {
              console.warn(`[SSE] Host action ${id} failed:`, err.message);
            });
        }
      },
        onCodeOpen: (data) => {
          traceEvent("code_open", { session: data.content.session_id, title: data.content.title });
          answerBufferRef.current?.drain();
          thinkingBufferRef.current?.drain();
          useCodeStudioStore.getState().openSession(
          data.content.session_id,
          data.content.title,
          data.content.language,
          data.content.version,
            {
              studioLane: data.content.studio_lane,
              artifactKind: data.content.artifact_kind,
              qualityProfile: data.content.quality_profile,
              rendererContract: data.content.renderer_contract,
              requestedView: data.content.requested_view,
            },
          );
          useUIStore.getState().openCodeStudio();
        },
      onCodeDelta: (data) => {
        traceEvent("code_delta", { session: data.content.session_id, idx: data.content.chunk_index });
        useCodeStudioStore.getState().appendCode(
          data.content.session_id,
          data.content.chunk,
          data.content.chunk_index,
          data.content.total_bytes,
        );
      },
      onCodeComplete: (data) => {
        traceEvent("code_complete", { session: data.content.session_id, version: data.content.version });
        useCodeStudioStore.getState().completeSession(
          data.content.session_id,
          data.content.full_code,
          data.content.language,
          data.content.version,
          data.content.visual_payload,
        );
      },
      onKeepAlive: () => {
        traceEvent("keepalive");
      },
    };

    // Sprint 121b: Include session_id from active conversation for history continuity
    // Backend uses this to load previous messages in the same session
    const activeConv = useChatStore.getState().activeConversation();
    const sessionId = activeConv?.session_id || activeConv?.id || "";

    // Sprint 156: Include org ID when not personal workspace
    const orgId = useOrgStore.getState().activeOrgId;

    // Sprint 222: Use host-context-store (generic, replaces Sprint 221 page-context-store)
    const hostCtx = useHostContextStore.getState().getContextForRequest();
    // Sprint 221 backward compat: also read old page-context-store as fallback
    const pageData = usePageContextStore.getState().getPageContextForRequest();

    // Build user_context: prefer host-context-store, fallback to page-context-store
    const buildUserContext = () => {
      const visualContext = useChatStore.getState().getActiveVisualContext();
      const widgetFeedback = useChatStore.getState().getActiveWidgetFeedbackContext();
      const codeStudioContext = useCodeStudioStore.getState().getActiveSessionContext();
      if (hostCtx) {
        return {
          display_name: settings.display_name || settings.user_id,
          role: settings.user_role,
          host_context: hostCtx,
          // Sprint 221 backward compat — keep flat fields for backend
          page_context: {
            page_type: hostCtx.page.type,
            page_title: hostCtx.page.title,
            ...(hostCtx.page.metadata || {}),
            content_snippet: hostCtx.content?.snippet,
          },
          student_state: hostCtx.user_state || undefined,
          available_actions: hostCtx.available_actions || undefined,
          visual_context: visualContext,
          widget_feedback: widgetFeedback,
          code_studio_context: codeStudioContext,
        };
      }
      if (pageData) {
        return {
          display_name: settings.display_name || settings.user_id,
          role: settings.user_role,
          ...pageData,
          visual_context: visualContext,
          widget_feedback: widgetFeedback,
          code_studio_context: codeStudioContext,
        };
      }
      if (visualContext || widgetFeedback || codeStudioContext) {
        return {
          display_name: settings.display_name || settings.user_id,
          role: settings.user_role,
          visual_context: visualContext,
          widget_feedback: widgetFeedback,
          code_studio_context: codeStudioContext,
        };
      }
      return undefined;
    };

    const request = {
      user_id: settings.user_id,
      message: content,
      role: settings.user_role,
      domain_id: domainId,
      session_id: sessionId,
      organization_id: orgId && orgId !== "personal" ? orgId : undefined,
      // Sprint 179: Include images for multimodal vision
      images: images && images.length > 0 ? images : undefined,
      // Sprint 222: Host-aware context (with Sprint 221 backward compat)
      user_context: buildUserContext(),
    };

    // Sprint 194b (H5): Facebook cookie now in secure storage, not settings
    try {
      const { loadFacebookCookie } = await import("@/lib/secure-token-storage");
      const fbCookie = await loadFacebookCookie();
      if (fbCookie) {
        authHeaders["X-Facebook-Cookie"] = fbCookie;
        initClient(settings.server_url, authHeaders);
      }
    } catch {
      // Secure storage not available — skip Facebook cookie
    }

    let lastEventId: string | null = null;
    let retryCount = 0;

    try {
      while (retryCount <= MAX_SSE_RETRIES) {
        try {
          const result = await sendMessageStream(
            request,
            handlers,
            streamController.signal,
            lastEventId,
          );
          lastEventId = result.lastEventId;
          clearIdleGuardIfCurrent();

          if (TRACE_SSE) {
            console.debug("[SSE] stream-end", result);
          }

          if (abortRef.current === streamController && useChatStore.getState().isStreaming) {
            finalizeFromTransport(result.sawDone ? "done" : "eof");
          }

          lastEventId = null;
          break; // Success — exit retry loop
        } catch (err) {
          clearIdleGuardIfCurrent();

          if (streamController.signal.aborted) {
            if (streamController.signal.reason === IDLE_TIMEOUT_ABORT_REASON) {
              break;
            }
            break;
          }
          retryCount++;
          if (retryCount > MAX_SSE_RETRIES) {
            // Sprint 153b: Discard buffered tokens on final failure
            answerBufferRef.current?.discard();
            thinkingBufferRef.current?.discard();
            // Sprint 165: Localized error messages based on error type
            const errorMsg = _getVietnameseErrorMessage(err);
            useChatStore.getState().setStreamError(errorMsg);
            break;
          }
          // Sprint 153b: Discard partially-buffered tokens before retry
          answerBufferRef.current?.discard();
          thinkingBufferRef.current?.discard();
          if (abortRef.current === streamController) {
            scheduleIdleGuard();
          }
          await sleep(SSE_BACKOFF_MS * Math.pow(2, retryCount - 1));
        }
      }
    } finally {
      if (abortRef.current === streamController) {
        abortRef.current = null;
      }
    }
  }, [clearIdleGuard, finalizeFromTransport, scheduleIdleGuard, traceEvent]);

  const cancelStream = useCallback(() => {
    // Sprint 150: Discard buffered tokens on cancel
    answerBufferRef.current?.discard();
    thinkingBufferRef.current?.discard();
    clearIdleGuard();
    abortRef.current?.abort(USER_CANCEL_ABORT_REASON);
    useChatStore.getState().clearStreaming();
  }, [clearIdleGuard]);

  return { sendMessage, cancelStream };
}
