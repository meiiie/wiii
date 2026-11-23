import type { editor } from "monaco-editor";

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

/** Skip the original editor when Monaco collapses it to an inline gutter. */
export function syncWorkspaceDiffTabOrder(diff: editor.IDiffEditor): void {
  const original = diff.getOriginalEditor();
  const sync = ({ contentWidth }: editor.EditorLayoutInfo) => {
    original.updateOptions({ tabIndex: contentWidth > 0 ? 0 : -1 });
  };
  sync(original.getLayoutInfo());
  const subscription = original.onDidLayoutChange(sync);
  diff.onDidDispose(() => subscription.dispose());
}
