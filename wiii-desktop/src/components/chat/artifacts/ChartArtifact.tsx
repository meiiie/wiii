/**
 * ChartArtifact — renders chart images (from matplotlib/backend).
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: M-4 — onError handler + fallback UI
 */
import { useState } from "react";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

export default function ChartArtifact({ artifact, mode }: Props) {
  const [imgError, setImgError] = useState(false);
  const imageUrl = artifact.metadata?.image_url;

  // If content is base64 image data
  const src = imageUrl
    ? (typeof imageUrl === "string" && imageUrl.startsWith("data:") ? imageUrl : `data:image/png;base64,${imageUrl}`)
    : artifact.content.startsWith("data:")
    ? artifact.content
    : `data:image/png;base64,${artifact.content}`;

  // M-4: Fallback UI on broken image
  if (imgError) {
    return (
      <div className="p-4 text-sm text-text-tertiary text-center">
        Không thể hiển thị biểu đồ.
      </div>
    );
  }

  return (
    <div className={mode === "card" ? "p-2" : "p-4"}>
      <img
        src={src}
        alt={artifact.title}
        onError={() => setImgError(true)}
        className={`rounded-lg bg-white ${mode === "card" ? "max-h-[200px]" : "max-w-full"} mx-auto`}
      />
    </div>
  );
}
