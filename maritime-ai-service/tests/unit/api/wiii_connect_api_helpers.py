from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.api.v1.wiii_connect import router as wiii_connect_router
from app.core.security import optional_auth, require_auth
from app.core.security_models import AuthenticatedUser


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(wiii_connect_router)
    return app


@pytest.fixture
def authenticated_app():
    app = FastAPI()
    app.include_router(wiii_connect_router)
    app.dependency_overrides[require_auth] = lambda: AuthenticatedUser(
        user_id="user_1",
        auth_method="test",
        role="admin",
        organization_id="org_1",
    )
    return app


@pytest.fixture
def optionally_authenticated_app():
    app = FastAPI()
    app.include_router(wiii_connect_router)
    app.dependency_overrides[optional_auth] = lambda: AuthenticatedUser(
        user_id="user_1",
        auth_method="test",
        role="admin",
        organization_id="org_1",
        session_id="session_1",
    )
    return app
