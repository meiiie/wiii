import { invoke } from "@tauri-apps/api/core";

export interface LocalModelPreset {
  id: string;
  label: string;
  provider: string;
  baseUrl: string;
  model: string;
  requiresKey: boolean;
  customEndpoint: boolean;
}

export interface LocalModelStatus {
  configured: boolean;
  presets: LocalModelPreset[];
}

export interface LocalModelDraft {
  presetId: string;
  model: string;
  baseUrl?: string;
  apiKey: string;
}

export interface SavedLocalModel {
  profileId: string;
  model: string;
  provider: string;
}

export function canConfigureLocalModels(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

// Exact native messages only; never reflect an unexpected IPC/parser payload,
// which might include submitted credential data.
const SAFE_ERRORS = new Set([
  "Chưa đọc được cấu hình mô hình trên máy này. Cấu hình cũ được giữ nguyên.",
  "Cấu hình mô hình hiện tại không hợp lệ. Wiii giữ nguyên, không ghi đè tệp cũ.",
  "Chưa lưu được mô hình trên máy này. Cấu hình cũ được giữ nguyên; hãy thử lại.",
  "Hãy chọn nhà cung cấp mô hình.",
  "Hãy nhập mã mô hình, không kèm khoảng trắng hoặc ký tự điều khiển.",
  "Hãy nhập khóa API hợp lệ của nhà cung cấp.",
  "Địa chỉ mô hình cần HTTPS, hoặc HTTP trên localhost; không kèm khóa, tài khoản hay tham số.",
  "Z.ai cần địa chỉ GLM Coding Plan, không dùng API tính phí theo lượt.",
  "Có cấu hình mô hình cũ đang ưu tiên trên máy này. Wiii giữ nguyên để tránh dùng nhầm khóa.",
  "Môi trường đang đặt mô hình hoặc khóa API ưu tiên. Wiii chưa thể thay cấu hình đó an toàn.",
]);

function safeError(cause: unknown): Error {
  return new Error(typeof cause === "string" && SAFE_ERRORS.has(cause)
    ? cause : "Chưa thiết lập được mô hình. Hãy thử lại; cấu hình cũ vẫn được giữ.");
}

export async function getLocalModelStatus(): Promise<LocalModelStatus> {
  if (!canConfigureLocalModels()) throw new Error("Thiết lập mô hình chỉ có trong ứng dụng Wiii trên máy.");
  try {
    return await invoke<LocalModelStatus>("local_model_status");
  } catch (cause) { throw safeError(cause); }
}

export async function saveLocalModel(request: LocalModelDraft): Promise<SavedLocalModel> {
  if (!canConfigureLocalModels()) throw new Error("Thiết lập mô hình chỉ có trong ứng dụng Wiii trên máy.");
  try {
    return await invoke<SavedLocalModel>("local_model_save", { request });
  } catch (cause) { throw safeError(cause); }
}
