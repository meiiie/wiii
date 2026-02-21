/**
 * Sprint 154: Persistent Screenshots + Facebook Cookie Settings.
 *
 * Tests:
 * 1. ScreenshotBlockData type — ContentBlock union
 * 2. Store — appendScreenshot, finalizeStream keeps full image
 * 3. ScreenshotBlock rendering — full image expand, placeholder, hostname
 * 4. Facebook cookie in settings
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen } from "@testing-library/react";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { ScreenshotBlock } from "@/components/chat/ScreenshotBlock";
import type {
  ContentBlock,
  ScreenshotBlockData,
} from "@/api/types";

// Mock blob-url module (happy-dom lacks URL.createObjectURL / atob for arbitrary strings)
vi.mock("@/lib/blob-url", () => ({
  base64ToBlobUrl: (base64: string) => `blob:mock/${base64.slice(0, 16)}`,
  revokeBlobUrl: vi.fn(),
  revokeAllBlobUrls: vi.fn(),
}));

// ===================================================================
// Group 1: ScreenshotBlockData type
// ===================================================================

describe("ScreenshotBlockData type", () => {
  it("screenshot block has required fields", () => {
    const block: ScreenshotBlockData = {
      type: "screenshot",
      id: "s-1",
      url: "https://example.com",
      image: "base64data",
      label: "Test",
    };
    expect(block.type).toBe("screenshot");
    expect(block.image).toBe("base64data");
  });

  it("ContentBlock union includes screenshot", () => {
    const block: ContentBlock = {
      type: "screenshot",
      id: "s-1",
      url: "https://example.com",
      image: "img64",
      label: "Loaded",
    };
    expect(block.type).toBe("screenshot");
  });
});

// ===================================================================
// Group 2: Store — appendScreenshot + finalizeStream
// ===================================================================

describe("chat-store screenshot persistence", () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [],
      activeConversationId: null,
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
      streamError: "",
      streamCompletedAt: null,
    });
  });

  it("appendScreenshot stores image and metadata", () => {
    useChatStore.setState({ isStreaming: true, streamingBlocks: [] });

    useChatStore.getState().appendScreenshot({
      url: "https://facebook.com/marketplace",
      image: "FULL_BASE64_IMAGE",
      label: "Đang tải trang...",
      node: "product_search_agent",
    });

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("screenshot");
    const shot = blocks[0] as ScreenshotBlockData;
    expect(shot.image).toBe("FULL_BASE64_IMAGE");
    expect(shot.url).toBe("https://facebook.com/marketplace");
    expect(shot.node).toBe("product_search_agent");
  });

  it("finalizeStream keeps full image (no stripping)", () => {
    // 1. Create a conversation
    const convId = useChatStore.getState().createConversation("maritime");

    // 2. Start streaming
    useChatStore.getState().startStreaming();

    // 3. Add a user message
    useChatStore.getState().addUserMessage("Tìm iPhone 16");

    // 4. Add some answer content
    useChatStore.getState().appendStreamingContent("Here are results...");

    // 5. Append screenshot
    useChatStore.getState().appendScreenshot({
      url: "https://facebook.com/marketplace",
      image: "FULL_BASE64_IMAGE_KEPT_PERMANENTLY",
      label: "Đã tải nội dung",
      node: "product_search_agent",
    });

    // 6. Finalize
    useChatStore.getState().finalizeStream({} as any);

    // 7. Check persisted message — image should be KEPT
    const conv = useChatStore
      .getState()
      .conversations.find((c) => c.id === convId);
    expect(conv).toBeDefined();
    const assistantMsg = conv!.messages.find((m) => m.role === "assistant");
    expect(assistantMsg).toBeDefined();
    expect(assistantMsg!.blocks).toBeDefined();

    const screenshotBlocks = assistantMsg!.blocks!.filter(
      (b) => b.type === "screenshot"
    ) as ScreenshotBlockData[];
    expect(screenshotBlocks).toHaveLength(1);

    // Full image kept permanently
    expect(screenshotBlocks[0].image).toBe("FULL_BASE64_IMAGE_KEPT_PERMANENTLY");
    expect(screenshotBlocks[0].url).toBe("https://facebook.com/marketplace");
    expect(screenshotBlocks[0].label).toBe("Đã tải nội dung");
  });

  it("multiple screenshots preserved after finalize", () => {
    const convId = useChatStore.getState().createConversation();
    useChatStore.getState().startStreaming();
    useChatStore.getState().addUserMessage("Test");

    useChatStore.getState().appendScreenshot({
      url: "https://fb.com/1",
      image: "IMAGE_1",
      label: "Đang tải trang...",
    });
    useChatStore.getState().appendScreenshot({
      url: "https://fb.com/2",
      image: "IMAGE_2",
      label: "Đã tải nội dung",
    });

    useChatStore.getState().finalizeStream({} as any);

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const assistantMsg = conv!.messages.find((m) => m.role === "assistant");
    const shots = assistantMsg!.blocks!.filter((b) => b.type === "screenshot") as ScreenshotBlockData[];

    expect(shots).toHaveLength(2);
    expect(shots[0].image).toBe("IMAGE_1");
    expect(shots[1].image).toBe("IMAGE_2");
  });
});

// ===================================================================
// Group 3: ScreenshotBlock component rendering
// ===================================================================

describe("ScreenshotBlock rendering", () => {
  it("full image renders clickable expand button", () => {
    const block: ScreenshotBlockData = {
      type: "screenshot",
      id: "s-1",
      url: "https://facebook.com/marketplace/item/123",
      image: "FULL_BASE64_IMAGE",
      label: "Đang tải trang...",
    };

    render(createElement(ScreenshotBlock, { block }));

    // Should have role="button" for click-to-expand
    const button = screen.getByRole("button");
    expect(button).toBeDefined();

    // Should show label and hostname
    expect(screen.getByText("Đang tải trang...")).toBeDefined();
    expect(screen.getByText("facebook.com")).toBeDefined();

    // Image should use blob URL (converted from base64)
    const img = screen.getByAltText("Đang tải trang...");
    expect(img.getAttribute("src")).toContain("blob:mock/");
  });

  it("no image shows placeholder text", () => {
    const block: ScreenshotBlockData = {
      type: "screenshot",
      id: "s-3",
      url: "https://example.com/page",
      image: "",
      label: "Đang tải trang...",
    };

    render(createElement(ScreenshotBlock, { block }));

    // Should show placeholder text
    expect(
      screen.getByText(/Ảnh chụp trình duyệt không khả dụng/)
    ).toBeDefined();

    // No expand button, no img element
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("extracts hostname from URL correctly", () => {
    const block: ScreenshotBlockData = {
      type: "screenshot",
      id: "s-4",
      url: "https://www.tiki.vn/search?q=iphone+16",
      image: "img",
      label: "Tìm kiếm",
    };

    render(createElement(ScreenshotBlock, { block }));
    expect(screen.getByText("www.tiki.vn")).toBeDefined();
  });
});

// ===================================================================
// Group 4: Facebook cookie in settings
// ===================================================================

describe("AppSettings facebook_cookie", () => {
  it("default settings include facebook_cookie as empty string", () => {
    const { settings } = useSettingsStore.getState();
    expect(settings.facebook_cookie).toBeDefined();
    expect(settings.facebook_cookie).toBe("");
  });
});
