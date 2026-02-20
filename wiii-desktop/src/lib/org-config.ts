/**
 * Organization config — icons, display helpers.
 * Sprint 156: Org-first UI restructuring.
 */
import { Building2, Ship } from "lucide-react";
import type { OrganizationSummary } from "@/api/types";

/** Icon component for known organizations. */
export const ORG_ICONS: Record<string, typeof Building2> = {
  personal: Building2,
  "lms-hang-hai": Ship,
};

/** Get display name for an organization. */
export function getOrgDisplayName(org: Pick<OrganizationSummary, "display_name" | "name">): string {
  return org.display_name || org.name;
}

/** Get icon component for an organization. */
export function getOrgIcon(orgId: string): typeof Building2 {
  return ORG_ICONS[orgId] || Building2;
}
