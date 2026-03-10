/**
 * Chat store — conversations, messages, streaming state.
 * Conversations are persisted via tauri-plugin-store (or localStorage fallback).
 *
 * Sprint 62: Added streamingBlocks for interleaved thinking/answer rendering.
 * Old flat fields (streamingContent, streamingThinking, streamingToolCalls)
 * are kept for backward compatibility with tests and simple consumers.
 *
 * Sprint 154: Added immer middleware to eliminate spread operators in streaming mutations.
 * Direct draft mutations reduce GC pressure during high-frequency token streaming.
 */
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { v4 as uuidv4 } from "uuid";
import { loadStore, saveStore } from "@/lib/storage";
import type {
  Conversation,
  Message,
  SourceInfo,
  ChatResponseMetadata,
  ToolCallInfo,
  ContentBlock,
  DisplayPresentationMeta,
  StreamingStep,
  ThinkingPhase,
  ScreenshotBlockData,
  SubagentGroupBlockData,
  SubagentWorker,
  AggregationSummary,
  PreviewItemData,
  PreviewBlockData,
  ArtifactData,
  ArtifactBlockData,
  ToolExecutionBlockData,
  ImageInput,
} from "@/api/types";

const BASE_STORE_NAME = "conversations.json";
const BASE_STORE_KEY = "conversations";

/**
 * Sprint 218: Per-user conversation storage.
 * Each user gets their own store file: conversations_{userId}.json
 * This prevents User A from seeing User B's chat history after OAuth switch.
 */
let _currentUserId: string | null = null;

function getStoreName(): string {
  if (_currentUserId) return `conversations_${_currentUserId}.json`;
  return BASE_STORE_NAME;
}

function getStoreKey(): string {
  if (_currentUserId) return `conversations_${_currentUserId}`;
  return BASE_STORE_KEY;
}

interface ChatState {
  // Data
  conversations: Conversation[];
  activeConversationId: string | null;

  // Sidebar search + pin (Sprint 80)
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  pinConversation: (id: string) => void;
  unpinConversation: (id: string) => void;

  // Streaming state — flat fields (backward compat)
  isStreaming: boolean;
  streamingContent: string;
  streamingThinking: string;
  streamingSources: SourceInfo[];
  streamingStep: string;
  streamingToolCalls: ToolCallInfo[];

  // Streaming state — block-based (interleaved support)
  streamingBlocks: ContentBlock[];

  // Streaming state — timer + pipeline steps (Sprint 63)
  streamingStartTime: number | null;
  streamingSteps: StreamingStep[];

  // Sprint 80b: Domain notice for off-domain content
  streamingDomainNotice: string;

  // Sprint 141: Unified thinking phases for ThinkingFlow
  streamingPhases: ThinkingPhase[];

  // Sprint 166: Preview cards state
  streamingPreviews: PreviewItemData[];

  // Sprint 167: Artifact state
  streamingArtifacts: ArtifactData[];
  pendingStreamMetadata: ChatResponseMetadata | null;

  // Sprint 164: Active subagent group tracking
  _activeSubagentGroupId: string | null;

  // Sprint 145: Transient avatar state fields
  streamError: string;
  streamCompletedAt: number | null;

  // Computed
  activeConversation: () => Conversation | undefined;

  // Persistence
  isLoaded: boolean;
  loadConversations: () => Promise<void>;

  // Actions
  createConversation: (domainId?: string, organizationId?: string, sessionId?: string) => string;
  deleteConversation: (id: string) => void;
  setActiveConversation: (id: string | null) => void;
  renameConversation: (id: string, title: string) => void;
  addUserMessage: (content: string, images?: ImageInput[]) => string | null;
  startStreaming: () => void;
  appendStreamingContent: (chunk: string) => void;
  setStreamingThinking: (thinking: string) => void;
  setStreamingStep: (step: string) => void;
  setStreamingSources: (sources: SourceInfo[]) => void;
  addStreamingStep: (label: string, node?: string) => void;
  appendThinkingDelta: (delta: string, node?: string, meta?: DisplayPresentationMeta) => void;
  openThinkingBlock: (label: string, summary?: string, node?: string, phase?: string, meta?: DisplayPresentationMeta) => void;
  closeThinkingBlock: (durationMs?: number) => void;
  appendToolCall: (tc: ToolCallInfo, meta?: DisplayPresentationMeta) => void;
  updateToolCallResult: (id: string, result: string, meta?: DisplayPresentationMeta) => void;
  setStreamingDomainNotice: (notice: string) => void;
  /** Sprint 147: Append bold action text between thinking blocks */
  appendActionText: (text: string, node?: string, meta?: DisplayPresentationMeta) => void;
  /** Sprint 153: Append browser screenshot block. */
  appendScreenshot: (data: { url: string; image: string; label: string; node?: string }, meta?: DisplayPresentationMeta) => void;
  /** Sprint 164: Open a subagent parallel dispatch group */
  openSubagentGroup: (label: string, agentNames: string[]) => void;
  /** Sprint 164: Close the active subagent group */
  closeSubagentGroup: () => void;
  /** Sprint 164: Attach aggregation decision to the most recent subagent group */
  setAggregationSummary: (summary: AggregationSummary) => void;
  /** Sprint 164: Mark a specific worker as completed within the active group */
  markWorkerCompleted: (workerNode: string) => void;
  /** Sprint 164: Append a status message to a specific worker */
  appendWorkerStatus: (workerNode: string, message: string) => void;
  /** Sprint 166: Add a preview item to the streaming state */
  addPreviewItem: (item: PreviewItemData, node?: string, meta?: DisplayPresentationMeta) => void;
  /** Sprint 167: Add an artifact to the streaming state */
  addArtifact: (artifact: ArtifactData, node?: string, meta?: DisplayPresentationMeta) => void;
  // Sprint 141: ThinkingFlow phase actions
  addOrUpdatePhase: (label: string, node?: string) => void;
  appendPhaseThinking: (content: string) => void;
  appendPhaseThinkingDelta: (delta: string, node?: string) => void;
  closeActivePhase: (durationMs?: number) => void;
  appendPhaseStatus: (message: string, node?: string) => void;
  appendPhaseToolCall: (tc: ToolCallInfo) => void;
  updatePhaseToolCallResult: (id: string, result: string) => void;
  setPendingStreamMetadata: (metadata: ChatResponseMetadata) => void;
  finalizeStream: (metadata?: ChatResponseMetadata) => void;
  setStreamError: (error: string) => void;
  setMessageFeedback: (messageId: string, feedback: "up" | "down" | null) => void;
  clearStreaming: () => void;
  /** Sprint 218: Clear conversations on logout (prevent cross-user leakage) */
  clearForLogout: () => void;
  /** Sprint 218: Switch to a different user's conversation store */
  switchUser: (userId: string | null) => Promise<void>;
  /** Sprint 225: Sync conversation list from server (additive merge) */
  syncFromServer: () => Promise<void>;
  /** Sprint 225: Lazy-load messages from server for a conversation */
  loadServerMessages: (conversationId: string) => Promise<void>;
}

