import type { AuthUser } from "@/stores/auth-store";

type AuthPayload = Partial<{
  id: string;
  sub: string;
  user_id: string;
  email: string;
  name: string;
  display_name: string;
  avatar_url: string;
  role: string;
  legacy_role: string;
  platform_role: string;
  organization_role: string;
  host_role: string;
  role_source: string;
  active_organization_id: string;
  organization_id: string;
  connector_id: string;
  identity_version: string;
}>;

export function normalizePlatformRole(value: unknown): "user" | "platform_admin" {
  return value === "platform_admin" ? "platform_admin" : "user";
}

function decodeBase64UrlJson(value: string): Record<string, unknown> | null {
  if (!value) return null;
  try {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
    const decoded = atob(`${normalized}${padding}`);
    const parsed = JSON.parse(decoded);
    return parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function buildAuthUserFromPayload(payload: AuthPayload): AuthUser {
  const platformRole = normalizePlatformRole(payload.platform_role);
  const legacyRole =
    typeof payload.legacy_role === "string" && payload.legacy_role.trim()
      ? payload.legacy_role.trim()
      : typeof payload.role === "string" && payload.role.trim()
        ? payload.role.trim()
        : platformRole === "platform_admin"
          ? "admin"
          : "student";

  return {
    id: payload.id || payload.sub || payload.user_id || "",
    email: payload.email || "",
    name: payload.name || payload.display_name || "",
    avatar_url: payload.avatar_url || "",
    role: legacyRole,
    legacy_role: legacyRole,
    platform_role: platformRole,
    organization_role:
      typeof payload.organization_role === "string" ? payload.organization_role : undefined,
    host_role: typeof payload.host_role === "string" ? payload.host_role : undefined,
    role_source: typeof payload.role_source === "string" ? payload.role_source : undefined,
    active_organization_id:
      typeof payload.active_organization_id === "string"
        ? payload.active_organization_id
        : typeof payload.organization_id === "string"
          ? payload.organization_id
          : undefined,
    connector_id: typeof payload.connector_id === "string" ? payload.connector_id : undefined,
    identity_version:
      typeof payload.identity_version === "string" ? payload.identity_version : undefined,
  };
}

export function buildAuthUserFromJwt(token: string): AuthUser {
  const parts = typeof token === "string" ? token.split(".") : [];
  const payload = parts.length >= 2 ? decodeBase64UrlJson(parts[1]) : null;
  return buildAuthUserFromPayload(payload || {});
}

export function toCompatibilitySettingsRole(
  user: Pick<AuthUser, "legacy_role" | "role"> | null | undefined
): "student" | "teacher" | "admin" {
  const raw = (user?.legacy_role || user?.role || "").trim().toLowerCase();
  if (raw === "teacher" || raw === "admin") {
    return raw;
  }
  if (raw === "org_admin" || raw === "owner") {
    return "teacher";
  }
  return "student";
}
