"""
Pydantic Models for Multi-Organization (Multi-Tenant) Architecture.

Sprint 24: Organization CRUD models for API request/response.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


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
