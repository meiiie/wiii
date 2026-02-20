/**
 * PermissionGate — declarative role-based UI gating.
 * Sprint 161: "Không Gian Riêng" — Phase 2 RBAC.
 *
 * Pattern: Permit.io / React-Admin RBAC (industry standard 2025-2026).
 * Security boundary is ALWAYS the backend — this is UX optimization only.
 *
 * Usage:
 *   <PermissionGate action="manage" resource="settings">
 *     <OrgSettingsPanel />
 *   </PermissionGate>
 *
 *   <PermissionGate action="read" resource="analytics" fallback={<UpgradeBanner />}>
 *     <AnalyticsDashboard />
 *   </PermissionGate>
 */
import type { ReactNode } from "react";
import { useOrgStore } from "@/stores/org-store";

interface PermissionGateProps {
  /** Permission action (e.g., "read", "manage", "use") */
  action: string;
  /** Permission resource (e.g., "chat", "settings", "branding") */
  resource: string;
  /** Content to render when permission is granted */
  children: ReactNode;
  /** Optional fallback content when permission is denied */
  fallback?: ReactNode;
}

export function PermissionGate({
  action,
  resource,
  children,
  fallback = null,
}: PermissionGateProps) {
  const hasPermission = useOrgStore((s) => s.hasPermission);

  if (hasPermission(action, resource)) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}
