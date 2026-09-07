import { describe, expect, it } from "vitest";
import {
  buildComputerViewerUrl,
  parseComputerViewerMessage,
} from "@/neko-computer/viewer-lifecycle";

describe("Neko Computer viewer contract", () => {
  it("keeps credentials while making observer projections view-only", () => {
    const result = new URL(buildComputerViewerUrl(
      "http://127.0.0.1:6080/wiii.html#password=secret",
      "observe",
    ));

    expect(result.searchParams.get("fit")).toBe("1");
    expect(result.searchParams.get("view_only")).toBe("1");
    expect(result.hash).toBe("#password=secret");
  });

  it("enables input only for the explicit control projection", () => {
    const result = new URL(buildComputerViewerUrl(
      "http://127.0.0.1:6080/wiii.html#password=secret",
      "control",
    ));

    expect(result.searchParams.get("view_only")).toBe("0");
  });

  it("rejects viewer messages from an unrelated source", () => {
    expect(parseComputerViewerMessage({
      source: "foreign-viewer",
      phase: "framebuffer.visible",
      at: Date.now(),
    })).toBeNull();
  });
});
