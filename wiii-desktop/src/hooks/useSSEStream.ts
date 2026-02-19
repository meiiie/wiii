/**
 * SSE streaming hook — connects chat store to SSE parser.
 */
import { useCallback, useRef } from "react";
import { sendMessageStream } from "@/api/chat";
import { initClient } from "@/api/client";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useDomainStore } from "@/stores/domain-store";
import { useContextStore } from "@/stores/context-store";
import { useCharacterStore } from "@/stores/character-store";
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

  const sendMessage = useCallback(async (content: string) => {
    const settings = useSettingsStore.getState().settings;
    const authHeaders = useSettingsStore.getState().getAuthHeaders();
    const domainId = useDomainStore.getState().activeDomainId;
    const chatStore = useChatStore.getState();

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

    // Create abort controller
    abortRef.current = new AbortController();

    const handlers: SSEEventHandler = {
      onThinking: (data) => {
        // Sprint 140b: Thinking events contain AI reasoning ONLY.
        // Pipeline progress is handled by onStatus (event: status).
        if (data.content) {
          useChatStore.getState().setStreamingThinking(data.content);
          useChatStore.getState().appendPhaseThinking(data.content);
        }
      },
      onAnswer: (data) => {
        useChatStore.getState().appendStreamingContent(data.content);
      },
      onSources: (data) => {
        useChatStore.getState().setStreamingSources(data.sources || []);
      },
      onMetadata: (data) => {
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
        useChatStore.getState().setStreamError(data.message);
      },
      onToolCall: (data) => {
        const store = useChatStore.getState();
        // Sprint 147: Think tool — redirect thought content into thinking block
        if (data.content.name === "tool_think") {
          const thought = data.content.args?.thought || "";
          if (thought) {
            store.appendThinkingDelta(thought, data.node);
            store.appendPhaseThinkingDelta(thought, data.node);
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
        const store = useChatStore.getState();
        const label = data.content || data.step;
        if (label) {
          store.addStreamingStep(label, data.node);
          store.setStreamingStep(label);
          store.appendPhaseStatus(label, data.node);
        }
      },
      onThinkingDelta: (data) => {
        useChatStore.getState().appendThinkingDelta(data.content, data.node);
        useChatStore.getState().appendPhaseThinkingDelta(data.content, data.node);
      },
      onThinkingStart: (data) => {
        useChatStore.getState().openThinkingBlock(
          data.content || data.node || "",
          data.summary,
        );
        useChatStore.getState().addOrUpdatePhase(data.content || data.node || "", data.node);
      },
      onThinkingEnd: (data) => {
        useChatStore.getState().closeThinkingBlock(data.duration_ms);
        useChatStore.getState().closeActivePhase(data.duration_ms);
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
        // Sprint 147: Bold action text between thinking blocks
        // Sprint 149: Pass node for agent attribution
        useChatStore.getState().appendActionText(data.content, data.node);
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
          useChatStore.getState().setStreamError(
            "Mất kết nối. Vui lòng thử lại."
          );
          break;
        }
        await sleep(SSE_BACKOFF_MS * Math.pow(2, retryCount - 1));
      }
    }
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    useChatStore.getState().clearStreaming();
  }, []);

  return { sendMessage, cancelStream };
}
