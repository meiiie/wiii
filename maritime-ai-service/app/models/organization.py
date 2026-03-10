"""
Pydantic Models for Multi-Organization (Multi-Tenant) Architecture.

Sprint 24: Organization CRUD models for API request/response.
Sprint 161: OrgSettings — typed schema for org-level customization
             (branding, feature flags, AI config, permissions).
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Sprint 161: Org Settings Schema — "Không Gian Riêng"
# =============================================================================


class OrgBranding(BaseModel):
    """Per-org branding configuration (logo, colors, persona name)."""

    logo_url: Optional[str] = None
    primary_color: str = "#AE5630"  # Wiii terracotta default
    accent_color: str = "#C4633A"
    welcome_message: str = "Xin chào! Mình là Wiii"
    chatbot_name: str = "Wiii"
    chatbot_avatar_url: Optional[str] = None
    institution_type: str = "general"  # university | k12 | corporate | government


class OrgFeatureFlags(BaseModel):
    """Per-org feature toggles — controls which tools/agents are visible."""

    enable_product_search: bool = False
    enable_deep_scanning: bool = False
    enable_thinking_chain: bool = False
    enable_browser_scraping: bool = False
    visible_agents: list[str] = Field(
        default_factory=lambda: ["rag", "tutor", "direct", "memory"],
    )
    max_search_iterations: int = 5


class OrgAIConfig(BaseModel):
    """Per-org AI behavior overrides — persona overlay and LLM parameters."""

    persona_prompt_overlay: Optional[str] = None  # Merged into system prompt
    temperature_override: Optional[float] = None
    max_response_length: Optional[int] = None
    default_domain: Optional[str] = None  # Org-level domain override
    external_connector_id: Optional[str] = None  # Sprint 220c: LMS/external connector


class OrgPermissions(BaseModel):
    """Per-org role-permission mapping override."""

    student: list[str] = Field(
        default_factory=lambda: ["read:chat", "read:knowledge", "use:tools"],
    )
    teacher: list[str] = Field(
        default_factory=lambda: [
            "read:chat", "read:knowledge", "use:tools",
            "read:analytics", "manage:courses",
        ],
    )
    admin: list[str] = Field(
        default_factory=lambda: [
            "read:chat", "read:knowledge", "use:tools",
            "read:analytics", "manage:courses",
            "manage:members", "manage:settings", "manage:branding",
            "manage:knowledge",
        ],
    )


class OrgOnboarding(BaseModel):
    """Per-org onboarding configuration."""

    quick_start_questions: list[str] = Field(default_factory=list)
    show_domain_suggestions: bool = True


class OrgSettings(BaseModel):
    """
    Typed schema for the organizations.settings JSONB column.

    Sprint 161: "Không Gian Riêng" — org-level customization.
    Merges with PLATFORM_DEFAULTS at runtime via deep_merge().
    """

    schema_version: int = 1
    branding: OrgBranding = Field(default_factory=OrgBranding)
    features: OrgFeatureFlags = Field(default_factory=OrgFeatureFlags)
    ai_config: OrgAIConfig = Field(default_factory=OrgAIConfig)
    permissions: OrgPermissions = Field(default_factory=OrgPermissions)
    onboarding: OrgOnboarding = Field(default_factory=OrgOnboarding)


class OrganizationCreate(BaseModel):
    """Request body for creating a new organization."""

    id: str = Field(
        ..., min_length=1, max_length=100,
        description="URL-safe slug: 'lms-hang-hai', 'phuong-luu-kiem'",
    )
    name: str = Field(..., min_length=1, max_length=200, description="Short name")
    display_name: Optional[str] = Field(default=None, max_length=500, description="Display name")
    description: Optional[str] = Field(default=None, description="Vietnamese description")
    allowed_domains: list[str] = Field(
        default_factory=list,
        description="Domain plugin IDs this org can use, e.g. ['maritime']",
    )
    default_domain: Optional[str] = Field(
        default=None, description="Org-specific default domain",
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Org-specific config (theme, branding)",
    )


class OrganizationUpdate(BaseModel):
    """Request body for updating an organization. All fields optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    allowed_domains: Optional[list[str]] = None
    default_domain: Optional[str] = None
    settings: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class OrganizationResponse(BaseModel):
    """Organization data returned from API."""

    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    allowed_domains: list[str] = Field(default_factory=list)
    default_domain: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserOrganizationResponse(BaseModel):
    """User-organization membership with nested org details."""

    user_id: str
    organization_id: str
    role: str = "member"
    joined_at: Optional[datetime] = None
    organization: Optional[OrganizationResponse] = None


class AddMemberRequest(BaseModel):
    """Request body for adding a user to an organization."""

    user_id: str = Field(..., min_length=1, description="User ID to add")
    role: Literal["member", "admin", "owner"] = Field(default="member", description="Organization role")
