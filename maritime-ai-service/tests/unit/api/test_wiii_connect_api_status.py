from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
    authenticated_app as authenticated_app,
    optionally_authenticated_app as optionally_authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_provider_registry_api_is_privacy_safe(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers")

    assert response.status_code == 200
    payload = response.json()
    providers = payload["providers"]
    by_slug = {provider["slug"]: provider for provider in providers}

    assert payload["version"] == "wiii_connect_provider_registry.v1"
    assert payload["adapter_version"] == "wiii_connect_adapter.v1"
    assert by_slug["facebook"]["provider_kind"] == "composio"
    assert isinstance(by_slug["facebook"]["enabled"], bool)
    assert isinstance(by_slug["facebook"]["agent_ready"], bool)
    assert by_slug["facebook"]["action_count"] >= 0
    assert isinstance(by_slug["facebook"]["requirements"], list)

    serialized = json.dumps(payload, sort_keys=True)
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "api_key" not in serialized
    assert "approval-secret" not in serialized
    assert "vault://" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_snapshot_api_returns_runtime_contract_without_secrets(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/snapshot",
            params={"query": "đăng facebook", "surface": "desktop"},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    by_slug = {connection["slug"]: connection for connection in payload["connections"]}
    by_path = {item["path"]: item for item in payload["path_capabilities"]}

    assert payload["version"] == "wiii_connect_snapshot.v0"
    assert payload["surface"] == "desktop"
    assert by_slug["server"]["status"] == "connected"
    assert by_slug["facebook"]["provider_kind"] == "composio"
    assert by_path["external_app_action"]["delegation_policy"] == (
        "delegate_to_integrations_agent"
    )
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "api_key" not in serialized
    assert "approval-secret" not in serialized
    assert "đăng facebook" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_doctor_api_returns_readiness_summary_without_secrets(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/wiii-connect/doctor",
            params={"query": "post private secret text", "surface": "desktop"},
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    by_path = {item["path"]: item for item in payload["path_diagnostics"]}
    by_provider = {
        item["provider_slug"]: item for item in payload["provider_diagnostics"]
    }

    assert payload["version"] == "wiii_connect_doctor.v0"
    assert payload["surface"] == "desktop"
    assert payload["summary"]["total_paths"] >= 1
    assert by_path["casual_chat"]["status"] == "ready"
    assert by_path["external_app_action"]["reason"] == (
        "no_agent_ready_external_provider"
    )
    assert by_provider["facebook"]["status"] == "blocked"
    assert by_provider["facebook"]["reason"] == "connection_storage_unavailable"
    assert by_provider["facebook"]["required_next"] == [
        "configure_wiii_connect_storage"
    ]
    assert "post private secret text" not in serialized
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "api_key" not in serialized
    assert "approval-secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_snapshot_rejects_invalid_optional_api_key(app):
    from unittest.mock import MagicMock, patch

    mock_settings = MagicMock()
    mock_settings.api_key = "valid-api-key"
    mock_settings.lms_service_token = None
    mock_settings.environment = "production"
    mock_settings.enable_auth_audit = False

    with patch("app.core.security.settings", mock_settings):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/wiii-connect/snapshot",
                headers={"X-API-Key": "wrong-api-key"},
            )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_wiii_connect_snapshot_and_doctor_use_optional_auth_scope(
    optionally_authenticated_app,
    monkeypatch,
):
    from dataclasses import replace

    from app.engine.wiii_connect import snapshot as snapshot_module
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
    )

    def enable_provider(entry, config):
        return replace(
            entry,
            enabled=True,
            agent_ready=True,
            action_allowlist=("FACEBOOK_CREATE_PAGE_POST",),
            default_scopes=WiiiConnectScopeGrant(read=True, preview=True, apply=True),
            requirements=(),
            connect_requirements=(),
            agent_ready_requirements=(),
            warnings=(),
        )

    class FakeStorage:
        def list_connection_records(self, **kwargs):
            assert kwargs["organization_id"] == "org_1"
            assert kwargs["user_id"] == "user_1"
            if kwargs["provider_slug"] != "facebook":
                return ()
            return (
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_private_active",
                    provider_slug="facebook",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True, preview=True, apply=True),
                    account_label="Private Facebook Page",
                    external_account_ref="external-private-ref",
                    reason="provider_connection_list",
                ),
            )

    monkeypatch.setattr(
        snapshot_module,
        "build_composio_execution_enabled_entry",
        enable_provider,
    )
    monkeypatch.setattr(
        snapshot_module,
        "storage_status_metadata",
        lambda: {
            "persistent": True,
            "connection_table_ready": True,
            "audit_ledger_ready": True,
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "get_wiii_connect_persistent_storage",
        lambda: FakeStorage(),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=optionally_authenticated_app),
        base_url="http://test",
    ) as client:
        snapshot_response = await client.get(
            "/wiii-connect/snapshot",
            params={"query": "dang facebook private text", "surface": "desktop"},
        )
        doctor_response = await client.get(
            "/wiii-connect/doctor",
            params={"query": "dang facebook private text", "surface": "desktop"},
        )

    assert snapshot_response.status_code == 200
    assert doctor_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    doctor_payload = doctor_response.json()
    serialized = json.dumps(
        {"snapshot": snapshot_payload, "doctor": doctor_payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    facebook = {
        connection["slug"]: connection
        for connection in snapshot_payload["connections"]
    }["facebook"]
    by_path = {item["path"]: item for item in doctor_payload["path_diagnostics"]}
    by_provider = {
        item["provider_slug"]: item for item in doctor_payload["provider_diagnostics"]
    }

    assert facebook["status"] == "connected"
    assert facebook["agent_ready"] is True
    assert facebook["connection_ref_present"] is True
    assert doctor_payload["summary"]["external_agent_ready_connections"] == 1
    assert by_path["external_app_action"]["status"] == "guarded"
    assert by_path["external_app_action"]["reason"] == (
        "provider_worker_gateway_required"
    )
    assert by_provider["facebook"]["status"] == "guarded"
    assert by_provider["facebook"]["reason"] == "agent_ready_gateway_required"
    assert by_provider["facebook"]["connection_status"] == "connected"
    assert by_provider["facebook"]["required_next"] == [
        "select_action_and_evaluate_gateway"
    ]
    assert "ca_private_active" not in serialized
    assert "Private Facebook Page" not in serialized
    assert "external-private-ref" not in serialized
    assert "dang facebook private text" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_vault_and_audit_status_apis_are_privacy_safe(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        vault_response = await client.get("/wiii-connect/vault/status")
        audit_response = await client.get("/wiii-connect/audit-ledger/status")

    assert vault_response.status_code == 200
    assert audit_response.status_code == 200
    vault_payload = vault_response.json()
    audit_payload = audit_response.json()
    serialized = json.dumps(
        {"vault": vault_payload, "audit": audit_payload},
        sort_keys=True,
    )

    assert vault_payload["version"] == "wiii_connect_vault.v1"
    assert vault_payload["enabled"] is False
    assert vault_payload["can_store_external_secret"] is False
    assert audit_payload["version"] == "wiii_connect_audit_ledger.v1"
    assert audit_payload["enabled"] is True
    assert audit_payload["persistent"] is False
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_storage_status_api_does_not_probe_by_default(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api

    def _raise_if_called():
        raise AssertionError("storage probe should be opt-in")

    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        _raise_if_called,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/storage/status")
        audit_response = await client.get("/wiii-connect/audit-ledger/status")

    assert response.status_code == 200
    assert audit_response.status_code == 200
    payload = response.json()
    audit_payload = audit_response.json()

    assert payload["version"] == "wiii_connect_persistent_storage.v1"
    assert payload["persistent"] is False
    assert payload["reason"] == "database_probe_not_requested"
    assert audit_payload["persistent"] is False
    assert audit_payload["storage"]["reason"] == "database_probe_not_requested"


@pytest.mark.asyncio
async def test_wiii_connect_storage_probe_is_explicit_and_privacy_safe(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        calls = 0
        audit_appends = 0

        def status(self, *, probe_database: bool = True):
            self.calls += 1
            assert probe_database is True
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

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        storage_response = await client.get(
            "/wiii-connect/storage/status",
            params={"probe_database": "true"},
        )
        audit_response = await client.get(
            "/wiii-connect/audit-ledger/status",
            params={"probe_database": "true"},
        )
        authorization_response = await client.post(
            "/wiii-connect/providers/facebook/authorization-url",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
                "state_present": True,
                "probe_database": True,
            },
        )

    assert storage_response.status_code == 200
    assert audit_response.status_code == 200
    assert authorization_response.status_code == 200
    assert fake_storage.calls == 3
    assert fake_storage.audit_appends == 1

    storage_payload = storage_response.json()
    audit_payload = audit_response.json()
    authorization_payload = authorization_response.json()
    serialized = json.dumps(
        {
            "storage": storage_payload,
            "audit": audit_payload,
            "authorization": authorization_payload,
        },
        sort_keys=True,
    )

    assert storage_payload["persistent"] is True
    assert storage_payload["reason"] == "ready"
    assert audit_payload["persistent"] is True
    assert audit_payload["storage"]["audit_ledger_ready"] is True
    assert authorization_payload["reason"] == "provider_disabled"
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_provider_adapter_status_api_is_fail_closed(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/provider-adapters/status")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    by_kind = {adapter["provider_kind"]: adapter for adapter in payload["adapters"]}

    assert payload["version"] == "wiii_connect_provider_adapter.v1"
    assert by_kind["composio"]["bound"] is False
    assert by_kind["composio"]["configured"] is False
    assert by_kind["composio"]["authorization_ready"] is False
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_provider_status_api_is_fail_closed(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/wiii-connect/providers/facebook/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "wiii_connect_session.v1"
    assert payload["provider_slug"] == "facebook"
    assert payload["can_start_authorization"] is False
    assert payload["reason"] == "provider_disabled"
    assert "provider_managed_vault_ref" in payload["missing_requirements"]
    assert "execution_gateway" not in payload["missing_requirements"]


@pytest.mark.asyncio
async def test_wiii_connect_session_status_uses_runtime_composio_config(
    app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
    )

    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            apply_execute_enabled=True,
            apply_action_allowlist_by_provider={
                "facebook": ("FACEBOOK_CREATE_POST",),
            },
        ),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        status_response = await client.get("/wiii-connect/providers/facebook/status")
        session_response = await client.post(
            "/wiii-connect/providers/facebook/sessions",
            json={
                "surface": "desktop",
                "redirect_uri": "https://wiii.example.test/callback",
            },
        )

    assert status_response.status_code == 200
    assert session_response.status_code == 200
    status_payload = status_response.json()
    session_payload = session_response.json()
    serialized = json.dumps(
        {"status": status_payload, "session": session_payload},
        sort_keys=True,
    )

    assert status_payload["enabled"] is True
    assert status_payload["agent_ready"] is True
    assert status_payload["reason"] == "provider_adapter_not_bound"
    assert status_payload["missing_requirements"] == []
    assert session_payload["status"] == "blocked"
    assert session_payload["reason"] == "provider_adapter_not_bound"
    assert "secret-api-key" not in serialized
