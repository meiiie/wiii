"""
Organization Repository — Multi-Tenant CRUD operations.

Sprint 24: Multi-Organization (Multi-Tenant) Architecture.
Uses the shared database engine (singleton pattern, same as scheduler_repository.py).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app.models.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    UserOrganizationResponse,
)

logger = logging.getLogger(__name__)


class OrganizationRepository:
    """
    Repository for organizations and user_organizations tables.

    Uses the shared database engine (singleton pattern).
    """

    ORG_TABLE = "organizations"
    MEMBERSHIP_TABLE = "user_organizations"

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization using shared database engine."""
        if not self._initialized:
            try:
                from app.core.database import get_shared_engine, get_shared_session_factory
                self._engine = get_shared_engine()
                self._session_factory = get_shared_session_factory()
                self._initialized = True
            except Exception as e:
                logger.error("OrganizationRepository init failed: %s", e)

    # =========================================================================
    # Organization CRUD
    # =========================================================================

    def create_organization(self, org: OrganizationCreate) -> Optional[OrganizationResponse]:
        """Create a new organization."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        now = datetime.now(timezone.utc)

        try:
            with self._session_factory() as session:
                # ON CONFLICT: reactivate soft-deleted org with new data
                session.execute(
                    text(
                        f"INSERT INTO {self.ORG_TABLE} "
                        f"(id, name, display_name, description, allowed_domains, "
                        f"default_domain, settings, is_active, created_at, updated_at) "
                        f"VALUES (:id, :name, :display_name, :description, "
                        f":allowed_domains, :default_domain, CAST(:settings AS jsonb), "
                        f"true, :now, :now) "
                        f"ON CONFLICT (id) DO UPDATE SET "
                        f"name = :name, display_name = :display_name, "
                        f"description = :description, allowed_domains = :allowed_domains, "
                        f"default_domain = :default_domain, "
                        f"settings = CAST(:settings AS jsonb), "
                        f"is_active = true, updated_at = :now"
                    ),
                    {
                        "id": org.id,
                        "name": org.name,
                        "display_name": org.display_name,
                        "description": org.description,
                        "allowed_domains": org.allowed_domains,
                        "default_domain": org.default_domain,
                        "settings": json.dumps(org.settings, ensure_ascii=False),
                        "now": now,
                    },
                )
                session.commit()

            logger.info("[ORG] Created organization: %s", org.id)
            return OrganizationResponse(
                id=org.id,
                name=org.name,
                display_name=org.display_name,
                description=org.description,
                allowed_domains=org.allowed_domains,
                default_domain=org.default_domain,
                settings=org.settings,
                is_active=True,
                created_at=now,
                updated_at=now,
            )

        except Exception as e:
            logger.error("Create organization failed: %s", e)
            return None

    def get_organization(self, org_id: str) -> Optional[OrganizationResponse]:
        """Get an organization by ID."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"SELECT id, name, display_name, description, "
                        f"allowed_domains, default_domain, settings, "
                        f"is_active, created_at, updated_at "
                        f"FROM {self.ORG_TABLE} WHERE id = :id AND is_active = true"
                    ),
                    {"id": org_id},
                ).fetchone()

                if not row:
                    return None

                return self._org_row_to_response(row)

        except Exception as e:
            logger.error("Get organization failed: %s", e)
            return None

    def list_organizations(self, active_only: bool = True) -> list[OrganizationResponse]:
        """List all organizations."""
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                where = "WHERE is_active = true" if active_only else ""
                rows = session.execute(
                    text(
                        f"SELECT id, name, display_name, description, "
                        f"allowed_domains, default_domain, settings, "
                        f"is_active, created_at, updated_at "
                        f"FROM {self.ORG_TABLE} {where} "
                        f"ORDER BY name ASC"
                    ),
                ).fetchall()

                return [self._org_row_to_response(row) for row in rows]

        except Exception as e:
            logger.error("List organizations failed: %s", e)
            return []

    def update_organization(
        self, org_id: str, data: OrganizationUpdate
    ) -> Optional[OrganizationResponse]:
        """Update an organization (partial update)."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        now = datetime.now(timezone.utc)
        updates = data.model_dump(exclude_none=True)
        if not updates:
            return self.get_organization(org_id)

        try:
            set_clauses = ["updated_at = :now"]
            params: dict = {"org_id": org_id, "now": now}

            for key, value in updates.items():
                if key == "settings":
                    set_clauses.append(f"{key} = CAST(:v_{key} AS jsonb)")
                    params[f"v_{key}"] = json.dumps(value, ensure_ascii=False)
                elif key == "allowed_domains":
                    set_clauses.append(f"{key} = :v_{key}")
                    params[f"v_{key}"] = value
                else:
                    set_clauses.append(f"{key} = :v_{key}")
                    params[f"v_{key}"] = value

            with self._session_factory() as session:
                session.execute(
                    text(
                        f"UPDATE {self.ORG_TABLE} SET "
                        f"{', '.join(set_clauses)} "
                        f"WHERE id = :org_id"
                    ),
                    params,
                )
                session.commit()

            return self.get_organization(org_id)

        except Exception as e:
            logger.error("Update organization failed: %s", e)
            return None

    def delete_organization(self, org_id: str) -> bool:
        """Soft-delete an organization (set is_active=False)."""
        self._ensure_initialized()
        if not self._session_factory:
            return False

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(
                        f"UPDATE {self.ORG_TABLE} "
                        f"SET is_active = false, updated_at = :now "
                        f"WHERE id = :org_id AND is_active = true"
                    ),
                    {"org_id": org_id, "now": datetime.now(timezone.utc)},
                )
                session.commit()
                return result.rowcount > 0

        except Exception as e:
            logger.error("Delete organization failed: %s", e)
            return False

    # =========================================================================
    # User-Organization Membership
    # =========================================================================

    def add_user_to_org(
        self, user_id: str, org_id: str, role: str = "member"
    ) -> bool:
        """Add a user to an organization."""
        self._ensure_initialized()
        if not self._session_factory:
            return False

        try:
            with self._session_factory() as session:
                session.execute(
                    text(
                        f"INSERT INTO {self.MEMBERSHIP_TABLE} "
                        f"(user_id, organization_id, role) "
                        f"VALUES (:user_id, :org_id, :role) "
                        f"ON CONFLICT (user_id, organization_id) DO UPDATE "
                        f"SET role = :role"
                    ),
                    {"user_id": user_id, "org_id": org_id, "role": role},
                )
                session.commit()
                return True

        except Exception as e:
            logger.error("Add user to org failed: %s", e)
            return False

    def remove_user_from_org(self, user_id: str, org_id: str) -> bool:
        """Remove a user from an organization."""
        self._ensure_initialized()
        if not self._session_factory:
            return False

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(
                        f"DELETE FROM {self.MEMBERSHIP_TABLE} "
                        f"WHERE user_id = :user_id AND organization_id = :org_id"
                    ),
                    {"user_id": user_id, "org_id": org_id},
                )
                session.commit()
                return result.rowcount > 0

        except Exception as e:
            logger.error("Remove user from org failed: %s", e)
            return False

    def get_user_organizations(
        self, user_id: str
    ) -> list[UserOrganizationResponse]:
        """Get all organizations a user belongs to."""
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                rows = session.execute(
                    text(
                        f"SELECT uo.user_id, uo.organization_id, uo.role, uo.joined_at, "
                        f"o.id, o.name, o.display_name, o.description, "
                        f"o.allowed_domains, o.default_domain, o.settings, "
                        f"o.is_active, o.created_at, o.updated_at "
                        f"FROM {self.MEMBERSHIP_TABLE} uo "
                        f"JOIN {self.ORG_TABLE} o ON uo.organization_id = o.id "
                        f"WHERE uo.user_id = :user_id AND o.is_active = true "
                        f"ORDER BY uo.joined_at ASC"
                    ),
                    {"user_id": user_id},
                ).fetchall()

                return [self._membership_row_to_response(row) for row in rows]

        except Exception as e:
            logger.error("Get user organizations failed: %s", e)
            return []

    def get_org_members(
        self, org_id: str, limit: int = 100
    ) -> list[dict]:
        """List members of an organization."""
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                rows = session.execute(
                    text(
                        f"SELECT user_id, organization_id, role, joined_at "
                        f"FROM {self.MEMBERSHIP_TABLE} "
                        f"WHERE organization_id = :org_id "
                        f"ORDER BY joined_at ASC "
                        f"LIMIT :limit"
                    ),
                    {"org_id": org_id, "limit": limit},
                ).fetchall()

                return [
                    {
                        "user_id": row[0],
                        "organization_id": row[1],
                        "role": row[2],
                        "joined_at": str(row[3]) if row[3] else None,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error("Get org members failed: %s", e)
            return []

    def get_user_default_org(self, user_id: str) -> Optional[str]:
        """Get the first active organization a user belongs to (default)."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"SELECT uo.organization_id "
                        f"FROM {self.MEMBERSHIP_TABLE} uo "
                        f"JOIN {self.ORG_TABLE} o ON uo.organization_id = o.id "
                        f"WHERE uo.user_id = :user_id AND o.is_active = true "
                        f"ORDER BY uo.joined_at ASC LIMIT 1"
                    ),
                    {"user_id": user_id},
                ).fetchone()

                return row[0] if row else None

        except Exception as e:
            logger.error("Get user default org failed: %s", e)
            return None

    def is_user_in_org(self, user_id: str, org_id: str) -> bool:
        """Check if a user is a member of an active organization."""
        self._ensure_initialized()
        if not self._session_factory:
            return False

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"SELECT 1 FROM {self.MEMBERSHIP_TABLE} uo "
                        f"JOIN {self.ORG_TABLE} o ON uo.organization_id = o.id "
                        f"WHERE uo.user_id = :user_id AND uo.organization_id = :org_id "
                        f"AND o.is_active = true"
                    ),
                    {"user_id": user_id, "org_id": org_id},
                ).fetchone()

                return row is not None

        except Exception as e:
            logger.error("Check user in org failed: %s", e)
            return False

    # =========================================================================
    # Sprint 181: Org-Level Admin Queries
    # =========================================================================

    def get_user_org_role(self, user_id: str, org_id: str) -> Optional[str]:
        """Get user's role within an organization. Returns None if not a member."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"SELECT uo.role FROM {self.MEMBERSHIP_TABLE} uo "
                        f"JOIN {self.ORG_TABLE} o ON uo.organization_id = o.id "
                        f"WHERE uo.user_id = :user_id AND uo.organization_id = :org_id "
                        f"AND o.is_active = true"
                    ),
                    {"user_id": user_id, "org_id": org_id},
                ).fetchone()

                return row[0] if row else None

        except Exception as e:
            logger.error("Get user org role failed: %s", e)
            return None

    def get_user_admin_orgs(self, user_id: str) -> list[str]:
        """Get org IDs where user has admin or owner role."""
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                rows = session.execute(
                    text(
                        f"SELECT uo.organization_id FROM {self.MEMBERSHIP_TABLE} uo "
                        f"JOIN {self.ORG_TABLE} o ON uo.organization_id = o.id "
                        f"WHERE uo.user_id = :user_id AND uo.role IN ('admin', 'owner') "
                        f"AND o.is_active = true"
                    ),
                    {"user_id": user_id},
                ).fetchall()

                return [row[0] for row in rows]

        except Exception as e:
            logger.error("Get user admin orgs failed: %s", e)
            return []

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _org_row_to_response(row) -> OrganizationResponse:
        """Convert an org database row to OrganizationResponse."""
        settings_raw = row[6]
        if isinstance(settings_raw, str):
            try:
                settings_data = json.loads(settings_raw)
            except (json.JSONDecodeError, TypeError):
                settings_data = {}
        elif isinstance(settings_raw, dict):
            settings_data = settings_raw
        else:
            settings_data = {}

        return OrganizationResponse(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            allowed_domains=row[4] if row[4] else [],
            default_domain=row[5],
            settings=settings_data,
            is_active=row[7] if row[7] is not None else True,
            created_at=row[8],
            updated_at=row[9],
        )

    @staticmethod
    def _membership_row_to_response(row) -> UserOrganizationResponse:
        """Convert a membership join row to UserOrganizationResponse."""
        settings_raw = row[10]
        if isinstance(settings_raw, str):
            try:
                settings_data = json.loads(settings_raw)
            except (json.JSONDecodeError, TypeError):
                settings_data = {}
        elif isinstance(settings_raw, dict):
            settings_data = settings_raw
        else:
            settings_data = {}

        org = OrganizationResponse(
            id=row[4],
            name=row[5],
            display_name=row[6],
            description=row[7],
            allowed_domains=row[8] if row[8] else [],
            default_domain=row[9],
            settings=settings_data,
            is_active=row[11] if row[11] is not None else True,
            created_at=row[12],
            updated_at=row[13],
        )

        return UserOrganizationResponse(
            user_id=row[0],
            organization_id=row[1],
            role=row[2],
            joined_at=row[3],
            organization=org,
        )


# =============================================================================
# Singleton
# =============================================================================

_org_repo: Optional[OrganizationRepository] = None


def get_organization_repository() -> OrganizationRepository:
    """Get or create the OrganizationRepository singleton."""
    global _org_repo
    if _org_repo is None:
        _org_repo = OrganizationRepository()
    return _org_repo