// Debounced persist — avoids excessive writes during streaming
let _persistTimer: ReturnType<typeof setTimeout> | null = null;

// Sprint 225: Prevent concurrent syncFromServer calls
let _syncInProgress = false;

function persistConversations(conversations: Conversation[]) {
  if (_persistTimer) clearTimeout(_persistTimer);
  const storeName = getStoreName();
  const storeKey = getStoreKey();
  _persistTimer = setTimeout(() => {
    saveStore(storeName, storeKey, conversations).catch((err) =>
      console.warn("[chat-store] Failed to persist:", err)
    );
  }, 2000);
}

function persistConversationsImmediate(conversations: Conversation[]) {
  if (_persistTimer) clearTimeout(_persistTimer);
  saveStore(getStoreName(), getStoreKey(), conversations).catch((err) =>
    console.warn("[chat-store] Failed to persist:", err)
  );
}

/** Close the last open thinking block in-place (immer-compatible). */
function closeLastThinkingBlockDraft(blocks: ContentBlock[]): void {
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.type === "thinking" && !block.endTime) {
      block.endTime = Date.now();
      block.stepState = "completed";
      break;
    }
  }
}

function extractSuggestedQuestions(metadata?: ChatResponseMetadata): string[] | undefined {
  const metaAny = metadata as unknown as Record<string, unknown> | undefined;
  const rawSQ =
    metaAny?.suggested_questions
    ?? (metaAny?.data as Record<string, unknown> | undefined)?.suggested_questions;
  return Array.isArray(rawSQ) ? rawSQ as string[] : undefined;
}

function buildDegradedAssistantContent(state: Pick<
  ChatState,
  | "streamingContent"
  | "streamingBlocks"
  | "streamingArtifacts"
  | "streamingPreviews"
>): string {
  if (state.streamingContent.trim()) return state.streamingContent;
  if (state.streamingArtifacts.length > 0 || state.streamingPreviews.length > 0) {
    return "Wiii đã hoàn tất phần tạo nội dung và giữ lại các tệp/kết quả cho bạn, nhưng câu trả lời cuối đã bị ngắt trước khi gửi trọn vẹn.";
  }
  if (state.streamingBlocks.length > 0) {
    return "Wiii đã đi hết phần suy luận, nhưng phản hồi cuối bị ngắt trước khi hiển thị trọn vẹn. Bạn có thể xem lại dòng suy luận hoặc gửi lại để mình chốt lại gọn hơn.";
  }
  return "Luồng phản hồi đã kết thúc sớm trước khi Wiii kịp gửi câu trả lời cuối.";
}

function mergeStreamMetadataIntoMessage(message: Message, metadata: ChatResponseMetadata): void {
  const metaAny = metadata as unknown as Record<string, unknown> | undefined;
  message.reasoning_trace = metadata.reasoning_trace;
  message.metadata = metaAny;
  message.suggested_questions = extractSuggestedQuestions(metadata);
}

function applyDisplayMeta<T extends DisplayPresentationMeta>(target: T, meta?: DisplayPresentationMeta): T {
  if (!meta) return target;
  if (meta.displayRole) target.displayRole = meta.displayRole;
  if (meta.sequenceId != null) target.sequenceId = meta.sequenceId;
  if (meta.stepId) target.stepId = meta.stepId;
  if (meta.stepState) target.stepState = meta.stepState;
  if (meta.presentation) target.presentation = meta.presentation;
  return target;
}

