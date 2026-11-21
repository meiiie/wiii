from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    app as app,
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_execution_decision_api_requires_auth(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/execution-decision",
            json={"action_slug": "FACEBOOK_GET_PAGE"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wiii_connect_execution_decision_api_audits_fail_closed(
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
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
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
            assert provider_slug == "facebook"
            return [
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_active",
                    provider_slug="facebook",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True, write=True),
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
            assert provider_slug == "facebook"
            assert connection_id == "ca_active"
            return WiiiConnectConnectionRecordV1(
                connection_id="ca_active",
                provider_slug="facebook",
                state="connected",
                scopes=WiiiConnectScopeGrant(read=True, write=True),
                reason="provider_connection_list",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["request"]["action_slug"] == "FACEBOOK_GET_PAGE"
            assert metadata["request"]["request_id"] == "req-wiii-connect-api-1"
            assert metadata["connection_found"] is True
            assert "approval_token" not in serialized
            assert "secret-value" not in serialized
            assert "access_token" not in serialized
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

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/execution-decision",
            headers={"X-Request-ID": "req-wiii-connect-api-1"},
            json={
                "surface": "desktop",
                "connection_ref": public_connection_ref("facebook", "ca_active"),
                "action_slug": "FACEBOOK_GET_PAGE",
                "path": "external_app_action",
                "mutation": "read",
                "argument_keys": ["page_id", "access_token"],
                "approval_token": "secret-value",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "wiii_connect_execution_gateway.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "provider_not_agent_ready"
    assert payload["connection_present"] is True
    assert payload["adapter"]["can_execute_actions"] is False
    assert fake_storage.lists == 1
    assert fake_storage.fetches == 1
    assert fake_storage.audit_appends == 1
    assert "secret-api-key" not in serialized
    assert "authcfg_fb" not in serialized
    assert "secret-value" not in serialized
    assert "access_token" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_execution_decision_requires_selected_connection(
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
        audit_appends = 0
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

        def get_connection_record(self, **kwargs):
            self.fetches += 1
            raise AssertionError(
                "execution preflight must not select latest connection",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["connection_id_present"] is False
            assert metadata["connection_found"] is False
            assert metadata["request"]["action_slug"] == "GMAIL_FETCH_EMAILS"
            assert "secret-api-key" not in serialized
            assert "access_token" not in serialized
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
        response = await client.post(
            "/wiii-connect/providers/gmail/execution-decision",
            json={
                "surface": "desktop",
                "connection_id": "ca_active",
                "action_slug": "GMAIL_FETCH_EMAILS",
                "path": "external_app_action",
                "mutation": "read",
                "argument_keys": ["query", "access_token"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "connection_selection_required"
    assert payload["connection_present"] is False
    assert "select_provider_connection" in payload["required_next"]
    assert fake_storage.fetches == 0
    assert fake_storage.audit_appends == 1
    assert "ca_active" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized
    assert "access_token" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_execute_api_runs_readonly_composio_action_safely(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect import backend_action_executor as executor_module
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioExecuteResult,
        WiiiConnectComposioToolSchemaResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
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
                    connection_id="ca_active",
                    provider_slug="gmail",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True),
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
            assert connection_id == "ca_active"
            return WiiiConnectConnectionRecordV1(
                connection_id="ca_active",
                provider_slug="gmail",
                state="connected",
                scopes=WiiiConnectScopeGrant(read=True),
                reason="provider_connection_list",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["request"]["action_slug"] == "GMAIL_FETCH_EMAILS"
            assert metadata["request"]["request_id"] == "req-wiii-connect-execute-1"
            assert "access_token" not in serialized
            assert "client-secret" not in serialized
            assert "private subject" not in serialized
            assert "secret-api-key" not in serialized
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
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "gmail": ("GMAIL_FETCH_EMAILS",),
            },
        ),
    )
    monkeypatch.setattr(
        executor_module,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_schema(**kwargs):
        assert kwargs["provider_slug"] == "gmail"
        assert kwargs["action_slug"] == "GMAIL_FETCH_EMAILS"
        assert kwargs["request_id"] == "req-wiii-connect-execute-1"
        return WiiiConnectComposioToolSchemaResult(
            ready=True,
            provider_slug="gmail",
            action_slug="GMAIL_FETCH_EMAILS",
            reason="ready",
            request_id=kwargs["request_id"],
            schema_present=True,
            argument_keys=("query",),
        )

    async def fake_execute(**kwargs):
        assert kwargs["provider_slug"] == "gmail"
        assert kwargs["action_slug"] == "GMAIL_FETCH_EMAILS"
        assert kwargs["connected_account_id"] == "ca_active"
        assert kwargs["request_id"] == "req-wiii-connect-execute-1"
        assert kwargs["arguments"] == {"query": "from:me"}
        return WiiiConnectComposioExecuteResult(
            ready=True,
            provider_slug="gmail",
            action_slug="GMAIL_FETCH_EMAILS",
            reason="ready",
            request_id=kwargs["request_id"],
            successful=True,
            status_code=200,
            data_keys=("messages",),
            log_id_present=True,
        )

    monkeypatch.setattr(executor_module, "verify_composio_tool_schema", fake_schema)
    monkeypatch.setattr(executor_module, "execute_composio_tool", fake_execute)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/gmail/execute",
            headers={"X-Request-ID": "req-wiii-connect-execute-1"},
            json={
                "surface": "desktop",
                "connection_ref": public_connection_ref("gmail", "ca_active"),
                "action_slug": "GMAIL_FETCH_EMAILS",
                "path": "external_app_action",
                "mutation": "read",
                "arguments": {
                    "query": "from:me",
                    "access_token": "client-secret",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "succeeded"
    assert payload["reason"] == "ready"
    assert payload["decision"]["outcome"] == "allowed"
    assert payload["schema"]["status"] == "ready"
    assert payload["execution"]["status"] == "succeeded"
    assert payload["execution"]["log_id_present"] is True
    assert payload["argument_policy"]["accepted_argument_keys"] == ["query"]
    assert payload["argument_policy"]["hidden_argument_count"] == 1
    assert payload["operation_policy"]["status"] == "not_required"
    assert fake_storage.lists == 1
    assert fake_storage.fetches == 0
    assert fake_storage.audit_appends == 2
    assert "client-secret" not in serialized
    assert "access_token" not in serialized
    assert "private subject" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_execute_api_ignores_unverified_mutation_authorization(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect import backend_action_executor as executor_module
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
        lists = 0

        def status(self, *, probe_database: bool = True):
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
            self.lists += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert provider_slug == "facebook"
            return [
                WiiiConnectConnectionRecordV1(
                    connection_id="ca_facebook",
                    provider_slug="facebook",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(
                        read=True,
                        preview=True,
                        apply=True,
                    ),
                    reason="provider_connection_list",
                ),
            ]

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["operation_policy"]["status"] == "required"
            assert metadata["operation_policy"]["caller_claim_ignored"] is True
            assert "approval-token" not in serialized
            assert "page_private" not in serialized
            assert "secret-api-key" not in serialized
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
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "facebook": ("FACEBOOK_LIST_MANAGED_PAGES",),
            },
            apply_execute_enabled=True,
            apply_action_allowlist_by_provider={
                "facebook": ("FACEBOOK_CREATE_POST",),
            },
        ),
    )
    monkeypatch.setattr(
        executor_module,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_schema(**kwargs):
        raise AssertionError("schema probe must not run without verified authorization")

    async def fake_execute(**kwargs):
        raise AssertionError("provider execution must not run without verified authorization")

    monkeypatch.setattr(executor_module, "verify_composio_tool_schema", fake_schema)
    monkeypatch.setattr(executor_module, "execute_composio_tool", fake_execute)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/execute",
            json={
                "surface": "desktop",
                "connection_ref": public_connection_ref("facebook", "ca_facebook"),
                "action_slug": "FACEBOOK_CREATE_POST",
                "path": "external_app_action",
                "mutation": "apply",
                "preview_evidence_required": True,
                "preview_evidence_id": "preview_injected",
                "approval_token_present": True,
                "arguments": {
                    "page_id": "page_private",
                    "message": "safe public copy",
                    "published": True,
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "missing_preview_evidence"
    assert payload["operation_policy"]["status"] == "required"
    assert payload["operation_policy"]["caller_claim_ignored"] is True
    assert payload["argument_policy"]["accepted_argument_keys"] == ["message"]
    assert payload["argument_policy"]["hidden_argument_count"] == 2
    assert payload["schema"] is None
    assert payload["execution"] is None
    assert fake_storage.lists == 1
    assert fake_storage.audit_appends == 1
    assert "preview_injected" not in serialized
    assert "approval-token" not in serialized
    assert "page_private" not in serialized
    assert "secret-api-key" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_execute_blocks_missing_required_schema_arguments(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect import backend_action_executor as executor_module
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioToolSchemaResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
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
                    connection_id="ca_active",
                    provider_slug="gmail",
                    state="connected",
                    scopes=WiiiConnectScopeGrant(read=True),
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
            assert connection_id == "ca_active"
            return WiiiConnectConnectionRecordV1(
                connection_id="ca_active",
                provider_slug="gmail",
                state="connected",
                scopes=WiiiConnectScopeGrant(read=True),
                reason="provider_connection_list",
            )

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["stage"] == "argument_validation"
            assert metadata["missing_argument_keys"] == [
                "query",
                "redacted_sensitive_field",
            ]
            assert metadata["request"]["action_slug"] == "GMAIL_FETCH_EMAILS"
            assert "client-secret" not in serialized
            assert "private subject" not in serialized
            assert "access_token" not in serialized
            assert "api_key" not in serialized
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
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "gmail": ("GMAIL_FETCH_EMAILS",),
            },
        ),
    )
    monkeypatch.setattr(
        executor_module,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_schema(**kwargs):
        assert kwargs["provider_slug"] == "gmail"
        assert kwargs["action_slug"] == "GMAIL_FETCH_EMAILS"
        return WiiiConnectComposioToolSchemaResult(
            ready=True,
            provider_slug="gmail",
            action_slug="GMAIL_FETCH_EMAILS",
            reason="ready",
            schema_present=True,
            argument_keys=("query",),
            required_argument_keys=("query", "access_token"),
        )

    async def fake_execute(**kwargs):
        raise AssertionError(
            "provider execution must not run with missing required arguments",
        )

    monkeypatch.setattr(executor_module, "verify_composio_tool_schema", fake_schema)
    monkeypatch.setattr(executor_module, "execute_composio_tool", fake_execute)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/gmail/execute",
            json={
                "surface": "desktop",
                "connection_ref": public_connection_ref("gmail", "ca_active"),
                "action_slug": "GMAIL_FETCH_EMAILS",
                "path": "external_app_action",
                "mutation": "read",
                "arguments": {
                    "api_key": "client-secret",
                    "subject": "private subject",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "missing_required_arguments"
    assert payload["decision"]["outcome"] == "allowed"
    assert payload["schema"]["status"] == "ready"
    assert payload["execution"] is None
    assert payload["missing_argument_keys"] == ["query", "redacted_sensitive_field"]
    assert fake_storage.lists == 1
    assert fake_storage.fetches == 0
    assert fake_storage.audit_appends == 1
    assert "client-secret" not in serialized
    assert "private subject" not in serialized
    assert "access_token" not in serialized
    assert "api_key" not in serialized
    assert "secret-api-key" not in serialized
    assert "authcfg_gmail" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_execute_requires_selected_connection_before_provider_call(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect import backend_action_executor as executor_module
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )

    class FakeStorage:
        audit_appends = 0
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
            raise AssertionError("execute must not select latest connection")

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            metadata = record.to_public_metadata()["metadata"]
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert metadata["stage"] == "api_execute"
            assert metadata["connection_ref_present"] is False
            assert metadata["connection_found"] is False
            assert metadata["request"]["action_slug"] == "GMAIL_FETCH_EMAILS"
            assert "client-secret" not in serialized
            assert "access_token" not in serialized
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
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "gmail": ("GMAIL_FETCH_EMAILS",),
            },
        ),
    )
    monkeypatch.setattr(
        executor_module,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_schema(**kwargs):
        raise AssertionError("schema probe must not run without selected connection")

    async def fake_execute(**kwargs):
        raise AssertionError(
            "provider execution must not run without selected connection",
        )

    monkeypatch.setattr(executor_module, "verify_composio_tool_schema", fake_schema)
    monkeypatch.setattr(executor_module, "execute_composio_tool", fake_execute)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/gmail/execute",
            json={
                "surface": "desktop",
                "connection_id": "ca_active",
                "action_slug": "GMAIL_FETCH_EMAILS",
                "path": "external_app_action",
                "mutation": "read",
                "arguments": {
                    "query": "from:me",
                    "access_token": "client-secret",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "connection_selection_required"
    assert payload["connection_present"] is False
    assert payload["schema"] is None
    assert payload["execution"] is None
    assert "select_provider_connection" in payload["required_next"]
    assert fake_storage.fetches == 0
    assert fake_storage.audit_appends == 1
    assert "ca_active" not in serialized
    assert "client-secret" not in serialized
    assert "access_token" not in serialized
    assert "secret-api-key" not in serialized
