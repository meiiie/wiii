/**
 * InlineHtmlWidget — Renders interactive HTML+JS widgets inline in chat.
 * Sprint 228: "Visual Tuong Tac" — Claude-like interactive visuals.
 *
 * Renders ```widget code blocks as sandboxed iframes directly in the chat flow.
 * Supports Chart.js, D3.js, SVG, and vanilla JS for interactive visualizations.
 *
 * Security model:
 * 1. iframe sandbox="allow-scripts" (NO allow-same-origin)
 * 2. Content via blob: URL (no network origin)
 * 3. CSP allows CDN scripts (Chart.js, D3.js) + inline styles/scripts
 * 4. Auto-resize via postMessage bridge
 * 5. Max height cap prevents layout abuse
 */
import { useEffect, useState, useRef, memo } from "react";

// Allowed CDN origins for interactive libraries
// Sprint 229: Added KaTeX (math), Three.js (3D), GSAP (animation)
const ALLOWED_CDNS = [
  "https://cdn.jsdelivr.net",
  "https://cdnjs.cloudflare.com",
  "https://unpkg.com",
  "https://d3js.org",
  "https://cdn.katex.org",
  "https://cdnjs.cloudflare.com",
];

const WIDGET_CSP = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' blob: ${ALLOWED_CDNS.join(" ")}; style-src 'unsafe-inline' ${ALLOWED_CDNS.join(" ")}; img-src blob: data: ${ALLOWED_CDNS.join(" ")}; font-src data: ${ALLOWED_CDNS.join(" ")}; connect-src 'none';">`;

function wrapWidgetHtml(content: string): string {
  // If content already has <html> shell, inject CSP into <head>
  if (/<html/i.test(content)) {
    return content.replace(/<head[^>]*>/i, (match) => `${match}\n  ${WIDGET_CSP}`);
  }

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  ${WIDGET_CSP}
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 12px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #1a1a2e;
      background: transparent;
      overflow: hidden;
    }
    canvas { max-width: 100%; height: auto; }
    svg { max-width: 100%; height: auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #e2e8f0; padding: 6px 10px; text-align: left; font-size: 13px; }
    th { background: #f1f5f9; font-weight: 600; }
    tr:hover { background: #f8fafc; }
    .chart-container { position: relative; width: 100%; }
    button, select, input {
      font-family: inherit;
      font-size: 13px;
      padding: 4px 10px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      background: #fff;
      cursor: pointer;
    }
    button:hover { background: #f3f4f6; }
  </style>
</head>
<body>
  ${content}
  <script>
    // Auto-resize: notify parent of content height changes
    function notifyResize() {
      var h = document.body.scrollHeight;
      parent.postMessage({ type: 'widget-resize', payload: { height: h } }, '*');
    }
    window.addEventListener('load', function() {
      notifyResize();
      new ResizeObserver(function() { notifyResize(); }).observe(document.body);
      // Also notify after scripts load (e.g., Chart.js renders async)
      setTimeout(notifyResize, 100);
      setTimeout(notifyResize, 500);
      setTimeout(notifyResize, 1500);
    });
  </script>
</body>
</html>`;
}

interface InlineHtmlWidgetProps {
  code: string;
  className?: string;
}

const InlineHtmlWidget = memo(function InlineHtmlWidget({ code, className = "" }: InlineHtmlWidgetProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [height, setHeight] = useState(280);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  // Create sandboxed blob URL
  useEffect(() => {
    if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);

    try {
      const html = wrapWidgetHtml(code);
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      blobUrlRef.current = url;
      setBlobUrl(url);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Khong the render widget");
    }

    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [code]);

  // Listen for resize messages from iframe
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (iframeRef.current && event.source !== iframeRef.current.contentWindow) return;
      const data = event.data;
      if (data && typeof data === "object" && data.type === "widget-resize") {
        const newHeight = (data.payload as { height?: number })?.height;
        if (typeof newHeight === "number" && newHeight > 0) {
          // Cap between 80px and 600px for inline display
          setHeight(Math.min(Math.max(newHeight + 8, 80), 600));
        }
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 ${className}`}>
        <p className="text-sm text-red-600 dark:text-red-400">Loi widget: {error}</p>
      </div>
    );
  }

  if (!blobUrl) return null;

  return (
    <div className={`inline-widget my-3 rounded-xl overflow-hidden border border-[var(--border-subtle,#e2e8f0)] dark:border-[var(--border-subtle,#334155)] bg-white dark:bg-[#1e293b] shadow-sm ${className}`}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#f8fafc] dark:bg-[#0f172a] border-b border-[var(--border-subtle,#e2e8f0)] dark:border-[var(--border-subtle,#334155)]">
        <div className="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--accent,#f97316)]">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="9" y1="3" x2="9" y2="21" />
          </svg>
          <span className="text-[11px] font-medium text-[var(--text-secondary,#64748b)]">
            Interactive Widget
          </span>
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-[11px] text-[var(--text-tertiary,#94a3b8)] hover:text-[var(--text-secondary,#64748b)] transition-colors"
          aria-label={collapsed ? "Mo rong widget" : "Thu gon widget"}
        >
          {collapsed ? "Mo rong" : "Thu gon"}
        </button>
      </div>

      {/* Iframe content */}
      {!collapsed && (
        <iframe
          ref={iframeRef}
          src={blobUrl}
          sandbox="allow-scripts"
          style={{
            width: "100%",
            height: `${height}px`,
            border: "none",
            display: "block",
            transition: "height 0.2s ease",
          }}
          title="Interactive Widget"
        />
      )}
    </div>
  );
});

export default InlineHtmlWidget;
