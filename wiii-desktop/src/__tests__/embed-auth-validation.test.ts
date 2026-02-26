/**
 * Sprint 194c: Embed auth format validation tests.
 * Tests org/domain/server format validation to prevent injection attacks.
 */
import { describe, it, expect } from "vitest";
import { parseEmbedConfig } from "@/lib/embed-auth";

describe("Sprint 194c: Embed config format validation", () => {
  // org validation
  describe("org validation", () => {
    it("accepts valid alphanumeric org with hyphens", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&org=maritime-lms");
      expect(config.org).toBe("maritime-lms");
    });

    it("accepts org with underscores", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&org=my_org_123");
      expect(config.org).toBe("my_org_123");
    });

    it("rejects org with special characters", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&org=../../../etc/passwd");
      expect(config.org).toBeUndefined();
    });

    it("rejects org with spaces", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&org=my%20org");
      expect(config.org).toBeUndefined();
    });

    it("rejects org with SQL injection attempt", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&org='; DROP TABLE--");
      expect(config.org).toBeUndefined();
    });

    it("rejects org longer than 64 chars", () => {
      const longOrg = "a".repeat(65);
      const config = parseEmbedConfig(`http://localhost/embed#token=jwt&org=${longOrg}`);
      expect(config.org).toBeUndefined();
    });

    it("accepts org exactly 64 chars", () => {
      const org64 = "a".repeat(64);
      const config = parseEmbedConfig(`http://localhost/embed#token=jwt&org=${org64}`);
      expect(config.org).toBe(org64);
    });
  });

  // domain validation
  describe("domain validation", () => {
    it("accepts valid domain like 'maritime'", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&domain=maritime");
      expect(config.domain).toBe("maritime");
    });

    it("accepts domain with hyphens and underscores", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&domain=traffic_law-v2");
      expect(config.domain).toBe("traffic_law-v2");
    });

    it("rejects domain with dots", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&domain=evil.domain");
      expect(config.domain).toBeUndefined();
    });

    it("rejects domain longer than 32 chars", () => {
      const longDomain = "d".repeat(33);
      const config = parseEmbedConfig(`http://localhost/embed#token=jwt&domain=${longDomain}`);
      expect(config.domain).toBeUndefined();
    });

    it("rejects domain with script injection", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&domain=<script>alert(1)</script>");
      expect(config.domain).toBeUndefined();
    });
  });

  // server URL validation
  describe("server URL validation", () => {
    it("accepts valid HTTPS server URL", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=https://ai.maritime.edu");
      expect(config.server).toBe("https://ai.maritime.edu");
    });

    it("accepts HTTP server URL (dev)", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=http://localhost:8000");
      expect(config.server).toBe("http://localhost:8000");
    });

    it("strips path from server URL", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=https://api.example.com/api/v1");
      expect(config.server).toBe("https://api.example.com");
    });

    it("strips query params from server URL", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=https://api.example.com?secret=leaked");
      expect(config.server).toBe("https://api.example.com");
    });

    it("rejects javascript: protocol", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=javascript:alert(1)");
      expect(config.server).toBeUndefined();
    });

    it("rejects data: protocol", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=data:text/html,<h1>evil</h1>");
      expect(config.server).toBeUndefined();
    });

    it("rejects ftp: protocol", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=ftp://evil.com/backdoor");
      expect(config.server).toBeUndefined();
    });

    it("rejects invalid URL", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=not-a-url");
      expect(config.server).toBeUndefined();
    });

    it("rejects empty server", () => {
      const config = parseEmbedConfig("http://localhost/embed#token=jwt&server=");
      expect(config.server).toBeUndefined();
    });
  });

  // Combined validation
  describe("combined validation", () => {
    it("valid config with all fields", () => {
      const config = parseEmbedConfig(
        "http://localhost/embed#token=jwt&org=maritime-lms&domain=maritime&server=https://ai.example.com/api"
      );
      expect(config.token).toBe("jwt");
      expect(config.org).toBe("maritime-lms");
      expect(config.domain).toBe("maritime");
      expect(config.server).toBe("https://ai.example.com"); // Path stripped
    });

    it("invalid org/domain ignored but valid fields still parsed", () => {
      const config = parseEmbedConfig(
        "http://localhost/embed#token=jwt&org=../hack&domain=valid-domain&server=https://ok.com"
      );
      expect(config.token).toBe("jwt");
      expect(config.org).toBeUndefined(); // Rejected
      expect(config.domain).toBe("valid-domain"); // Accepted
      expect(config.server).toBe("https://ok.com"); // Accepted
    });
  });
});