function findLastOpenThinkingBlock(
  blocks: ContentBlock[],
  stepId?: string,
  node?: string,
) {
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.type !== "thinking" || block.endTime) continue;
    if (stepId && block.stepId === stepId) return block;
    if (!stepId && node && block.node === node) return block;
    if (!stepId && !node) return block;
  }
  return undefined;
}

function findLastThinkingBlock(
  blocks: ContentBlock[],
  stepId?: string,
  node?: string,
) {
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.type !== "thinking") continue;
    if (stepId && block.stepId === stepId) return block;
    if (!stepId && node && block.node === node) return block;
    if (!stepId && !node) return block;
  }
  return undefined;
}

function resetStreamingDraft(state: ChatState): void {
  state.isStreaming = false;
  state.streamingContent = "";
  state.streamingThinking = "";
  state.streamingSources = [];
  state.streamingStep = "";
  state.streamingToolCalls = [];
  state.streamingBlocks = [];
  state.streamingStartTime = null;
  state.streamingSteps = [];
  state.streamingDomainNotice = "";
  state.streamingPhases = [];
  state.streamingPreviews = [];
  state.streamingArtifacts = [];
  state.pendingStreamMetadata = null;
  state._activeSubagentGroupId = null;
}

export const useChatStore = create<ChatState>()(
  immer((set, get) => ({
    conversations: [],
    activeConversationId: null,
    searchQuery: "",
    isLoaded: false,
    isStreaming: false,
    streamingContent: "",
    streamingThinking: "",
    streamingSources: [],
    streamingStep: "",
    streamingToolCalls: [],
    streamingBlocks: [],
    streamingStartTime: null,
    streamingSteps: [],
    streamingDomainNotice: "",
    streamingPhases: [],
    streamingPreviews: [],
    streamingArtifacts: [],
    pendingStreamMetadata: null,
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,

    loadConversations: async () => {
      try {
        // Sprint 218: Resolve current user_id for per-user storage
        // Sprint 223-fix: Also read from embed config as fallback (JWT user_id)
        try {
          const { useAuthStore } = await import("@/stores/auth-store");
          const authState = useAuthStore.getState();
          if (authState.authMode === "oauth" && authState.user?.id) {
            _currentUserId = authState.user.id;
          } else {
            // Legacy mode: use settings user_id
            const { useSettingsStore } = await import("@/stores/settings-store");
            const userId = useSettingsStore.getState().settings.user_id;
            _currentUserId = userId || null;
          }
        } catch {
          _currentUserId = null;
        }

        // Fallback: read user_id from embed config (set by EmbedApp after JWT decode)
        if (!_currentUserId) {
          const embedConfig = (window as any)?.__WIII_EMBED_CONFIG__;
          if (embedConfig?.user_id) {
            _currentUserId = embedConfig.user_id;
          }
        }

        const saved = await loadStore<Conversation[]>(getStoreName(), getStoreKey(), []);
        if (saved.length > 0) {
          set((state) => {
            state.conversations = saved;
            state.activeConversationId = saved[0]?.id || null;
            state.isLoaded = true;
          });
        } else {
          set((state) => { state.isLoaded = true; });
        }

        // Sprint 225: Background server sync (non-blocking)
        get().syncFromServer().catch((err) =>
          console.debug("[chat-store] Server sync skipped:", err)
        );
      } catch (err) {
        console.warn("[chat-store] Failed to load conversations:", err);
        set((state) => { state.isLoaded = true; });
      }
    },

    activeConversation: () => {
      const { conversations, activeConversationId } = get();
      return conversations.find((c) => c.id === activeConversationId);
    },

    createConversation: (domainId, organizationId, sessionId) => {
      const id = uuidv4();
      const now = new Date().toISOString();
      const conversation: Conversation = {
        id,
        title: "Cuộc trò chuyện mới",
        domain_id: domainId,
        organization_id: organizationId || undefined,
        created_at: now,
        updated_at: now,
        messages: [],
        // Sprint 220c: Pre-set session_id for embed session resumption
        session_id: sessionId || undefined,
      };

      set((state) => {
        state.conversations.unshift(conversation);
        state.activeConversationId = id;
      });

      persistConversationsImmediate(get().conversations);
      return id;
    },

    deleteConversation: (id) => {
      // Sprint 225: Capture thread_id before removing from state
      const conv = get().conversations.find((c) => c.id === id);
      const threadId = conv?.thread_id;

      set((state) => {
        const idx = state.conversations.findIndex((c) => c.id === id);
        if (idx >= 0) state.conversations.splice(idx, 1);
        if (state.activeConversationId === id) {
          state.activeConversationId = state.conversations[0]?.id || null;
        }
      });
      persistConversationsImmediate(get().conversations);

      // Sprint 225: Fire-and-forget server delete
      if (threadId) {
        import("@/api/threads").then(({ deleteServerThread }) =>
          deleteServerThread(threadId).catch(() => {})
        );
      }
    },

    setActiveConversation: (id) => {
      set((state) => { state.activeConversationId = id; });
      // Sprint 225: Lazy-load server messages for stub conversations
      if (id) {
        get().loadServerMessages(id);
      }
    },

    renameConversation: (id, title) => {
      // Sprint 225: Capture thread_id for server propagation
      const conv = get().conversations.find((c) => c.id === id);
      const threadId = conv?.thread_id;

      set((state) => {
        const found = state.conversations.find((c) => c.id === id);
        if (found) {
          found.title = title;
          found.updated_at = new Date().toISOString();
          found.user_renamed = true; // Sprint 225: prevent server overwrite
        }
      });
      persistConversationsImmediate(get().conversations);

      // Sprint 225: Fire-and-forget server rename
      if (threadId) {
        import("@/api/threads").then(({ renameServerThread }) =>
          renameServerThread(threadId, title).catch(() => {})
        );
      }
    },

    setSearchQuery: (query) => {
      set((state) => { state.searchQuery = query; });
    },

    pinConversation: (id) => {
      set((state) => {
        const conv = state.conversations.find((c) => c.id === id);
        if (conv) conv.pinned = true;
      });
      persistConversationsImmediate(get().conversations);
    },

    unpinConversation: (id) => {
      set((state) => {
        const conv = state.conversations.find((c) => c.id === id);
        if (conv) conv.pinned = false;
      });
      persistConversationsImmediate(get().conversations);
    },

    addUserMessage: (content, images) => {
      const { activeConversationId, conversations } = get();
      if (!activeConversationId) return null;

      const messageId = uuidv4();
      const message: Message = {
        id: messageId,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
        // Sprint 179: Attach images to user message for display
        ...(images && images.length > 0 ? { images } : {}),
      };

      const conversation = conversations.find(
        (c) => c.id === activeConversationId
      );
      const isFirstMessage = conversation?.messages.length === 0;

      set((state) => {
        const conv = state.conversations.find((c) => c.id === activeConversationId);
        if (conv) {
          conv.messages.push(message);
          conv.updated_at = new Date().toISOString();
          if (isFirstMessage) {
            conv.title = content.slice(0, 50) + (content.length > 50 ? "..." : "");
          }
        }
      });

      persistConversations(get().conversations);
      return messageId;
    },

    startStreaming: () => {
      set((state) => {
        resetStreamingDraft(state);
        state.isStreaming = true;
        state.streamingStartTime = Date.now();
        state.streamError = "";
        state.streamCompletedAt = null;
      });
    },

    appendStreamingContent: (chunk) => {
      set((state) => {
        // Flat field — backward compat
        state.streamingContent += chunk;

        // Block-based: append to last answer block, or create new one
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "answer") {
          lastBlock.content += chunk;
        } else {
          closeLastThinkingBlockDraft(state.streamingBlocks);
          state.streamingBlocks.push({
            type: "answer",
            id: uuidv4(),
            content: chunk,
            displayRole: "answer",
            presentation: "compact",
          });
        }
      });
    },

    setStreamingThinking: (thinking) => {
      set((state) => {
        // Flat field — backward compat
        state.streamingThinking = state.streamingThinking
          ? state.streamingThinking + "\n" + thinking
          : thinking;

        // Block-based: append to last thinking block, or create new one
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking") {
          lastBlock.content = lastBlock.content
            ? lastBlock.content + "\n" + thinking
            : thinking;
        } else {
          state.streamingBlocks.push({
            type: "thinking",
            id: uuidv4(),
            label: state.streamingStep || undefined,
            content: thinking,
            toolCalls: [],
            startTime: Date.now(),
          });
        }
      });
    },

    setStreamingStep: (step) => {
      set((state) => {
        state.streamingStep = step;
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking" && !lastBlock.label && step) {
          lastBlock.label = step;
        }
      });
    },

    setStreamingSources: (sources) => {
      set((state) => { state.streamingSources = sources; });
    },

    addStreamingStep: (label, node) => {
      set((state) => {
        state.streamingSteps.push({ label, node, timestamp: Date.now() });
      });
    },

    appendThinkingDelta: (delta, node, meta) => {
      set((state) => {
        // Flat field - backward compat
        state.streamingThinking += delta;

        // Block-based: append to matching open thinking block, or create new one
        const openBlock = findLastOpenThinkingBlock(state.streamingBlocks, meta?.stepId, node);
        if (openBlock) {
          openBlock.content += delta;
          if (node && !openBlock.node) {
            openBlock.node = node;
          }
          applyDisplayMeta(openBlock, meta);
        } else {
          const previousBlock = findLastThinkingBlock(state.streamingBlocks, meta?.stepId, node);
          if (previousBlock && meta?.stepId && previousBlock.stepId === meta.stepId) {
            previousBlock.content += delta;
            if (node && !previousBlock.node) {
              previousBlock.node = node;
            }
            applyDisplayMeta(previousBlock, meta);
            return;
          }
          const groupId = state._activeSubagentGroupId;
          state.streamingBlocks.push(applyDisplayMeta({
            type: "thinking",
            id: uuidv4(),
            label: previousBlock?.label || state.streamingStep || node || undefined,
            summary: previousBlock?.summary,
            phase: previousBlock?.phase,
            node,
            content: delta,
            toolCalls: [],
            startTime: Date.now(),
            ...(groupId ? { groupId, workerNode: node } : {}),
            displayRole: "thinking",
            presentation: "expanded",
          }, meta));
        }
      });
    },

    openThinkingBlock: (label, summary, node, phase, meta) => {
      set((state) => {
        // Close any open thinking block first
        const lastBlock = findLastOpenThinkingBlock(state.streamingBlocks);
        if (lastBlock) {
          lastBlock.endTime = Date.now();
          lastBlock.stepState = "completed";
        }
        // Open new thinking block - tag with group + workerNode if inside parallel dispatch
        const groupId = state._activeSubagentGroupId;
        state.streamingBlocks.push(applyDisplayMeta({
          type: "thinking",
          id: uuidv4(),
          label,
          summary,
          node,
          phase,
          content: "",
          toolCalls: [],
          startTime: Date.now(),
          ...(groupId ? { groupId, workerNode: node } : {}),
          displayRole: "thinking",
          stepState: "live",
          presentation: "expanded",
        }, meta));
      });
    },

    setStreamingDomainNotice: (notice) => {
      set((state) => { state.streamingDomainNotice = notice; });
    },

    appendActionText: (text, node, meta) => {
      set((state) => {
        closeLastThinkingBlockDraft(state.streamingBlocks);
        state.streamingBlocks.push(
          applyDisplayMeta(
            {
              type: "action_text",
              id: uuidv4(),
              content: text,
              node,
              displayRole: "action",
              presentation: "compact",
            },
            meta,
          )
        );
      });
    },

    appendScreenshot: (data, meta) => {
      set((state) => {
        closeLastThinkingBlockDraft(state.streamingBlocks);
        const block: ScreenshotBlockData = applyDisplayMeta({
          type: "screenshot",
          id: `screenshot-${Date.now()}`,
          ...data,
          displayRole: "artifact",
          presentation: "compact",
        }, meta);
        state.streamingBlocks.push(block);
      });
    },

    // ---- Sprint 164: Subagent group actions ----

    openSubagentGroup: (label, agentNames) => {
      set((state) => {
        // Close any open thinking block first
        closeLastThinkingBlockDraft(state.streamingBlocks);

        const groupId = uuidv4();
        const workers: SubagentWorker[] = agentNames.map((name) => ({
          agentName: name,
          label: name,
          status: "active" as const,
          startTime: Date.now(),
          statusMessages: [],
        }));

        const block: SubagentGroupBlockData = {
          type: "subagent_group",
          id: groupId,
          label,
          workers,
          startTime: Date.now(),
        };

        state.streamingBlocks.push(block);
        state._activeSubagentGroupId = groupId;
      });
    },

    closeSubagentGroup: () => {
      set((state) => {
        const groupId = state._activeSubagentGroupId;
        if (!groupId) return;

        // Close any open thinking block
        closeLastThinkingBlockDraft(state.streamingBlocks);

        // Find the group block and set endTime + mark workers completed
        for (const block of state.streamingBlocks) {
          if (block.type === "subagent_group" && block.id === groupId) {
            block.endTime = Date.now();
            for (const w of block.workers) {
              if (w.status === "active") {
                w.status = "completed";
                w.endTime = Date.now();
              }
            }
            break;
          }
        }

        state._activeSubagentGroupId = null;
      });
    },

    setAggregationSummary: (summary) => {
      set((state) => {
        // Find the most recent subagent_group block
        for (let i = state.streamingBlocks.length - 1; i >= 0; i--) {
          const block = state.streamingBlocks[i];
          if (block.type === "subagent_group") {
            block.aggregation = summary;
            break;
          }
        }
      });
    },

    markWorkerCompleted: (workerNode) => {
      set((state) => {
        const groupId = state._activeSubagentGroupId;
        if (!groupId) return;

        for (const block of state.streamingBlocks) {
          if (block.type === "subagent_group" && block.id === groupId) {
            const worker = block.workers.find((w) => w.agentName === workerNode);
            if (worker && worker.status === "active") {
              worker.status = "completed";
              worker.endTime = Date.now();
            }
            break;
          }
        }
      });
    },

    appendWorkerStatus: (workerNode, message) => {
      set((state) => {
        const groupId = state._activeSubagentGroupId;
        if (!groupId) return;

        for (const block of state.streamingBlocks) {
          if (block.type === "subagent_group" && block.id === groupId) {
            const worker = block.workers.find((w) => w.agentName === workerNode);
            if (worker) {
              worker.statusMessages.push(message);
            }
            break;
          }
        }
      });
    },

    // ---- Sprint 166: Preview card actions ----

    addPreviewItem: (item, node, meta) => {
      set((state) => {
        // Dedup by preview_id
        if (state.streamingPreviews.some((p) => p.preview_id === item.preview_id)) return;
        state.streamingPreviews.push(item);

        // Find or create preview block in streamingBlocks
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "preview" && (lastBlock as PreviewBlockData).node === node) {
          // Append to existing group
          (lastBlock as PreviewBlockData).items.push(item);
          applyDisplayMeta(lastBlock as PreviewBlockData, meta);
        } else {
          // New preview block
          closeLastThinkingBlockDraft(state.streamingBlocks);
          state.streamingBlocks.push(applyDisplayMeta({
            type: "preview",
            id: uuidv4(),
            items: [item],
            node,
            displayRole: "tool",
            presentation: "compact",
          } as PreviewBlockData, meta));
        }
      });
    },

    // ---- Sprint 167: Artifact actions ----

    addArtifact: (artifact, node, meta) => {
      set((state) => {
        // L-4: Content size limit (1MB)
        const MAX_ARTIFACT_SIZE = 1_000_000;
        if (artifact.content.length > MAX_ARTIFACT_SIZE) {
          console.warn(`[chat-store] Artifact ${artifact.artifact_id} exceeds 1MB, truncating`);
          artifact = { ...artifact, content: artifact.content.slice(0, MAX_ARTIFACT_SIZE) + "\n// ... truncated" };
        }

        // M-1: Upsert — update existing artifact instead of dropping
        const existingIdx = state.streamingArtifacts.findIndex(
          (a) => a.artifact_id === artifact.artifact_id
        );
        if (existingIdx >= 0) {
          state.streamingArtifacts[existingIdx] = artifact;
          // Update block too
          const blockIdx = state.streamingBlocks.findIndex(
            (b) => b.type === "artifact" && (b as ArtifactBlockData).id === artifact.artifact_id
          );
          if (blockIdx >= 0) {
            (state.streamingBlocks[blockIdx] as ArtifactBlockData).artifact = artifact;
            applyDisplayMeta(state.streamingBlocks[blockIdx] as ArtifactBlockData, meta);
          }
          return;
        }

        // New artifact
        state.streamingArtifacts.push(artifact);

        // Artifacts can arrive mid-step (e.g. think -> tool -> artifact -> think).
        // Do not force-close the active thinking block here, otherwise later
        // post-tool reflections get split into a duplicate block.
        state.streamingBlocks.push(applyDisplayMeta({
          type: "artifact",
          id: artifact.artifact_id,
          artifact,
          node,
          displayRole: "artifact",
          presentation: "compact",
        } as ArtifactBlockData, meta));
      });
    },

    // ---- Sprint 141: ThinkingFlow phase actions ----

    addOrUpdatePhase: (label, node) => {
      set((state) => {
        for (const p of state.streamingPhases) {
          if (p.status === "active") {
            p.status = "completed";
            p.endTime = Date.now();
          }
        }
        state.streamingPhases.push({
          id: uuidv4(),
          label,
          node,
          status: "active",
          startTime: Date.now(),
          thinkingContent: "",
          toolCalls: [],
          statusMessages: [],
        });
      });
    },

    appendPhaseThinking: (content) => {
      set((state) => {
        for (let i = state.streamingPhases.length - 1; i >= 0; i--) {
          if (state.streamingPhases[i].status === "active") {
            const phase = state.streamingPhases[i];
            phase.thinkingContent = phase.thinkingContent
              ? phase.thinkingContent + "\n" + content
              : content;
            break;
          }
        }
      });
    },

    appendPhaseThinkingDelta: (delta, _node) => {
      set((state) => {
        for (let i = state.streamingPhases.length - 1; i >= 0; i--) {
          if (state.streamingPhases[i].status === "active") {
            state.streamingPhases[i].thinkingContent += delta;
            break;
          }
        }
      });
    },

    closeActivePhase: (durationMs) => {
      set((state) => {
        for (const p of state.streamingPhases) {
          if (p.status === "active") {
            p.status = "completed";
            p.endTime = durationMs != null ? p.startTime + durationMs : Date.now();
          }
        }
      });
    },

    appendPhaseStatus: (message, node) => {
      set((state) => {
        let idx = -1;
        for (let i = state.streamingPhases.length - 1; i >= 0; i--) {
          if (state.streamingPhases[i].status === "active") {
            if (!node || state.streamingPhases[i].node === node) { idx = i; break; }
            if (idx === -1) idx = i;
          }
        }
        if (idx >= 0) {
          state.streamingPhases[idx].statusMessages.push(message);
        } else {
          state.streamingPhases.push({
            id: uuidv4(),
            label: message,
            node,
            status: "active",
            startTime: Date.now(),
            thinkingContent: "",
            toolCalls: [],
            statusMessages: [],
          });
        }
      });
    },

    appendPhaseToolCall: (tc) => {
      set((state) => {
        for (let i = state.streamingPhases.length - 1; i >= 0; i--) {
          if (state.streamingPhases[i].status === "active") {
            state.streamingPhases[i].toolCalls.push(tc);
            break;
          }
        }
      });
    },

    updatePhaseToolCallResult: (id, result) => {
      set((state) => {
        for (const phase of state.streamingPhases) {
          const tc = phase.toolCalls.find((t) => t.id === id);
          if (tc) {
            tc.result = result;
            break;
          }
        }
      });
    },

    closeThinkingBlock: (durationMs) => {
      set((state) => {
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
          lastBlock.endTime =
            durationMs != null && lastBlock.startTime
              ? lastBlock.startTime + durationMs
              : Date.now();
        }
      });
    },

    appendToolCall: (tc, meta) => {
      set((state) => {
        // Flat field - backward compat
        state.streamingToolCalls.push(tc);

        // Keep tool call mirrored on current thinking block for backward compat
        const openBlock = findLastOpenThinkingBlock(state.streamingBlocks, meta?.stepId, tc.node);
        if (openBlock) {
          openBlock.toolCalls.push(tc);
        }

        state.streamingBlocks.push(applyDisplayMeta({
          type: "tool_execution",
          id: tc.id,
          tool: { ...tc },
          node: tc.node,
          status: tc.result ? "completed" : "pending",
        } as ToolExecutionBlockData, {
          displayRole: "tool",
          presentation: meta?.presentation || "technical",
          ...meta,
        }));
      });
    },

    updateToolCallResult: (id, result, meta) => {
      set((state) => {
        // Flat field - backward compat
        const flatTc = state.streamingToolCalls.find((tc) => tc.id === id);
        if (flatTc) flatTc.result = result;

        // Backward compat: find tool call in thinking blocks and update
        for (const block of state.streamingBlocks) {
          if (block.type === "thinking") {
            const tc = block.toolCalls.find((t) => t.id === id);
            if (tc) {
              tc.result = result;
            }
          }
          if (block.type === "tool_execution" && block.tool.id === id) {
            block.tool.result = result;
            block.status = "completed";
            applyDisplayMeta(block, meta);
          }
        }
      });
    },

    setPendingStreamMetadata: (metadata) => {
      if (!metadata) return;
      const wasStreaming = get().isStreaming;

      set((state) => {
        if (state.isStreaming) {
          state.pendingStreamMetadata = metadata;
          return;
        }

        if (!state.streamCompletedAt || Date.now() - state.streamCompletedAt > 15_000) {
          return;
        }

        const conv = state.conversations.find((c) => c.id === state.activeConversationId);
        const message = conv?.messages[conv.messages.length - 1];
        if (!conv || !message || message.role !== "assistant") return;

        mergeStreamMetadataIntoMessage(message, metadata);

        if (metadata.session_id && !conv.session_id) {
          conv.session_id = metadata.session_id;
        }

        const metaAny = metadata as unknown as Record<string, unknown>;
        const backendThreadId = typeof metaAny?.thread_id === "string" ? metaAny.thread_id : undefined;
        if (backendThreadId && !conv.thread_id) {
          conv.thread_id = backendThreadId;
        }
      });

      if (!wasStreaming) {
        persistConversationsImmediate(get().conversations);
      }
    },

    finalizeStream: (metadata) => {
      const {
        isStreaming,
        activeConversationId,
        streamingContent,
        streamingThinking,
        streamingSources,
        streamingToolCalls,
        streamingBlocks,
        streamingDomainNotice,
        streamingPreviews,
        streamingArtifacts,
        pendingStreamMetadata,
      } = get();

      // Sprint 153b: Guard against double finalization.
      if (!isStreaming || !activeConversationId) return;

      const effectiveMetadata = metadata ?? pendingStreamMetadata ?? undefined;
      const metaAny = effectiveMetadata as unknown as Record<string, unknown> | undefined;
      const suggestedQuestions = extractSuggestedQuestions(effectiveMetadata);

      // Close any remaining open thinking blocks (immutable copy for message)
      const closedBlocks: ContentBlock[] = streamingBlocks.map((block) => {
        if (block.type === "thinking" && !block.endTime) {
          return { ...block, endTime: Date.now(), stepState: "completed" as const };
        }
        return block;
      });

      // Sprint 154: Keep full screenshot images (no stripping).
      // Storage cost is minimal and full images look more professional.

      const message: Message = {
        id: uuidv4(),
        role: "assistant",
        content: buildDegradedAssistantContent({
          streamingContent,
          streamingBlocks,
          streamingArtifacts,
          streamingPreviews,
        }),
        timestamp: new Date().toISOString(),
        sources: streamingSources.length > 0 ? streamingSources : undefined,
        thinking: streamingThinking || undefined,
        reasoning_trace: effectiveMetadata?.reasoning_trace,
        suggested_questions: suggestedQuestions,
        tool_calls: streamingToolCalls.length > 0 ? [...streamingToolCalls] : undefined,
        blocks: closedBlocks.length > 0 ? closedBlocks : undefined,
        domain_notice: streamingDomainNotice || undefined,
        previews: streamingPreviews.length > 0 ? [...streamingPreviews] : undefined,
        artifacts: streamingArtifacts.length > 0 ? [...streamingArtifacts] : undefined,
        metadata: metaAny,
      };

      const backendSessionId = effectiveMetadata?.session_id;
      // Sprint 225: Save thread_id for cross-platform sync
      const backendThreadId = (metaAny?.thread_id as string) || undefined;

      set((state) => {
        resetStreamingDraft(state);
        state.streamError = "";
        state.streamCompletedAt = Date.now();

        const conv = state.conversations.find((c) => c.id === activeConversationId);
        if (conv) {
          conv.messages.push(message);
          conv.updated_at = new Date().toISOString();
          if (backendSessionId && !conv.session_id) {
            conv.session_id = backendSessionId;
          }
          // Sprint 225: Store thread_id for server sync
          if (backendThreadId && !conv.thread_id) {
            conv.thread_id = backendThreadId;
          }
        }
      });

      persistConversationsImmediate(get().conversations);
    },

    setStreamError: (error) => {
      const { activeConversationId } = get();
      if (!activeConversationId) return;

      const message: Message = {
        id: uuidv4(),
        role: "assistant",
        content: `❌ Lỗi: ${error}`,
        timestamp: new Date().toISOString(),
      };

      set((state) => {
        resetStreamingDraft(state);
        state.streamError = error;
        state.streamCompletedAt = null;

        const conv = state.conversations.find((c) => c.id === activeConversationId);
        if (conv) {
          conv.messages.push(message);
          conv.updated_at = new Date().toISOString();
        }
      });

      persistConversationsImmediate(get().conversations);
    },

    setMessageFeedback: (messageId, feedback) => {
      set((state) => {
        for (const conv of state.conversations) {
          const msg = conv.messages.find((m) => m.id === messageId);
          if (msg) {
            msg.feedback = feedback;
            break;
          }
        }
      });
      persistConversations(get().conversations);
    },

    clearStreaming: () => {
      set((state) => {
        resetStreamingDraft(state);
        state.streamError = "";
        state.streamCompletedAt = null;
      });
    },

    // Sprint 225: Sync conversation list from server (additive merge)
    syncFromServer: async () => {
      if (_syncInProgress) return;
      _syncInProgress = true;
      try {
        const { useAuthStore } = await import("@/stores/auth-store");
        const authState = useAuthStore.getState();
        if (authState.isLoaded && !authState.isAuthenticated) return;

        const { fetchThreads } = await import("@/api/threads");
        const resp = await fetchThreads(200, 0);
        if (!resp.threads || resp.threads.length === 0) return;

        set((state) => {
          // Build lookup of existing local conversations by thread_id
          const byThreadId = new Map<string, Conversation>();
          for (const c of state.conversations) {
            if (c.thread_id) byThreadId.set(c.thread_id, c);
          }

          for (const t of resp.threads) {
            const existing = byThreadId.get(t.thread_id);
            if (existing) {
              // Update metadata from server (server is source of truth for list)
              // Update title unless user explicitly renamed it (user_renamed flag)
              if (t.title && !existing.user_renamed) {
                existing.title = t.title;
              }
              existing.message_count = t.message_count;
            } else {
              // New conversation from another platform — add stub
              // Extract session_id from thread_id format:
              // "user_{uid}__session_{sid}" or "org_{oid}__user_{uid}__session_{sid}"
              let sessionId: string | undefined;
              const sesMatch = t.thread_id.match(/__session_(.+)$/);
              if (sesMatch) sessionId = sesMatch[1];

              const stub: Conversation = {
                id: t.thread_id, // Use thread_id as local id for dedup
                title: t.title || "Cuộc trò chuyện mới",
                domain_id: t.domain_id || undefined,
                created_at: t.created_at || new Date().toISOString(),
                updated_at: t.updated_at || new Date().toISOString(),
                messages: [], // Lazy-loaded on demand
                session_id: sessionId,
                thread_id: t.thread_id,
                message_count: t.message_count,
              };
              state.conversations.push(stub);
            }
          }

          // Sort by updated_at descending
          state.conversations.sort((a, b) =>
            (b.updated_at || "").localeCompare(a.updated_at || "")
          );
        });

        persistConversations(get().conversations);
      } catch (err) {
        // Graceful degradation — server unreachable, keep local conversations
        console.debug("[chat-store] syncFromServer failed:", err);
      } finally {
        _syncInProgress = false;
      }
    },

    // Sprint 225: Lazy-load messages from server for a conversation with no local messages
    loadServerMessages: async (conversationId: string) => {
      const conv = get().conversations.find((c) => c.id === conversationId);
      if (!conv || conv.messages.length > 0 || !conv.thread_id) return;

      try {
        const { useAuthStore } = await import("@/stores/auth-store");
        const authState = useAuthStore.getState();
        if (authState.isLoaded && !authState.isAuthenticated) return;

        const { fetchThreadMessages } = await import("@/api/threads");
        const msgs = await fetchThreadMessages(conv.thread_id, 500);
        if (!msgs || msgs.length === 0) return;

        set((state) => {
          const target = state.conversations.find((c) => c.id === conversationId);
          if (target && target.messages.length === 0) {
            target.messages = msgs.map((m) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: m.created_at || new Date().toISOString(),
            }));
          }
        });

        persistConversations(get().conversations);
      } catch (err) {
        console.debug("[chat-store] loadServerMessages failed:", err);
      }
    },

    // Sprint 218: Clear in-memory state on logout (prevent cross-user leakage)
    clearForLogout: () => {
      if (_persistTimer) clearTimeout(_persistTimer);
      _currentUserId = null;
      set((state) => {
        state.conversations = [];
        state.activeConversationId = null;
        state.isLoaded = false;
      });
    },

    // Sprint 218: Switch user and reload their conversations
    switchUser: async (userId: string | null) => {
      if (_persistTimer) clearTimeout(_persistTimer);
      _currentUserId = userId;
      try {
        const saved = await loadStore<Conversation[]>(getStoreName(), getStoreKey(), []);
        set((state) => {
          state.conversations = saved;
          state.activeConversationId = saved.length > 0 ? saved[0].id : null;
          state.isLoaded = true;
        });
      } catch (err) {
        console.warn("[chat-store] Failed to load conversations for user:", err);
        set((state) => {
          state.conversations = [];
          state.activeConversationId = null;
          state.isLoaded = true;
        });
      }
    },
  }))
);
