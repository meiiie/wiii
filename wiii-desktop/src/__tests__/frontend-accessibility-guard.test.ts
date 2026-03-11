import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("frontend accessibility guards", () => {
  it("keeps global text selection enabled and exposes focus-visible styling", () => {
    const globalsCss = readFileSync(resolve(process.cwd(), "src/styles/globals.css"), "utf8");

    expect(globalsCss).toContain("user-select: text;");
    expect(globalsCss).toContain(":focus-visible");
  });

  it("keeps login errors announced to assistive tech", () => {
    const loginScreen = readFileSync(
      resolve(process.cwd(), "src/components/auth/LoginScreen.tsx"),
      "utf8",
    );

    expect(loginScreen).toContain('role="alert"');
    expect(loginScreen).toContain('aria-live="assertive"');
  });
});
