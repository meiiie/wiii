/**
 * Keep one visual gutter row per source line. Wrapping adds unnumbered visual
 * rows, while sticky scroll repeats ancestor lines above the real viewport.
 */
export const WORKSPACE_CODE_EDITOR_OPTIONS = {
  readOnly: true,
  domReadOnly: true,
  automaticLayout: true,
  minimap: { enabled: false },
  wordWrap: "off",
  lineNumbers: "on",
  lineNumbersMinChars: 4,
  stickyScroll: { enabled: false },
  glyphMargin: false,
  folding: false,
  lineDecorationsWidth: 8,
  letterSpacing: 0,
  scrollBeyondLastLine: false,
  scrollBeyondLastColumn: 4,
  fontSize: 12,
  lineHeight: 20,
} as const;
