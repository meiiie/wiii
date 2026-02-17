/**
 * Chat store — conversations, messages, streaming state.
 * Conversations are persisted via tauri-plugin-store (or localStorage fallback).
 *
 * Sprint 62: Added streamingBlocks for interleaved thinking/answer rendering.
 * Old flat fields (streamingContent, streamingThinking, streamingToolCalls)
 * are kept for backward compatibility with tests and simple consumers.
 */
import { create } from "zustand";
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

  // Computed
  activeConversation: () => Conversation | undefined;

  // Persistence
  isLoaded: boolean;
  loadConversations: () => Promise<void>;

  // Actions
  createConversation: (domainId?: string) => string;
  deleteConversation: (id: string) => void;
  setActiveConversation: (id: string | null) => void;
  renameConversation: (id: string, title: string) => void;
  addUserMessage: (content: string) => string | null;
  startStreaming: () => void;
  appendStreamingContent: (chunk: string) => void;
  setStreamingThinking: (thinking: string) => void;
  setStreamingStep: (step: string) => void;
  setStreamingSources: (sources: SourceInfo[]) => void;
  addStreamingStep: (label: string, node?: string) => void;
  appendThinkingDelta: (delta: string, node?: string) => void;
  openThinkingBlock: (label: string) => void;
  closeThinkingBlock: (durationMs?: number) => void;
  appendToolCall: (tc: ToolCallInfo) => void;
  updateToolCallResult: (id: string, result: string) => void;
  setStreamingDomainNotice: (notice: string) => void;
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

/** Close the last thinking block (set endTime) */
function closeLastThinkingBlock(blocks: ContentBlock[]): ContentBlock[] {
  const updated = [...blocks];
  for (let i = updated.length - 1; i >= 0; i--) {
    const block = updated[i];
    if (block.type === "thinking" && !block.endTime) {
      updated[i] = { ...block, endTime: Date.now() };
      break;
    }
  }
  return updated;
}

