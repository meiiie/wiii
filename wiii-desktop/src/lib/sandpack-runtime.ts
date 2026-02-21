/**
 * Sandpack Runtime — configuration generator for JS/React artifact execution.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Lazy-loaded @codesandbox/sandpack-react (~400 KB gzip) on first use.
 * Template detection: React (JSX/TSX) vs vanilla JS vs HTML.
 */

export type SandpackTemplate = "react" | "vanilla" | "vanilla-ts" | "static";

export interface SandpackConfig {
  template: SandpackTemplate;
  files: Record<string, string>;
  entry: string;
}

/**
 * Detect the appropriate Sandpack template from code content and language.
 */
function detectTemplate(code: string, language: string): SandpackTemplate {
  // React detection — M-2: require actual React import or hook usage
  if (language === "jsx" || language === "tsx" || language === "react") {
    return "react";
  }
  const hasReactImport = code.includes("from 'react'") || code.includes('from "react"') || code.includes("import React");
  const hasHooks = /\buse(State|Effect|Memo|Callback|Ref|Context)\b/.test(code);
  if (hasReactImport || hasHooks) {
    return "react";
  }

  // TypeScript
  if (language === "typescript" || language === "ts") {
    return "vanilla-ts";
  }

  // HTML
  if (language === "html" || code.includes("<!DOCTYPE") || code.includes("<html")) {
    return "static";
  }

  return "vanilla";
}

/**
 * Create a Sandpack configuration for the given code and language.
 */
export function createSandpackConfig(
  code: string,
  language: string
): SandpackConfig {
  const template = detectTemplate(code, language);

  switch (template) {
    case "react": {
      const ext = language === "tsx" ? "tsx" : "jsx";
      const entry = `/App.${ext}`;
      return {
        template: "react",
        files: {
          [entry]: code,
        },
        entry,
      };
    }
    case "vanilla-ts":
      return {
        template: "vanilla-ts",
        files: { "/src/index.ts": code },
        entry: "/src/index.ts",
      };
    case "static":
      return {
        template: "static",
        files: { "/index.html": code },
        entry: "/index.html",
      };
    default:
      return {
        template: "vanilla",
        files: { "/src/index.js": code },
        entry: "/src/index.js",
      };
  }
}
