/**
 * Organization Branding — CSS custom property injection.
 * Sprint 161: "Khong Gian Rieng" — per-org visual customization.
 *
 * Pattern: Canva Brand Kit + Microsoft Teams tenant branding.
 * Implementation: CSS custom properties (industry standard 2025-2026).
 *
 * Flow:
 *  1. User switches org -> org-store fetches OrgSettings from backend
 *  2. applyOrgBranding() sets CSS custom properties on :root
 *  3. All Tailwind/CSS references use var(--accent) etc. — instant theme update
 *  4. resetBranding() restores Wiii platform defaults
 */
import type { OrgBranding } from "@/api/types";

/** Wiii platform default branding (matches globals.css :root) */
export const DEFAULT_BRANDING: OrgBranding = {
  logo_url: null,
  primary_color: "#AE5630",
  accent_color: "#C4633A",
  welcome_message: "Xin chào! Mình là Wiii",
  chatbot_name: "Wiii",
  chatbot_avatar_url: null,
  institution_type: "general",
};

/**
 * Apply organization branding to the document via CSS custom properties.
 * Only overrides --accent and --accent-hover (the org-customizable colors).
 * Surface/text/border colors remain unchanged (theme-controlled).
 */
export function applyOrgBranding(branding: OrgBranding): void {
  const root = document.documentElement;

  // Only override accent colors — surface/text stay theme-controlled
  root.style.setProperty("--accent", branding.primary_color);
  root.style.setProperty("--accent-hover", branding.accent_color);
  root.style.setProperty("--accent-orange", branding.primary_color);
  root.style.setProperty("--accent-orange-hover", branding.accent_color);
}

/**
 * Reset branding to Wiii platform defaults.
 * Called when switching to personal workspace or on logout.
 */
export function resetBranding(): void {
  applyOrgBranding(DEFAULT_BRANDING);
}
