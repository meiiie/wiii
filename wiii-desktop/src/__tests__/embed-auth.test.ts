/**
 * Sprint 176: Embed auth tests.
 * Tests URL hash parsing, config validation, auth mode detection.
 */
import { describe, it, expect } from "vitest";
import { parseEmbedConfig, validateEmbedConfig, getAuthMode } from "@/lib/embed-auth";

describe("parseEmbedConfig", () => {
  it("parses JWT token from hash", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.abc");
    expect(config.token).toBe("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.abc");
  });

  it("parses refresh token from hash", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=jwt1&refresh_token=jwt2");
    expect(config.token).toBe("jwt1");
    expect(config.refresh_token).toBe("jwt2");
  });

  it("parses legacy auth from hash", () => {
    const config = parseEmbedConfig("http://localhost/embed#api_key=key123&user_id=user-456");
    expect(config.api_key).toBe("key123");
    expect(config.user_id).toBe("user-456");
  });

  it("parses org and domain", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=jwt&org=maritime-lms&domain=maritime");
    expect(config.org).toBe("maritime-lms");
    expect(config.domain).toBe("maritime");
  });

  it("parses server URL", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=https://ai.maritime.edu");
    expect(config.server).toBe("https://ai.maritime.edu");
  });

  it("parses theme", () => {
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&theme=dark").theme).toBe("dark");
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&theme=light").theme).toBe("light");
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&theme=system").theme).toBe("system");
  });

  it("ignores invalid theme values", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=jwt&theme=purple");
    expect(config.theme).toBeUndefined();
  });

  it("parses hide_welcome", () => {
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&hide_welcome=true").hide_welcome).toBe(true);
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&hide_welcome=1").hide_welcome).toBe(true);
    expect(parseEmbedConfig("http://localhost/embed#token=jwt&hide_welcome=false").hide_welcome).toBeUndefined();
  });

  it("parses role", () => {
    const config = parseEmbedConfig("http://localhost/embed#token=jwt&role=teacher");
    expect(config.role).toBe("teacher");
  });

  it("returns empty config for no params", () => {
    const config = parseEmbedConfig("http://localhost/embed");
    expect(config).toEqual({});
  });

  it("parses full URL with all params", () => {
    const url = "http://localhost/embed#token=jwt1&refresh_token=jwt2&org=maritime-lms&domain=maritime&server=https://ai.edu&theme=dark&role=student&hide_welcome=true";
    const config = parseEmbedConfig(url);
    expect(config.token).toBe("jwt1");
    expect(config.refresh_token).toBe("jwt2");
    expect(config.org).toBe("maritime-lms");
    expect(config.domain).toBe("maritime");
    expect(config.server).toBe("https://ai.edu");
    expect(config.theme).toBe("dark");
    expect(config.role).toBe("student");
    expect(config.hide_welcome).toBe(true);
  });

  it("falls back to query params when no hash", () => {
    const config = parseEmbedConfig("http://localhost/embed?token=jwt&org=test");
    expect(config.token).toBe("jwt");
    expect(config.org).toBe("test");
  });

  it("prefers hash over query params", () => {
    const config = parseEmbedConfig("http://localhost/embed?token=query-jwt#token=hash-jwt");
    expect(config.token).toBe("hash-jwt");
  });

  it("handles URL-encoded values", () => {
    // Sprint 194c: org now validates /^[a-zA-Z0-9_-]{1,64}$/ — "my org" (with space) is rejected
    const config = parseEmbedConfig("http://localhost/embed#token=eyJ%2BIg&org=my%20org");
    expect(config.token).toBe("eyJ+Ig");
    expect(config.org).toBeUndefined(); // Spaces not allowed in org ID
  });
});

describe("validateEmbedConfig", () => {
  it("returns null for valid JWT config", () => {
    expect(validateEmbedConfig({ token: "jwt123" })).toBeNull();
  });

  it("returns null for valid legacy config", () => {
    expect(validateEmbedConfig({ api_key: "key", user_id: "user" })).toBeNull();
  });

  it("returns error for empty config", () => {
    expect(validateEmbedConfig({})).toBe(
      "Missing auth: provide either 'token' (JWT) or 'api_key' + 'user_id' (legacy)"
    );
  });

  it("returns error for api_key without user_id", () => {
    expect(validateEmbedConfig({ api_key: "key" })).not.toBeNull();
  });

  it("returns error for user_id without api_key", () => {
    expect(validateEmbedConfig({ user_id: "user" })).not.toBeNull();
  });
});

describe("getAuthMode", () => {
  it("returns jwt when token is present", () => {
    expect(getAuthMode({ token: "jwt123" })).toBe("jwt");
  });

  it("returns legacy when api_key is present", () => {
    expect(getAuthMode({ api_key: "key", user_id: "user" })).toBe("legacy");
  });

  it("returns jwt when both token and api_key are present", () => {
    expect(getAuthMode({ token: "jwt", api_key: "key", user_id: "user" })).toBe("jwt");
  });

  it("returns legacy when no token", () => {
    expect(getAuthMode({})).toBe("legacy");
  });
});
