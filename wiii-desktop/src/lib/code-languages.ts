/**
 * Code language configuration — friendly display names and language categories.
 * Used by CodeBlock for language badges and future language-specific features.
 *
 * To add a new language:
 *   1. Add entry to LANGUAGE_LABELS (key = alias, value = display name)
 *   2. If runnable, add to RUNNABLE_LANGUAGES
 *   3. If previewable in sandbox, add to PREVIEWABLE_LANGUAGES
 */

/** Friendly display names for language identifiers */
export const LANGUAGE_LABELS: Record<string, string> = {
  // Web
  js: "JavaScript", javascript: "JavaScript",
  ts: "TypeScript", typescript: "TypeScript",
  jsx: "JSX", tsx: "TSX",
  html: "HTML", css: "CSS", scss: "SCSS", sass: "Sass", less: "Less",

  // Backend
  py: "Python", python: "Python", python3: "Python",
  java: "Java", kotlin: "Kotlin", scala: "Scala",
  go: "Go", rust: "Rust",
  cpp: "C++", c: "C", csharp: "C#", cs: "C#",
  ruby: "Ruby", rb: "Ruby", php: "PHP", swift: "Swift",

  // Data / Config
  sql: "SQL", json: "JSON", yaml: "YAML", yml: "YAML",
  xml: "XML", toml: "TOML", csv: "CSV",

  // Shell
  bash: "Bash", sh: "Shell", zsh: "Zsh", shell: "Shell",
  powershell: "PowerShell", ps1: "PowerShell", cmd: "CMD", bat: "Batch",

  // DevOps / Infra
  dockerfile: "Dockerfile", docker: "Docker",

  // Documentation
  md: "Markdown", markdown: "Markdown",

  // Query / Schema
  graphql: "GraphQL", prisma: "Prisma",

  // Scientific
  r: "R", matlab: "MATLAB", latex: "LaTeX", tex: "LaTeX",

  // Other
  lua: "Lua", perl: "Perl", dart: "Dart", elixir: "Elixir", haskell: "Haskell",
  vue: "Vue", svelte: "Svelte", astro: "Astro",

  // Plain text
  text: "Text", plaintext: "Text", txt: "Text",
};

/** Languages that can be executed inline via Pyodide */
export const RUNNABLE_LANGUAGES = new Set(["python", "py", "python3"]);

/** Languages that can be previewed in the sandbox iframe */
export const PREVIEWABLE_LANGUAGES = new Set(["html", "css", "jsx", "tsx", "react"]);

/** Resolve a language identifier to its friendly display name */
export function getLanguageDisplayName(language: string): string {
  const lower = language.toLowerCase();
  return LANGUAGE_LABELS[lower] || LANGUAGE_LABELS[language] || language || "Text";
}
