import { describe, expect, it } from "vitest";
import {
  buildAuthUserFromJwt,
  buildAuthUserFromPayload,
  toCompatibilitySettingsRole,
} from "@/lib/auth-user";

function buildFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

describe("auth-user normalization", () => {
  it("keeps legacy_role separate from platform_role", () => {
    const user = buildAuthUserFromPayload({
      id: "u1",
      email: "user@example.com",
      name: "User",
      role: "teacher",
      legacy_role: "teacher",
      platform_role: "user",
      host_role: "teacher",
      role_source: "lms_host",
      connector_id: "lms-main",
    });

    expect(user.platform_role).toBe("user");
    expect(user.legacy_role).toBe("teacher");
    expect(user.role).toBe("teacher");
    expect(user.host_role).toBe("teacher");
    expect(user.role_source).toBe("lms_host");
    expect(user.connector_id).toBe("lms-main");
  });

  it("falls back to platform admin compatibility role only when legacy role is absent", () => {
    const user = buildAuthUserFromPayload({
      id: "admin-1",
      email: "admin@example.com",
      platform_role: "platform_admin",
    });

    expect(user.platform_role).toBe("platform_admin");
    expect(user.legacy_role).toBe("admin");
    expect(user.role).toBe("admin");
  });

  it("maps unknown compatibility roles back to student for settings", () => {
    expect(toCompatibilitySettingsRole({ role: "observer", legacy_role: "observer" })).toBe("student");
    expect(toCompatibilitySettingsRole({ role: "teacher", legacy_role: "teacher" })).toBe("teacher");
    expect(toCompatibilitySettingsRole({ role: "admin" })).toBe("admin");
    expect(toCompatibilitySettingsRole({ role: "org_admin", legacy_role: "org_admin" })).toBe("teacher");
  });

  it("builds identity v2 fields from JWT payloads", () => {
    const user = buildAuthUserFromJwt(
      buildFakeJwt({
        sub: "user-123",
        email: "teacher@example.com",
        name: "Teacher",
        role: "teacher",
        legacy_role: "teacher",
        platform_role: "user",
        host_role: "teacher",
        role_source: "lms_host",
        active_organization_id: "lms-main",
        connector_id: "maritime-lms",
        identity_version: "2",
      }),
    );

    expect(user.id).toBe("user-123");
    expect(user.email).toBe("teacher@example.com");
    expect(user.legacy_role).toBe("teacher");
    expect(user.platform_role).toBe("user");
    expect(user.host_role).toBe("teacher");
    expect(user.role_source).toBe("lms_host");
    expect(user.active_organization_id).toBe("lms-main");
    expect(user.connector_id).toBe("maritime-lms");
    expect(user.identity_version).toBe("2");
  });
});