export const useChatStore = create<ChatState>((set, get) => ({
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

  loadConversations: async () => {
    try {
      const saved = await loadStore<Conversation[]>(STORE_NAME, STORE_KEY, []);
      if (saved.length > 0) {
        set({
          conversations: saved,
          activeConversationId: saved[0]?.id || null,
          isLoaded: true,
        });
      } else {
        set({ isLoaded: true });
      }
    } catch (err) {
      console.warn("[chat-store] Failed to load conversations:", err);
      set({ isLoaded: true });
    }
  },

  activeConversation: () => {
    const { conversations, activeConversationId } = get();
    return conversations.find((c) => c.id === activeConversationId);
  },

  createConversation: (domainId) => {
    const id = uuidv4();
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id,
      title: "Cuộc trò chuyện mới",
      domain_id: domainId,
      created_at: now,
      updated_at: now,
      messages: [],
    };

    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: id,
    }));

    persistConversationsImmediate(get().conversations);
    return id;
  },

  deleteConversation: (id) => {
    set((state) => {
      const remaining = state.conversations.filter((c) => c.id !== id);
      return {
        conversations: remaining,
        activeConversationId:
          state.activeConversationId === id
            ? remaining[0]?.id || null
            : state.activeConversationId,
      };
    });
    persistConversationsImmediate(get().conversations);
  },

  setActiveConversation: (id) => {
    set({ activeConversationId: id });
  },

  renameConversation: (id, title) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title, updated_at: new Date().toISOString() } : c
      ),
    }));
    persistConversationsImmediate(get().conversations);
  },

  setSearchQuery: (query) => {
    set({ searchQuery: query });
  },

  pinConversation: (id) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, pinned: true } : c
      ),
    }));
    persistConversationsImmediate(get().conversations);
  },

  unpinConversation: (id) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, pinned: false } : c
      ),
    }));
    persistConversationsImmediate(get().conversations);
  },

  addUserMessage: (content) => {
    const { activeConversationId, conversations } = get();
    if (!activeConversationId) return null;

    const messageId = uuidv4();
    const message: Message = {
      id: messageId,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    // Auto-title from first message
    const conversation = conversations.find(
      (c) => c.id === activeConversationId
    );
    const isFirstMessage = conversation?.messages.length === 0;

    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === activeConversationId
          ? {
              ...c,
              messages: [...c.messages, message],
              updated_at: new Date().toISOString(),
              title: isFirstMessage
                ? content.slice(0, 50) + (content.length > 50 ? "..." : "")
                : c.title,
            }
          : c
      ),
    }));

    persistConversations(get().conversations);
    return messageId;
  },

  startStreaming: () => {
    set({
      isStreaming: true,
      streamingContent: "",
      streamingThinking: "",
      streamingSources: [],
      streamingStep: "",
      streamingToolCalls: [],
      streamingBlocks: [],
      streamingStartTime: Date.now(),
      streamingSteps: [],
      streamingDomainNotice: "",
    });
  },

  appendStreamingContent: (chunk) => {
    set((state) => {
      // Old field — backward compat
      const newContent = state.streamingContent + chunk;

      // Block-based: append to last answer block, or create new one
      let blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];

      if (lastBlock?.type === "answer") {
        // Append to existing answer block
        blocks[blocks.length - 1] = {
          ...lastBlock,
          content: lastBlock.content + chunk,
        };
      } else {
        // Close any open thinking block, then create new answer block
        blocks = closeLastThinkingBlock(blocks);
        blocks.push({ type: "answer", content: chunk });
      }

      return {
        streamingContent: newContent,
        streamingBlocks: blocks,
      };
    });
  },

  setStreamingThinking: (thinking) => {
    set((state) => {
      // Old field — backward compat
      const newThinking = state.streamingThinking
        ? state.streamingThinking + "\n" + thinking
        : thinking;

      // Block-based: append to last thinking block, or create new one
      let blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];

      if (lastBlock?.type === "thinking") {
        // Append to existing thinking block
        blocks[blocks.length - 1] = {
          ...lastBlock,
          content: lastBlock.content
            ? lastBlock.content + "\n" + thinking
            : thinking,
        };
      } else {
        // Create new thinking block (label from current streamingStep)
        blocks.push({
          type: "thinking",
          label: state.streamingStep || undefined,
          content: thinking,
          toolCalls: [],
          startTime: Date.now(),
        });
      }

      return {
        streamingThinking: newThinking,
        streamingBlocks: blocks,
      };
    });
  },

  setStreamingStep: (step) => {
    set((state) => {
      // Also update label on current thinking block if it has no label yet
      const blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "thinking" && !lastBlock.label && step) {
        blocks[blocks.length - 1] = { ...lastBlock, label: step };
      }
      return { streamingStep: step, streamingBlocks: blocks };
    });
  },

  setStreamingSources: (sources) => {
    set({ streamingSources: sources });
  },

  addStreamingStep: (label, node) => {
    set((state) => ({
      streamingSteps: [
        ...state.streamingSteps,
        { label, node, timestamp: Date.now() },
      ],
    }));
  },

  appendThinkingDelta: (delta, node) => {
    set((state) => {
      // Flat field — backward compat
      const newThinking = state.streamingThinking + delta;

      // Block-based: append to last open thinking block, or create new one
      let blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];

      if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
        // Append to existing open thinking block
        blocks[blocks.length - 1] = {
          ...lastBlock,
          content: lastBlock.content + delta,
        };
      } else {
        // Create new thinking block
        blocks.push({
          type: "thinking",
          label: node || state.streamingStep || undefined,
          content: delta,
          toolCalls: [],
          startTime: Date.now(),
        });
      }

      return {
        streamingThinking: newThinking,
        streamingBlocks: blocks,
      };
    });
  },

  openThinkingBlock: (label) => {
    set((state) => {
      // Close any open thinking block first
      const blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
        blocks[blocks.length - 1] = { ...lastBlock, endTime: Date.now() };
      }
      // Open new thinking block
      blocks.push({
        type: "thinking",
        label,
        content: "",
        toolCalls: [],
        startTime: Date.now(),
      });
      return { streamingBlocks: blocks };
    });
  },

  setStreamingDomainNotice: (notice) => {
    set({ streamingDomainNotice: notice });
  },

  closeThinkingBlock: (durationMs) => {
    set((state) => {
      const blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "thinking" && !lastBlock.endTime) {
        const endTime =
          durationMs != null && lastBlock.startTime
            ? lastBlock.startTime + durationMs
            : Date.now();
        blocks[blocks.length - 1] = { ...lastBlock, endTime };
      }
      return { streamingBlocks: blocks };
    });
  },

  appendToolCall: (tc) => {
    set((state) => {
      // Old field — backward compat
      const newToolCalls = [...state.streamingToolCalls, tc];

      // Block-based: add to last thinking block, or create one
      let blocks = [...state.streamingBlocks];
      const lastBlock = blocks[blocks.length - 1];

      if (lastBlock?.type === "thinking") {
        blocks[blocks.length - 1] = {
          ...lastBlock,
          toolCalls: [...lastBlock.toolCalls, tc],
        };
      } else {
        // Create a thinking block for this tool call
        blocks.push({
          type: "thinking",
          content: "",
          toolCalls: [tc],
          startTime: Date.now(),
        });
      }

      return {
        streamingToolCalls: newToolCalls,
        streamingBlocks: blocks,
      };
    });
  },

  updateToolCallResult: (id, result) => {
    set((state) => {
      // Old field — backward compat
      const newToolCalls = state.streamingToolCalls.map((tc) =>
        tc.id === id ? { ...tc, result } : tc
      );

      // Block-based: find tool call in blocks and update
      const blocks = state.streamingBlocks.map((block) => {
        if (block.type !== "thinking") return block;
        const hasMatch = block.toolCalls.some((tc) => tc.id === id);
        if (!hasMatch) return block;
        return {
          ...block,
          toolCalls: block.toolCalls.map((tc) =>
            tc.id === id ? { ...tc, result } : tc
          ),
        };
      });

      return {
        streamingToolCalls: newToolCalls,
        streamingBlocks: blocks,
      };
    });
  },

  finalizeStream: (metadata) => {
    const {
      activeConversationId,
      streamingContent,
      streamingThinking,
      streamingSources,
      streamingToolCalls,
      streamingBlocks,
      streamingDomainNotice,
    } = get();

    if (!activeConversationId) return;

    // Extract suggested_questions from metadata if present
    // SSE metadata may carry extra fields beyond ChatResponseMetadata
    const metaAny = metadata as Record<string, unknown> | undefined;
    const rawSQ = metaAny?.suggested_questions ?? (metaAny?.data as Record<string, unknown> | undefined)?.suggested_questions;
    const suggestedQuestions = Array.isArray(rawSQ) ? rawSQ as string[] : undefined;

    // Close any remaining open thinking blocks
    const finalBlocks = closeLastThinkingBlock(streamingBlocks);

    const message: Message = {
      id: uuidv4(),
      role: "assistant",
      content: streamingContent,
      timestamp: new Date().toISOString(),
      sources: streamingSources.length > 0 ? streamingSources : undefined,
      thinking: streamingThinking || undefined,
      reasoning_trace: metadata?.reasoning_trace,
      suggested_questions: suggestedQuestions,
      tool_calls: streamingToolCalls.length > 0 ? streamingToolCalls : undefined,
      blocks: finalBlocks.length > 0 ? finalBlocks : undefined,
      domain_notice: streamingDomainNotice || undefined,
      metadata: metaAny,
    };

    // Sprint 121b: Save backend session_id to conversation for history continuity
    const backendSessionId = metadata?.session_id;

    set((state) => ({
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
      conversations: state.conversations.map((c) =>
        c.id === activeConversationId
          ? {
              ...c,
              messages: [...c.messages, message],
              updated_at: new Date().toISOString(),
              // Persist backend session_id so next message uses same session
              ...(backendSessionId && !c.session_id
                ? { session_id: backendSessionId }
                : {}),
            }
          : c
      ),
    }));

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

    set((state) => ({
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
      conversations: state.conversations.map((c) =>
        c.id === activeConversationId
          ? {
              ...c,
              messages: [...c.messages, message],
              updated_at: new Date().toISOString(),
            }
          : c
      ),
    }));

    persistConversationsImmediate(get().conversations);
  },

  setMessageFeedback: (messageId, feedback) => {
    set((state) => ({
      conversations: state.conversations.map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === messageId ? { ...m, feedback } : m
        ),
      })),
    }));
    persistConversations(get().conversations);
  },

  clearStreaming: () => {
    set({
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
    });
  },
}));
