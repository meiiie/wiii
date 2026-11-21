from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_actions_api_lists_curated_catalog_without_secrets(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers/gmail/actions")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_action_catalog.v1"
    assert payload["provider_slug"] == "gmail"
    assert payload["action_count"] == 1
    assert payload["enabled_action_count"] == 0
    assert payload["actions"][0]["slug"] == "GMAIL_FETCH_EMAILS"
    assert payload["actions"][0]["enabled"] is False
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_actions_api_hides_backend_owned_argument_keys(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers/facebook/actions")

    assert response.status_code == 200
    payload = response.json()
    by_slug = {action["slug"]: action for action in payload["actions"]}
    post = by_slug["FACEBOOK_CREATE_POST"]
    serialized = json.dumps(post, sort_keys=True)

    assert post["argument_keys"] == ["message", "link"]
    assert post["model_argument_keys"] == ["message", "link"]
    assert post["hidden_argument_count"] == 3
    assert "page_id" not in serialized
    assert "published" not in serialized
    assert "scheduled_publish_time" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_effective_actions_api_requires_selected_connection(
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
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def get_connection_record(self, **kwargs):
            self.fetches += 1
            raise AssertionError("inventory must not select a connection without a ref")

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
        response = await client.get("/wiii-connect/providers/gmail/effective-actions")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_action_inventory.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "connection_selection_required"
    assert payload["selected_connection_required"] is True
    assert payload["runtime_enabled_action_count"] == 1
    assert payload["visible_action_count"] == 0
    assert payload["actions"][0]["slug"] == "GMAIL_FETCH_EMAILS"
    assert payload["actions"][0]["runtime_enabled"] is True
    assert payload["actions"][0]["visible_to_agent"] is False
    assert payload["actions"][0]["gateway"]["reason"] == "connection_selection_required"
    assert fake_storage.fetches == 0
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_effective_actions_api_projects_ready_read_action(
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

    connection_ref = public_connection_ref("gmail", "ca_private")

    class FakeStorage:
        fetches = 0
        lists = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                reason="ready",
            )

        def expire_stale_pending_connections(self, **kwargs):
            return 0

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
            return [
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_private",
                    provider_slug="gmail",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True),
                    vault_ref=WiiiConnectVaultSecretRef(
                        provider_slug="gmail",
                        connection_id="ca_private",
                        vault_key_id="provider-managed://composio/ca_private",
                    ),
                    account_label="private-user@example.test",
                    external_account_ref="acct_private",
                    reason="provider_connection_list",
                ),
            ]

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
            assert connection_id == "ca_private"
            return self.list_connection_records(
                organization_id=organization_id,
                user_id=user_id,
                provider_slug=provider_slug,
            )[0]

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
            "/wiii-connect/providers/gmail/effective-actions",
            params={"connection_ref": connection_ref},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "ready"
    assert payload["reason"] == "ready"
    assert payload["connection_ref_present"] is True
    assert payload["connection_present"] is True
    assert payload["visible_action_count"] == 1
    assert payload["executable_action_count"] == 1
    assert payload["actions"][0]["gateway"]["status"] == "allowed"
    assert payload["actions"][0]["executable_now"] is True
    assert fake_storage.fetches == 1
    assert fake_storage.lists >= 1
    assert "ca_private" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized
    assert "provider-managed://" not in serialized
    assert "private-user@example.test" not in serialized
    assert "acct_private" not in serialized
