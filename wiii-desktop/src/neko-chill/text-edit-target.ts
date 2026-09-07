export type TextEditCommand = "undo" | "redo" | "cut" | "copy" | "paste" | "selectAll";
type TextField = HTMLInputElement | HTMLTextAreaElement;

export interface TextEditTarget {
  field: TextField;
  value: string;
  start: number;
  end: number;
  enabled: Record<TextEditCommand, boolean>;
}

function supports(command: string): boolean {
  return typeof document.execCommand === "function"
    && typeof document.queryCommandSupported === "function"
    && document.queryCommandSupported(command);
}

function canUndo(command: "undo" | "redo"): boolean {
  return supports(command) && typeof document.queryCommandEnabled === "function"
    && document.queryCommandEnabled(command);
}

export function captureTextEditTarget(root: Element | null): TextEditTarget | null {
  const field = document.activeElement;
  if (!(field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement)
    || !root?.contains(field) || field.disabled || field.readOnly
    || (field instanceof HTMLInputElement && !["text", "search", "url", "tel"].includes(field.type))
    || field.closest('[data-menu-edit="off"], .monaco-editor')) return null;
  const start = field.selectionStart ?? 0;
  const end = field.selectionEnd ?? start;
  return {
    field, value: field.value, start, end,
    enabled: {
      undo: canUndo("undo"),
      redo: canUndo("redo"),
      cut: end > start && Boolean(navigator.clipboard?.writeText) && supports("delete"),
      copy: end > start && Boolean(navigator.clipboard?.writeText),
      paste: Boolean(navigator.clipboard?.readText) && supports("insertText"),
      selectAll: field.value.length > 0,
    },
  };
}

export async function runTextEdit(command: TextEditCommand, target: TextEditTarget): Promise<void> {
  const { field, value, start, end } = target;
  const unchanged = () => field.isConnected && !field.disabled && !field.readOnly
    && field.value === value && field.selectionStart === start && field.selectionEnd === end;
  if (!target.enabled[command] || !unchanged()) throw new Error("Ô nhập đã thay đổi. Hãy chọn lại nội dung cần sửa.");
  field.focus({ preventScroll: true });
  if (document.activeElement !== field) throw new Error("Không thể chọn ô nhập. Hãy đóng hộp thoại rồi thử lại.");
  if (command === "selectAll") {
    field.select();
    return;
  }
  let text: string | undefined;
  if (command === "copy" || command === "cut") {
    await navigator.clipboard.writeText(value.slice(start, end));
    if (command === "copy") return;
  } else if (command === "paste") {
    text = await navigator.clipboard.readText();
    if (!text) return;
  }
  if (!unchanged() || document.activeElement !== field) {
    throw new Error("Nội dung hoặc vùng nhập đã đổi. Không thực hiện lại thao tác tự động.");
  }
  // WebView edit commands preserve the native undo buffer; direct value writes do not.
  const applied = document.execCommand(command === "paste" ? "insertText" : command === "cut" ? "delete" : command, false, text);
  if (!applied) throw new Error("Ô nhập chưa hỗ trợ lệnh này. Hãy dùng phím tắt trong ô nhập.");
}
