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
  ImageInput,
} from "@/api/types";

const STORE_NAME = "conversations.json";
const STORE_KEY = "conversations";

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
  createConversation: (domainId?: string, organizationId?: string) => string;
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
  appendThinkingDelta: (delta: string, node?: string) => void;
  openThinkingBlock: (label: string, summary?: string, node?: string) => void;
  closeThinkingBlock: (durationMs?: number) => void;
  appendToolCall: (tc: ToolCallInfo) => void;
  updateToolCallResult: (id: string, result: string) => void;
  setStreamingDomainNotice: (notice: string) => void;
  /** Sprint 147: Append bold action text between thinking blocks */
  appendActionText: (text: string, node?: string) => void;
  /** Sprint 153: Append browser screenshot block. */
  appendScreenshot: (data: { url: string; image: string; label: string; node?: string }) => void;
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
  addPreviewItem: (item: PreviewItemData, node?: string) => void;
  /** Sprint 167: Add an artifact to the streaming state */
  addArtifact: (artifact: ArtifactData, node?: string) => void;
  // Sprint 141: ThinkingFlow phase actions
  addOrUpdatePhase: (label: string, node?: string) => void;
  appendPhaseThinking: (content: string) => void;
  appendPhaseThinkingDelta: (delta: string, node?: string) => void;
  closeActivePhase: (durationMs?: number) => void;
  appendPhaseStatus: (message: string, node?: string) => void;
  appendPhaseToolCall: (tc: ToolCallInfo) => void;
  updatePhaseToolCallResult: (id: string, result: string) => void;
  finalizeStream: (metadata?: ChatResponseMetadata) => void;
  setStreamError: (error: string) => void;
  setMessageFeedback: (messageId: string, feedback: "up" | "down" | null) => void;
  clearStreaming: () => void;
}

// Debounced persist — avoids excessive writes during streaming
let _persistTimer: ReturnType<typeof setTimeout> | null = null;

function persistConversations(conversations: Conversation[]) {
  if (_persistTimer) clearTimeout(_persistTimer);
  _persistTimer = setTimeout(() => {
    saveStore(STORE_NAME, STORE_KEY, conversations).catch((err) =>
      console.warn("[chat-store] Failed to persist:", err)
    );
  }, 2000);
}

function persistConversationsImmediate(conversations: Conversation[]) {
  if (_persistTimer) clearTimeout(_persistTimer);
  saveStore(STORE_NAME, STORE_KEY, conversations).catch((err) =>
    console.warn("[chat-store] Failed to persist:", err)
  );
}

