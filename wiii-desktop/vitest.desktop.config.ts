import { defineConfig } from "vitest/config";
import config from "./vitest.config";

export default defineConfig({
  ...config,
  test: {
    ...config.test,
    // Opt new desktop suites in here or place them in an owning directory.
    // The default Vitest config is still available for legacy/Embed work.
    include: [
      "src/__tests__/{ade,layout,neko,neko-chill,neko-computer,workbench}/**/*.test.{ts,tsx}",
      "src/__tests__/{neko-computer-viewer,neko-coworker-*,neko-motion-lab,workspace-pane-state,skill-mentions}.test.{ts,tsx}",
      "src/__tests__/{assistant-markdown-rendering,assistant-markdown,code-block-highlighting,markdown-code-routing}.test.{ts,tsx}",
      "src/__tests__/{mascot-identity,wiii-mark,theme,tailwind-compat,storage-strict*,async-assertion-guard,frontend-accessibility-guard}.test.{ts,tsx}",
      "src/__tests__/{auth-identity-ssot,auth-mode-fallback,auth-store,auth-user,connection-store,login-screen-dev-login,org-store,sprint160b-oauth,sprint224-magic-link-frontend}.test.{ts,tsx}",
      "src/__tests__/{capability-status,runtime-flow-trace,wiii-connect-page}.test.{ts,tsx}",
    ],
    exclude: [
      ...config.test!.exclude!,
      // The merge gate supplies a pinned binary in its dedicated ACP job.
      "src/__tests__/neko-chill/neko-core-acp-contract.real.test.ts",
      "src/__tests__/neko-computer/app-events.test.ts",
    ],
    coverage: {
      ...config.test!.coverage,
      include: ["src/{ade,neko,neko-chill,neko-computer,neko-coworker,workbench,components/auth,components/connect}/**/*.{ts,tsx}"],
    },
  },
});
