/**
 * HtmlArtifact — sandboxed iframe preview for HTML content.
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: H-3 (blob leak), H-4 (iframeRef source validation)
 */
import { useEffect, useState, useRef } from "react";
import { wrapInSandboxHtml, createSandboxUrl, listenFromSandbox } from "@/lib/artifact-sandbox";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

export default function HtmlArtifact({ artifact, mode }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(mode === "card" ? 200 : 400);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  // H-3: Create/revoke blob URL properly — track via ref to avoid race condition
  useEffect(() => {
    if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    const html = wrapInSandboxHtml(artifact.content, artifact.title);
    const url = createSandboxUrl(html);
    blobUrlRef.current = url;
    setBlobUrl(url);
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [artifact.content, artifact.title]);

  // H-4: Listen for resize with source validation via iframeRef
  useEffect(() => {
    const cleanup = listenFromSandbox((msg) => {
      if (msg.type === "resize" && typeof (msg.payload as { height?: number })?.height === "number") {
        const maxHeight = mode === "card" ? 300 : 800;
        setIframeHeight(Math.min((msg.payload as { height: number }).height, maxHeight));
      }
    }, iframeRef);
    return cleanup;
  }, [mode]);

  if (!blobUrl) return null;

  return (
    <div className={mode === "card" ? "rounded-lg overflow-hidden" : "p-4"}>
      <iframe
        ref={iframeRef}
        src={blobUrl}
        sandbox="allow-scripts"
        style={{
          width: "100%",
          height: `${iframeHeight}px`,
          border: "none",
          borderRadius: "8px",
        }}
        className="bg-white"
        title={artifact.title}
      />
    </div>
  );
}
