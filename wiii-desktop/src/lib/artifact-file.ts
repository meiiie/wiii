import type { ArtifactData } from "@/api/types";

export function resolveArtifactFileUrl(
  artifact: ArtifactData,
  serverUrl: string,
): string | null {
  const rawUrl = artifact.metadata?.file_url;
  if (typeof rawUrl !== "string" || !rawUrl) return null;
  if (/^https?:\/\//i.test(rawUrl)) return rawUrl;

  const base = serverUrl.endsWith("/") ? serverUrl : `${serverUrl}/`;
  try {
    return new URL(rawUrl.replace(/^\//, ""), base).toString();
  } catch {
    return rawUrl;
  }
}

export function describeArtifactFile(artifact: ArtifactData): string | null {
  const filename = typeof artifact.metadata?.filename === "string" ? artifact.metadata.filename : null;
  if (filename) return filename;

  const fileUrl = typeof artifact.metadata?.file_url === "string" ? artifact.metadata.file_url : "";
  const lastSegment = fileUrl.split("/").pop();
  if (lastSegment) return lastSegment;

  const filePath = typeof artifact.metadata?.file_path === "string" ? artifact.metadata.file_path : "";
  return filePath.split(/[/\\]/).pop() || null;
}

export function artifactPreviewSnippet(artifact: ArtifactData, maxLength = 160): string {
  const preview =
    (typeof artifact.metadata?.preview === "string" && artifact.metadata.preview) ||
    artifact.content ||
    "";
  if (preview.length <= maxLength) return preview;
  return `${preview.slice(0, maxLength).trimEnd()}...`;
}

export function artifactHasBinaryFile(artifact: ArtifactData): boolean {
  return typeof artifact.metadata?.file_url === "string" && artifact.metadata.file_url.length > 0;
}
