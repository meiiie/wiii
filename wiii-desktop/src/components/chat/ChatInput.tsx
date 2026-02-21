/**
 * Chat input — Claude Desktop style.
 * Sprint 82b: `centered` prop for elevated card styling in welcome mode.
 * Paperclip attachment button, domain selector inside card, subtle shadow.
 */
import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { ArrowUp, Square, X, Paperclip } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { useUIStore } from "@/stores/ui-store";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";
import { getWelcomePlaceholder } from "@/lib/greeting";
import { DomainSelector } from "./DomainSelector";

interface ChatInputProps {
  onSend: (message: string) => void;
  onCancel: () => void;
  editingMessage?: string | null;
  onClearEdit?: () => void;
  /** Elevated card style for welcome centered composition */
  centered?: boolean;
}

export function ChatInput({ onSend, onCancel, editingMessage, onClearEdit, centered }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { isStreaming } = useChatStore();
  const { addToast } = useToastStore();
  const setInputFocused = useUIStore((s) => s.setInputFocused);

  // Set input when editing a message
  useEffect(() => {
    if (editingMessage !== null && editingMessage !== undefined) {
      setInput(editingMessage);
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
      }
    }
  }, [editingMessage]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      // Re-focus input after sending (Sprint 106)
      textareaRef.current.focus();
    }
  }, [input, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        addToast("info", "Mình chưa xem được ảnh, xin lỗi bạn!");
        return;
      }
    }
  };

  const handleAttach = () => {
    addToast("info", "Mình chưa nhận được file, xin lỗi bạn!");
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const welcomePlaceholder = useMemo(() => getWelcomePlaceholder(), []);

  const charCount = input.length;
  const showCharCount = charCount > MAX_MESSAGE_LENGTH * 0.8;
  const isNearLimit = charCount > MAX_MESSAGE_LENGTH * 0.95;

  // Centered (welcome) mode: Claude F12 exact — floating card, m-3.5 inner
  if (centered) {
    return (
      <div className="w-full">
        <div className="input-card">
          <div className="m-3.5 flex flex-col gap-3">
            {/* Textarea — min-h-[3rem], max-h-96 */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              placeholder={welcomePlaceholder}
              className="w-full resize-none bg-transparent pl-1.5 pt-1.5 text-[16px] leading-[1.6] text-text placeholder:text-text-tertiary placeholder:italic focus:outline-none min-h-[3rem] max-h-96"
              rows={2}
              maxLength={MAX_MESSAGE_LENGTH}
              disabled={isStreaming}
              aria-label="Nhập tin nhắn"
            />
            {/* Toolbar: attach + domain | char count + send */}
            <div className="flex items-center justify-between h-8">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleAttach}
                  className="flex items-center justify-center w-8 h-8 rounded-md text-text-tertiary hover:text-text-secondary hover:bg-surface-tertiary active:scale-95 transition-all duration-300"
                  style={{ border: "0.5px solid var(--border)" }}
                  title="Đính kèm file"
                  aria-label="Đính kèm file"
                >
                  <Paperclip size={16} />
                </button>
                <DomainSelector compact />
              </div>
              <div className="flex items-center gap-2">
                {showCharCount && (
                  <span
                    className={`text-[10px] tabular-nums ${
                      isNearLimit ? "text-red-500" : "text-text-tertiary"
                    }`}
                  >
                    {charCount}/{MAX_MESSAGE_LENGTH}
                  </span>
                )}
                {isStreaming ? (
                  <button
                    onClick={onCancel}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-red-500/90 text-white hover:bg-red-600 active:scale-95 transition-all duration-300"
                    title="Dừng"
                    aria-label="Dừng tạo phản hồi"
                  >
                    <Square size={13} />
                  </button>
                ) : (
                  <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.985] transition-all duration-300"
                    style={{ transitionTimingFunction: "cubic-bezier(0.165, 0.85, 0.45, 1)" }}
                    title="Gửi (Enter)"
                    aria-label="Gửi tin nhắn"
                  >
                    <ArrowUp size={16} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Normal bottom-bar mode — input-card style (Sprint 162)
  return (
    <div className="bg-surface px-4 py-3">
      <div className="max-w-[720px] mx-auto">
        {/* Edit mode banner */}
        {editingMessage && onClearEdit && (
          <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-[var(--accent-light)] text-[var(--accent)] text-xs">
            <span className="flex-1">Chỉnh sửa tin nhắn</span>
            <button
              onClick={() => {
                onClearEdit();
                setInput("");
              }}
              className="p-0.5 rounded hover:bg-[var(--accent)]/10"
              aria-label="Huỷ chỉnh sửa"
            >
              <X size={14} />
            </button>
          </div>
        )}

        <div className="input-card">
          <div className="m-3 flex flex-col gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              placeholder="Hỏi Wiii bất cứ điều gì..."
              className="w-full resize-none bg-transparent px-1.5 pt-1 text-[14px] text-text placeholder:text-text-tertiary focus:outline-none min-h-[2.5rem] max-h-48"
              rows={1}
              maxLength={MAX_MESSAGE_LENGTH}
              disabled={isStreaming}
              aria-label="Nhập tin nhắn"
            />
            <div className="flex items-center justify-between h-8">
              <div className="flex items-center gap-3">
                <DomainSelector />
                <span className="text-[10px] text-text-tertiary">
                  Enter gửi · Shift+Enter xuống dòng
                </span>
              </div>
              <div className="flex items-center gap-2">
                {showCharCount && (
                  <span
                    className={`text-[10px] tabular-nums ${
                      isNearLimit ? "text-red-500" : "text-text-tertiary"
                    }`}
                  >
                    {charCount}/{MAX_MESSAGE_LENGTH}
                  </span>
                )}
                {isStreaming ? (
                  <button
                    onClick={onCancel}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-red-500/90 text-white hover:bg-red-600 active:scale-95 transition-all duration-300"
                    title="Dừng"
                    aria-label="Dừng tạo phản hồi"
                  >
                    <Square size={13} />
                  </button>
                ) : (
                  <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-all duration-150"
                    title="Gửi (Enter)"
                    aria-label="Gửi tin nhắn"
                  >
                    <ArrowUp size={15} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
