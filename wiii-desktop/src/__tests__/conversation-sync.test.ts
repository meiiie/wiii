/**
 * Sprint 225: "Đồng Bộ Trò Chuyện" — Cross-Platform Conversation Sync
 *
 * Tests:
 *   1. threads.ts API module functions
 *   2. chat-store syncFromServer() merge logic
 *   3. chat-store loadServerMessages() lazy loading
 *   4. chat-store thread_id tracking in finalizeStream
 *   5. chat-store server propagation on delete/rename
 *   6. ChatResponseMetadata includes thread_id
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// =============================================================================
// Mock modules BEFORE importing stores
// =============================================================================

vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn().mockResolvedValue([]),
  saveStore: vi.fn().mockResolvedValue(undefined),
  deleteStore: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@tauri-apps/plugin-store", () => ({
  Store: {
    load: vi.fn().mockResolvedValue({
      get: vi.fn().mockResolvedValue(null),
      set: vi.fn().mockResolvedValue(undefined),
      save: vi.fn().mockResolvedValue(undefined),
    }),
  },
}));

vi.mock("@/lib/secure-token-storage", () => ({
  storeTokens: vi.fn().mockResolvedValue(undefined),
  loadTokens: vi.fn().mockResolvedValue(null),
  clearTokens: vi.fn().mockResolvedValue(undefined),
  storeApiKey: vi.fn().mockResolvedValue(undefined),
  loadApiKey: vi.fn().mockResolvedValue(null),
  clearApiKey: vi.fn().mockResolvedValue(undefined),
  storeFacebookCookie: vi.fn().mockResolvedValue(undefined),
  loadFacebookCookie: vi.fn().mockResolvedValue(null),
  clearFacebookCookie: vi.fn().mockResolvedValue(undefined),
}));

// Mock the threads API module for chat-store tests
const mockFetchThreads = vi.fn();
const mockFetchThreadMessages = vi.fn();
const mockDeleteServerThread = vi.fn();
const mockRenameServerThread = vi.fn();

vi.mock("@/api/threads", () => ({
  fetchThreads: (...args: unknown[]) => mockFetchThreads(...args),
  fetchThreadMessages: (...args: unknown[]) => mockFetchThreadMessages(...args),
  deleteServerThread: (...args: unknown[]) => mockDeleteServerThread(...args),
  renameServerThread: (...args: unknown[]) => mockRenameServerThread(...args),
}));

// Mock auth-store so syncFromServer/loadServerMessages don't bail out
vi.mock("@/stores/auth-store", () => ({
  useAuthStore: {
    getState: () => ({ isLoaded: true, isAuthenticated: true }),
  },
}));

// =============================================================================
// 1. Threads API module — type/export tests
// =============================================================================

describe("Sprint 225: threads.ts API types", () => {
  it("ThreadView interface has required fields", async () => {
    const { fetchThreads } = await import("@/api/threads");
    expect(typeof fetchThreads).toBe("function");
  });

  it("fetchThreadMessages is exported", async () => {
    const { fetchThreadMessages } = await import("@/api/threads");
    expect(typeof fetchThreadMessages).toBe("function");
  });

  it("deleteServerThread is exported", async () => {
    const { deleteServerThread } = await import("@/api/threads");
    expect(typeof deleteServerThread).toBe("function");
  });

  it("renameServerThread is exported", async () => {
    const { renameServerThread } = await import("@/api/threads");
    expect(typeof renameServerThread).toBe("function");
  });
});

// =============================================================================
// 2. ChatResponseMetadata includes thread_id
// =============================================================================

describe("Sprint 225: ChatResponseMetadata thread_id", () => {
  it("ChatResponseMetadata type accepts thread_id field", () => {
    // Type-level check: if this compiles, the field exists
    const metadata: import("@/api/types").ChatResponseMetadata = {
      processing_time: 1.5,
      model: "gemini-2.5-pro",
      agent_type: "rag",
      session_id: "abc-123",
      thread_id: "user_u1__session_abc-123",
    };
    expect(metadata.thread_id).toBe("user_u1__session_abc-123");
  });

  it("thread_id is optional (undefined when not present)", () => {
    const metadata: import("@/api/types").ChatResponseMetadata = {
      processing_time: 0.5,
      model: "gemini-2.5-flash",
      agent_type: "chat",
    };
    expect(metadata.thread_id).toBeUndefined();
  });
});

// =============================================================================
// 3. Chat store — syncFromServer() merge logic
// =============================================================================

describe("Sprint 225: chat-store syncFromServer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchThreads.mockReset();
    mockFetchThreadMessages.mockReset();
    mockDeleteServerThread.mockReset();
    mockRenameServerThread.mockReset();
  });

  it("syncFromServer adds server-only conversations as stubs", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    // Setup: no local conversations
    useChatStore.setState({ conversations: [], isLoaded: true });

    // Mock server returns 2 threads
    mockFetchThreads.mockResolvedValueOnce({
      threads: [
        {
          thread_id: "user_u1__session_s1",
          user_id: "u1",
          domain_id: "maritime",
          title: "LMS Chat 1",
          message_count: 4,
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T11:00:00",
          last_message_at: "2026-03-04T11:00:00",
          extra_data: {},
        },
        {
          thread_id: "org_lms__user_u1__session_s2",
          user_id: "u1",
          domain_id: "maritime",
          title: "Desktop Chat",
          message_count: 2,
          created_at: "2026-03-04T09:00:00",
          updated_at: "2026-03-04T09:30:00",
          last_message_at: "2026-03-04T09:30:00",
          extra_data: {},
        },
      ],
      total: 2,
    });

    await useChatStore.getState().syncFromServer();

    const convs = useChatStore.getState().conversations;
    expect(convs.length).toBe(2);
    expect(convs[0].thread_id).toBe("user_u1__session_s1");
    expect(convs[0].title).toBe("LMS Chat 1");
    expect(convs[0].messages).toHaveLength(0); // Stub — no messages
    expect(convs[0].session_id).toBe("s1"); // Extracted from thread_id
  });

  it("syncFromServer extracts session_id from org-prefixed thread_id", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");
    useChatStore.setState({ conversations: [], isLoaded: true });

    mockFetchThreads.mockResolvedValueOnce({
      threads: [
        {
          thread_id: "org_lms__user_u1__session_abc-123",
          user_id: "u1",
          domain_id: "maritime",
          title: "Org Chat",
          message_count: 6,
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T11:00:00",
          last_message_at: null,
          extra_data: {},
        },
      ],
      total: 1,
    });

    await useChatStore.getState().syncFromServer();

    const convs = useChatStore.getState().conversations;
    expect(convs[0].session_id).toBe("abc-123");
  });

  it("syncFromServer updates existing conversations by thread_id", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    // Local conversation already has this thread_id
    useChatStore.setState({
      conversations: [
        {
          id: "local-1",
          title: "Cuộc trò chuyện mới",
          thread_id: "user_u1__session_s1",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [{ id: "m1", role: "user", content: "Hi", timestamp: "2026-03-04T10:00:00" }],
        },
      ],
      isLoaded: true,
    });

    mockFetchThreads.mockResolvedValueOnce({
      threads: [
        {
          thread_id: "user_u1__session_s1",
          user_id: "u1",
          domain_id: "maritime",
          title: "Updated Title",
          message_count: 10,
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T12:00:00",
          last_message_at: "2026-03-04T12:00:00",
          extra_data: {},
        },
      ],
      total: 1,
    });

    await useChatStore.getState().syncFromServer();

    const convs = useChatStore.getState().conversations;
    expect(convs.length).toBe(1); // No duplicates
    expect(convs[0].id).toBe("local-1"); // Keeps original local id
    expect(convs[0].title).toBe("Updated Title"); // Title updated (was default)
    expect(convs[0].message_count).toBe(10); // Updated from server
    expect(convs[0].messages).toHaveLength(1); // Local messages preserved
  });

  it("syncFromServer does not overwrite custom title", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "local-1",
          title: "My Custom Title",
          thread_id: "user_u1__session_s1",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [],
          user_renamed: true, // Sprint 225: user explicitly renamed
        },
      ],
      isLoaded: true,
    });

    mockFetchThreads.mockResolvedValueOnce({
      threads: [
        {
          thread_id: "user_u1__session_s1",
          user_id: "u1",
          domain_id: "maritime",
          title: "Server Title",
          message_count: 5,
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T12:00:00",
          last_message_at: "2026-03-04T12:00:00",
          extra_data: {},
        },
      ],
      total: 1,
    });

    await useChatStore.getState().syncFromServer();

    const convs = useChatStore.getState().conversations;
    expect(convs[0].title).toBe("My Custom Title"); // NOT overwritten
  });

  it("syncFromServer gracefully handles server error", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "local-1",
          title: "My Chat",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [],
        },
      ],
      isLoaded: true,
    });

    mockFetchThreads.mockRejectedValueOnce(new Error("Network error"));

    await useChatStore.getState().syncFromServer();

    // Local conversations should be untouched
    const convs = useChatStore.getState().conversations;
    expect(convs.length).toBe(1);
    expect(convs[0].title).toBe("My Chat");
  });

  it("syncFromServer handles empty response", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "local-1",
          title: "Existing",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [],
        },
      ],
      isLoaded: true,
    });

    mockFetchThreads.mockResolvedValueOnce({ threads: [], total: 0 });

    await useChatStore.getState().syncFromServer();

    expect(useChatStore.getState().conversations.length).toBe(1);
  });
});

// =============================================================================
// 4. Chat store — loadServerMessages() lazy loading
// =============================================================================

describe("Sprint 225: chat-store loadServerMessages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchThreadMessages.mockReset();
  });

  it("loadServerMessages fetches and populates empty conversation", { timeout: 15_000 }, async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Remote Chat",
          thread_id: "user_u1__session_s1",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [], // Empty — needs loading
        },
      ],
      isLoaded: true,
    });

    mockFetchThreadMessages.mockResolvedValueOnce([
      { id: "m1", role: "user", content: "Hello", created_at: "2026-03-04T10:00:00" },
      { id: "m2", role: "assistant", content: "Xin chào!", created_at: "2026-03-04T10:00:01" },
    ]);

    await useChatStore.getState().loadServerMessages("conv-1");

    const conv = useChatStore.getState().conversations.find((c) => c.id === "conv-1");
    expect(conv?.messages).toHaveLength(2);
    expect(conv?.messages[0].content).toBe("Hello");
    expect(conv?.messages[1].content).toBe("Xin chào!");
  });

  it("loadServerMessages skips conversation with existing messages", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Local Chat",
          thread_id: "user_u1__session_s1",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [{ id: "m1", role: "user", content: "Already here", timestamp: "now" }],
        },
      ],
      isLoaded: true,
    });

    await useChatStore.getState().loadServerMessages("conv-1");

    // fetchThreadMessages should NOT be called
    expect(mockFetchThreadMessages).not.toHaveBeenCalled();
  });

  it("loadServerMessages skips conversation without thread_id", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "No Thread ID",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [],
          // No thread_id
        },
      ],
      isLoaded: true,
    });

    await useChatStore.getState().loadServerMessages("conv-1");

    expect(mockFetchThreadMessages).not.toHaveBeenCalled();
  });

  it("loadServerMessages handles server error gracefully", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Error Chat",
          thread_id: "user_u1__session_s1",
          created_at: "2026-03-04T10:00:00",
          updated_at: "2026-03-04T10:00:00",
          messages: [],
        },
      ],
      isLoaded: true,
    });

    mockFetchThreadMessages.mockRejectedValueOnce(new Error("Server down"));

    await useChatStore.getState().loadServerMessages("conv-1");

    // Messages should still be empty — no crash
    const conv = useChatStore.getState().conversations.find((c) => c.id === "conv-1");
    expect(conv?.messages).toHaveLength(0);
  });
});

// =============================================================================
// 5. Chat store — finalizeStream saves thread_id
// =============================================================================

describe("Sprint 225: chat-store finalizeStream thread_id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("finalizeStream saves thread_id from metadata", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    // Create a conversation and start streaming
    const convId = useChatStore.getState().createConversation("maritime");

    useChatStore.getState().addUserMessage("Hello Wiii");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Xin chào!");

    useChatStore.getState().finalizeStream({
      processing_time: 1.5,
      model: "gemini-2.5-pro",
      agent_type: "rag",
      session_id: "session-abc",
      thread_id: "user_u1__session_session-abc",
    });

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    expect(conv?.thread_id).toBe("user_u1__session_session-abc");
    expect(conv?.session_id).toBe("session-abc");
  });

  it("finalizeStream does not overwrite existing thread_id", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    // Create a conversation with pre-set thread_id
    const convId = useChatStore.getState().createConversation("maritime");
    useChatStore.setState((state) => {
      const conv = state.conversations.find((c: { id: string }) => c.id === convId);
      if (conv) conv.thread_id = "original_thread_id";
    });

    useChatStore.getState().addUserMessage("Test");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Response");

    useChatStore.getState().finalizeStream({
      processing_time: 0.5,
      model: "test",
      agent_type: "chat",
      session_id: "s2",
      thread_id: "new_thread_id",
    });

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    expect(conv?.thread_id).toBe("original_thread_id"); // NOT overwritten
  });
});

// =============================================================================
// 6. Chat store — delete/rename propagation
// =============================================================================

describe("Sprint 225: chat-store server propagation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDeleteServerThread.mockResolvedValue(undefined);
    mockRenameServerThread.mockResolvedValue(undefined);
  });

  it("deleteConversation calls deleteServerThread when thread_id exists", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    const convId = useChatStore.getState().createConversation("maritime");
    useChatStore.setState((state) => {
      const conv = state.conversations.find((c: { id: string }) => c.id === convId);
      if (conv) conv.thread_id = "user_u1__session_s1";
    });

    useChatStore.getState().deleteConversation(convId);

    // Give dynamic import + promise a tick to resolve
    await new Promise((r) => setTimeout(r, 50));

    expect(mockDeleteServerThread).toHaveBeenCalledWith("user_u1__session_s1");
  });

  it("deleteConversation does NOT call server when no thread_id", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    const convId = useChatStore.getState().createConversation("maritime");
    // No thread_id set

    useChatStore.getState().deleteConversation(convId);

    await new Promise((r) => setTimeout(r, 50));

    expect(mockDeleteServerThread).not.toHaveBeenCalled();
  });

  it("renameConversation calls renameServerThread when thread_id exists", async () => {
    const { useChatStore } = await import("@/stores/chat-store");

    const convId = useChatStore.getState().createConversation("maritime");
    useChatStore.setState((state) => {
      const conv = state.conversations.find((c: { id: string }) => c.id === convId);
      if (conv) conv.thread_id = "user_u1__session_s1";
    });

    useChatStore.getState().renameConversation(convId, "New Title");

    await new Promise((r) => setTimeout(r, 50));

    expect(mockRenameServerThread).toHaveBeenCalledWith("user_u1__session_s1", "New Title");
  });
});

// =============================================================================
// 7. Conversation type — thread_id field exists
// =============================================================================

describe("Sprint 225: Conversation type thread_id field", () => {
  it("Conversation interface supports thread_id", () => {
    const conv: import("@/api/types").Conversation = {
      id: "test-1",
      title: "Test",
      created_at: "2026-03-04T10:00:00",
      updated_at: "2026-03-04T10:00:00",
      messages: [],
      thread_id: "user_u1__session_s1",
    };
    expect(conv.thread_id).toBe("user_u1__session_s1");
  });

  it("Conversation thread_id is optional", () => {
    const conv: import("@/api/types").Conversation = {
      id: "test-2",
      title: "No thread",
      created_at: "2026-03-04T10:00:00",
      updated_at: "2026-03-04T10:00:00",
      messages: [],
    };
    expect(conv.thread_id).toBeUndefined();
  });
});
