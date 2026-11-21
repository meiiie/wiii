from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_activation_readiness_api_fails_closed_without_config(
    authenticated_app,
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/gmail/activation-readiness",
            params={"probe_database": "false"},
        )

    assert response.status_code == 200
    payload = response.json()
    gates = {gate["key"]: gate for gate in payload["gates"]}
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["version"] == "wiii_connect_activation_readiness.v1"
    assert payload["status"] == "blocked"
    assert payload["provider_slug"] == "gmail"
    assert payload["ready_to_connect"] is False
    assert payload["ready_to_execute_readonly"] is False
    assert gates["provider_registered"]["ready"] is True
    assert gates["provider_adapter"]["ready"] is False
    assert gates["persistent_storage"]["ready"] is False
    assert gates["curated_readonly_action"]["ready"] is False
    assert gates["local_connection"]["reason"] == "connection_missing"
    assert payload["connection"]["present"] is False
    assert payload["connection_lifecycle"]["version"] == (
        "wiii_connect_connection_lifecycle.v1"
    )
    assert payload["connection_lifecycle"]["status"] == "disconnected"
    assert payload["connection_lifecycle"]["connection_present"] is False
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "api_key" not in serialized
    assert "approval_token" not in serialized
    assert "authcfg" not in serialized
    assert "vault://" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_activation_readiness_default_action_is_provider_scoped(
    authenticated_app,
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/facebook/activation-readiness",
            params={"probe_database": "false"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_slug"] == "facebook"
    assert payload["action"]["provider_slug"] == "facebook"
    assert payload["action"]["slug"] == "FACEBOOK_LIST_MANAGED_PAGES"


@pytest.mark.asyncio
async def test_wiii_connect_activation_readiness_api_reports_ready_without_leaks(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        WiiiConnectVaultSecretRef,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        fetches = 0
        expires = 0
        lists = 0

        def status(self, *, probe_database: bool = True):
            assert probe_database is True
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def expire_stale_pending_connections(
            self,
            *,
            organization_id: str,
            user_id: str,
            provider_slug: str,
            ttl_seconds: int,
        ):
            self.expires += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "gmail"
            assert ttl_seconds >= 60
            return 1

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
                vault_ref=WiiiConnectVaultSecretRef(
                    provider_slug="gmail",
                    connection_id="ca_active",
                    vault_key_id="provider-managed://composio/ca_active",
                    secret_version="provider_managed",
                ),
                account_label="private-user@example.test",
                external_account_ref="acct_private",
                reason="provider_connection_list",
            )

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"gmail": "authcfg_gmail"},
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "gmail": ("GMAIL_FETCH_EMAILS",),
            },
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/gmail/activation-readiness",
            params={
                "action_slug": "GMAIL_FETCH_EMAILS",
                "connection_ref": public_connection_ref("gmail", "ca_active"),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    gates = {gate["key"]: gate for gate in payload["gates"]}
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "ready"
    assert payload["provider_slug"] == "gmail"
    assert payload["ready_to_connect"] is True
    assert payload["ready_to_execute_readonly"] is True
    assert payload["action"]["slug"] == "GMAIL_FETCH_EMAILS"
    assert payload["action"]["runtime_enabled"] is True
    assert payload["connection"]["present"] is True
    assert payload["connection"]["active"] is True
    assert payload["connection"]["vault_ref_present"] is True
    assert payload["connection_lifecycle"]["status"] == "connected"
    assert payload["connection_lifecycle"]["active"] is True
    assert payload["connection_lifecycle"]["ready_to_execute_action"] is True
    assert payload["execution_gateway"]["status"] == "allowed"
    assert gates["provider_adapter"]["ready"] is True
    assert gates["vault"]["ready"] is True
    assert gates["persistent_storage"]["ready"] is True
    assert gates["audit_ledger"]["ready"] is True
    assert gates["curated_readonly_action"]["ready"] is True
    assert gates["execution_gateway"]["ready"] is True
    assert fake_storage.lists == 1
    assert fake_storage.fetches == 1
    assert fake_storage.expires == 1
    assert "ca_active" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized
    assert "provider-managed://" not in serialized
    assert "private-user@example.test" not in serialized
    assert "acct_private" not in serialized
    assert "access_token" not in serialized
    assert "api_key" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_activation_readiness_requires_selected_connection(
    authenticated_app,
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
        fetches = 0

        def status(self, *, probe_database: bool = True):
            assert probe_database is True
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def get_connection_record(self, **kwargs):
            self.fetches += 1
            raise AssertionError("readiness must not select latest connection")

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"gmail": "authcfg_gmail"},
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "gmail": ("GMAIL_FETCH_EMAILS",),
            },
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/providers/gmail/activation-readiness",
            params={"action_slug": "GMAIL_FETCH_EMAILS"},
        )

    assert response.status_code == 200
    payload = response.json()
    gates = {gate["key"]: gate for gate in payload["gates"]}
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "blocked"
    assert payload["ready_to_connect"] is True
    assert payload["ready_to_execute_readonly"] is False
    assert payload["connection"]["present"] is False
    assert payload["connection_lifecycle"]["status"] == "disconnected"
    assert payload["connection_lifecycle"]["ready_to_connect"] is True
    assert "complete_provider_oauth" in payload["connection_lifecycle"]["required_next"]
    assert payload["execution_gateway"]["reason"] == "connection_selection_required"
    assert (
        "select_provider_connection" in payload["execution_gateway"]["required_next"]
    )
    assert gates["local_connection"]["reason"] == "connection_missing"
    assert gates["execution_gateway"]["reason"] == "connection_selection_required"
    assert fake_storage.fetches == 0
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized
