from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_connections_api_requires_auth(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers/facebook/connections")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wiii_connect_connections_api_returns_stored_rows_when_provider_disabled(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import WiiiConnectConnectionRecordV1
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        def status(self, *, probe_database: bool = True):
            assert probe_database is True
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def list_connection_records(
            self,
            *,
            organization_id: str,
            user_id: str,
            provider_slug: str,
        ):
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "facebook"
            return (
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_active",
                    provider_slug="facebook",
                    state="connected",
                    reason="stored_connection",
                ),
            )

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(enabled=False),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fail_list_connections(**kwargs):
        raise AssertionError("disabled provider must not call provider network")

    monkeypatch.setattr(
        wiii_connect_api,
        "list_composio_connected_accounts",
        fail_list_connections,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/connections",
            params={"probe_database": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_disabled"
    assert payload["connection_count"] == 1
    assert payload["connections"][0]["connection_ref"].startswith("wcn_")
    assert payload["connections"][0]["state"] == "connected"
    assert payload["connections"][0]["connection_lifecycle"]["status"] == "connected"
    assert payload["connection_lifecycle"]["status"] == "connected"
    assert payload["connection_lifecycle"]["reason"] == "provider_disabled"
    assert payload["storage"]["reason"] == "ready"
    assert "ca_active" not in serialized
    assert "connection_id" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_connections_api_lists_and_persists_safely(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import WiiiConnectConnectionRecordV1
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioConnectionListResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        upserts = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def get_connection_record(self, **kwargs):
            return None

        def upsert_connection_record(
            self,
            connection,
            *,
            organization_id: str,
            user_id: str,
            provider_kind: str,
        ):
            self.upserts += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_kind == "composio"
            assert connection.connection_id == "ca_active"
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

    async def fake_list_connections(**kwargs):
        assert kwargs["provider_slug"] == "facebook"
        assert kwargs["user_id"].startswith("wiii_")
        return WiiiConnectComposioConnectionListResult(
            ready=True,
            reason="ready",
            connections=(
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_active",
                    provider_slug="facebook",
                    state="connected",
                    reason="provider_connection_list",
                ),
            ),
        )

    monkeypatch.setattr(
        wiii_connect_api,
        "list_composio_connected_accounts",
        fake_list_connections,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/connections",
            params={"probe_database": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "ready"
    assert payload["reason"] == "ready"
    assert payload["connection_count"] == 1
    assert payload["connections"][0]["connection_ref"].startswith("wcn_")
    assert payload["connections"][0]["state"] == "connected"
    assert payload["connections"][0]["connection_lifecycle"]["status"] == "connected"
    assert payload["connection_lifecycle"]["status"] == "connected"
    assert payload["connection_lifecycle"]["connection_present"] is True
    assert fake_storage.upserts == 1
    assert "ca_active" not in serialized
    assert "connection_id" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_fb" not in serialized
    assert "access_token" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_connections_api_does_not_reanimate_user_disconnect(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import WiiiConnectConnectionRecordV1
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioConnectionListResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        upserts = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def get_connection_record(
            self,
            *,
            organization_id: str,
            user_id: str,
            provider_slug: str,
            connection_id: str | None = None,
        ):
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "gmail"
            assert connection_id == "ca_active"
            return WiiiConnectConnectionRecordV1(
                connection_id="ca_active",
                provider_slug="gmail",
                state="disabled",
                reason="user_disconnect_requested",
            )

        def upsert_connection_record(self, *args, **kwargs):
            self.upserts += 1
            raise AssertionError("poll must not re-enable user-disconnected row")

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"gmail": "authcfg_gmail"},
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_list_connections(**kwargs):
        return WiiiConnectComposioConnectionListResult(
            ready=True,
            reason="ready",
            connections=(
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_active",
                    provider_slug="gmail",
                    state="connected",
                    reason="provider_connection_list",
                ),
            ),
        )

    monkeypatch.setattr(
        wiii_connect_api,
        "list_composio_connected_accounts",
        fake_list_connections,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/gmail/connections",
            params={"probe_database": "true"},
        )

    assert response.status_code == 200
    assert fake_storage.upserts == 0


@pytest.mark.asyncio
async def test_wiii_connect_disconnect_api_requires_auth(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            "/wiii-connect/providers/gmail/connections/wcn_public_ref",
        )

    assert response.status_code == 401


def test_wiii_connect_openapi_names_disconnect_path_connection_ref(app):
    schema = app.openapi()
    paths = schema["paths"]

    assert "/wiii-connect/providers/{slug}/connections/{connection_ref}" in paths
    assert "/wiii-connect/providers/{slug}/connections/{connection_id}" not in paths


@pytest.mark.asyncio
async def test_wiii_connect_disconnect_api_disables_local_before_provider_delete(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioDisconnectResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
        fetches = 0
        lists = 0
        upserts = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def get_connection_record(
            self,
            *,
            organization_id: str,
            user_id: str,
            provider_slug: str,
            connection_id: str | None = None,
        ):
            self.fetches += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "gmail"
            assert connection_id == "ca_active"
            return WiiiConnectConnectionRecordV1(
                connection_id="ca_active",
                provider_slug="gmail",
                state="connected",
                scopes=WiiiConnectScopeGrant(read=True),
                reason="provider_connection_list",
            )

        def list_connection_records(
            self,
            *,
            organization_id: str,
            user_id: str,
            provider_slug: str,
        ):
            self.lists += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "gmail"
            return (
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_active",
                    provider_slug="gmail",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True),
                ),
            )

        def upsert_connection_record(
            self,
            connection,
            *,
            organization_id: str,
            user_id: str,
            provider_kind: str,
        ):
            self.upserts += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_kind == "composio"
            assert connection.connection_id == "ca_active"
            assert connection.state == "disabled"
            assert connection.scopes.enabled_scopes() == ()
            assert "disconnected_by_user" in connection.warnings
            return True

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert "secret-api-key" not in serialized
            assert "authcfg_gmail" not in serialized
            assert "access_token" not in serialized
            assert "ca_active" not in serialized
            return True

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"gmail": "authcfg_gmail"},
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_disconnect(**kwargs):
        assert fake_storage.upserts == 1
        assert kwargs["provider_slug"] == "gmail"
        assert kwargs["connected_account_id"] == "ca_active"
        return WiiiConnectComposioDisconnectResult(
            ready=True,
            provider_slug="gmail",
            reason="ready",
            status_code=200,
            connection_ref_present=True,
            provider_success=True,
        )

    monkeypatch.setattr(
        wiii_connect_api,
        "disconnect_composio_connected_account",
        fake_disconnect,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.request(
            "DELETE",
            "/wiii-connect/providers/gmail/connections/"
            f"{public_connection_ref('gmail', 'ca_active')}",
            json={"surface": "desktop"},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_disconnect.v1"
    assert payload["status"] == "succeeded"
    assert payload["reason"] == "ready"
    assert payload["connection_present"] is True
    assert payload["local_disabled"] is True
    assert payload["provider"]["provider_success"] is True
    assert fake_storage.lists == 1
    assert fake_storage.fetches == 1
    assert fake_storage.upserts == 1
    assert fake_storage.audit_appends == 2
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized
    assert "access_token" not in serialized
