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
import { useContextStore } from "@/stores/context-store";
import { useCharacterStore } from "@/stores/character-store";
import { StreamBuffer } from "@/lib/stream-buffer";
import type { SSEEventHandler } from "@/api/sse";
import type { ChatResponseMetadata, MoodType } from "@/api/types";

const MAX_SSE_RETRIES = 3;
const SSE_BACKOFF_MS = 1000; // 1s, 2s, 4s

// Sprint 147: Track think tool IDs to skip their results
const _thinkToolIds = new Set<string>();

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useSSEStream() {
  const abortRef = useRef<AbortController | null>(null);
  // Sprint 150: Token smoothing buffers
  const answerBufferRef = useRef<StreamBuffer | null>(null);
  const thinkingBufferRef = useRef<StreamBuffer | null>(null);
  // Track current thinking node for buffer flush callback
  const thinkingNodeRef = useRef<string | undefined>(undefined);

  const sendMessage = useCallback(async (content: string) => {
    const settings = useSettingsStore.getState().settings;
    const authHeaders = useSettingsStore.getState().getAuthHeaders();
    const domainId = useDomainStore.getState().activeDomainId;
    const chatStore = useChatStore.getState();

    // Sprint 153b: Concurrent stream guard — abort previous stream before starting new one
    if (abortRef.current) {
      abortRef.current.abort();
      answerBufferRef.current?.discard();
      thinkingBufferRef.current?.discard();
    }

    // Ensure we have an active conversation
    let conversationId = chatStore.activeConversationId;
    if (!conversationId) {
      conversationId = chatStore.createConversation(domainId);
    }

    // Add user message
    chatStore.addUserMessage(content);

    // Initialize the HTTP client with current settings
    initClient(settings.server_url, authHeaders);

    // Start streaming
    chatStore.startStreaming();
    useCharacterStore.getState().clearSoulEmotion();

    // Sprint 153b: Clear stale think/progress tool IDs from previous streams
    _thinkToolIds.clear();

    // Create abort controller
    abortRef.current = new AbortController();

    // Sprint 150: Create fresh StreamBuffer instances for this stream
    answerBufferRef.current = new StreamBuffer({
      onFlush: (chars) => useChatStore.getState().appendStreamingContent(chars),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 12,
      targetFrames: 8,
    });
    thinkingBufferRef.current = new StreamBuffer({
      onFlush: (chars) => {
        useChatStore.getState().appendThinkingDelta(chars, thinkingNodeRef.current);
        useChatStore.getState().appendPhaseThinkingDelta(chars, thinkingNodeRef.current);
      },
      minCharsPerFrame: 2,
      maxCharsPerFrame: 16,
      targetFrames: 6,
    });

    const handlers: SSEEventHandler = {
      onThinking: (data) => {
        // Sprint 140b: Thinking events contain AI reasoning ONLY.
        // Pipeline progress is handled by onStatus (event: status).
        // Full thinking events are complete paragraphs — no buffering needed.
        if (data.content) {
          const store = useChatStore.getState();
          store.setStreamingThinking(data.content);
          store.appendPhaseThinking(data.content);
        }
      },
      onAnswer: (data) => {
        // Sprint 150: Push to buffer instead of direct store update
        answerBufferRef.current?.push(data.content);
      },
      onSources: (data) => {
        useChatStore.getState().setStreamingSources(data.sources || []);
      },
      onMetadata: (data) => {
        // Sprint 150: Drain both buffers before finalization
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        // Metadata comes before done — store it for finalization
        useChatStore.getState().finalizeStream(data as Partial<ChatResponseMetadata> as ChatResponseMetadata);
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
        // Sprint 150: Drain both buffers before finalizing
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        // Stream complete — if not already finalized by metadata
        const store = useChatStore.getState();
        if (store.isStreaming) {
          store.finalizeStream();
        }
        // Refresh context info after stream ends (500ms delay)
        const activeConv = useChatStore.getState().activeConversation();
        const sid = activeConv?.session_id || activeConv?.id || "";
        if (sid) {
          setTimeout(() => {
            useContextStore.getState().fetchContextInfo(sid);
          }, 500);
        }
      },
      onError: (data) => {
        // Sprint 150: Discard buffered tokens on error
        answerBufferRef.current?.discard();
        thinkingBufferRef.current?.discard();
        useChatStore.getState().setStreamError(data.message);
      },
      onToolCall: (data) => {
        const store = useChatStore.getState();
        // Sprint 147: Think tool — redirect thought content into thinking block
        if (data.content.name === "tool_think") {
          const thought = data.content.args?.thought || "";
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
        store.appendToolCall(tc);
        store.setStreamingStep(`🔧 ${data.content.name}`);
        store.appendPhaseToolCall(tc);
      },
      onToolResult: (data) => {
        // Sprint 147: Skip think tool results (just acknowledgments)
        if (_thinkToolIds.has(data.content.id)) {
          _thinkToolIds.delete(data.content.id);
          return;
        }
        const store = useChatStore.getState();
        store.updateToolCallResult(data.content.id, data.content.result);
        store.updatePhaseToolCallResult(data.content.id, data.content.result);
      },
      onStatus: (data) => {
        const label = data.content || data.step;
        if (label) {
          const store = useChatStore.getState();
          store.addStreamingStep(label, data.node);
          store.setStreamingStep(label);
          store.appendPhaseStatus(label, data.node);
        }
      },
      onThinkingDelta: (data) => {
        // Sprint 150: Push to thinking buffer instead of direct update
        thinkingNodeRef.current = data.node;
        thinkingBufferRef.current?.push(data.content);
      },
      onThinkingStart: (data) => {
        // Sprint 150: Drain thinking buffer before opening new block
        thinkingBufferRef.current?.drain();
        const store = useChatStore.getState();
        store.openThinkingBlock(data.content || data.node || "", data.summary);
        store.addOrUpdatePhase(data.content || data.node || "", data.node);
      },
      onThinkingEnd: (data) => {
        // Sprint 150: Drain thinking buffer before closing block
        thinkingBufferRef.current?.drain();
        const store = useChatStore.getState();
        store.closeThinkingBlock(data.duration_ms);
        store.closeActivePhase(data.duration_ms);
      },
      onDomainNotice: (data) => {
        useChatStore.getState().setStreamingDomainNotice(data.content);
      },
      onEmotion: (data) => {
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
        // Sprint 150: Drain both buffers before action text block
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        // Sprint 147: Bold action text between thinking blocks
        // Sprint 149: Pass node for agent attribution
        useChatStore.getState().appendActionText(data.content, data.node);
      },
      onBrowserScreenshot: (data) => {
        // Sprint 153: Browser screenshot — visual transparency during search
        answerBufferRef.current?.drain();
        thinkingBufferRef.current?.drain();
        useChatStore.getState().appendScreenshot({
          url: data.content.url,
          image: data.content.image,
          label: data.content.label,
          node: data.node,
        });
      },
    };

    // Sprint 121b: Include session_id from active conversation for history continuity
    // Backend uses this to load previous messages in the same session
    const activeConv = useChatStore.getState().activeConversation();
    const sessionId = activeConv?.session_id || activeConv?.id || "";

    const request = {
      user_id: settings.user_id,
      message: content,
      role: settings.user_role,
      domain_id: domainId,
      session_id: sessionId,
    };

    let lastEventId: string | null = null;
    let retryCount = 0;

    while (retryCount <= MAX_SSE_RETRIES) {
      try {
        await sendMessageStream(
          request,
          handlers,
          abortRef.current.signal,
          lastEventId,
        );
        // Sprint 85: Reset lastEventId after successful completion
        // to prevent stale IDs causing event duplication on next stream
        lastEventId = null;
        break; // Success — exit retry loop
      } catch (err) {
        if (abortRef.current.signal.aborted) break;
        retryCount++;
        if (retryCount > MAX_SSE_RETRIES) {
          // Sprint 153b: Discard buffered tokens on final failure
          answerBufferRef.current?.discard();
          thinkingBufferRef.current?.discard();
          useChatStore.getState().setStreamError(
            "Mất kết nối. Vui lòng thử lại."
          );
          break;
        }
        // Sprint 153b: Discard partially-buffered tokens before retry
        answerBufferRef.current?.discard();
        thinkingBufferRef.current?.discard();
        await sleep(SSE_BACKOFF_MS * Math.pow(2, retryCount - 1));
      }
    }
  }, []);

  const cancelStream = useCallback(() => {
    // Sprint 150: Discard buffered tokens on cancel
    answerBufferRef.current?.discard();
    thinkingBufferRef.current?.discard();
    abortRef.current?.abort();
    useChatStore.getState().clearStreaming();
  }, []);

  return { sendMessage, cancelStream };
}
