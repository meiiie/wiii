import { describe, expect, it } from "vitest";

import { resolvePreviewAssetPath } from "@/neko-chill/workspace-preview";

describe("workspace HTML preview asset paths", () => {
  it("resolves project-relative assets beside and above the selected HTML file", () => {
    expect(resolvePreviewAssetPath("web/pages/index.html", "../styles/base.css?v=2"))
      .toBe("web/styles/base.css");
    expect(resolvePreviewAssetPath("web/pages/index.html", "./hero%20image.png"))
      .toBe("web/pages/hero image.png");
    expect(resolvePreviewAssetPath("web/pages/index.html", "/shared/theme.css"))
      .toBe("shared/theme.css");
  });

  it("rejects network URLs, data URLs, anchors, and paths escaping the Project", () => {
    expect(resolvePreviewAssetPath("index.html", "https://example.com/theme.css")).toBeNull();
    expect(resolvePreviewAssetPath("index.html", "data:text/css,body{}")).toBeNull();
    expect(resolvePreviewAssetPath("index.html", "#section")).toBeNull();
    expect(resolvePreviewAssetPath("web/index.html", "../../outside.css")).toBeNull();
  });
});
