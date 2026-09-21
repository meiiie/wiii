/**
 * Browser-preview honesty for Kết nối / Tài khoản when the chill shell
 * cannot open Wiii Connect (no Workbench host / Service gate).
 *
 * Do not invent OAuth or a full Connect surface under Vite chill preview —
 * production wires openWiiiConnect; ?preview=wiii-connect is the separate
 * Connect review rig.
 */

export const CONNECTIONS_UNAVAILABLE_IN_CHILL_PREVIEW_VI =
  "Bản xem trước Neko Chill trong trình duyệt không mở được Kết nối / Tài khoản & ứng dụng (cần Wiii Service trên desktop). Để xem riêng surface kết nối, mở ?preview=wiii-connect.";

/** Preview-safe handler: explain instead of a silent no-op. */
export function explainConnectionsUnavailableInPreview(): void {
  window.alert(CONNECTIONS_UNAVAILABLE_IN_CHILL_PREVIEW_VI);
}
