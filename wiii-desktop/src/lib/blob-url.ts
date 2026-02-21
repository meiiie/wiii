/**
 * Base64→Blob URL converter for screenshot memory optimization.
 * Sprint 162b: Converts inline base64 data to object URLs, reducing DOM memory.
 *
 * Usage: const url = base64ToBlobUrl(base64Data, "image/jpeg");
 * Cleanup: revokeBlobUrl(url);
 */

const _cache = new Map<string, string>();

/**
 * Convert a base64 string to a Blob URL (object URL).
 * Caches by a hash of the first 64 chars to avoid re-creating blobs for the same image.
 */
export function base64ToBlobUrl(base64: string, mimeType = "image/jpeg"): string {
  // Use first 64 chars as cache key (unique enough for different images)
  const cacheKey = base64.slice(0, 64);
  const cached = _cache.get(cacheKey);
  if (cached) return cached;

  const byteChars = atob(base64);
  const byteNumbers = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteNumbers[i] = byteChars.charCodeAt(i);
  }
  const blob = new Blob([byteNumbers], { type: mimeType });
  const url = URL.createObjectURL(blob);
  _cache.set(cacheKey, url);
  return url;
}

/**
 * Revoke a blob URL and remove from cache.
 */
export function revokeBlobUrl(url: string): void {
  URL.revokeObjectURL(url);
  for (const [key, val] of _cache) {
    if (val === url) {
      _cache.delete(key);
      break;
    }
  }
}

/**
 * Revoke all cached blob URLs. Call on conversation switch or cleanup.
 */
export function revokeAllBlobUrls(): void {
  for (const url of _cache.values()) {
    URL.revokeObjectURL(url);
  }
  _cache.clear();
}
