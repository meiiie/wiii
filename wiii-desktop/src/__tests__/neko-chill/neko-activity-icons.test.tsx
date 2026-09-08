import { describe, expect, it } from "vitest";
import { resolveNekoToolIconKind } from "@/components/icons/neko";

describe("Neko activity icon vocabulary", () => {
  it("maps native tool labels to stable semantic glyphs", () => {
    expect(resolveNekoToolIconKind("Bash(npm test)")).toBe("terminal");
    expect(resolveNekoToolIconKind("Read(src/app.ts)")).toBe("read");
    expect(resolveNekoToolIconKind("Write(src/app.ts)")).toBe("write");
    expect(resolveNekoToolIconKind("Edit(src/app.ts)")).toBe("edit");
    expect(resolveNekoToolIconKind("Grep(authentication)")).toBe("search");
    expect(resolveNekoToolIconKind("Browser(open page)")).toBe("web");
    expect(resolveNekoToolIconKind("Skill(web-app)")).toBe("skill");
    expect(resolveNekoToolIconKind("UnknownTool")).toBe("generic");
  });
});
