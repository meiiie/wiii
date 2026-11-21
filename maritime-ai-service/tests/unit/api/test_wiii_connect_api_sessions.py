from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_session_start_api_blocks_without_leaking_secrets(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/sessions",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "requested_scopes": {"read": True, "write": True},
                "request_metadata": {
                    "access_token": "secret-value",
                    "client_secret": "secret-value",
                    "workspace_id": "workspace_1",
                },
                "refresh_token": "secret-value",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_session.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_disabled"
    assert payload["authorization_url"] == ""
    assert payload["audit_event"]["request"]["requested_scopes"]["write"] is True
    assert "redacted_sensitive_field" in serialized
    assert "workspace_id" in serialized
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized
    assert "secret-value" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_session_api_404_for_unknown_provider(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/wiii-connect/providers/not-real/sessions")

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown_wiii_connect_provider"


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_blocks_without_leaking_secrets(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/authorization-url",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "state_present": True,
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_blocks_without_leaking_secrets_when_authenticated(
    authenticated_app,
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/authorization-url",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "state_present": True,
                "requested_scopes": {"read": True},
                "request_metadata": {
                    "access_token": "secret-value",
                    "client_secret": "secret-value",
                    "workspace_id": "workspace_1",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_provider_adapter.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_disabled"
    assert payload["authorization_url"] == ""
    assert "redacted_sensitive_field" in serialized
    assert "workspace_id" in serialized
    assert "access_token" not in serialized
    assert "client_secret" not in serialized
    assert "secret-value" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_issues_sanitized_composio_link(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioConnectLinkResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
        connection_upserts = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(metadata, sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["connect_link"]["ready"] is True
            assert "link_token" not in serialized
            assert "ca_secret" not in serialized
            return True

        def upsert_connection_record(
            self,
            connection,
            *,
            organization_id: str,
            user_id: str,
            provider_kind: str,
        ):
            self.connection_upserts += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_kind == "composio"
            assert connection.connection_id == "ca_123"
            assert connection.state == "authorizing"
            return True

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"facebook": "authcfg_fb"},
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_connect_link(**kwargs):
        assert kwargs["provider_slug"] == "facebook"
        callback = urlsplit(kwargs["callback_url"])
        assert callback.scheme == "https"
        assert callback.netloc == "wiii.example.test"
        assert callback.path == "/callback"
        assert "wiii_state" in parse_qs(callback.query)
        assert kwargs["user_id"].startswith("wiii_")
        return WiiiConnectComposioConnectLinkResult(
            ready=True,
            redirect_url="https://composio.example.test/connect/session",
            connected_account_id="ca_123",
            connected_account_ref_present=True,
            reason="ready",
        )

    monkeypatch.setattr(
        wiii_connect_api,
        "create_composio_connect_link",
        fake_connect_link,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/authorization-url",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "state_present": True,
                "probe_database": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "ready"
    assert payload["reason"] == "authorization_url_issued"
    assert payload["authorization_url"] == "https://composio.example.test/connect/session"
    assert payload["adapter"]["can_execute_actions"] is False
    assert fake_storage.audit_appends == 1
    assert fake_storage.connection_upserts == 1
    assert "secret-api-key" not in serialized
    assert "authcfg_fb" not in serialized
    assert "link_token" not in serialized
    assert "ca_secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_sanitizes_composio_failure(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioConnectLinkResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert "provider raw error with secret-api-key" not in serialized
            return True

    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"facebook": "authcfg_fb"},
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: FakeStorage(),
    )

    async def fake_connect_link(**kwargs):
        return WiiiConnectComposioConnectLinkResult(
            ready=False,
            reason="provider raw error with secret-api-key",
        )

    monkeypatch.setattr(
        wiii_connect_api,
        "create_composio_connect_link",
        fake_connect_link,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/authorization-url",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "state_present": True,
                "probe_database": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "authorization_url_missing"
    assert payload["authorization_url"] == ""
    assert "secret-api-key" not in serialized
    assert "provider raw error" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_404_for_unknown_provider(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/not-real/authorization-url",
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wiii_connect_authorization_url_api_404_for_unknown_provider_when_authenticated(
    authenticated_app,
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/not-real/authorization-url",
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown_wiii_connect_provider"
