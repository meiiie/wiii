import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { tabbable } from "tabbable";
import {
  getLocalModelStatus, saveLocalModel,
  type LocalModelPreset, type SavedLocalModel,
} from "@/lib/local-model-setup";
import { NekoButton, NekoDialogPanel, NekoIconButton, NekoInput } from "./ui";
import { isPlainTab, nativeTabBoundaryEnabled } from "./NativeTabBoundary";

export function LocalModelSetupDialog({ onClose, onSaved }: {
  onClose: () => void;
  onSaved: (model: SavedLocalModel) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const providerInput = useRef<HTMLSelectElement>(null);
  const modelInput = useRef<HTMLInputElement>(null);
  const keyInput = useRef<HTMLInputElement>(null);
  const savingRef = useRef(false);
  const [presets, setPresets] = useState<LocalModelPreset[]>([]);
  const [presetId, setPresetId] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  // Ephemeral only: never put this state in drafts, browser stores or telemetry.
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const preset = presets.find((item) => item.id === presetId);

  useEffect(() => {
    const element = dialog.current;
    const opener = document.activeElement;
    element?.showModal();
    return () => {
      element?.close();
      if (opener instanceof HTMLElement && opener.isConnected && !opener.matches(":disabled")) {
        opener.focus({ preventScroll: true });
      } else {
        document.querySelector<HTMLElement>('[data-testid="project-home-input"], [data-testid="neko-composer-input"]')?.focus({ preventScroll: true });
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getLocalModelStatus().then((status) => {
      if (cancelled) return;
      setPresets(status.presets);
      const first = status.presets[0];
      setPresetId(first?.id ?? "");
      setModel(first?.model ?? "");
      setBaseUrl(first?.baseUrl ?? "");
      setApiKey("");
    }).catch((cause: unknown) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : "Chưa đọc được danh sách mô hình. Hãy thử lại.");
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [attempt]);

  useEffect(() => {
    if (!loading) providerInput.current?.focus();
  }, [loading]);

  const close = () => {
    if (savingRef.current) return;
    setApiKey("");
    onClose();
  };

  const save = async () => {
    if (savingRef.current || !preset) return;
    if (!model.trim()) {
      setError("Hãy nhập mã mô hình.");
      modelInput.current?.focus();
      return;
    }
    if (preset.requiresKey && !apiKey.trim()) {
      setError("Hãy nhập khóa API của nhà cung cấp.");
      keyInput.current?.focus();
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const saved = await saveLocalModel({ presetId, model: model.trim(), baseUrl: preset.customEndpoint ? baseUrl.trim() : undefined, apiKey });
      setApiKey("");
      onSaved(saved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Chưa lưu được mô hình. Hãy thử lại.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  return <dialog ref={dialog} className="nk-dialog" aria-labelledby="local-model-title" aria-describedby="local-model-description"
    onKeyDown={(event) => {
      if (!nativeTabBoundaryEnabled(true) || !isPlainTab(event.nativeEvent)) return;
      // WebKitGTK also inserts an empty webview stop at native modal edges.
      // Only join this dialog's ends; leave inner traversal and other platforms native.
      const controls = tabbable(event.currentTarget);
      const first = controls[0], last = controls[controls.length - 1];
      const focused = event.currentTarget.ownerDocument.activeElement;
      const next = event.shiftKey && focused === first ? last
        : !event.shiftKey && focused === last ? first : undefined;
      if (next) {
        event.preventDefault();
        next.focus({ preventScroll: true });
      }
    }}
    onCancel={(event) => { event.preventDefault(); close(); }}
    onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
    <div className="nk-dialog-layout" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
    <NekoDialogPanel size="compact" className="max-h-[calc(100dvh-32px)] overflow-y-auto">
      <div className="flex items-start justify-between gap-4">
        <div><h2 id="local-model-title" className="text-[18px] font-medium text-[var(--nk-text)]">Thiết lập mô hình</h2>
          <p id="local-model-description" className="mt-1 text-[12px] leading-5 text-[var(--nk-text-3)]">Dùng cho chat mới. Không cần tài khoản Wiii.</p></div>
        <NekoIconButton label="Đóng thiết lập mô hình" disabled={saving} onClick={close}><X size={16} aria-hidden="true" /></NekoIconButton>
      </div>
      {loading ? <p role="status" className="mt-5 text-[13px]">Đang đọc thiết lập…</p> : preset ? <form className="mt-5 grid gap-4" autoComplete="off" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <label className="grid gap-1.5 text-[12px] text-[var(--nk-text-2)]">Nhà cung cấp
          <select ref={providerInput} className="nk-control-input w-full" value={presetId} disabled={saving} onChange={(event) => {
            const next = presets.find((item) => item.id === event.target.value);
            if (!next) return;
            setPresetId(next.id); setModel(next.model); setBaseUrl(next.baseUrl); setApiKey(""); setError(null);
          }}>{presets.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
        </label>
        {preset.customEndpoint ? <label className="grid gap-1.5 text-[12px] text-[var(--nk-text-2)]">Địa chỉ máy chủ
          <NekoInput type="url" value={baseUrl} disabled={saving} autoComplete="off" spellCheck={false} onChange={(event) => { setBaseUrl(event.target.value); setApiKey(""); }} aria-describedby="local-model-url-help" />
          <span id="local-model-url-help" className="text-[11px] text-[var(--nk-text-3)]">API tương thích OpenAI. Chỉ dùng HTTP cho localhost.</span>
        </label> : null}
        <label className="grid gap-1.5 text-[12px] text-[var(--nk-text-2)]">Mã mô hình
          <NekoInput ref={modelInput} value={model} disabled={saving} maxLength={200} autoComplete="off" spellCheck={false} placeholder="Ví dụ: llama3.2" onChange={(event) => setModel(event.target.value)} />
        </label>
        <label className="grid gap-1.5 text-[12px] text-[var(--nk-text-2)]">{preset.requiresKey ? "Khóa API" : "Khóa API (có thể bỏ trống trên localhost)"}
          <NekoInput ref={keyInput} type="password" value={apiKey} disabled={saving} maxLength={8192} autoComplete="off" spellCheck={false} onChange={(event) => setApiKey(event.target.value)} aria-describedby="local-model-key-help" />
          <span id="local-model-key-help" className="text-[11px] leading-4 text-[var(--nk-text-3)]">Khóa chỉ lưu trên máy này, trong tệp cấu hình riêng tư chưa mã hóa. Không đồng bộ lên Wiii.</span>
        </label>
        {error ? <p role="alert" className="text-[12px] leading-5 text-[var(--nk-danger)]">{error}</p> : null}
        <p className="text-[11px] leading-4 text-[var(--nk-text-3)]">Lưu xong, gửi tin đầu tiên để kiểm tra kết nối.</p>
        <div className="flex justify-end gap-2"><NekoButton disabled={saving} onClick={close}>Hủy</NekoButton><NekoButton type="submit" variant="primary" disabled={saving}>{saving ? "Đang lưu…" : "Lưu mô hình"}</NekoButton></div>
      </form> : <div className="mt-5"><p role="alert" className="text-[12px] text-[var(--nk-danger)]">{error ?? "Chưa đọc được danh sách mô hình."}</p><NekoButton className="mt-3" onClick={() => setAttempt((value) => value + 1)}>Thử lại</NekoButton></div>}
    </NekoDialogPanel>
    </div>
  </dialog>;
}
