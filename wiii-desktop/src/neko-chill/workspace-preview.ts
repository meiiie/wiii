export function resolvePreviewAssetPath(
  filePath: string,
  rawReference: string,
): string | null {
  const reference = rawReference.trim();
  if (
    !reference ||
    reference.startsWith("#") ||
    reference.startsWith("//") ||
    /^(?:[a-z][a-z\d+.-]*:)/i.test(reference)
  ) {
    return null;
  }

  const cleanReference = reference.split(/[?#]/, 1)[0].replace(/\\/g, "/");
  const parts = filePath.replace(/\\/g, "/").split("/");
  parts.pop();
  if (cleanReference.startsWith("/")) parts.length = 0;

  for (const part of cleanReference.replace(/^\/+/, "").split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (parts.length === 0) return null;
      parts.pop();
      continue;
    }
    try {
      parts.push(decodeURIComponent(part));
    } catch {
      return null;
    }
  }
  return parts.join("/");
}
