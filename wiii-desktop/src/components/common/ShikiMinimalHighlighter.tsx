import { useEffect, useState } from "react";
import type { LanguageRegistration } from "shiki";

type ThemeConfig = { light: string; dark: string };

interface ShikiMinimalHighlighterProps {
  children: string;
  language: string;
  theme: ThemeConfig;
  delay?: number;
  showLineNumbers?: boolean;
  showLanguage?: boolean;
  addDefaultStyles?: boolean;
}

type CoreModule = typeof import("react-shiki/core");
type CoreHighlighter = Awaited<ReturnType<CoreModule["createHighlighterCore"]>>;

const TEXT_FALLBACK_LANGS = new Set(["", "plain", "plaintext", "text", "txt"]);

const LANGUAGE_ALIASES: Record<string, string> = {
  "c#": "csharp",
  "c++": "cpp",
  cjs: "javascript",
  env: "ini",
  htm: "html",
  js: "javascript",
  json5: "jsonc",
  md: "markdown",
  mts: "typescript",
  ps1: "powershell",
  py: "python",
  rb: "ruby",
  shell: "shellscript",
  sh: "shellscript",
  svg: "xml",
  ts: "typescript",
  yml: "yaml",
  zsh: "shellscript",
};

const LANGUAGE_IMPORTERS: Record<
  string,
  () => Promise<{ default: LanguageRegistration[] }>
> = {
  astro: () => import("@shikijs/langs/astro"),
  bash: () => import("@shikijs/langs/bash"),
  bat: () => import("@shikijs/langs/bat"),
  batch: () => import("@shikijs/langs/batch"),
  c: () => import("@shikijs/langs/c"),
  cmd: () => import("@shikijs/langs/cmd"),
  console: () => import("@shikijs/langs/console"),
  cpp: () => import("@shikijs/langs/cpp"),
  csharp: () => import("@shikijs/langs/csharp"),
  css: () => import("@shikijs/langs/css"),
  diff: () => import("@shikijs/langs/diff"),
  docker: () => import("@shikijs/langs/docker"),
  dockerfile: () => import("@shikijs/langs/dockerfile"),
  go: () => import("@shikijs/langs/go"),
  graphql: () => import("@shikijs/langs/graphql"),
  html: () => import("@shikijs/langs/html"),
  ini: () => import("@shikijs/langs/ini"),
  java: () => import("@shikijs/langs/java"),
  javascript: () => import("@shikijs/langs/javascript"),
  json: () => import("@shikijs/langs/json"),
  jsonc: () => import("@shikijs/langs/jsonc"),
  jsx: () => import("@shikijs/langs/jsx"),
  kotlin: () => import("@shikijs/langs/kotlin"),
  make: () => import("@shikijs/langs/make"),
  markdown: () => import("@shikijs/langs/markdown"),
  nginx: () => import("@shikijs/langs/nginx"),
  objc: () => import("@shikijs/langs/objc"),
  perl: () => import("@shikijs/langs/perl"),
  php: () => import("@shikijs/langs/php"),
  powershell: () => import("@shikijs/langs/powershell"),
  python: () => import("@shikijs/langs/python"),
  r: () => import("@shikijs/langs/r"),
  regex: () => import("@shikijs/langs/regex"),
  ruby: () => import("@shikijs/langs/ruby"),
  rust: () => import("@shikijs/langs/rust"),
  scala: () => import("@shikijs/langs/scala"),
  scss: () => import("@shikijs/langs/scss"),
  shellscript: () => import("@shikijs/langs/shellscript"),
  sql: () => import("@shikijs/langs/sql"),
  svelte: () => import("@shikijs/langs/svelte"),
  swift: () => import("@shikijs/langs/swift"),
  toml: () => import("@shikijs/langs/toml"),
  tsx: () => import("@shikijs/langs/tsx"),
  typescript: () => import("@shikijs/langs/typescript"),
  vue: () => import("@shikijs/langs/vue"),
  xml: () => import("@shikijs/langs/xml"),
  yaml: () => import("@shikijs/langs/yaml"),
};

let coreModulePromise: Promise<CoreModule> | null = null;
let highlighterPromise: Promise<CoreHighlighter> | null = null;

const loadedLanguages = new Set<string>();
const loadingLanguages = new Map<string, Promise<void>>();

function getCoreModule(): Promise<CoreModule> {
  coreModulePromise ??= import("react-shiki/core");
  return coreModulePromise;
}

async function getHighlighter(): Promise<CoreHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      const core = await getCoreModule();
      return core.createHighlighterCore({
        themes: [
          import("@shikijs/themes/github-light"),
          import("@shikijs/themes/github-dark"),
        ],
        langs: [],
        engine: core.createJavaScriptRegexEngine({ forgiving: true }),
      });
    })();
  }

  return highlighterPromise;
}

function normalizeLanguage(language: string): string {
  const normalized = language.trim().toLowerCase();
  if (TEXT_FALLBACK_LANGS.has(normalized)) {
    return "text";
  }

  const resolved = LANGUAGE_ALIASES[normalized] ?? normalized;
  return resolved in LANGUAGE_IMPORTERS ? resolved : "text";
}

async function ensureLanguageLoaded(language: string): Promise<void> {
  if (language === "text" || loadedLanguages.has(language)) {
    return;
  }

  const importer = LANGUAGE_IMPORTERS[language];
  if (!importer) {
    return;
  }

  let loading = loadingLanguages.get(language);
  if (!loading) {
    loading = (async () => {
      const highlighter = await getHighlighter();
      await highlighter.loadLanguage(importer());
      loadedLanguages.add(language);
    })().finally(() => {
      loadingLanguages.delete(language);
    });
    loadingLanguages.set(language, loading);
  }

  await loading;
}

export function ShikiMinimalHighlighter({
  children,
  language,
  theme,
  delay,
  showLineNumbers,
  showLanguage,
  addDefaultStyles,
}: ShikiMinimalHighlighterProps) {
  const [runtime, setRuntime] = useState<{
    highlighter: CoreHighlighter;
    component: CoreModule["ShikiHighlighter"];
    resolvedLanguage: string;
  } | null>(null);

  useEffect(() => {
    let isCancelled = false;

    void (async () => {
      const resolvedLanguage = normalizeLanguage(language);

      try {
        const [core, highlighter] = await Promise.all([
          getCoreModule(),
          getHighlighter(),
          ensureLanguageLoaded(resolvedLanguage),
        ]);

        if (!isCancelled) {
          setRuntime({
            highlighter,
            component: core.ShikiHighlighter,
            resolvedLanguage,
          });
        }
      } catch {
        if (!isCancelled) {
          setRuntime(null);
        }
      }
    })();

    return () => {
      isCancelled = true;
    };
  }, [language]);

  if (!runtime) {
    return (
      <pre>
        <code className="text-sm font-mono leading-relaxed">{children}</code>
      </pre>
    );
  }

  const HighlighterComponent = runtime.component;

  return (
    <HighlighterComponent
      highlighter={runtime.highlighter}
      language={runtime.resolvedLanguage}
      theme={theme}
      delay={delay}
      showLineNumbers={showLineNumbers}
      showLanguage={showLanguage}
      addDefaultStyles={addDefaultStyles}
    >
      {children}
    </HighlighterComponent>
  );
}
