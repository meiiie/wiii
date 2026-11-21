from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
)


@pytest.mark.asyncio
async def test_wiii_connect_callback_api_blocks_and_redacts_oauth_values(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "state": "secret-state-value",
                "code": "oauth-code-value",
                "client_secret": "secret-value",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_callback.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_disabled"
    assert payload["vault_ref_issued"] is False
    assert payload["audit_event"]["request"]["state_present"] is True
    assert payload["audit_event"]["request"]["code_present"] is True
    assert "redacted_sensitive_field" in serialized
    assert "secret-state-value" not in serialized
    assert "oauth-code-value" not in serialized
    assert "client_secret" not in serialized
    assert "secret-value" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_callback_api_validates_state_before_provider_error(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
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

        def append_audit_record(self, *args, **kwargs):
            self.audit_appends += 1
            raise AssertionError("invalid state must not append tenant audit")

        def upsert_connection_record(self, *args, **kwargs):
            self.connection_upserts += 1
            raise AssertionError("invalid state must not upsert connection")

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

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing_state = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "error": "access_denied",
                "connected_account_id": "ca_secret",
            },
        )
        invalid_state = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "wiii_state": "tampered-state",
                "error": "access_denied",
                "connected_account_id": "ca_secret",
            },
        )

    missing_payload = missing_state.json()
    invalid_payload = invalid_state.json()
    serialized = json.dumps(
        {
            "missing": missing_payload,
            "invalid": invalid_payload,
        },
        sort_keys=True,
    )

    assert missing_state.status_code == 200
    assert invalid_state.status_code == 200
    assert missing_payload["status"] == "blocked"
    assert missing_payload["reason"] == "missing_state"
    assert invalid_payload["status"] == "blocked"
    assert invalid_payload["reason"] == "invalid_state"
    assert fake_storage.audit_appends == 0
    assert fake_storage.connection_upserts == 0
    assert "access_denied" not in serialized
    assert "tampered-state" not in serialized
    assert "ca_secret" not in serialized
    assert "secret-api-key" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_callback_api_blocks_valid_state_provider_error(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.core.config import settings
    from app.engine.wiii_connect.callback_state import (
        build_wiii_connect_callback_state,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
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
            assert metadata["state"]["valid"] is True
            assert "access_denied" not in serialized
            assert "secret-state-value" not in serialized
            return True

        def upsert_connection_record(self, *args, **kwargs):
            self.connection_upserts += 1
            raise AssertionError("provider error must not upsert connection")

    state = build_wiii_connect_callback_state(
        provider_slug="facebook",
        organization_id="org_1",
        user_id="user_1",
        secret_key=settings.session_secret_key,
    )
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

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "wiii_state": state,
                "error": "access_denied",
                "connected_account_id": "ca_secret",
            },
        )

    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_error"
    assert payload["vault_ref_issued"] is False
    assert fake_storage.audit_appends == 1
    assert fake_storage.connection_upserts == 0
    assert "access_denied" not in serialized
    assert "ca_secret" not in serialized
    assert state not in serialized
    assert "secret-api-key" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_callback_api_reconciles_signed_composio_connection(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.core.config import settings
    from app.engine.wiii_connect.callback_state import (
        build_wiii_connect_callback_state,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
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
            assert metadata["state"]["valid"] is True
            assert "secret-state-value" not in serialized
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
            assert connection.state == "connected"
            return True

    state = build_wiii_connect_callback_state(
        provider_slug="facebook",
        organization_id="org_1",
        user_id="user_1",
        secret_key=settings.session_secret_key,
    )
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

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "wiii_state": state,
                "connected_account_id": "ca_123",
                "status": "ACTIVE",
                "client_secret": "secret-value",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "accepted"
    assert payload["reason"] == "accepted"
    assert payload["vault_ref_issued"] is True
    assert fake_storage.audit_appends == 1
    assert fake_storage.connection_upserts == 1
    assert payload["connection_ref"] == "pending_connection_ref"
    assert "connection_id" not in serialized
    assert "ca_123" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_fb" not in serialized
    assert "secret-value" not in serialized
    assert state not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_callback_browser_accept_returns_handoff_html(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.core.config import settings
    from app.engine.wiii_connect.callback_state import (
        build_wiii_connect_callback_state,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
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
            assert organization_id == "org_1"
            assert user_id == "user_1"
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
            assert connection.state == "connected"
            return True

    state = build_wiii_connect_callback_state(
        provider_slug="facebook",
        organization_id="org_1",
        user_id="user_1",
        secret_key=settings.session_secret_key,
    )
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

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/callback",
            params={
                "wiii_state": state,
                "connected_account_id": "ca_123",
                "status": "ACTIVE",
                "client_secret": "secret-value",
            },
            headers={"accept": "text/html,application/xhtml+xml"},
        )

    body = response.text
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Wiii Connect" in body
    assert "Facebook" in body
    assert "Kết nối Facebook đã được ghi nhận" in body
    assert "wiii-connect:callback" in body
    assert fake_storage.audit_appends == 1
    assert fake_storage.connection_upserts == 1
    assert "ca_123" not in body
    assert "connection_id" not in body
    assert "secret-api-key" not in body
    assert "authcfg_fb" not in body
    assert "secret-value" not in body
    assert state not in body


@pytest.mark.asyncio
async def test_wiii_connect_callback_api_404_for_unknown_provider(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers/not-real/callback")

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown_wiii_connect_provider"
