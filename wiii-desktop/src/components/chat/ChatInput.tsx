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
import type { ImageInput } from "@/api/types";

/** Sprint 179: Attached image before upload */
interface AttachedImage {
  data: string;
  media_type: string;
  preview: string;
}

interface ChatInputProps {
  onSend: (message: string, images?: ImageInput[]) => void;
  onCancel: () => void;
  editingMessage?: string | null;
  onClearEdit?: () => void;
  /** Elevated card style for welcome centered composition */
  centered?: boolean;
}

export function ChatInput({ onSend, onCancel, editingMessage, onClearEdit, centered }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [images, setImages] = useState<AttachedImage[]>([]);
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
    // Sprint 179: Include attached images in send
    const imageInputs: ImageInput[] | undefined = images.length > 0
      ? images.map(img => ({ type: "base64" as const, media_type: img.media_type, data: img.data, detail: "auto" as const }))
      : undefined;
    onSend(trimmed, imageInputs);
    setInput("");
    setImages([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      // Re-focus input after sending (Sprint 106)
      textareaRef.current.focus();
    }
  }, [input, images, isStreaming, onSend]);

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
        const file = item.getAsFile();
        if (!file || images.length >= 5) {
          if (images.length >= 5) addToast("info", "Tối đa 5 ảnh mỗi tin nhắn.");
          return;
        }
        // Security: enforce 10MB file size limit
        if (file.size > 10 * 1024 * 1024) {
          addToast("error", "Ảnh quá lớn (tối đa 10MB).");
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(",")[1];
          const preview = reader.result as string;
          setImages(prev => [...prev, { data: base64, media_type: file.type, preview }]);
        };
        reader.onerror = () => addToast("error", "Không thể đọc ảnh từ clipboard.");
        reader.readAsDataURL(file);
        return;
      }
    }
  };

  const handleAttach = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/webp,image/gif";
    input.multiple = true;
    input.onchange = (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files) return;
      const remaining = 5 - images.length;
      if (remaining <= 0) {
        addToast("info", "Tối đa 5 ảnh mỗi tin nhắn.");
        return;
      }
      Array.from(files).slice(0, remaining).forEach(file => {
        // Security: enforce 10MB file size limit
        if (file.size > 10 * 1024 * 1024) {
          addToast("error", `"${file.name}" quá lớn (tối đa 10MB).`);
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(",")[1];
          const preview = reader.result as string;
          setImages(prev => [...prev, { data: base64, media_type: file.type, preview }]);
        };
        reader.onerror = () => addToast("error", "Không thể đọc file ảnh.");
        reader.readAsDataURL(file);
      });
    };
    input.click();
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
            {/* Sprint 179: Image preview strip */}
            {images.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {images.map((img, i) => (
                  <div key={`img-${img.data.substring(0, 16)}`} className="relative group">
                    <img src={img.preview} alt={`Ảnh đính kèm ${i + 1}`} className="w-16 h-16 object-cover rounded-lg border border-gray-200 dark:border-gray-700" />
                    <button
                      onClick={() => setImages(prev => prev.filter((_, idx) => idx !== i))}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
                      aria-label={`Xoá ảnh ${i + 1}`}
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
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
    <div className="chat-composer-shell px-4 py-3">
      <div className="chat-lane">
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
            {/* Sprint 179: Image preview strip */}
            {images.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {images.map((img, i) => (
                  <div key={`img-${img.data.substring(0, 16)}`} className="relative group">
                    <img src={img.preview} alt={`Ảnh đính kèm ${i + 1}`} className="w-16 h-16 object-cover rounded-lg border border-gray-200 dark:border-gray-700" />
                    <button
                      onClick={() => setImages(prev => prev.filter((_, idx) => idx !== i))}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
                      aria-label={`Xoá ảnh ${i + 1}`}
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
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
                <button
                  onClick={handleAttach}
                  className="flex items-center justify-center w-7 h-7 rounded-md text-text-tertiary hover:text-text-secondary hover:bg-surface-tertiary active:scale-95 transition-all duration-300"
                  style={{ border: "0.5px solid var(--border)" }}
                  title="Đính kèm ảnh"
                  aria-label="Đính kèm ảnh"
                >
                  <Paperclip size={14} />
                </button>
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
