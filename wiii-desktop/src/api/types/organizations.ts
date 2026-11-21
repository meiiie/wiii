import type { PlatformRole } from "./identity";

export interface DomainSummary {
  id: string;
  name: string;
  name_vi?: string;
  version: string;
  description: string;
  skill_count: number;
  keyword_count: number;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  allowed_domains: string[];
  default_domain?: string;
  is_active: boolean;
}

export interface OrgBranding {
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  welcome_message: string;
  chatbot_name: string;
  chatbot_avatar_url: string | null;
  institution_type: string;
}

export interface OrgFeatureFlags {
  enable_product_search: boolean;
  enable_deep_scanning: boolean;
  enable_thinking_chain: boolean;
  enable_browser_scraping: boolean;
  visible_agents: string[];
  max_search_iterations: number;
}

export interface OrgPermissions {
  student: string[];
  teacher: string[];
  admin: string[];
}

export interface OrgOnboarding {
  quick_start_questions: string[];
  show_domain_suggestions: boolean;
}

export interface OrgSettings {
  schema_version: number;
  branding: OrgBranding;
  features: OrgFeatureFlags;
  ai_config: {
    persona_prompt_overlay: string | null;
    temperature_override: number | null;
    max_response_length: number | null;
    default_domain: string | null;
  };
  permissions: OrgPermissions;
  onboarding: OrgOnboarding;
}

export interface OrgPermissionsResponse {
  permissions: string[];
  role: string;
  permission_role?: string;
  legacy_role?: string;
  platform_role?: PlatformRole | string;
  organization_id: string;
  org_role?: string | null;  // Sprint 215: member | admin | owner
}
