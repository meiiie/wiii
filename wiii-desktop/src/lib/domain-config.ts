/**
 * Shared domain configuration — icons, labels, badges.
 * Sprint 109: Extracted from WelcomeScreen, DomainSelector, StatusBar, conversation-groups.
 */
import { Anchor, Car } from "lucide-react";

/** Icon component for each domain. */
export const DOMAIN_ICONS: Record<string, typeof Anchor> = {
  maritime: Anchor,
  traffic_law: Car,
};

/** Vietnamese display labels for each domain. */
export const DOMAIN_LABELS: Record<string, string> = {
  maritime: "Hàng hải",
  traffic_law: "Luật giao thông",
};

/** Short sidebar badge codes (2-char). */
export const DOMAIN_BADGES: Record<string, string> = {
  maritime: "HH",
  traffic_law: "GT",
};
