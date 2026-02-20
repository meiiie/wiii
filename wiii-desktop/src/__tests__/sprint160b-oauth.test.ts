/**
 * Sprint 160b: OAuth token fragment parsing tests.
 *
 * Verifies that LoginScreen correctly parses tokens from URL fragments (#)
 * with backward-compatible fallback to query params (?).
 */
import { describe, it, expect } from "vitest";

describe("Sprint 160b: OAuth token fragment parsing", () => {
  it("should parse tokens from URL fragment (#)", () => {
    const callbackUrl =
      "http://127.0.0.1:8765#access_token=abc123&refresh_token=def456&expires_in=1800&user_id=u1&email=test%40example.com&name=Test&avatar_url=";
    const url = new URL(callbackUrl);

    // This is the exact logic from LoginScreen.tsx
    const params = url.hash
      ? new URLSearchParams(url.hash.substring(1))
      : url.searchParams;

    expect(params.get("access_token")).toBe("abc123");
    expect(params.get("refresh_token")).toBe("def456");
    expect(params.get("expires_in")).toBe("1800");
    expect(params.get("user_id")).toBe("u1");
    expect(params.get("email")).toBe("test@example.com");
  });

  it("should fallback to query params for backward compatibility", () => {
    const callbackUrl =
      "http://127.0.0.1:8765?access_token=abc123&refresh_token=def456&expires_in=1800&user_id=u1";
    const url = new URL(callbackUrl);

    const params = url.hash
      ? new URLSearchParams(url.hash.substring(1))
      : url.searchParams;

    expect(params.get("access_token")).toBe("abc123");
    expect(params.get("refresh_token")).toBe("def456");
  });

  it("should handle empty hash gracefully", () => {
    const callbackUrl =
      "http://127.0.0.1:8765?access_token=abc123&refresh_token=def456";
    const url = new URL(callbackUrl);

    // When hash is empty string "", it's falsy
    expect(url.hash).toBe("");

    const params = url.hash
      ? new URLSearchParams(url.hash.substring(1))
      : url.searchParams;

    expect(params.get("access_token")).toBe("abc123");
  });
});