/** Close the last open thinking block in-place (immer-compatible). */
function closeLastThinkingBlockDraft(blocks: ContentBlock[]): void {
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.type === "thinking" && !block.endTime) {
      block.endTime = Date.now();
      break;
    }
  }
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
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,

    loadConversations: async () => {
      try {
        const saved = await loadStore<Conversation[]>(STORE_NAME, STORE_KEY, []);
        if (saved.length > 0) {
          set((state) => {
            state.conversations = saved;
            state.activeConversationId = saved[0]?.id || null;
            state.isLoaded = true;
          });
        } else {
          set((state) => { state.isLoaded = true; });
        }
      } catch (err) {
        console.warn("[chat-store] Failed to load conversations:", err);
        set((state) => { state.isLoaded = true; });
      }
    },

    activeConversation: () => {
      const { conversations, activeConversationId } = get();
      return conversations.find((c) => c.id === activeConversationId);
    },

    createConversation: (domainId, organizationId) => {
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
      };

      set((state) => {
        state.conversations.unshift(conversation);
        state.activeConversationId = id;
      });

      persistConversationsImmediate(get().conversations);
      return id;
    },

    deleteConversation: (id) => {
      set((state) => {
        const idx = state.conversations.findIndex((c) => c.id === id);
        if (idx >= 0) state.conversations.splice(idx, 1);
        if (state.activeConversationId === id) {
          state.activeConversationId = state.conversations[0]?.id || null;
        }
      });
      persistConversationsImmediate(get().conversations);
    },

    setActiveConversation: (id) => {
      set((state) => { state.activeConversationId = id; });
    },

    renameConversation: (id, title) => {
      set((state) => {
        const conv = state.conversations.find((c) => c.id === id);
        if (conv) {
          conv.title = title;
          conv.updated_at = new Date().toISOString();
        }
      });
      persistConversationsImmediate(get().conversations);
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
        state.isStreaming = true;
        state.streamingContent = "";
        state.streamingThinking = "";
        state.streamingSources = [];
        state.streamingStep = "";
        state.streamingToolCalls = [];
        state.streamingBlocks = [];
        state.streamingStartTime = Date.now();
        state.streamingSteps = [];
        state.streamingDomainNotice = "";
        state.streamingPhases = [];
        state.streamingPreviews = [];
        state.streamingArtifacts = [];
        state._activeSubagentGroupId = null;
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
          state.streamingBlocks.push({ type: "answer", id: uuidv4(), content: chunk });
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

    appendThinkingDelta: (delta, node) => {
      set((state) => {
        // Flat field — backward compat
        state.streamingThinking += delta;

        // Block-based: append to last open thinking block, or create new one
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
          lastBlock.content += delta;
        } else {
          const groupId = state._activeSubagentGroupId;
          state.streamingBlocks.push({
            type: "thinking",
            id: uuidv4(),
            label: node || state.streamingStep || undefined,
            content: delta,
            toolCalls: [],
            startTime: Date.now(),
            ...(groupId ? { groupId, workerNode: node } : {}),
          });
        }
      });
    },

    openThinkingBlock: (label, summary, node) => {
      set((state) => {
        // Close any open thinking block first
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
          lastBlock.endTime = Date.now();
        }
        // Open new thinking block — tag with group + workerNode if inside parallel dispatch
        const groupId = state._activeSubagentGroupId;
        state.streamingBlocks.push({
          type: "thinking",
          id: uuidv4(),
          label,
          summary,
          content: "",
          toolCalls: [],
          startTime: Date.now(),
          ...(groupId ? { groupId, workerNode: node } : {}),
        });
      });
    },

    setStreamingDomainNotice: (notice) => {
      set((state) => { state.streamingDomainNotice = notice; });
    },

    appendActionText: (text, node) => {
      set((state) => {
        closeLastThinkingBlockDraft(state.streamingBlocks);
        state.streamingBlocks.push({ type: "action_text", id: uuidv4(), content: text, node });
      });
    },

    appendScreenshot: (data) => {
      set((state) => {
        closeLastThinkingBlockDraft(state.streamingBlocks);
        const block: ScreenshotBlockData = {
          type: "screenshot",
          id: `screenshot-${Date.now()}`,
          ...data,
        };
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

    addPreviewItem: (item, node) => {
      set((state) => {
        // Dedup by preview_id
        if (state.streamingPreviews.some((p) => p.preview_id === item.preview_id)) return;
        state.streamingPreviews.push(item);

        // Find or create preview block in streamingBlocks
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "preview" && (lastBlock as PreviewBlockData).node === node) {
          // Append to existing group
          (lastBlock as PreviewBlockData).items.push(item);
        } else {
          // New preview block
          closeLastThinkingBlockDraft(state.streamingBlocks);
          state.streamingBlocks.push({
            type: "preview",
            id: uuidv4(),
            items: [item],
            node,
          } as PreviewBlockData);
        }
      });
    },

    // ---- Sprint 167: Artifact actions ----

    addArtifact: (artifact, node) => {
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
          }
          return;
        }

        // New artifact
        state.streamingArtifacts.push(artifact);

        // Add artifact block to streamingBlocks
        closeLastThinkingBlockDraft(state.streamingBlocks);
        state.streamingBlocks.push({
          type: "artifact",
          id: artifact.artifact_id,
          artifact,
          node,
        } as ArtifactBlockData);
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

    appendToolCall: (tc) => {
      set((state) => {
        // Flat field — backward compat
        state.streamingToolCalls.push(tc);

        // Block-based: add to last thinking block, or create one
        const lastBlock = state.streamingBlocks[state.streamingBlocks.length - 1];
        if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
          lastBlock.toolCalls.push(tc);
        } else if (lastBlock?.type === "thinking" && lastBlock.endTime) {
          // Sprint 146b: Reopen closed thinking block (safety net)
          lastBlock.endTime = undefined;
          lastBlock.toolCalls.push(tc);
        } else {
          state.streamingBlocks.push({
            type: "thinking",
            id: uuidv4(),
            content: "",
            toolCalls: [tc],
            startTime: Date.now(),
          });
        }
      });
    },

    updateToolCallResult: (id, result) => {
      set((state) => {
        // Flat field — backward compat
        const flatTc = state.streamingToolCalls.find((tc) => tc.id === id);
        if (flatTc) flatTc.result = result;

        // Block-based: find tool call in blocks and update
        for (const block of state.streamingBlocks) {
          if (block.type !== "thinking") continue;
          const tc = block.toolCalls.find((t) => t.id === id);
          if (tc) {
            tc.result = result;
            break;
          }
        }
      });
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
      } = get();

      // Sprint 153b: Guard against double finalization (onMetadata + onDone race)
      if (!isStreaming || !activeConversationId) return;

      // Extract suggested_questions from metadata if present
      const metaAny = metadata as Record<string, unknown> | undefined;
      const rawSQ = metaAny?.suggested_questions ?? (metaAny?.data as Record<string, unknown> | undefined)?.suggested_questions;
      const suggestedQuestions = Array.isArray(rawSQ) ? rawSQ as string[] : undefined;

      // Close any remaining open thinking blocks (immutable copy for message)
      const closedBlocks = streamingBlocks.map((block) => {
        if (block.type === "thinking" && !block.endTime) {
          return { ...block, endTime: Date.now() };
        }
        return block;
      });

      // Sprint 154: Keep full screenshot images (no stripping).
      // Storage cost is minimal and full images look more professional.

      const message: Message = {
        id: uuidv4(),
        role: "assistant",
        content: streamingContent,
        timestamp: new Date().toISOString(),
        sources: streamingSources.length > 0 ? streamingSources : undefined,
        thinking: streamingThinking || undefined,
        reasoning_trace: metadata?.reasoning_trace,
        suggested_questions: suggestedQuestions,
        tool_calls: streamingToolCalls.length > 0 ? [...streamingToolCalls] : undefined,
        blocks: closedBlocks.length > 0 ? closedBlocks : undefined,
        domain_notice: streamingDomainNotice || undefined,
        previews: streamingPreviews.length > 0 ? [...streamingPreviews] : undefined,
        artifacts: streamingArtifacts.length > 0 ? [...streamingArtifacts] : undefined,
        metadata: metaAny,
      };

      const backendSessionId = metadata?.session_id;

      set((state) => {
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
        state._activeSubagentGroupId = null;
        state.streamError = "";
        state.streamCompletedAt = Date.now();

        const conv = state.conversations.find((c) => c.id === activeConversationId);
        if (conv) {
          conv.messages.push(message);
          conv.updated_at = new Date().toISOString();
          if (backendSessionId && !conv.session_id) {
            conv.session_id = backendSessionId;
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
        state._activeSubagentGroupId = null;
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
        state._activeSubagentGroupId = null;
        state.streamError = "";
        state.streamCompletedAt = null;
      });
    },
  }))
);
