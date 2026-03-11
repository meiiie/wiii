/**
 * Artifact sandbox utilities — iframe communication bridge.
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: Security hardening (C-1, C-2, C-3, H-4)
 *
 * Security model (5 layers):
 * 1. iframe sandbox="allow-scripts" (NO allow-same-origin)
 * 2. Content via blob: URL or srcdoc (no network origin)
 * 3. CSP: default-src 'none'; script-src 'unsafe-inline' blob:
 * 4. postMessage bridge with source validation + structured messages only
 * 5. Pyodide WASM (no filesystem, no network)
 */

import type { RefObject } from "react";

// ===== Message Types =====

export interface ArtifactMessage {
  type: "result" | "error" | "resize" | "ready";
  payload: unknown;
}

// ===== HTML Escaping (C-1) =====

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export { escapeHtml };

// ===== Sandbox HTML Template =====

// C-3: Removed 'unsafe-eval' from CSP — eval handler deleted
const SANDBOX_CSP = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; img-src blob: data:; font-src data:;">`;

/**
 * Wrap raw HTML content in a sandboxed HTML document with CSP and postMessage bridge.
 */
export function wrapInSandboxHtml(content: string, title?: string): string {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  ${SANDBOX_CSP}
  <title>${escapeHtml(title || "Wiii Artifact")}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: #1a1a2e;
      background: #ffffff;
    }
    pre, code { font-family: 'IBM Plex Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
    th { background: #f7fafc; font-weight: 600; }
    tr:hover { background: #f0f4f8; }
    img { max-width: 100%; height: auto; }
  </style>
</head>
<body>
  ${content}
  <script>
    // PostMessage bridge: notify parent of ready + auto-resize
    window.addEventListener('load', function() {
      parent.postMessage({ type: 'ready', payload: null }, '*');
      // Auto-resize observer
      var ro = new ResizeObserver(function(entries) {
        for (var i = 0; i < entries.length; i++) {
          parent.postMessage({
            type: 'resize',
            payload: { height: entries[i].contentRect.height + 32 }
          }, '*');
        }
      });
      ro.observe(document.body);
    });
  </script>
</body>
</html>`;
}

/**
 * Create a sandboxed blob URL from HTML content.
 * The URL should be revoked when the iframe is unmounted.
 */
export function createSandboxUrl(html: string): string {
  const blob = new Blob([html], { type: "text/html" });
  return URL.createObjectURL(blob);
}

/**
 * Listen for messages from sandboxed iframes.
 * Returns a cleanup function to remove the listener.
 *
 * C-2 + H-4: When iframeRef is provided, validates event.source matches
 * the iframe's contentWindow — prevents cross-iframe interference.
 */
export function listenFromSandbox(
  callback: (msg: ArtifactMessage) => void,
  iframeRef?: RefObject<HTMLIFrameElement | null>
): () => void {
  const handler = (event: MessageEvent) => {
    // C-2: Validate source — only accept messages from our iframe
    if (iframeRef?.current && event.source !== iframeRef.current.contentWindow) {
      return;
    }
    const data = event.data;
    if (data && typeof data === "object" && typeof data.type === "string") {
      callback(data as ArtifactMessage);
    }
  };
  window.addEventListener("message", handler);
  return () => window.removeEventListener("message", handler);
}
