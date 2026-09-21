import { describe, expect, it } from "vitest";
import { projectHomeSendTitle } from "@/neko-chill/components/ProjectHome";
import { nekoComposerSendTitle } from "@/neko-chill/components/NekoComposer";

describe("projectHomeSendTitle", () => {
  const base = {
    canStart: false,
    starting: false,
    isLoading: false,
    discoveryError: null as string | null,
    selectedRoot: true,
    selectedAgent: false,
    draftReady: true,
    nekoProfileBlocked: false,
    codexBlocked: false,
  };

  it("mirrors the harness-not-ready banner when the agent is missing", () => {
    expect(projectHomeSendTitle(base)).toBe(
      "Harness đã chọn chưa sẵn sàng. Bản nháp vẫn được giữ.",
    );
  });

  it("asks for draft when everything else is ready", () => {
    expect(projectHomeSendTitle({
      ...base,
      selectedAgent: true,
      draftReady: false,
    })).toBe("Nhập lời nhắn đầu tiên trước khi gửi.");
  });

  it("returns the enabled label when canStart", () => {
    expect(projectHomeSendTitle({ ...base, canStart: true, selectedAgent: true })).toBe(
      "Gửi và mở phiên",
    );
  });
});

describe("nekoComposerSendTitle", () => {
  it("explains missing workspace", () => {
    expect(nekoComposerSendTitle({
      streaming: false,
      hasWorkspace: false,
      composerDisabled: false,
      submitting: false,
      hasDraft: true,
      pendingPermission: false,
      pendingControl: false,
    })).toBe("Gắn dự án trước khi gửi.");
  });

  it("explains empty draft", () => {
    expect(nekoComposerSendTitle({
      streaming: false,
      hasWorkspace: true,
      composerDisabled: false,
      submitting: false,
      hasDraft: false,
      pendingPermission: false,
      pendingControl: false,
    })).toBe("Nhập nội dung trước khi gửi.");
  });

  it("returns Gửi when ready", () => {
    expect(nekoComposerSendTitle({
      streaming: false,
      hasWorkspace: true,
      composerDisabled: false,
      submitting: false,
      hasDraft: true,
      pendingPermission: false,
      pendingControl: false,
    })).toBe("Gửi");
  });
});
