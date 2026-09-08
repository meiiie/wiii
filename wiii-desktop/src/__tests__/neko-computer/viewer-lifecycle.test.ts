import { describe, expect, it } from "vitest";
import { parseComputerViewerMessage } from "@/neko-computer/viewer-lifecycle";

describe("Wiii Computer viewer lifecycle boundary", () => {
  it("accepts typed framebuffer evidence from the embedded viewer", () => {
    expect(parseComputerViewerMessage({
      source: "wiii-computer-viewer-v1",
      phase: "framebuffer.visible",
      at: 1_777_777,
    })).toEqual({
      source: "wiii-computer-viewer-v1",
      phase: "framebuffer.visible",
      at: 1_777_777,
    });
  });

  it("rejects unrelated, malformed, and invented viewer events", () => {
    expect(parseComputerViewerMessage(null)).toBeNull();
    expect(parseComputerViewerMessage({ source: "other", phase: "framebuffer.visible", at: 1 })).toBeNull();
    expect(parseComputerViewerMessage({ source: "wiii-computer-viewer-v1", phase: "framebuffer.visible", at: "now" })).toBeNull();
    expect(parseComputerViewerMessage({ source: "wiii-computer-viewer-v1", phase: "credential.exposed", at: 1 })).toBeNull();
  });
});
